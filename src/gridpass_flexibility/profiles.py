"""Independent, versioned flexibility test profiles.

A profile is a contract/test envelope, not an official classification or proof
of reliability across every possible sequence.
"""
from __future__ import annotations
from .dispatch import evaluate, _number

def evaluate_profile(profile, scenarios):
    """Check modeled schedules and explicitly report test coverage.

    Each supplied scenario must exercise the required notice and duration.
    To assess annual utilization, supply a full 8760-hour schedule; shorter
    schedules only demonstrate their observed coverage.
    """
    notice=_number(profile["notice_minutes"],"profile notice")
    duration=_number(profile["activation_hours"],"profile activation",0.0001,8760)
    utilization=_number(profile["annual_event_hours"],"annual event hours",0,8760)
    target=_number(profile["reduction_mw"],"required reduction MW",0.000001)
    if utilization<duration:raise ValueError("Annual hours must cover at least one activation")
    if not scenarios:raise ValueError("At least one test scenario required")
    cases=[];full_year=False;stress_covered=False
    for scenario in scenarios:
        r=evaluate(scenario);dt=scenario["interval_hours"]
        # An event only covers the profile when the requested reduction actually
        # exceeds the stated target for its full duration.
        baseline=scenario["baseline_mw"]
        normal=scenario["normal_import_cap_mw"]
        if not isinstance(normal,list):normal=[normal]*len(baseline)
        qualifying=[e for e in scenario.get("events",[])
                    if e["notice_minutes"]<=notice and all(min(baseline[t],normal[t])-e["cap_mw"]>=target-1e-8
                           for t in range(e["start"],e["end"]))]
        hours=sum((e["end"]-e["start"])*dt for e in qualifying)
        stress=any(e["notice_minutes"]<=notice and (e["end"]-e["start"])*dt>=duration-1e-8 for e in qualifying)
        year=abs(len(baseline)*dt-8760)<1e-6 and hours>=utilization-1e-6
        stress_covered|=stress;full_year|=year
        cases.append({"feasible":r.get("feasible",False),"status":r["status"],"event_hours":hours,"stress_event_covered":stress,
                      "annual_usage_covered":year,"evidence":r["evidence"],"uncovered_mwh":r.get("uncovered_mwh")})
    coverage=stress_covered and full_year
    return {"profile_id":profile["id"],"profile_version":profile["version"],"profile":profile,
            "cases":cases,"coverage":{"notice_and_duration":stress_covered,"annual_usage":full_year},
            "result":"modeled_cases_pass" if coverage and all(c["feasible"] for c in cases) else "modeled_cases_fail" if any(not c["feasible"] for c in cases) else "incomplete_coverage",
            "limitations":"Only the supplied event sequences and resource assumptions are evaluated. Not a certificate, guarantee, or official Flex MOSAIC classification."}
