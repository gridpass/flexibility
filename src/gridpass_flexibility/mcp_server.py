"""Local Model Context Protocol server for all open evaluation operations."""
from __future__ import annotations
import argparse
import json
from typing import Any, Literal
from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from .interface import evaluate_request
from .interface_schema import evaluation_schema
from .mcp_discovery import GUIDE, WORKFLOW, example_request

Operation = Literal["screen", "dispatch", "compare_designs", "profile", "size", "stress", "causal", "economics"]

from .budget import check_budget as _check_budget

def create_server(port=8765):
    server=FastMCP("GridPass Flexibility",host="127.0.0.1",port=port,stateless_http=True,json_response=True,
        instructions="Read-only open-source numerical evaluation. Read gridpass://evaluation/guide or use the assess_connection prompt. Results are modeled engineering evidence, not grid approval.")

    @server.resource("gridpass://evaluation/guide", mime_type="text/markdown")
    def evaluation_guide() -> str:
        """Operation selection, input evidence, units and assessment boundaries."""
        return GUIDE

    @server.resource("gridpass://evaluation/schema/request", mime_type="application/schema+json")
    def request_schema() -> str:
        """Existing versioned JSON Schema for all evaluation requests."""
        return json.dumps(evaluation_schema("request"))

    @server.resource("gridpass://evaluation/schema/response", mime_type="application/schema+json")
    def response_schema() -> str:
        """Existing versioned JSON Schema for operation-tagged results."""
        return json.dumps(evaluation_schema("response"))

    @server.resource("gridpass://evaluation/examples/{operation}", mime_type="application/json")
    def evaluation_example(operation: str) -> str:
        """Synthetic request for one of the eight operations; never actual site data."""
        return json.dumps(example_request(operation))

    @server.prompt()
    def assess_connection() -> str:
        """Assess a site's offered grid import limit using supplied evidence."""
        return WORKFLOW

    @server.tool(structured_output=True, annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False))
    def evaluate_flexibility(operation: Operation, payload: dict[str, Any]) -> dict[str, Any]:
        """Evaluate grid flexibility using the open GridPass engine.

        Select screen, dispatch, compare_designs, profile, size, stress, causal or economics.
        Read gridpass://evaluation/guide for contracts and synthetic examples.
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
