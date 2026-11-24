"""Chronological site planning with SciPy/HiGHS (optional dependency).

All intervals are equal length. This is perfect-foresight planning, not
real-time control or a reliability certificate.
"""
from __future__ import annotations
import hashlib
import json
import math
from copy import deepcopy
from . import __version__

MAX_INTERVALS = 35_040
EPS = 1e-7

def _number(value, name, minimum=0, maximum=1e8):
    if type(value) not in (int,float) or not math.isfinite(value) or not minimum <= value <= maximum:
        raise ValueError(f"Invalid {name}: expected finite number in [{minimum}, {maximum}]")
    return float(value)

def _series(data, key, n):
    val=data[key]
    if not isinstance(val,list): val=[val]*n
    if len(val)!=n: raise ValueError(f"{key}: expected {n} intervals")
    return [_number(x,key) for x in val]

def _digest(data):
    return hashlib.sha256(json.dumps(data,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()

def _index(x, name, n):
    if type(x) is not int or not 0<=x<=n: raise ValueError(f"Invalid {name}")
    return x

def _build_model(scenario: dict, expansion=None, hard_caps=False, *, causal_state=None, peak_import_cost=0):
    """Build the same sparse physical model for dispatch and capacity planning.

    Expansion resource IDs refer to resources with upper bounds given by their
    rated capacities. The capacity columns are linked across planning scenarios.
    """
    import numpy as np
    from scipy.sparse import coo_matrix
    dt=_number(scenario["interval_hours"],"interval_hours",1/3600,24)
    demand=scenario["baseline_mw"]
    if not isinstance(demand,list) or not 1<=len(demand)<=MAX_INTERVALS: raise ValueError("Invalid baseline_mw horizon")
    n=len(demand)
    if n*dt>8760+EPS: raise ValueError("Horizon exceeds 8760 hours")
    demand=_series(scenario,"baseline_mw",n)
    protected=_series({"protected":scenario.get("protected_load_mw",0)},"protected",n)
    cooling_baseline=[0.0]*n
    normal_cap=_series(scenario,"normal_import_cap_mw",n)
    prices=_series(scenario,"price_eur_mwh",n)
    caps=list(normal_cap)
    # Event windows are half-open, non-overlapping. Notice is advance warning.
    events=[]; event_at=[None]*n
    for item in scenario.get("events",[]):
        start=_index(item["start"],"event start",n)
        end=_index(item["end"],"event end",n)
        if start>=end or any(x is not None for x in event_at[start:end]): raise ValueError("Events must be nonempty and nonoverlapping")
        notice=_number(item["notice_minutes"],"event notice")
        cap=_number(item["cap_mw"],"event cap")
        event={"start":start,"end":end,"notice_minutes":notice,"cap_mw":cap}
        events.append(event)
        for t in range(start,end): event_at[t]=event;caps[t]=min(caps[t],cap)

    bounds=[]; operating=[]; sizing={}; integer=[]
    expansion=expansion or {}
    recovery_columns=[]
    fallback_backlog_columns=[]
    causal_state=causal_state or {}
    eq_r=[];eq_c=[];eq_v=[];eq_b=[]
    ub_r=[];ub_c=[];ub_v=[];ub_b=[]
    def variable(lo,hi,cost=0,binary=False):
        i=len(bounds);bounds.append((lo,hi));operating.append(cost);integer.append(int(binary));return i
    def series(lo,hi,cost=0):
        return [variable(lo,hi[t] if isinstance(hi,list) else hi,cost[t] if isinstance(cost,list) else cost) for t in range(n)]
    def constraint(terms,rhs,equal=False):
        rr,cc,vv,bb=(eq_r,eq_c,eq_v,eq_b) if equal else (ub_r,ub_c,ub_v,ub_b)
        row=len(bb);bb.append(rhs)
        for col,coef in terms:
            if coef:rr.append(row);cc.append(col);vv.append(coef)
    grid=series(0,None,[p*dt for p in prices]); gap=series(0,0 if hard_caps else None)
    balance=[[(grid[t],1)] for t in range(n)]
    for t in range(n):constraint([(grid[t],1),(gap[t],-1)],caps[t])
    peak=None
    if peak_import_cost:
        peak=variable(0,None,peak_import_cost)
        for t in range(n):constraint([(grid[t],1),(peak,-1)],0)
    resources=[]
    ids=set()
    for spec in scenario.get("resources",[]):
        name=spec["id"];kind=spec["kind"]
        if not isinstance(name,str) or not name or name in ids: raise ValueError("Resource IDs must be unique strings")
        ids.add(name)
        if len(ids)>64: raise ValueError("At most 64 resources supported")
        p=_number(spec["power_mw"],name+" power")
        response=_number(spec.get("response_minutes",0),name+" response")
        availability=_series({"availability":spec.get("availability",1)},"availability",n)
        if any(x>1 for x in availability):raise ValueError("Availability must be 0..1")
        ready=[event_at[t] is None or event_at[t]["notice_minutes"]+(t-event_at[t]["start"])*dt*60>=response-EPS for t in range(n)]
        available=[p*availability[t]*(1 if ready[t] else 0) for t in range(n)]
        cost=_number(spec.get("variable_cost_eur_mwh",0),name+" cost")
        option=expansion.get(name)
        discrete=spec.get("discrete",False)
        if type(discrete) is not bool:raise ValueError("discrete must be boolean")
        if discrete and kind not in ("generator","battery"):raise ValueError("discrete supported only for generator and battery")
        if discrete and expansion:raise ValueError("Continuous capacity sizing does not support discrete assets; use design comparison")
        if (not discrete or kind!="generator") and any(k in spec for k in ("minimum_output_mw","minimum_up_hours","minimum_down_hours","initial_on","initial_state_hours","startup_cost_eur","online_cost_eur_per_hour")):
            raise ValueError("Unit commitment fields require a discrete generator")
        power_col=None
        if option is not None:
            power_col=variable(0,p)
            sizing[(name,"power_mw")]=power_col
        if kind=="generator":
            if causal_state:
                # An already running generator can retain its observed output
                # during notification delay; it cannot increase it until ready.
                floor=_number(spec.get("initial_mw",0),name+" initial output",0,p)
                available=[max(available[t],min(floor,p*availability[t])) for t in range(n)]
            # Generation can be scheduled outside events for pre-ramp/recovery.
            gen=series(0,available,cost*dt)
            ramp=_number(spec.get("ramp_mw_per_hour",p/dt),name+" ramp")*dt
            initial=_number(spec.get("initial_mw",0),name+" initial output",0,p)
            for t in range(n):
                prev=[(gen[t-1],-1)] if t else []
                if power_col is not None:
                    ramp_ratio=option["ramp_fraction_per_hour"]*dt
                    constraint([(gen[t],1),(power_col,-availability[t]*int(ready[t]))],0)
                    constraint([(gen[t],1)]+prev+[(power_col,-ramp_ratio)],0)
                    constraint([(gen[t],-1)]+[(i,-v) for i,v in prev]+[(power_col,-ramp_ratio)],0)
                else:
                    constraint([(gen[t],1)]+prev,ramp+(initial if not t else 0))
                    constraint([(gen[t],-1)]+[(i,-v) for i,v in prev],ramp-(initial if not t else 0))
                balance[t].append((gen[t],1))
            if "fuel_budget_mwh" in spec: constraint([(i,dt) for i in gen],_number(spec["fuel_budget_mwh"],name+" fuel budget"))
            trace={"generation_mw":gen}
            if discrete:
                minimum=_number(spec.get("minimum_output_mw",0),name+" minimum output",0,p)
                initial_on=spec.get("initial_on",initial>0)
                if type(initial_on) is not bool or (not initial_on and initial>EPS) or (initial_on and initial<minimum-EPS):
                    raise ValueError("Inconsistent initial generator state")
                up=_number(spec.get("minimum_up_hours",0),name+" minimum up time",0,8760)
                down=_number(spec.get("minimum_down_hours",0),name+" minimum down time",0,8760)
                age=_number(spec.get("initial_state_hours",8760),name+" initial state duration",0,8760)
                startup_cost=_number(spec.get("startup_cost_eur",0),name+" startup cost")
                online_cost=_number(spec.get("online_cost_eur_per_hour",0),name+" online cost")
                # Never schedule an online unit when no capacity is available.
                on=[variable(0,int(available[t]>0 and available[t]>=minimum-EPS),online_cost*dt,True) for t in range(n)]
                start=[variable(0,1,startup_cost,True) for t in range(n)]
                stop=[variable(0,1,0,True) for t in range(n)]
                up_n=math.ceil(up/dt-1e-9);down_n=math.ceil(down/dt-1e-9)
                initial_remaining=math.ceil(max(0,(up if initial_on else down)-age)/dt-1e-9)
                # Cumulative start/stop counts give linear-size dwell constraints.
                starts=series(0,None);stops=series(0,None)
                for t in range(n):
                    constraint([(gen[t],1),(on[t],-available[t])],0)
                    constraint([(gen[t],-1),(on[t],minimum)],0)
                    prev=[(on[t-1],-1)] if t else []
                    constraint([(on[t],1),(start[t],-1),(stop[t],1)]+prev,0 if t else int(initial_on),True)
                    constraint([(start[t],1),(stop[t],1)],1)
                    for cumulative,flow in ((starts,start),(stops,stop)):
                        constraint([(cumulative[t],1),(flow[t],-1)]+([(cumulative[t-1],-1)] if t else []),0,True)
                    if up_n:
                        constraint([(starts[t],1),(on[t],-1)]+([(starts[t-up_n],-1)] if t>=up_n else []),0)
                    if down_n:
                        constraint([(stops[t],1),(on[t],1)]+([(stops[t-down_n],-1)] if t>=down_n else []),1)
                    if t<initial_remaining:constraint([(on[t],1)],int(initial_on),True)
                trace.update(online=on,startup=start,shutdown=stop)
            resources.append((name,kind,trace))
        elif kind=="battery":
            energy=_number(spec["energy_mwh"],name+" energy")
            reserve=_number(spec.get("reserve_mwh",0),name+" reserve",0,energy)
            initial=_number(spec.get("initial_mwh",energy),name+" initial energy",reserve,energy)
            final=_number(spec.get("terminal_mwh",initial),name+" terminal energy",reserve,energy)
            eta_c=_number(spec.get("charge_efficiency",.95),name+" charge efficiency",.01,1)
            eta_d=_number(spec.get("discharge_efficiency",.95),name+" discharge efficiency",.01,1)
            charge_p=_number(spec.get("charge_power_mw",p),name+" charge power")
            charge=series(0,[charge_p*a for a in availability],[EPS*dt]*n)
            discharge=series(0,available,(cost+EPS)*dt)
            energy_col=None
            if option is not None:
                energy_col=variable(0,energy)
                sizing[(name,"energy_mwh")]=energy_col
            soc=[variable(0 if option is not None else reserve,energy) for _ in range(n)]
            for t in range(n):
                terms=[(soc[t],1),(charge[t],-eta_c*dt),(discharge[t],dt/eta_d)]
                if t:terms.append((soc[t-1],-1))
                if option is not None:
                    if not t:terms.append((energy_col,-option["initial_fraction"]))
                    constraint(terms,0,True)
                    constraint([(soc[t],1),(energy_col,-1)],0)
                    constraint([(soc[t],-1),(energy_col,option["reserve_fraction"])],0)
                    ratio=option["charge_power_ratio"]
                    constraint([(charge[t],1),(power_col,-ratio*availability[t])],0)
                    constraint([(discharge[t],1),(power_col,-availability[t]*int(ready[t]))],0)
                    constraint([(charge[t],1/ratio),(discharge[t],1),(power_col,-1)],0)
                else:
                    constraint(terms,0 if t else initial,True)
                    if charge_p and p:constraint([(charge[t],1/charge_p),(discharge[t],1/p)],1)
                balance[t]+=[(charge[t],-1),(discharge[t],1)]
            if option is not None:
                constraint([(soc[-1],-1),(energy_col,option["terminal_fraction"])],0)
            else:constraint([(soc[-1],-1)],-final)
            if name in causal_state.get("recharge_targets",{}):
                target=_number(causal_state["recharge_targets"][name],name+" recharge target",reserve,energy)
                for t in range(n):
                    if event_at[t] is None:
                        deficit=variable(0,target)
                        constraint([(soc[t],-1),(deficit,-1)],-target)
                        recovery_columns.append(deficit)
            trace={"charge_mw":charge,"discharge_mw":discharge,"soc_mwh":soc}
            if discrete:
                mode=[variable(0,1,0,True) for _ in range(n)]
                for t in range(n):
                    constraint([(charge[t],1),(mode[t],-charge_p*availability[t])],0)
                    constraint([(discharge[t],1),(mode[t],available[t])],available[t])
                trace["charging_mode"]=mode
            resources.append((name,kind,trace))
        elif kind=="renewable":
            # Non-dispatchable available generation may be curtailed; no export.
            if response!=0:raise ValueError("Renewable availability is exogenous; response_minutes must be zero")
            gen=series(0,[p*a for a in availability],cost*dt)
            for t in range(n):balance[t].append((gen[t],1))
            resources.append((name,kind,{"generation_mw":gen}))
        elif kind=="thermal_cooling":
            from .thermal import parameters, coefficients
            th=parameters(spec,n)
            decay,gain=coefficients(th["capacitance"],th["conductance"],dt)
            # Input demand already contains the declared baseline cooling power.
            # Replace that contribution with scheduled cooling, not a second load.
            base=th["baseline_cooling_mw"]
            for t in range(n):cooling_baseline[t]+=base[t]
            cooling=[variable(min(base[t],p*availability[t]) if not ready[t] else 0,
                              p*availability[t],cost*dt) for t in range(n)]
            temp=[variable(th["lower"],th["upper"]) for _ in range(n)]
            for t in range(n):
                rhs=(1-decay)*th["ambient_c"][t]+gain*th["heat_gain_mw"][t]
                terms=[(temp[t],1),(cooling[t],gain*th["cop"][t])]
                if t:terms.append((temp[t-1],-decay))
                else:rhs+=decay*th["initial"]
                constraint(terms,rhs,True)
                balance[t].append((cooling[t],-1))
            constraint([(temp[-1],1)],th["terminal"])
            target=causal_state.get("thermal_targets",{}).get(name)
            if target is not None:
                for t in range(n):
                    if event_at[t] is None:
                        deficit=variable(0,None)
                        constraint([(temp[t],th["capacitance"]),(deficit,-1)],target*th["capacitance"])
                        recovery_columns.append(deficit)
            resources.append((name,kind,{"cooling_mw":cooling,"temperature_c":temp}))
        elif kind in ("workload","cooling","flexible_load"):
            # Energy-equivalent shift budget. No lost workloads; deferred energy must
            # be recovered before the specified deadline and within available cap.
            backlog_cap=_number(spec["shift_budget_mwh"],name+" shift budget")
            recover=_number(spec.get("recovery_power_mw",p),name+" recovery power")
            max_delay=_number(spec["max_delay_hours"],name+" delay",dt,8760)
            delay=max(1,math.floor(max_delay/dt+EPS))
            initial_queue=causal_state.get("backlogs",{}).get(name,[])
            initial_backlog=sum(amount for _,amount in initial_queue)
            fallback=causal_state.get("recovery_fallback",False)
            if fallback and n!=1:raise ValueError("Recovery fallback requires one interval")
            shed=series(0,[min(available[t],demand[t]) if event_at[t] and not fallback else 0 for t in range(n)],cost*dt)
            restore=series(0,[recover*availability[t] if event_at[t] is None else 0 for t in range(n)],[EPS*dt]*n)
            backlog=[variable(0,backlog_cap) for _ in range(n)]
            # Cumulative deferrals/recovery make the deadline constraints O(n).
            deferred=[variable(0,None) for _ in range(n)]
            recovered=[variable(0,None) for _ in range(n)]
            for t in range(n):
                terms=[(backlog[t],1),(shed[t],-dt),(restore[t],dt)]
                if t:terms.append((backlog[t-1],-1))
                constraint(terms,0 if t else initial_backlog,True)
                for cumulative,flow in ((deferred,shed),(recovered,restore)):
                    terms=[(cumulative[t],1),(flow[t],-dt)]
                    if t:terms.append((cumulative[t-1],-1))
                    constraint(terms,0,True)
                due=sum(amount for deadline,amount in initial_queue if deadline<=t)
                if not fallback and (t>=delay or due):
                    constraint(([(deferred[t-delay],1)] if t>=delay else [])+[(recovered[t],-1)],-due)
                balance[t]+=[(shed[t],1),(restore[t],-1)]
            if fallback:fallback_backlog_columns.append(backlog[-1])
            else:constraint([(backlog[-1],1)],0,True)
            resources.append((name,kind,{"shift_mw":shed,"recovery_mw":restore,"backlog_mwh":backlog}))
        else:raise ValueError(f"Unsupported resource kind {kind}")
    # No combination may defer more than the underlying total load.
    for t in range(n):
        shed=[(cols["shift_mw"][t],1) for _,_,cols in resources if "shift_mw" in cols]
        shiftable=demand[t]-protected[t]-cooling_baseline[t]
        if shiftable < -EPS:raise ValueError("Protected and baseline cooling loads exceed total demand")
        if shed:constraint(shed,max(0,shiftable))
        constraint(balance[t],demand[t]-cooling_baseline[t],True)
    def matrix(r,c,v,b):return coo_matrix((v,(r,c)),shape=(len(b),len(bounds))).tocsc()
    return {"bounds":bounds,"operating":np.asarray(operating),"A_ub":matrix(ub_r,ub_c,ub_v,ub_b),
            "b_ub":np.asarray(ub_b),"A_eq":matrix(eq_r,eq_c,eq_v,eq_b),"b_eq":np.asarray(eq_b),
            "grid":grid,"gap":gap,"caps":caps,"dt":dt,"n":n,"demand":demand,"prices":prices,
            "events":events,"resources":resources,"sizing":sizing,"integrality":np.asarray(integer),"recovery_columns":recovery_columns,"fallback_backlog_columns":fallback_backlog_columns}

def evaluate(scenario: dict, *, _causal_state=None, _deadline=None, _peak_import_cost=0) -> dict:
    """Minimize import-cap violations, then operating cost at that minimum."""
    import numpy as np
    import scipy
    from time import monotonic
    from scipy.optimize import linprog, milp, Bounds, LinearConstraint, OptimizeResult
    from scipy.sparse import coo_matrix, vstack
    m=_build_model(scenario,causal_state=_causal_state,peak_import_cost=_number(_peak_import_cost,"peak import cost"))
    bounds,operating,grid,gap,caps,dt,n,demand,prices,events,resources=(
        m[k] for k in ("bounds","operating","grid","gap","caps","dt","n","demand","prices","events","resources"))
    extra=[]
    def solve(objective):
        remaining=60 if _deadline is None else min(60,_deadline-monotonic())
        if remaining<=0:
            return OptimizeResult(success=False,status=1,message="Shared solver time budget exhausted")
        A_ub,b_ub=m["A_ub"],m["b_ub"]
        if extra:
            A_ub=vstack([A_ub]+[row for row,_ in extra],format="csc")
            b_ub=np.append(b_ub,[value for _,value in extra])

        if m["integrality"].any():
            lo,hi=zip(*bounds)
            return milp(objective,integrality=m["integrality"],
                        bounds=Bounds(lo,[np.inf if v is None else v for v in hi]),
                        constraints=[LinearConstraint(A_ub,-np.inf,b_ub),LinearConstraint(m["A_eq"],m["b_eq"],m["b_eq"])],
                        options={"time_limit":remaining,"mip_rel_gap":0})
        return linprog(objective,A_ub=A_ub,b_ub=b_ub,A_eq=m["A_eq"],b_eq=m["b_eq"],bounds=bounds,method="highs",options={"time_limit":remaining})
    evidence={"engine_version":__version__,"solver":"scipy.optimize.milp/HiGHS" if m["integrality"].any() else "scipy.optimize.linprog/HiGHS","scipy_version":scipy.__version__,
              "scenario_sha256":_digest(scenario),"evidence_type":"modelled_perfect_foresight" if _causal_state is None else "observed_state_forecast_plan"}
    if _peak_import_cost:evidence["peak_import_cost_eur_mw"]=_peak_import_cost
    def failed(sol):
        return {"status":"solver_failed","solver_status":int(sol.status),"message":sol.message,"evidence":evidence}
    def limit(indices,coefficients,objective):
        sol=solve(objective)
        if not sol.success:return sol
        row=coo_matrix((coefficients,([0]*len(indices),indices)),shape=(1,len(bounds))).tocsc()
        extra.append((row,max(0,float(sol.fun))+EPS))
        return sol
    if _causal_state is not None:
        priority=np.zeros(len(bounds));priority[gap[0]]=1
        first=limit([gap[0]],[1],priority)
        if not first.success:return failed(first)
    priority=np.zeros(len(bounds));priority[gap]=1
    first=limit(gap,[1]*n,priority)
    if not first.success:return failed(first)
    if m["fallback_backlog_columns"]:
        cols=m["fallback_backlog_columns"]
        priority=np.zeros(len(bounds));priority[cols]=1
        recovered=limit(cols,[1]*len(cols),priority)
        if not recovered.success:return failed(recovered)
    if m["recovery_columns"]:
        cols=m["recovery_columns"]
        recovery=np.zeros(len(bounds));recovery[cols]=1
        recovered=limit(cols,[1]*len(cols),recovery)
        if not recovered.success:return failed(recovered)
    second=solve(operating)
    if not second.success:return failed(second)
    x=second.x
    def vals(indices):return [float(max(0,x[i])) for i in indices]
    g=vals(grid)
    commitment_cost=sum(
        sum(x[i] for i in cols.get("startup",[]))*float(sp.get("startup_cost_eur",0))+
        sum(x[i] for i in cols.get("online",[]))*dt*float(sp.get("online_cost_eur_per_hour",0))
        for name,_,cols in resources for sp in scenario.get("resources",[]) if sp["id"]==name)
    violations=[max(0,g[t]-caps[t]) for t in range(n)]
    result={"status":"solved","feasible":max(violations,default=0)<=1e-5,
            "horizon_hours":n*dt,"uncovered_mwh":sum(violations)*dt,"peak_uncovered_mw":max(violations,default=0),
            "event_hours":sum((ev["end"]-ev["start"])*dt for ev in events),
            "grid_energy_cost_eur":sum(g[t]*prices[t]*dt for t in range(n)),
            "commitment_cost_eur":float(commitment_cost),
            "operating_cost_eur":float(commitment_cost + sum(g[t]*prices[t]*dt for t in range(n)) + sum(
                (sum(x[i] for key in ("generation_mw","discharge_mw","shift_mw","cooling_mw") for i in cols.get(key,[]))
                 *dt*next(float(sp.get("variable_cost_eur_mwh",0)) for sp in scenario.get("resources",[]) if sp["id"]==name))
                for name,_,cols in resources)),
            "schedule":{"grid_import_mw":g,"import_cap_mw":caps,"uncovered_mw":violations,
                        "resources":{name:{"kind":kind,**{k:vals(v) for k,v in cols.items()}} for name,kind,cols in resources}},
            "evidence":evidence}
    if _peak_import_cost:
        result["peak_import_cost_eur"]=max(g)*_peak_import_cost
        result["operating_cost_eur"]+=result["peak_import_cost_eur"]
    diagnostics=[]
    for name,kind,cols in resources:
        spec=next(sp for sp in scenario.get("resources",[]) if sp["id"]==name)
        trace=result["schedule"]["resources"][name]
        active=[t for t in range(n) if violations[t]>1e-5]
        if kind=="battery":
            reserve=float(spec.get("reserve_mwh",0))
            diagnostics.append({"resource":name,"kind":kind,
                "minimum_soc_mwh":min(trace["soc_mwh"]),
                "reserve_reached_during_gap":any(trace["soc_mwh"][t]<=reserve+1e-5 for t in active),
                "rated_discharge_reached_during_gap":any(trace["discharge_mw"][t]>=float(spec["power_mw"])-1e-5 for t in active)})
        elif kind=="generator":
            total=sum(trace["generation_mw"])*dt
            diagnostics.append({"resource":name,"kind":kind,"total_generated_mwh":total,
                "fuel_budget_reached": "fuel_budget_mwh" in spec and total>=float(spec["fuel_budget_mwh"])-1e-5,
                "rated_power_reached_during_gap":any(trace["generation_mw"][t]>=float(spec["power_mw"])-1e-5 for t in active)})
        elif kind=="thermal_cooling":
            diagnostics.append({"resource":name,"kind":kind,
                "maximum_temperature_c":max(trace["temperature_c"]),
                "minimum_temperature_c":min(trace["temperature_c"]),
                "temperature_limit_reached_during_gap":any(trace["temperature_c"][t]>=spec["max_temp_c"]-1e-5 for t in active)})
        elif kind=="renewable":
            avail=_series({"a":spec.get("availability",1)},"a",n)
            diagnostics.append({"resource":name,"kind":kind,
                "generated_mwh":sum(trace["generation_mw"])*dt,
                "curtailed_mwh":sum(max(0,spec["power_mw"]*a-g) for a,g in zip(avail,trace["generation_mw"]))*dt})
        else:
            diagnostics.append({"resource":name,"kind":kind,"peak_deferred_mwh":max(trace["backlog_mwh"]),
                "shift_budget_reached_during_gap":any(trace["backlog_mwh"][t]>=float(spec["shift_budget_mwh"])-1e-5 for t in active)})
    result["diagnostics"]={"first_gap_interval":next((t for t,v in enumerate(violations) if v>1e-5),None),
                           "observed_limits":diagnostics,"note":"Observed bound saturation, not a unique causal diagnosis. Compare designs to test remedies."}
    result["events"]=[{**ev,"maximum_violation_mw":max(violations[ev["start"]:ev["end"]]),
                       "uncovered_mwh":sum(violations[ev["start"]:ev["end"]])*dt} for ev in events]
    result["evidence"]["result_sha256"]=_digest(result)
    return result

def compare_designs(scenario, designs):
    """Compare explicitly supplied resource additions, not continuous sizing."""
    rows=[]
    for design in [{"id":"existing","resources":[],"fixed_cost_eur":0},*designs]:
        case=deepcopy(scenario);case["resources"]=case.get("resources",[])+design["resources"]
        r=evaluate(case);fixed=_number(design["fixed_cost_eur"],"fixed cost")
        row={"id":design["id"],"fixed_cost_eur":fixed,"status":r["status"],"evidence":r["evidence"]}
        if r["status"]=="solved":
            row.update(feasible=r["feasible"],uncovered_mwh=r["uncovered_mwh"],peak_uncovered_mw=r["peak_uncovered_mw"],
                       operating_cost_eur=r["operating_cost_eur"],scenario_total_cost_eur=fixed+r["operating_cost_eur"])
        rows.append(row)
    rows.sort(key=lambda r:(r["status"]!="solved",not r.get("feasible",False),r.get("uncovered_mwh",math.inf) if not r.get("feasible",False) else 0,r.get("scenario_total_cost_eur",math.inf)))
    return {"designs":rows,"recommended":next((r["id"] for r in rows if r.get("feasible")),None),"cost_basis":"Fixed costs must be allocated to the modeled horizon; no annualization is inferred."}
