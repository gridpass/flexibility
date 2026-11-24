"""Shared continuous capacity expansion across a finite set of grid events.

This is a single sparse LP: every case has its own operating schedule, but
the battery MW/MWh and generator MW investments are equal in every case.
"""
from __future__ import annotations
from copy import deepcopy
from .dispatch import _build_model, _digest, _number, evaluate
from . import __version__

def _option(raw):
    o=deepcopy(raw)
    if ("discrete" in o and o["discrete"] is not False) or any(k in o for k in ("minimum_output_mw","minimum_up_hours","minimum_down_hours","initial_on","initial_state_hours","startup_cost_eur","online_cost_eur_per_hour")):
        raise ValueError("Continuous capacity sizing does not support discrete options; use design comparison")
    name=o["id"]
    if not isinstance(name,str) or not name:raise ValueError("Invalid option ID")
    kind=o["kind"]
    power=_number(o["max_power_mw"],name+" max power",0)
    _number(o["cost_eur_per_mw"],name+" power cost")
    if kind=="battery":
        energy=_number(o["max_energy_mwh"],name+" max energy")
        _number(o["cost_eur_per_mwh"],name+" energy cost")
        o["charge_power_ratio"]=_number(o.get("charge_power_ratio",1),name+" charge ratio",.001,10)
        o["reserve_fraction"]=_number(o.get("reserve_fraction",0),name+" reserve fraction",0,1)
        o["initial_fraction"]=_number(o.get("initial_fraction",1),name+" initial fraction",o["reserve_fraction"],1)
        o["terminal_fraction"]=_number(o.get("terminal_fraction",o["initial_fraction"]),name+" terminal fraction",o["reserve_fraction"],1)
        o["charge_efficiency"]=_number(o.get("charge_efficiency",.95),name+" charge efficiency",.01,1)
        o["discharge_efficiency"]=_number(o.get("discharge_efficiency",.95),name+" discharge efficiency",.01,1)
    elif kind=="generator":
        o["ramp_fraction_per_hour"]=_number(o.get("ramp_fraction_per_hour",60),name+" ramp fraction",0)
    else:raise ValueError("Capacity options support battery and generator")
    return o

def _resource(o, power, energy=None, availability=1):
    r={"id":o["id"],"kind":o["kind"],"power_mw":power,
       "response_minutes":o.get("response_minutes",0),
       "availability":availability,"variable_cost_eur_mwh":o.get("variable_cost_eur_mwh",0)}
    if o["kind"]=="battery":
        r.update(energy_mwh=energy,charge_power_mw=power*o["charge_power_ratio"],
                 reserve_mwh=energy*o["reserve_fraction"],initial_mwh=energy*o["initial_fraction"],
                 terminal_mwh=energy*o["terminal_fraction"],charge_efficiency=o["charge_efficiency"],
                 discharge_efficiency=o["discharge_efficiency"])
    else:
        r.update(ramp_mw_per_hour=power*o["ramp_fraction_per_hour"],initial_mw=0)
        if "fuel_budget_mwh" in o:r["fuel_budget_mwh"]=o["fuel_budget_mwh"]
    return r

