#!/usr/bin/env python3
"""Read-only production smoke test using exclusively the public synthetic examples.

Run from an installed checkout of the version deployed by the hosted service:
    python scripts/verify_hosted.py
This is deliberately opt-in, not a CI test against the live service.
"""
from __future__ import annotations
import argparse
import json
import urllib.error
import urllib.request
from pathlib import Path
from gridpass_flexibility.interface import evaluate_request

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

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="https://gridpass.co")
    parser.add_argument("--operation", choices=tuple(CASES), action="append")
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

    for op in args.operation or CASES:
        payload = json.loads((EXAMPLES / CASES[op]).read_text())
        expected = evaluate_request(op, payload)
        envelope = {"operation": op, "payload": payload}
        status, browser = post("/api/flexibility/evaluate", envelope)
        if status != 200:
            raise RuntimeError(f"{op}: browser HTTP {status}, error={browser.get('error')}")
        response = rpc("tools/call", {"name": "evaluate_flexibility", "arguments": envelope})
        actual = json.loads(response["content"][0]["text"])
        if browser != expected or actual != expected:
            raise RuntimeError(f"{op}: numerical or evidence parity failed (check engine/solver versions)")
        print(f"{op}: exact browser/MCP/local parity", flush=True)

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
