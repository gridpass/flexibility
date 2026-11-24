"""Construct deterministic full-year commitment scenarios with explicit coverage."""
from __future__ import annotations
import math
from copy import deepcopy
from .dispatch import _number, _series, _digest
from .profiles import evaluate_profile, validate_profile

def build_stress_suite(site, profile, outage_ids=()):
    """Evenly distributed and clustered activations; optional whole-horizon outage.

    The cap is chosen conservatively for the complete event. Exact alignment of
    duration to interval size is required. Annual use rounds up by one interval.
    """
    profile=validate_profile(profile)
    dt=_number(site["interval_hours"],"interval hours",1/3600,24)
    if dt*60>profile.get("maximum_interval_minutes",1440)+1e-8:raise ValueError("Site interval exceeds profile resolution limit")
    n=len(site["baseline_mw"])
    if abs(n*dt-8760)>1e-6:raise ValueError("Stress suite requires one 8760-hour baseline")
    duration=_number(profile["activation_hours"],"activation hours",dt,8760)
    length=round(duration/dt)
    if abs(length*dt-duration)>1e-6:raise ValueError("Activation duration must align with intervals")
    annual=_number(profile["annual_event_hours"],"annual event hours",duration,8760)
    total=min(n,math.ceil(annual/dt-1e-9))
    recovery=_number(profile.get("minimum_recovery_hours",0),"minimum recovery")
    gap=round(recovery/dt)
    if abs(gap*dt-recovery)>1e-6:raise ValueError("Recovery duration must align with intervals")
    target=_number(profile["reduction_mw"],"reduction MW",.000001)
    notice=_number(profile["notice_minutes"],"notice minutes")
    lengths=[length]*(total//length)+([total%length] if total%length else [])
    occupied=sum(lengths)+gap*max(0,len(lengths)-1)
    if occupied>n:raise ValueError("Annual event budget and recovery do not fit in one year")
    # Keep extra time after final event for terminal recovery whenever possible.
    slack=n-occupied
    baseline=_series(site,"baseline_mw",n);normal=_series(site,"normal_import_cap_mw",n)
    out=[]
    for strategy in ("distributed","clustered"):
        case=deepcopy(site);case["events"]=[]
        cursor=0
        for k,width in enumerate(lengths):
            if strategy=="distributed": extra=round(slack*(k+1)/(len(lengths)+1))
            else:extra=slack//2
            start=cursor+extra;end=start+width
            cap=min(min(baseline[t],normal[t]) for t in range(start,end))-target
            if cap < -1e-8:raise ValueError("Requested reduction exceeds baseline or normal cap")
            case["events"].append({"start":start,"end":end,"notice_minutes":notice,"cap_mw":max(0,cap)})
            cursor+=width+gap
        out.append({"id":strategy,"scenario":case})
    valid_ids={r["id"] for r in site.get("resources",[])}
    if len(set(outage_ids))!=len(outage_ids) or set(outage_ids)-valid_ids:raise ValueError("Invalid outage resource ID")
    for rid in outage_ids:
        c=deepcopy(out[1]["scenario"])
        for r in c["resources"]:
            if r["id"]==rid:
                r["availability"]=0
                # Initial output is zero for a whole-horizon outage.
                if r["kind"]=="generator":r["initial_mw"]=0
        out.append({"id":"clustered-outage-"+rid,"scenario":c})
    return out

def test_commitment(site, profile, outage_ids=()):
    suite=build_stress_suite(site,profile,outage_ids)
    r=evaluate_profile(profile,[x["scenario"] for x in suite])
    for case,desc in zip(r["cases"],suite):case["id"]=desc["id"]
    r["suite"]={"version":"gridpass-stress-v1","outage_ids":list(outage_ids),
                "description":"Distributed and clustered annual events at a conservative cap, optional whole-horizon resource outages."}
    r["evidence"].pop("result_sha256",None)
    r["evidence"]["result_sha256"]=_digest(r)
    return r
