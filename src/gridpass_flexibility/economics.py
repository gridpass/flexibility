"""Real-EUR lifecycle comparison of feasible annual connection alternatives.

The chronological dispatch engine optimizes energy, carbon, fuel and an
annual or monthly non-coincident site peak fees. Finance is a separate transparent layer.
No inferred revenue, emissions factors, discount rate or annualization.
"""
from __future__ import annotations

from copy import deepcopy
from time import monotonic
from math import isclose
from . import __version__
from .dispatch import evaluate, _number, _series, _digest

MAX_ALTERNATIVES=8
MAX_SENSITIVITIES=8

def _fields(obj, required, optional, name):
    if not isinstance(obj,dict) or not set(required)<=obj.keys() or set(obj)-set(required)-set(optional):
        raise ValueError(f"Invalid {name} fields")

def _id(v):
    if not isinstance(v,str) or not v or len(v)>100:
        raise ValueError("IDs must be nonempty strings up to 100 characters")
    return v

def _cashflows(annual, a, years, discount, capex_factor, extra_delay):
    capex=_number(a["capex_eur"],"initial capital expenditure",0,1e12)*capex_factor
    delay=_number(a["delay_months"],"connection delay",0,1200)+extra_delay
    margin=_number(a["annual_contribution_eur"],"annual contribution before modeled costs",-1e12,1e12)
    fixed=_number(a["annual_fixed_opex_eur"],"annual fixed operating cost",0,1e12)
    salvage=_number(a.get("residual_value_eur",0),"residual value",0,1e12)*capex_factor
    replacement={}
    replacements=a.get("replacements",[])
    if not isinstance(replacements,list) or len(replacements)>100:raise ValueError("Expected at most 100 replacements")
    for item in replacements:
        _fields(item,["year","cost_eur"],[],"replacement")
        y=item["year"]
        if type(y) is not int or not 1<=y<=years or y*12<=delay:
            raise ValueError("Replacement year must be in operating horizon")
        replacement[y]=replacement.get(y,0)+_number(item["cost_eur"],"replacement cost",0,1e12)*capex_factor
    # All amounts in constant EUR, initial investment now, year-end discounting.
    flows=[{"year":0,"service_fraction":0,"net_cashflow_eur":-capex,"discounted_cashflow_eur":-capex}]
    for y in range(1,years+1):
        fraction=max(0,min(1,(y*12-delay)/12))
        # Residual value is explicitly assumed realizable, even if the project is delayed.
        terminal=salvage if y==years else 0
        net=fraction*(margin-fixed-annual)-replacement.get(y,0)+terminal
        flows.append({"year":y,"service_fraction":fraction,
                      "contribution_eur":fraction*margin,"fixed_opex_eur":fraction*fixed,
                      "operating_cost_eur":fraction*annual,"replacement_eur":replacement.get(y,0),
                      "residual_eur":terminal,"net_cashflow_eur":net,"discounted_cashflow_eur":net/(1+discount)**y})
    npv=sum(x["discounted_cashflow_eur"] for x in flows)
    discounted_service_years=sum(x["service_fraction"]/(1+discount)**x["year"] for x in flows)
    return {"npv_eur":npv,"cashflows":flows,"initial_capex_eur":capex,"delay_months":delay,
            "discounted_service_years":discounted_service_years}

def _monthly_periods(tariff, dt, n):
    """Non-leap Jan–Dec billing periods; samples cannot straddle boundaries."""
    if "monthly_peak_eur_mw" not in tariff:
        return []
    if "annual_peak_eur_mw" in tariff:
        raise ValueError("Choose annual or monthly peak tariff, not both")
    rates=tariff["monthly_peak_eur_mw"]
    if not isinstance(rates,list) or len(rates)!=12:
        raise ValueError("monthly_peak_eur_mw requires 12 Jan–Dec rates")
    periods=[]
    hours=0
    for days,rate in zip((31,28,31,30,31,30,31,31,30,31,30,31),rates):
        start=round(hours/dt)
        hours+=24*days
        end=round(hours/dt)
        if abs(end*dt-hours)>1e-6 or not 0<=start<end<=n:
            raise ValueError("Intervals must align with calendar month boundaries")
        periods.append((start,end,_number(rate,"monthly peak tariff")))
    return periods

