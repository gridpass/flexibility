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

def evaluate(scenario: dict) -> dict:
    """Return a schedule, constraint violations, cost and reproducible input digest.

    First minimize import-cap violations, then minimize operating cost at that
    minimum. Grid import, resource availability and storage recovery are enforced.
    """
    import numpy as np
    import scipy
    from scipy.optimize import linprog
    from scipy.sparse import coo_matrix
    dt=_number(scenario["interval_hours"],"interval_hours",1/3600,24)
    demand=scenario["baseline_mw"]
    if not isinstance(demand,list) or not 1<=len(demand)<=MAX_INTERVALS: raise ValueError("Invalid baseline_mw horizon")
    n=len(demand)
    if n*dt>8760+EPS: raise ValueError("Horizon exceeds 8760 hours")
    demand=_series(scenario,"baseline_mw",n)
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

    bounds=[]; operating=[]
    eq_r=[];eq_c=[];eq_v=[];eq_b=[]
    ub_r=[];ub_c=[];ub_v=[];ub_b=[]
    def variable(lo,hi,cost=0):
        i=len(bounds);bounds.append((lo,hi));operating.append(cost);return i
    def series(lo,hi,cost=0):
        return [variable(lo,hi[t] if isinstance(hi,list) else hi,cost[t] if isinstance(cost,list) else cost) for t in range(n)]
    def constraint(terms,rhs,equal=False):
        rr,cc,vv,bb=(eq_r,eq_c,eq_v,eq_b) if equal else (ub_r,ub_c,ub_v,ub_b)
        row=len(bb);bb.append(rhs)
        for col,coef in terms:
            if coef:rr.append(row);cc.append(col);vv.append(coef)
    grid=series(0,None,[p*dt for p in prices]); gap=series(0,None)
    balance=[[(grid[t],1)] for t in range(n)]
    for t in range(n):constraint([(grid[t],1),(gap[t],-1)],caps[t])
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
        if kind=="generator":
            # Generation can be scheduled outside events for pre-ramp/recovery.
            gen=series(0,available,cost*dt)
            ramp=_number(spec.get("ramp_mw_per_hour",p/dt),name+" ramp")*dt
            initial=_number(spec.get("initial_mw",0),name+" initial output",0,p)
            for t in range(n):
                prev=[(gen[t-1],-1)] if t else []
                constraint([(gen[t],1)]+prev,ramp+(initial if not t else 0))
                constraint([(gen[t],-1)]+[(i,-v) for i,v in prev],ramp-(initial if not t else 0))
                balance[t].append((gen[t],1))
            if "fuel_budget_mwh" in spec: constraint([(i,dt) for i in gen],_number(spec["fuel_budget_mwh"],name+" fuel budget"))
            resources.append((name,kind,{"generation_mw":gen}))
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
            soc=[variable(reserve,energy) for _ in range(n)]
            for t in range(n):
                terms=[(soc[t],1),(charge[t],-eta_c*dt),(discharge[t],dt/eta_d)]
                if t:terms.append((soc[t-1],-1))
                constraint(terms,0 if t else initial,True)
                if charge_p and p:constraint([(charge[t],1/charge_p),(discharge[t],1/p)],1)
                balance[t]+=[(charge[t],-1),(discharge[t],1)]
            constraint([(soc[-1],-1)],-final)
            resources.append((name,kind,{"charge_mw":charge,"discharge_mw":discharge,"soc_mwh":soc}))
        elif kind in ("workload","cooling","flexible_load"):
            # Energy-equivalent shift budget. No lost workloads; deferred energy must
            # be recovered before the specified deadline and within available cap.
            backlog_cap=_number(spec["shift_budget_mwh"],name+" shift budget")
            recover=_number(spec.get("recovery_power_mw",p),name+" recovery power")
            max_delay=_number(spec["max_delay_hours"],name+" delay",dt,8760)
            if max_delay/dt > n+EPS: delay=n
            else:delay=max(1,math.floor(max_delay/dt+EPS))
            shed=series(0,[min(available[t],demand[t]) if event_at[t] else 0 for t in range(n)],cost*dt)
            restore=series(0,[recover*availability[t] if event_at[t] is None else 0 for t in range(n)],[EPS*dt]*n)
            backlog=[variable(0,backlog_cap) for _ in range(n)]
            # Cumulative deferrals/recovery make the deadline constraints O(n).
            deferred=[variable(0,None) for _ in range(n)]
            recovered=[variable(0,None) for _ in range(n)]
            for t in range(n):
                terms=[(backlog[t],1),(shed[t],-dt),(restore[t],dt)]
                if t:terms.append((backlog[t-1],-1))
                constraint(terms,0,True)
                for cumulative,flow in ((deferred,shed),(recovered,restore)):
                    terms=[(cumulative[t],1),(flow[t],-dt)]
                    if t:terms.append((cumulative[t-1],-1))
                    constraint(terms,0,True)
                if t>=delay:constraint([(deferred[t-delay],1),(recovered[t],-1)],0)
                balance[t]+=[(shed[t],1),(restore[t],-1)]
            constraint([(backlog[-1],1)],0,True)
            resources.append((name,kind,{"shift_mw":shed,"recovery_mw":restore,"backlog_mwh":backlog}))
        else:raise ValueError(f"Unsupported resource kind {kind}")
    # No combination may defer more than the underlying total load.
    for t in range(n):
        shed=[(cols["shift_mw"][t],1) for _,_,cols in resources if "shift_mw" in cols]
        if shed:constraint(shed,demand[t])
        constraint(balance[t],demand[t],True)
    def matrix(r,c,v,b):return coo_matrix((v,(r,c)),shape=(len(b),len(bounds))).tocsc()
    def solve(objective):
        return linprog(objective,A_ub=matrix(ub_r,ub_c,ub_v,ub_b),b_ub=np.array(ub_b),
                       A_eq=matrix(eq_r,eq_c,eq_v,eq_b),b_eq=np.array(eq_b),bounds=bounds,method="highs")
    priority=np.zeros(len(bounds));priority[gap]=dt
    first=solve(priority)
    evidence={"engine_version":__version__,"solver":"scipy.optimize.linprog/HiGHS","scipy_version":scipy.__version__,
              "scenario_sha256":_digest(scenario),"evidence_type":"modelled_perfect_foresight"}
    if not first.success:return {"status":"solver_failed","solver_status":int(first.status),"message":first.message,"evidence":evidence}
    constraint([(i,dt) for i in gap],max(0,float(first.fun))+EPS)
    second=solve(np.asarray(operating))
    if not second.success:return {"status":"solver_failed","solver_status":int(second.status),"message":second.message,"evidence":evidence}
    x=second.x
    def vals(indices):return [float(max(0,x[i])) for i in indices]
    g=vals(grid); violations=[max(0,g[t]-caps[t]) for t in range(n)]
    result={"status":"solved","feasible":max(violations,default=0)<=1e-5,
            "horizon_hours":n*dt,"uncovered_mwh":sum(violations)*dt,"peak_uncovered_mw":max(violations,default=0),
            "event_hours":sum((ev["end"]-ev["start"])*dt for ev in events),
            "grid_energy_cost_eur":sum(g[t]*prices[t]*dt for t in range(n)),
            "operating_cost_eur":float(sum(g[t]*prices[t]*dt for t in range(n)) + sum(
                (sum(x[i] for key in ("generation_mw","discharge_mw","shift_mw") for i in cols.get(key,[]))
                 *dt*next(float(sp.get("variable_cost_eur_mwh",0)) for sp in scenario.get("resources",[]) if sp["id"]==name))
                for name,_,cols in resources)),
            "schedule":{"grid_import_mw":g,"import_cap_mw":caps,"uncovered_mw":violations,
                        "resources":{name:{"kind":kind,**{k:vals(v) for k,v in cols.items()}} for name,kind,cols in resources}},
            "evidence":evidence}
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
