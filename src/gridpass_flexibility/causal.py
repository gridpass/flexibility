"""Sampled receding-horizon replay with announced events and observed asset states.

The policy receives only the current observation and announced event windows.
Future demand, prices, ordinary import capacity, and asset availability use
persistence forecasts. Only the first action of each HiGHS plan is executed.
"""
from __future__ import annotations
import math
from time import monotonic
from copy import deepcopy
from . import __version__
from .dispatch import evaluate, _digest, _index, _number, _series

TOL=1e-5
MAX_STEPS=672
MAX_LOOKAHEAD=96

def replay(scenario: dict, lookahead_intervals: int=24, time_limit_s: float=60) -> dict:
    time_limit_s=_number(time_limit_s,"replay time limit",.1,600)
    deadline=monotonic()+time_limit_s
    dt=_number(scenario["interval_hours"],"interval hours",1/3600,24)
    if not isinstance(scenario["baseline_mw"],list):raise ValueError("baseline_mw must be an array")
    n=len(scenario["baseline_mw"])
    if not 1<=n<=MAX_STEPS or n*dt>8760:
        raise ValueError("Causal replay supports 1–672 intervals per run")
    if type(lookahead_intervals) is not int or not 1<=lookahead_intervals<=MAX_LOOKAHEAD:
        raise ValueError("Lookahead must be 1–96 intervals")
    demand=_series(scenario,"baseline_mw",n)
    normal=_series(scenario,"normal_import_cap_mw",n)
    prices=_series(scenario,"price_eur_mwh",n)
    protected=_series({"protected":scenario.get("protected_load_mw",0)},"protected",n)
    actual_events=[];active=[None]*n
    for raw in scenario.get("events",[]):
        start=_index(raw["start"],"event start",n);end=_index(raw["end"],"event end",n)
        if start>=end or any(x is not None for x in active[start:end]):
            raise ValueError("Events must be nonempty and nonoverlapping")
        notice=_number(raw["notice_minutes"],"event notice")
        cap=_number(raw["cap_mw"],"event cap")
        # At discrete samples, a notification first becomes visible at ceil(time).
        reveal=math.ceil(start-notice/(dt*60)-1e-9)
        ev={"start":start,"end":end,"notice_minutes":max(0,(start-reveal)*dt*60),"cap_mw":cap,"reveal":reveal}
        actual_events.append(ev)
        for t in range(start,end):active[t]=ev
    specs=deepcopy(scenario.get("resources",[]))
    if len(specs)>64 or len({r["id"] for r in specs})!=len(specs):
        raise ValueError("Resource IDs must be unique; maximum 64")
    availability={};state={};trace={};targets={};thermal={};thermal_targets={}
    for r in specs:
        rid=r["id"];kind=r["kind"]
        p=_number(r["power_mw"],rid+" power")
        availability[rid]=_series({"a":r.get("availability",1)},"a",n)
        if max(availability[rid])>1:raise ValueError("Availability must be 0..1")
        if kind=="battery":
            e=_number(r["energy_mwh"],rid+" energy")
            reserve=_number(r.get("reserve_mwh",0),rid+" reserve",0,e)
            initial=_number(r.get("initial_mwh",e),rid+" initial energy",reserve,e)
            targets[rid]=_number(r.get("terminal_mwh",initial),rid+" recovery target",reserve,e)
            state[rid]={"soc":initial}
        elif kind=="generator":
            initial=_number(r.get("initial_mw",0),rid+" initial output",0,p)
            on=r.get("initial_on",initial>0)
            age=_number(r.get("initial_state_hours",8760),rid+" initial dwell",0,8760)
            if type(on) is not bool or (not on and initial>TOL) or (on and initial<r.get("minimum_output_mw",0)-TOL):
                raise ValueError("Inconsistent initial generator state")
            state[rid]={"mw":initial,"on":on,"age":age,
                        "fuel":_number(r["fuel_budget_mwh"],rid+" fuel") if "fuel_budget_mwh" in r else None}
        elif kind=="thermal_cooling":
            from .thermal import parameters
            th=parameters(r,n)
            thermal[rid]=th
            thermal_targets[rid]=th["terminal"]
            state[rid]={"temperature_c":th["initial"]}
        elif kind=="renewable":
            state[rid]={}
        elif kind in ("workload","cooling","flexible_load"):
            delay=_number(r["max_delay_hours"],rid+" delay",dt,8760)
            state[rid]={"queue":[],"delay":max(1,math.floor(delay/dt+1e-7))}
        else:raise ValueError(f"Unsupported resource kind {kind}")
        trace[rid]={"kind":kind}
    result={"status":"solved","feasible":False,"horizon_hours":n*dt,"executed_intervals":0,
            "schedule":{"grid_import_mw":[],"import_cap_mw":[],"uncovered_mw":[],"resources":trace},
            "observations":[],"forced_trips":[],"fallbacks":[],"missed_deadlines":[],"operating_cost_eur":0.0,
            "evidence":{"engine_version":__version__,"evidence_type":"causal_sampled_replay",
                        "scenario_sha256":_digest(scenario),"policy":"persistence-receding-horizon-v2",
                        "lookahead_intervals":lookahead_intervals,"time_limit_s":time_limit_s},
            "limitations":"Sampled simulation, not live control. Future observations are forecast by persistence. Only announced event schedules are known. The solver prioritizes current cap, forecast total gaps, battery recovery outside events, then cost. On an infeasible workload forecast a one-sample fallback forbids new deferrals and preserves outstanding energy; fallback use is non-passing. No subinterval response or universal robustness claim."}
    for t in range(n):
        if monotonic()>=deadline:
            result.update(status="replay_failed",failure={"interval":t,"message":"Causal replay time budget exhausted","solver_status":1})
            break
        width=min(lookahead_intervals,n-t)
        end=t+width
        known=[e for e in actual_events if e["reveal"]<=t and e["end"]>t]
        window_events=[]
        for e in known:
            if e["start"]>=end:continue
            start=max(t,e["start"])
            window_events.append({"start":start-t,"end":min(end,e["end"])-t,"cap_mw":e["cap_mw"],
                                  "notice_minutes":e["notice_minutes"]+max(0,t-e["start"])*dt*60})
        window={"interval_hours":dt,"baseline_mw":[demand[t]]*width,
                "normal_import_cap_mw":normal[t],"price_eur_mwh":prices[t],"protected_load_mw":protected[t],"events":window_events,"resources":[]}
        backlogs={}
        trips=[]
        for r in specs:
            rid=r["id"];kind=r["kind"];st=state[rid];s=deepcopy(r)
            avail=availability[rid][t]
            s["availability"]=avail
            if kind=="battery":
                # A rolling window must not reset stored energy or require impossible
                # restoration during an ongoing restriction. Recovery is prioritized
                # separately outside events; terminal reserve remains a hard bound.
                s["initial_mwh"]=st["soc"]
                s["terminal_mwh"]=s.get("reserve_mwh",0)
            elif kind=="generator":
                p=s["power_mw"]
                ramp=s.get("ramp_mw_per_hour",p/dt)*dt
                minimum=s.get("minimum_output_mw",0)
                if (st["mw"]>p*avail+ramp+TOL or
                    (st["on"] and (avail<=0 or p*avail<minimum-TOL))):
                    trips.append({"interval":t,"resource":rid,"previous_mw":st["mw"],"availability":avail})
                    st.update(mw=0.0,on=False,age=0.0)
                    # A forced trip cannot restart in the same sample, even if
                    # residual derated capacity is available.
                    s["availability"]=0.0
                s["initial_mw"]=st["mw"]
                if s.get("discrete"):
                    s["initial_on"]=st["on"]
                    s["initial_state_hours"]=min(8760,st["age"])
                if st["fuel"] is not None:s["fuel_budget_mwh"]=st["fuel"]
            elif kind=="thermal_cooling":
                from .thermal import SERIES_FIELDS
                for field in SERIES_FIELDS:s[field]=thermal[rid][field][t]
                s["initial_temp_c"]=st["temperature_c"]
                # Terminal recovery is checked at the real end, not imposed at
                # every artificial horizon boundary.
                s["terminal_max_temp_c"]=s["max_temp_c"]
            elif kind=="renewable":
                pass
            else:
                backlogs[rid]=[(due-t,amount) for due,amount in st["queue"]]
            window["resources"].append(s)
        result["forced_trips"].extend(trips)
        result["observations"].append({"interval":t,"baseline_mw":demand[t],"normal_import_cap_mw":normal[t],
            "price_eur_mwh":prices[t],"protected_load_mw":protected[t],"thermal_inputs":{rid:{key:th[key][t] for key in ("ambient_c","heat_gain_mw","cop","baseline_cooling_mw")} for rid,th in thermal.items()},"availability":{rid:a[t] for rid,a in availability.items()},
            "announced_events":[{k:v for k,v in e.items() if k!="reveal"} for e in known]})
        context={"backlogs":backlogs,"recharge_targets":targets,"thermal_targets":thermal_targets}
        plan=evaluate(window,_causal_state=context,_deadline=deadline)
        # Only a proven infeasible forecast triggers the single-step policy.
        # Never reinterpret timeouts, numerical failures or invalid inputs.
        if plan["status"]!="solved" and plan.get("solver_status")==2 and backlogs:
            reason=plan["message"]
            one=deepcopy(window)
            one["baseline_mw"]=one["baseline_mw"][:1]
            one["events"]=[{**e,"end":1} for e in window_events if e["start"]==0]
            plan=evaluate(one,_causal_state={**context,"recovery_fallback":True},_deadline=deadline)
            result["fallbacks"].append({"interval":t,"reason":reason,"status":plan["status"]})
        if plan["status"]!="solved":
            result.update(status="replay_failed",failure={"interval":t,"message":plan["message"],
                "solver_status":plan.get("solver_status"),"observed_backlog_mwh":{rid:sum(a for _,a in q) for rid,q in backlogs.items()}})
            break
        schedule=plan["schedule"]
        g=schedule["grid_import_mw"][0]
        cap=min(normal[t],active[t]["cap_mw"]) if active[t] else normal[t]
        result["schedule"]["grid_import_mw"].append(g)
        result["schedule"]["import_cap_mw"].append(cap)
        result["schedule"]["uncovered_mw"].append(max(0,g-cap))
        cost=g*prices[t]*dt
        for r in specs:
            rid=r["id"];kind=r["kind"];st=state[rid]
            action={k:v[0] for k,v in schedule["resources"][rid].items() if k!="kind"}
            for k,v in action.items():trace[rid].setdefault(k,[]).append(v)
            variable=r.get("variable_cost_eur_mwh",0)
            if kind=="battery":
                st["soc"]=min(r["energy_mwh"],max(r.get("reserve_mwh",0),action["soc_mwh"]))
                cost+=action["discharge_mw"]*dt*variable
            elif kind=="generator":
                st["mw"]=action["generation_mw"]
                on=action.get("online",float(st["mw"]>TOL))>.5
                st["age"]=st["age"]+dt if on==st["on"] else dt
                st["on"]=on
                if st["fuel"] is not None:st["fuel"]=max(0,st["fuel"]-st["mw"]*dt)
                cost+=st["mw"]*dt*variable+action.get("startup",0)*r.get("startup_cost_eur",0)+action.get("online",0)*dt*r.get("online_cost_eur_per_hour",0)
            elif kind=="thermal_cooling":
                st["temperature_c"]=min(r["max_temp_c"],max(r["min_temp_c"],action["temperature_c"]))
                cost+=action["cooling_mw"]*dt*variable
            elif kind=="renewable":
                cost+=action["generation_mw"]*dt*variable
            else:
                # FIFO recovery of previously deferred energy; each item retains
                # its original deadline across solves, not a fresh delay window.
                amount=action["recovery_mw"]*dt;queue=[]
                for due,remaining in st["queue"]:
                    used=min(amount,remaining);amount-=used;remaining-=used
                    if remaining>1e-8:queue.append((due,remaining))
                shifted=action["shift_mw"]*dt
                if shifted>1e-8:queue.append((t+st["delay"],shifted))
                # Record each newly missed deadline exactly once. Overdue
                # work remains in the queue until actually recovered.
                missed=sum(a for due,a in queue if due==t)
                if missed>TOL:
                    result["missed_deadlines"].append({"interval":t,"resource":rid,"mwh":missed})
                st["queue"]=queue
                cost+=shifted*variable
        result["operating_cost_eur"]+=cost
        result["executed_intervals"]+=1
    result["terminal_state"]=state
    gap=result["schedule"]["uncovered_mw"]
    result["uncovered_mwh"]=sum(gap)*dt
    result["peak_uncovered_mw"]=max(gap,default=0)
    result["terminal_recovery_shortfall_mwh"]={rid:max(0,goal-state[rid]["soc"]) for rid,goal in targets.items()}
    result["terminal_backlog_mwh"]={rid:sum(a for _,a in st["queue"]) for rid,st in state.items() if "queue" in st}
    result["terminal_thermal_shortfall_c"]={rid:max(0,state[rid]["temperature_c"]-goal) for rid,goal in thermal_targets.items()}
    result["missed_deadline_mwh"]=sum(x["mwh"] for x in result["missed_deadlines"])
    result["feasible"]=(result["status"]=="solved" and not result["fallbacks"] and not result["missed_deadlines"] and result["peak_uncovered_mw"]<=TOL and
        all(v<=TOL for v in result["terminal_recovery_shortfall_mwh"].values()) and all(v<=TOL for v in result["terminal_backlog_mwh"].values()) and all(v<=TOL for v in result["terminal_thermal_shortfall_c"].values()))
    result["evidence"]["result_sha256"]=_digest(result)
    return result
