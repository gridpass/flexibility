"""Local Model Context Protocol server for all open evaluation operations."""
from __future__ import annotations
import argparse
from typing import Any, Literal
from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from .interface import evaluate_request

Operation = Literal["screen", "dispatch", "compare_designs", "profile", "size", "stress", "causal", "economics"]

from .budget import check_budget as _check_budget

def create_server(port=8765):
    server=FastMCP("GridPass Flexibility",host="127.0.0.1",port=port,stateless_http=True,json_response=True,
        instructions="Read-only open-source numerical evaluation. Results are modeled engineering evidence, not grid approval.")
    @server.tool(structured_output=True, annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False))
    def evaluate_flexibility(operation: Operation, payload: dict[str, Any]) -> dict[str, Any]:
        """Evaluate grid flexibility using the open GridPass engine.

        Select screen, dispatch, compare_designs, profile, size, stress, causal or economics.
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