def _annual(a, modifiers, deadline):
    scenario=deepcopy(a["scenario"])
    n=len(scenario["baseline_mw"]);dt=_number(scenario["interval_hours"],"interval hours",1/3600,24)
    if abs(n*dt-8760)>1e-6:raise ValueError("Economics requires a complete 8760-hour operating year")
    prices=_series(scenario,"price_eur_mwh",n)
    tariff=a.get("tariff",{})
    _fields(tariff,[],["grid_emissions_kg_mwh","carbon_eur_tonne","annual_peak_eur_mw","monthly_peak_eur_mw"],"tariff")
    # Require explicit grid factor, including a declared zero, to avoid silently omitting emissions.
    if "grid_emissions_kg_mwh" not in tariff:raise ValueError("Declare grid_emissions_kg_mwh explicitly")
    grid_ef=_series({"ef":tariff["grid_emissions_kg_mwh"]},"ef",n)
    carbon=_number(tariff.get("carbon_eur_tonne",0),"carbon price")*modifiers["carbon_multiplier"]
    peak_price=_number(tariff.get("annual_peak_eur_mw",0),"annual peak tariff")
    monthly=_monthly_periods(tariff,dt,n)
    energy_price=[p*modifiers["electricity_multiplier"] for p in prices]
    scenario["price_eur_mwh"]=[p+carbon*ef/1000 for p,ef in zip(energy_price,grid_ef)]
    fuel=a.get("fuel",{})
    generators={r["id"] for r in scenario.get("resources",[]) if r["kind"]=="generator"}
    if not isinstance(fuel,dict) or set(fuel)!=generators:raise ValueError("Declare fuel assumptions for every generator, and no other resource")
    factors={}
    for r in scenario.get("resources",[]):
        if r["kind"]!="generator":continue
        f=fuel[r["id"]]
        _fields(f,["electrical_efficiency","fuel_eur_mwh","fuel_emissions_kg_mwh"],[],"fuel")
        eta=_number(f["electrical_efficiency"],"generator efficiency",.01,1)
        price=_number(f["fuel_eur_mwh"],"fuel price")*modifiers["fuel_multiplier"]
        ef=_number(f["fuel_emissions_kg_mwh"],"fuel emissions factor")
        # The unmodified generator variable cost is nonfuel, noncarbon variable O&M.
        r["variable_cost_eur_mwh"]=_number(r.get("variable_cost_eur_mwh",0),"nonfuel variable cost")+(price+carbon*ef/1000)/eta
        factors[r["id"]]=(eta,price,ef)
    if monotonic()>=deadline:
        return {"dispatch_status":"solver_failed","feasible":False,"message":"Economics time budget exhausted",
                "evidence":{"engine_version":__version__,"scenario_sha256":_digest(scenario)}}
    solved=evaluate(scenario,_peak_import_cost=peak_price,_peak_periods=monthly,_deadline=deadline)
    result={"dispatch_status":solved["status"],"feasible":solved.get("feasible",False),"evidence":solved["evidence"]}
    if solved["status"]!="solved":
        result["message"]=solved["message"]
        return result
    grid=solved["schedule"]["grid_import_mw"]
    grid_cost=sum(p*g*dt for p,g in zip(energy_price,grid))
    grid_emissions=sum(ef*g*dt for ef,g in zip(grid_ef,grid))/1000
    peak=max(grid);fuel_cost=0;fuel_emissions=0;fuel_mwh=0
    for name,(eta,price,ef) in factors.items():
        consumed=sum(solved["schedule"]["resources"][name]["generation_mw"])*dt/eta
        fuel_mwh+=consumed;fuel_cost+=consumed*price;fuel_emissions+=consumed*ef/1000
    carbon_cost=carbon*(grid_emissions+fuel_emissions)
    monthly_rows=[{"month":i+1,"peak_import_mw":max(grid[start:end]),"rate_eur_mw":rate,
                   "cost_eur":max(grid[start:end])*rate} for i,(start,end,rate) in enumerate(monthly)]
    peak_cost=peak*peak_price+sum(row["cost_eur"] for row in monthly_rows)
    operating=solved["operating_cost_eur"]
    # Independently reconstruct operating costs from the *original* nonfuel
    # resource rates and the optimized trace; do not hide errors in a residual.
    other=0
    for spec in a["scenario"].get("resources",[]):
        trace=solved["schedule"]["resources"][spec["id"]]
        other+=sum(sum(trace.get(key,[])) for key in ("generation_mw","discharge_mw","shift_mw","cooling_mw"))*dt*spec.get("variable_cost_eur_mwh",0)
    breakdown=grid_cost+fuel_cost+carbon_cost+peak_cost+other+solved["commitment_cost_eur"]
    if not isclose(breakdown,operating,rel_tol=1e-9,abs_tol=.01):
        return {**result,"dispatch_status":"accounting_error","feasible":False,"message":"Operating cost reconciliation failed"}
    result.update(annual_operating_cost_eur=operating,grid_energy_mwh=sum(grid)*dt,
                  peak_import_mw=peak,grid_energy_cost_eur=grid_cost,peak_tariff_cost_eur=peak_cost,
                  fuel_mwh=fuel_mwh,fuel_cost_eur=fuel_cost,grid_emissions_tonnes=grid_emissions,
                  fuel_emissions_tonnes=fuel_emissions,carbon_cost_eur=carbon_cost,
                  other_variable_cost_eur=other,commitment_cost_eur=solved["commitment_cost_eur"],
                  uncovered_mwh=solved["uncovered_mwh"])
    if monthly:result["monthly_peak_tariffs"]=monthly_rows
    return result

