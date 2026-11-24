"""Local Model Context Protocol server for all open evaluation operations."""
from __future__ import annotations
import argparse
from typing import Any, Literal
from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from .interface import evaluate_request

Operation = Literal["screen", "dispatch", "compare_designs", "profile", "size", "stress"]

def _check_budget(operation, payload):
    # These bounds are specific to the agent adapter, not to engineering CLI use.
    # A resource interval is a conservative proxy for solver work; not a runtime guarantee.
    def effort(s, extra=0):
        return len(s["baseline_mw"]) * (2 + len(s.get("resources", [])) + extra)
    if operation == "screen":
        return
    if operation == "dispatch":
        work=effort(payload)
    elif operation == "compare_designs":
        designs=payload["designs"]
        if len(designs)>32:raise ValueError("At most 32 candidate designs per agent request")
        work=effort(payload["scenario"])+sum(effort(payload["scenario"],len(d["resources"])) for d in designs)
    elif operation == "profile":
        scenarios=payload["scenarios"]
        if len(scenarios)>32:raise ValueError("At most 32 profile cases per agent request")
        work=sum(effort(s) for s in scenarios)
    elif operation == "size":
        if len(payload["cases"])>32 or len(payload["options"])>16:raise ValueError("Too many cases or capacity options")
        if payload.get("time_limit_s",60)>60:raise ValueError("Agent sizing time limit is 60 seconds")
        work=sum(effort(c["scenario"],len(payload["options"])) for c in payload["cases"])*2
    else:
        work=effort(payload["site"])*(2+len(payload.get("outage_ids",[])))
    if work>500_000:
        raise ValueError("Agent request exceeds 500,000 resource-interval units. Use a smaller case or the engineering CLI.")

def create_server(port=8765):
    server=FastMCP("GridPass Flexibility",host="127.0.0.1",port=port,stateless_http=True,json_response=True,
        instructions="Read-only open-source numerical evaluation. Results are modeled engineering evidence, not grid approval.")
    @server.tool(structured_output=True, annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False))
    def evaluate_flexibility(operation: Operation, payload: dict[str, Any]) -> dict[str, Any]:
        """Evaluate grid flexibility using the open GridPass engine.

        Select screen, dispatch, compare_designs, profile, size or stress.
        Payloads use the documented JSON examples and units (MW, MWh, hours,
        minutes for notice, EUR). Returns feasibility, cost, constraints and
        evidence as supported by the chosen operation. No live asset control.
        """
        _check_budget(operation,payload)
        return evaluate_request(operation,payload)
    return server

def main():
    parser=argparse.ArgumentParser(description="Run the local GridPass MCP server")
    parser.add_argument("--transport",choices=["stdio","streamable-http"],default="stdio")
    parser.add_argument("--port",type=int,default=8765)
    args=parser.parse_args()
    if not 1<=args.port<=65535:parser.error("Invalid port")
    create_server(args.port).run(transport=args.transport)

if __name__=="__main__":
    main()
