"""Shared complexity limits for remote evaluation adapters."""
def check_budget(operation, payload):
    # These bounds are specific to the agent adapter, not to engineering CLI use.
    # A resource interval is a conservative proxy for solver work; not a runtime guarantee.
    def effort(s, extra=0):
        n=len(s["baseline_mw"])
        rs=s.get("resources",[])
        binary_intervals=n*sum(3 if r.get("kind")=="generator" else 1 for r in rs if r.get("discrete") is True)
        if binary_intervals>12_000:
            raise ValueError("Agent request exceeds 12,000 binary variables per dispatch; use the engineering CLI.")
        return n*(2+len(rs)+extra)+10*binary_intervals
    from .interface import OPERATIONS
    if operation not in OPERATIONS:
        raise ValueError("Unsupported evaluation operation")
    if operation == "screen":
        return
    if operation == "dispatch":
        work=effort(payload)
    elif operation == "compare_designs":
        designs=payload["designs"]
        if len(designs)>32:raise ValueError("At most 32 candidate designs per agent request")
        work=effort(payload["scenario"])+sum(effort({**payload["scenario"],"resources":payload["scenario"].get("resources",[])+d["resources"]}) for d in designs)
    elif operation == "profile":
        scenarios=payload["scenarios"]
        if len(scenarios)>32:raise ValueError("At most 32 profile cases per agent request")
        work=sum(effort(s) for s in scenarios)
    elif operation == "size":
        if len(payload["cases"])>32 or len(payload["options"])>16:raise ValueError("Too many cases or capacity options")
        if payload.get("time_limit_s",60)>60:raise ValueError("Agent sizing time limit is 60 seconds")
        work=sum(effort(c["scenario"],len(payload["options"])) for c in payload["cases"])*2
    elif operation == "economics":
        alternatives=payload["alternatives"]; sensitivities=payload.get("sensitivities",[])
        if not 1<=len(alternatives)<=8 or len(sensitivities)>8:raise ValueError("Agent economics case limit exceeded")
        if payload.get("time_limit_s",60)>60:raise ValueError("Agent economics time limit is 60 seconds")
        work=sum(effort(a["scenario"]) for a in alternatives)*(1+len(sensitivities))
    elif operation == "causal":
        s=payload["scenario"];steps=len(s["baseline_mw"]);width=payload.get("lookahead_intervals",24)
        if type(width) is not int or not 1<=width<=96 or steps>96:
            raise ValueError("Agent causal replay is limited to 96 steps and 96 lookahead intervals")
        if payload.get("time_limit_s",60)>60:raise ValueError("Agent replay time limit is 60 seconds")
        # Bound the repeated LP/MILP work, not merely the trace length.
        work=effort({**s,"baseline_mw":[0]*min(width,steps)})*steps*4
    else:
        work=effort(payload["site"])*(2+len(payload.get("outage_ids",[])))
    if work>500_000:
        raise ValueError("Agent request exceeds 500,000 resource-interval units. Use a smaller case or the engineering CLI.")
