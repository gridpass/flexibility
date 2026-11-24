#!/usr/bin/env python3
"""Read-only production smoke test using exclusively the public synthetic examples.

Run from an installed checkout of the version deployed by the hosted service:
    python scripts/verify_hosted.py
This is deliberately opt-in, not a CI test against the live service.
"""
from __future__ import annotations
import argparse
from copy import deepcopy
import json
import urllib.error
import urllib.request
from pathlib import Path
from gridpass_flexibility.interface import evaluate_request
from gridpass_flexibility.interface_schema import validate_evaluation

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
CASES = {
    "screen": "data-centre.json",
    "dispatch": "chronological.json",
    "compare_designs": "design-comparison.json",
    "profile": "profile-check.json",
    "size": "capacity-sizing.json",
    "stress": "annual-stress.json",
    "causal": "causal-replay.json",
    "economics": "lifecycle-economics.json",
}

def release_cases():
    """Synthetic commissioning fixture: no energy can be borrowed before opening."""
    a = {"id": "commissioning", "scenario": {
        "interval_hours": 24, "baseline_mw": [1]*365,
        "normal_import_cap_mw": 2, "price_eur_mwh": 100,
        "events": [{"start":181,"end":182,"cap_mw":0,"notice_minutes":1440}],
        "resources": [{"id":"b","kind":"battery","power_mw":1,"energy_mwh":24,
                       "initial_mwh":0,"terminal_mwh":0,
                       "charge_efficiency":1,"discharge_efficiency":1}]},
        "capex_eur":100000,"delay_months":6,"seasonal_commissioning":True,
        "annual_contribution_eur":2000000,"annual_fixed_opex_eur":10000,
        "tariff":{"grid_emissions_kg_mwh":0,"monthly_peak_eur_mw":[0]*12}}
    b = deepcopy(a)
    b.update(id="interyear", delay_months=0, seasonal_commissioning=False,
             interyear_reoptimization=True, tariff={"grid_emissions_kg_mwh":0})
    b["scenario"]["events"][0].update(start=364, end=365)
    b["scenario"]["resources"][0]["initial_mwh"] = 24
    c = deepcopy(b)
    c["scenario"]["normal_import_cap_mw"] = 1
    cases = {name: ("economics", {"years":2,"real_discount_rate":.1,
                                 "alternatives":[alternative]})
            for name, alternative in [("commissioning", a), ("interyear", b),
                                      ("interyear_infeasible", c)]}
    cases["capacity_candidates"] = ("size", json.loads((EXAMPLES / "capacity-candidates.json").read_text()))
    return cases


def assert_release_case(name, expected):
    if name == "capacity_candidates":
        if (not expected["comparison_complete"] or expected["selected_candidate_id"] != "combined"
                or abs(expected["total_cost_eur"]-8120)>1e-5
                or [c["status"] for c in expected["candidates"]] != ["infeasible","infeasible","solved","solved"]):
            raise RuntimeError("Capacity package acceptance failed")
        return
    if name not in ("commissioning", "interyear", "interyear_infeasible"):
        return
    case = expected["cases"][0]
    row = case["alternatives"][0]
    if name == "commissioning":
        if (not row["annual"]["feasible"] or row["commissioning"]["feasible"]
                or abs(row["commissioning"]["uncovered_mwh"] - 24) > 1e-5
                or row["eligible"] or case["recommended"] is not None):
            raise RuntimeError("Commissioning fixture failed independent acceptance assertions")
        return
    first, second = row["operating_years"]
    if (first["next_initial_state"]["b"]["initial_mwh"] != 0 or
            second["carried_initial_state"] != first["next_initial_state"]):
        raise RuntimeError("Inter-year state continuity failed")
    if name == "interyear":
        if (not row["eligible"] or case["recommended"] != "interyear" or
                abs(second["annual_operating_cost_eur"] - first["annual_operating_cost_eur"] - 2400) > 1e-5):
            raise RuntimeError("Inter-year recharge cost acceptance failed")
    elif (row["eligible"] or case["recommended"] is not None or
          abs(second["uncovered_mwh"] - 24) > 1e-5):
        raise RuntimeError("Inter-year infeasibility acceptance failed")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="https://gridpass.co")
    parser.add_argument("--operation", choices=tuple(CASES), action="append")
    parser.add_argument("--release-cases", action="store_true", help="Also probe commissioning, inter-year continuity and equipment package selection")
    args = parser.parse_args()
    base = args.base.rstrip("/")
    headers = {"Origin": base, "Content-Type": "application/json",
               "Accept": "application/json", "User-Agent": "Mozilla/5.0 (GridPass synthetic acceptance probe)"}

    def post(path, obj):
        request = urllib.request.Request(base + path, json.dumps(obj, allow_nan=False).encode(), headers)
        try:
            with urllib.request.urlopen(request, timeout=65) as reply:
                return reply.status, json.load(reply)
        except urllib.error.HTTPError as exc:
            try:
                body = json.load(exc)
            except ValueError:
                body = {"error": "non-JSON HTTP response"}
            return exc.code, body

    def rpc(method, params):
        status, body = post("/api/mcp", {"jsonrpc": "2.0", "id": 1, "method": method, "params": params})
        if status != 200 or "result" not in body:
            raise RuntimeError(f"MCP {method}: HTTP {status}")
        return body["result"]

    with urllib.request.urlopen(urllib.request.Request(base + "/tools/flexibility-assessment/",
                                                        headers=headers), timeout=15) as reply:
        if reply.status != 200:
            raise RuntimeError("Calculator unavailable")
    tools = rpc("tools/list", {})["tools"]
    if tools[0]["name"] != "evaluate_flexibility" or "oneOf" not in tools[0]["inputSchema"]:
        raise RuntimeError("Advanced MCP schema unavailable")

    cases = {op: (op, json.loads((EXAMPLES / CASES[op]).read_text()))
             for op in args.operation or CASES}
    if args.release_cases:
        cases.update(release_cases())
    for name, (op, payload) in cases.items():
        # Compare JSON values, not Python-only container types (e.g. tariff tuples).
        validate_evaluation("request", op, payload)
        expected = json.loads(json.dumps(evaluate_request(op, payload), allow_nan=False))
        assert_release_case(name, expected)
        envelope = {"operation": op, "payload": payload}
        status, browser = post("/api/flexibility/evaluate", envelope)
        if status != 200:
            raise RuntimeError(f"{op}: browser HTTP {status}, error={browser.get('error')}")
        response = rpc("tools/call", {"name": "evaluate_flexibility", "arguments": envelope})
        actual = json.loads(response["content"][0]["text"])
        for result in (expected, browser, actual):
            validate_evaluation("response", op, result)
        if browser != expected or actual != expected:
            raise RuntimeError(f"{name}: numerical or evidence parity failed (check engine/solver versions)")
        print(f"{name}: exact browser/MCP/local parity", flush=True)

    status, body = post("/api/flexibility/evaluate", {"operation": "dispatch", "payload": {}})
    if status != 422 or body != {"error": "invalid_evaluation"}:
        raise RuntimeError("Invalid input rejection failed")
    # No contact data or positive consent. This must not create an enquiry.
    res = rpc("tools/call", {"name": "request_free_site_review", "arguments": {"consent": False}})
    if not res["isError"]:
        raise RuntimeError("Consent rejection failed")
    print("Invalid input and consent rejection passed")

if __name__ == "__main__":
    main()
