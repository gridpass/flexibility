"""Independent, versioned flexibility test profiles and coverage evidence."""
from __future__ import annotations
import json
from importlib.resources import files
from .dispatch import evaluate, _number, _digest

PROFILE_SCHEMA_VERSION = "gridpass-profile-v1"
TOL = 1e-8

def profile_schema():
    return json.loads(files("gridpass_flexibility").joinpath("schemas/profile-v1.json").read_text(encoding="utf-8"))

def validate_profile(profile):
    """Validate structure, finite units and cross-field constraints."""
    from jsonschema import Draft202012Validator
    errors=sorted(Draft202012Validator(profile_schema()).iter_errors(profile),
                  key=lambda e: tuple(map(str,e.absolute_path)))
    if errors:raise ValueError("Invalid commitment profile: "+errors[0].message)
    result={**profile,"schema_version":PROFILE_SCHEMA_VERSION}
    notice=_number(result["notice_minutes"],"profile notice",0,525600)
    duration=_number(result["activation_hours"],"profile activation",.0001,8760)
    utilization=_number(result["annual_event_hours"],"annual event hours",.0001,8760)
    _number(result["reduction_mw"],"required reduction MW",.000001)
    if utilization<duration:raise ValueError("Annual hours must cover at least one activation")
    if "minimum_recovery_hours" in result:
        _number(result["minimum_recovery_hours"],"minimum recovery",0,8760)
    if "maximum_interval_minutes" in result:
        _number(result["maximum_interval_minutes"],"maximum interval minutes",1/60,1440)
    return result

def evaluate_profile(profile, scenarios):
    """Check supplied modeled schedules, not every possible future call.

    An annual case must exercise the required notice, activation duration,
    utilization, and (if specified and needed) a short recovery interval.
    A finer time step is a coverage criterion, not measured response evidence.
    """
    profile=validate_profile(profile)
    notice=profile["notice_minutes"]
    duration=profile["activation_hours"]
    utilization=profile["annual_event_hours"]
    target=profile["reduction_mw"]
    recovery=profile.get("minimum_recovery_hours")
    needs_recovery=recovery is not None and utilization>duration+TOL
    if not isinstance(scenarios,list) or not scenarios:raise ValueError("At least one test scenario required")
    cases=[]
    for scenario in scenarios:
        r=evaluate(scenario);dt=scenario["interval_hours"]
        baseline=scenario["baseline_mw"]
        normal=scenario["normal_import_cap_mw"]
        if not isinstance(normal,list):normal=[normal]*len(baseline)
        qualifying=sorted([e for e in scenario.get("events",[])
                    if e["notice_minutes"]<=notice and all(min(baseline[t],normal[t])-e["cap_mw"]>=target-TOL
                           for t in range(e["start"],e["end"]))],key=lambda e:e["start"])
        hours=sum((e["end"]-e["start"])*dt for e in qualifying)
        resolution_ok=dt*60<=profile.get("maximum_interval_minutes",1440)+TOL
        stress=resolution_ok and any((e["end"]-e["start"])*dt>=duration-TOL for e in qualifying)
        shortest_gap=min(((b["start"]-a["end"])*dt for a,b in zip(qualifying,qualifying[1:])),default=None)
        recovery_ok=not needs_recovery or (shortest_gap is not None and shortest_gap<=recovery+TOL)
        annual=resolution_ok and abs(len(baseline)*dt-8760)<1e-6 and hours>=utilization-1e-6
        complete=annual and stress and recovery_ok
        cases.append({"feasible":r.get("feasible",False),"status":r["status"],"event_hours":hours,
                      "interval_minutes":dt*60,"resolution_covered":resolution_ok,
                      "stress_event_covered":stress,"annual_usage_covered":annual,
                      "shortest_qualifying_recovery_hours":shortest_gap,"recovery_covered":recovery_ok,
                      "complete_profile_coverage":complete,"evidence":r["evidence"],
                      "uncovered_mwh":r.get("uncovered_mwh")})
    coverage={"notice_and_duration":any(c["stress_event_covered"] for c in cases),
              "annual_usage":any(c["annual_usage_covered"] for c in cases),
              "minimum_recovery":any(c["recovery_covered"] for c in cases) if needs_recovery else None,
              "single_complete_annual_case":any(c["complete_profile_coverage"] for c in cases)}
    if any(c["status"]!="solved" for c in cases):outcome="evaluation_error"
    elif any(not c["feasible"] for c in cases):outcome="modeled_cases_fail"
    elif coverage["single_complete_annual_case"]:outcome="modeled_cases_pass"
    else:outcome="incomplete_coverage"
    result={"profile_id":profile["id"],"profile_version":profile["version"],"profile":profile,
            "cases":cases,"coverage":coverage,"result":outcome,
            "evidence":{"profile_schema_version":PROFILE_SCHEMA_VERSION,"profile_sha256":_digest(profile),
                        "scenario_suite_sha256":_digest(scenarios)},
            "limitations":"Only the supplied event sequences and resource assumptions are evaluated. Interval resolution is not proof of transient response. Not a certificate, guarantee, or official Flex MOSAIC classification."}
    result["evidence"]["result_sha256"]=_digest(result)
    return result