def size_capacity(cases, options, time_limit_s=60):
    """Minimize allocated capex plus weighted operating costs across hard-cap cases.

    `cases` contains id, scenario, weight, and optional availability overrides
    for new resources. Weights explicitly allocate operating costs to the same
    horizon as investment costs. Cases with zero weight still enforce feasibility.
    Independent perfect-foresight schedules are not a causal robust policy.
    """
    import numpy as np
    import scipy
    from scipy.optimize import linprog
    from scipy.sparse import block_diag, coo_matrix, vstack
    if not isinstance(cases,list) or not 1<=len(cases)<=32:raise ValueError("1–32 cases required")
    if not isinstance(options,list) or not 1<=len(options)<=16:raise ValueError("1–16 capacity options required")
    time_limit=_number(time_limit_s,"solver time limit",.1,600)
    opts=[_option(x) for x in options]
    by_name={o["id"]:o for o in opts}
    if len(by_name)!=len(opts):raise ValueError("Duplicate capacity option")
    if len({c["id"] for c in cases})!=len(cases):raise ValueError("Duplicate case ID")
    sizes={}; models=[]; inputs=[];offset=0; objective=[];bounds=[]
    for c in cases:
        scenario=deepcopy(c["scenario"])
        weight=_number(c.get("weight",1),"operating cost weight",0,1e6)
        availability=c.get("new_resource_availability",{})
        if set(availability)-set(by_name):raise ValueError("Unknown new resource availability override")
        scenario["resources"]=scenario.get("resources",[])+[
            _resource(o,o["max_power_mw"],o.get("max_energy_mwh"),availability.get(o["id"],1)) for o in opts]
        m=_build_model(scenario,by_name,hard_caps=True)
        local=m["operating"].copy()*weight
        for key,col in m["sizing"].items():
            sizes.setdefault(key,[]).append(offset+col)
            if len(models)==0:
                o=by_name[key[0]]
                local[col]=o["cost_eur_per_mw" if key[1]=="power_mw" else "cost_eur_per_mwh"]
        models.append(m);inputs.append((c,scenario,weight));bounds+=m["bounds"]
        objective.extend(local);offset+=len(m["bounds"])
    eq=block_diag([m["A_eq"] for m in models],format="csc")
    eq_rhs=np.concatenate([m["b_eq"] for m in models])
    rows=[];cols=[];vals=[];n=0
    for same in sizes.values():
        for i in same[1:]:
            rows.extend([n,n]);cols.extend([same[0],i]);vals.extend([1,-1]);n+=1
    if n:
        eq=vstack([eq,coo_matrix((vals,(rows,cols)),shape=(n,len(bounds)))],format="csc")
        eq_rhs=np.append(eq_rhs,np.zeros(n))
    ub=block_diag([m["A_ub"] for m in models],format="csc")
    ub_rhs=np.concatenate([m["b_ub"] for m in models])
    sol=linprog(np.asarray(objective),A_ub=ub,b_ub=ub_rhs,A_eq=eq,b_eq=eq_rhs,bounds=bounds,method="highs",
                options={"time_limit":time_limit})
    evidence={"engine_version":__version__,"solver":"scipy.optimize.linprog/HiGHS","scipy_version":scipy.__version__,
              "input_sha256":_digest({"cases":cases,"options":options}),"evidence_type":"finite_scenario_capacity_planning"}
    if not sol.success:
        return {"status":"infeasible" if sol.status==2 else "solver_failed","message":sol.message,"evidence":evidence}
    selected={name:{} for name in by_name}
    for (name,dim),indices in sizes.items():selected[name][dim]=float(max(0,sol.x[indices[0]]))
    capex=sum(d["power_mw"]*by_name[name]["cost_eur_per_mw"]+d.get("energy_mwh",0)*by_name[name].get("cost_eur_per_mwh",0)
              for name,d in selected.items())
    checks=[];weighted=0
    for c,_,weight in inputs:
        scenario=deepcopy(c["scenario"]);availability=c.get("new_resource_availability",{})
        scenario["resources"]=scenario.get("resources",[])+[
            _resource(o,selected[o["id"]]["power_mw"],selected[o["id"]].get("energy_mwh"),availability.get(o["id"],1)) for o in opts]
        check=evaluate(scenario)
        if check["status"]=="solved":weighted+=weight*check["operating_cost_eur"]
        checks.append({"id":c["id"],"weight":weight,"status":check["status"],"feasible":check.get("feasible",False),
                       "uncovered_mwh":check.get("uncovered_mwh"),"operating_cost_eur":check.get("operating_cost_eur"),
                       "evidence":check["evidence"]})
    valid=all(c["feasible"] for c in checks)
    result={"status":"solved" if valid else "replay_failed","capacities":selected,"allocated_capex_eur":capex,
            "weighted_operating_cost_eur":weighted,"total_cost_eur":capex+weighted,"optimizer_objective_eur":float(sol.fun),
            "cases":checks,"all_cases_feasible":valid,"evidence":evidence,
            "limitations":"Independent perfect-foresight schedules, continuous capacity and dispatch. Feasible only for the supplied cases. Costs must refer to a consistent horizon; no annualization is inferred."}
    result["evidence"]["result_sha256"]=_digest(result)
    return result
