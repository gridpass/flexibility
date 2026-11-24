"""Independent, bounded screening for an illustrative repeated flexibility event."""
from __future__ import annotations

import math
from typing import Any

FIELDS = {
    "load": ("Site demand (MW)", 20), "limit": ("Event grid import limit (MW)", 15),
    "notice": ("Advance notice (minutes)", 60), "duration": ("Event duration (hours)", 4),
    "events": ("Events per year (integer)", 50), "recovery": ("Minimum recovery (hours)", 12),
    "flex": ("Approved load reduction (MW)", 1.5), "flexNotice": ("Load preparation time (minutes)", 10),
    "flexDuration": ("Sustained load reduction duration (hours)", 4), "flexCost": ("Load reduction cost (EUR/MWh)", 80),
    "gen": ("Available on-site generation (MW)", 2), "genNotice": ("Generation start and ramp time (minutes)", 30),
    "genDuration": ("Permitted generation duration (hours)", 12), "genCost": ("Generation variable cost (EUR/MWh)", 160),
    "battery": ("Battery charge/discharge power (MW)", 3), "energy": ("Usable discharge energy (MWh)", 8),
    "recharge": ("Spare grid recharge power (MW)", 2), "efficiency": ("Round-trip efficiency (percent)", 90),
    "electricity": ("Recharge electricity cost (EUR/MWh)", 100),
}
ASSUMPTIONS = ("Independent screening model, not EPRI software or a certification. Constant site demand, identical "
               "non-overlapping events, full initial usable battery energy and available resources. "
               "Excludes capital and fixed costs, detailed ramp curves, correlated failures, rebound unless "
               "included in inputs, network flows and site-specific protection and regulatory constraints.")
SCHEMA = {"type":"object", "properties":{
    k:{"type":"integer" if k=="events" else "number","description":label,
       "minimum":1 if k=="events" or k=="efficiency" else 0.01 if k=="duration" else 0,
       "maximum":100 if k=="efficiency" else 1_000_000}
    for k,(label,_) in FIELDS.items()}, "required":list(FIELDS), "additionalProperties":False}

def assess(v: Any) -> dict:
    if not isinstance(v, dict) or set(v) != set(FIELDS):
        return {"valid":False,"error":"Supply exactly the documented numeric inputs."}
    for k in FIELDS:
        value=v[k]
        if type(value) not in (int,float) or not 0 <= value <= 1_000_000 or not math.isfinite(value):
            return {"valid":False,"error":"Invalid numeric input: "+k}
    if (v["duration"] < 0.01 or v["events"] < 1 or int(v["events"]) != v["events"]
            or not 1 <= v["efficiency"] <= 100
            or v["events"]*v["duration"]+(v["events"]-1)*v["recovery"] > 8760):
        return {"valid":False,"error":"Check duration, whole annual event count, efficiency and the 8,760-hour annual schedule."}
    required=max(0,v["load"]-v["limit"])
    eta=v["efficiency"]/100
    charge_power=min(v["recharge"],v["battery"])
    storage_cap=min(v["battery"], v["energy"]/v["duration"],
                    charge_power*v["recovery"]*eta/v["duration"] if v["events"]>1 else math.inf)
    resources=[
        {"name":"Approved flexible loads","max":min(v["flex"],v["load"]) if v["notice"]>=v["flexNotice"] and v["duration"]<=v["flexDuration"] else 0,"cost":v["flexCost"]},
        {"name":"On-site generation","max":v["gen"] if v["notice"]>=v["genNotice"] and v["duration"]<=v["genDuration"] else 0,"cost":v["genCost"]},
        {"name":"Battery discharge","max":storage_cap,"cost":v["electricity"]/eta},
    ]
    remaining=required
    dispatch=[]
    for r in sorted(resources,key=lambda r:r["cost"]):
        power=min(remaining,r["max"])
        remaining=max(0,remaining-power)
        dispatch.append({**r,"power":power,"mwh":power*v["duration"],"eventCost":power*v["duration"]*r["cost"]})
    b=next(r for r in dispatch if r["name"]=="Battery discharge")
    charge_time=0 if b["mwh"]==0 else b["mwh"]/(eta*charge_power) if charge_power>0 else None
    hours=v["events"]*v["duration"]
    return {"valid":True,"required":required,"available":min(v["load"],sum(r["max"] for r in resources)),
            "dispatch":dispatch,"remaining":remaining,"importMW":v["load"]-required+remaining,
            "annualHours":hours,"annualUtilization":hours/8760*100,"annualCost":v["events"]*sum(r["eventCost"] for r in dispatch),
            "chargeTime":charge_time,"feasible":remaining<1e-9,"assumptions":ASSUMPTIONS}