def compare_lifecycle(payload):
    """Compute NPV and feasible ranking for base and explicit sensitivities."""
    _fields(payload,["years","real_discount_rate","alternatives"],["sensitivities","reference_id","time_limit_s"],"economics")
    deadline=monotonic()+_number(payload.get("time_limit_s",60),"economics time budget",.1,600)
    years=payload["years"]
    if type(years) is not int or not 1<=years<=50:raise ValueError("Analysis years must be 1–50")
    discount=_number(payload["real_discount_rate"],"real discount rate",0,1)
    alternatives=payload["alternatives"]
    if not isinstance(alternatives,list) or not 1<=len(alternatives)<=MAX_ALTERNATIVES:raise ValueError("1–8 alternatives required")
    for a in alternatives:
        _fields(a,["id","scenario","capex_eur","delay_months","annual_contribution_eur","annual_fixed_opex_eur","tariff"],
                ["fuel","replacements","residual_value_eur"],"alternative")
    ids=[_id(a["id"]) for a in alternatives]
    if len(set(ids))!=len(ids):raise ValueError("Duplicate alternative ID")
    reference=payload.get("reference_id",ids[0])
    if reference not in ids:raise ValueError("Unknown reference_id")
    sensitivities=payload.get("sensitivities",[])
    if not isinstance(sensitivities,list) or len(sensitivities)>MAX_SENSITIVITIES:raise ValueError("At most 8 sensitivities")
    defaults={"electricity_multiplier":1,"fuel_multiplier":1,"carbon_multiplier":1,"capex_multiplier":1,"extra_delay_months":0}
    cases=[{"id":"base",**defaults}]
    for raw in sensitivities:
        _fields(raw,["id"],defaults,"sensitivity")
        sid=_id(raw["id"])
        if sid in {c["id"] for c in cases}:raise ValueError("Duplicate sensitivity ID")
        cases.append({"id":sid,**{k:_number(raw.get(k,v),k,0,1200 if k=="extra_delay_months" else 100) for k,v in defaults.items()}})
    results=[]
    for case in cases:
        rows=[]
        for a in alternatives:
            annual=_annual(a,case,deadline)
            row={"id":a["id"],"annual":annual,"eligible":False}
            if annual["dispatch_status"]=="solved":
                finance=_cashflows(annual["annual_operating_cost_eur"],a,years,discount,case["capex_multiplier"],case["extra_delay_months"])
                row["finance"]=finance
                row["eligible"]=annual["feasible"] and finance["discounted_service_years"]>0
            else:
                # Validate financial inputs even if the solver fails.
                _cashflows(0,a,years,discount,case["capex_multiplier"],case["extra_delay_months"])
            rows.append(row)
        reference_row=next(r for r in rows if r["id"]==reference)
        for row in rows:
            # An infeasible alternative is not a valid financial counterfactual.
            row["incremental_npv_eur"]=(row["finance"]["npv_eur"]-reference_row["finance"]["npv_eur"]
                                         if row["eligible"] and reference_row["eligible"] else None)
        ranked=sorted((r for r in rows if r["eligible"]),key=lambda r:(-r["finance"]["npv_eur"],r["id"]))
        complete=all(r["annual"]["dispatch_status"]=="solved" for r in rows)
        results.append({"id":case["id"],"assumptions":case,"alternatives":rows,
                        "comparison_complete":complete,"recommended":ranked[0]["id"] if complete and ranked else None})
    result={"status":"solved" if all(r["annual"]["dispatch_status"]=="solved" for c in results for r in c["alternatives"]) else "evaluation_error",
            "years":years,"real_discount_rate":discount,"reference_id":reference,"cases":results,
            "evidence":{"engine_version":__version__,"input_sha256":_digest(payload),"evidence_type":"modeled_lifecycle_economics"},
            "limitations":"One supplied operating year repeated in real EUR; fractional service years prorate all annual costs and contribution, including peak tariff. Capex at year zero, cashflows at year end. No tax, financing, degradation, escalation, outage probabilities or external certification. Annual peak tariff is a single site maximum, not monthly demand billing. Emissions factors and contribution are user assumptions, not forecasts. Perfect-foresight dispatch."}
    if any("monthly_peak_eur_mw" in a["tariff"] for a in alternatives):
        result["limitations"]=result["limitations"].replace("Annual peak tariff is a single site maximum, not monthly demand billing.", "Monthly peak tariff uses sampled maxima in a non-leap Jan–Dec year.")
    result["evidence"]["result_sha256"]=_digest(result)
    return result
