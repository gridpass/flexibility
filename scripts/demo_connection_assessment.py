#!/usr/bin/env python3
"""Run a synthetic connection assessment through the installed GridPass MCP.

Install with ``pip install '.[agent]'``, then run this script. It discovers the
contract and example through MCP, validates them, and calls the existing engine.
JSON goes to stdout. No operator data, customer data or equipment is accessed.
"""
from __future__ import annotations

import asyncio
import json
import sys

import anyio
from jsonschema import Draft202012Validator
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def read_json(client, uri):
    resource = await client.read_resource(uri)
    if len(resource.contents) != 1 or not hasattr(resource.contents[0], "text"):
        raise RuntimeError(f"Expected one JSON text resource: {uri}")
    return json.loads(resource.contents[0].text)


async def assess():
    server = StdioServerParameters(
        command=sys.executable, args=["-m", "gridpass_flexibility.mcp_server"]
    )
    with anyio.fail_after(60):
        async with stdio_client(server) as (read, write):
            async with ClientSession(read, write) as client:
                initialized = await client.initialize()
                tools = await client.list_tools()
                resources = await client.list_resources()
                prompts = await client.list_prompts()
                await client.get_prompt("assess_connection")
                request_schema = await read_json(
                    client, "gridpass://evaluation/schema/request"
                )
                response_schema = await read_json(
                    client, "gridpass://evaluation/schema/response"
                )
                request = await read_json(
                    client, "gridpass://evaluation/examples/compare_designs"
                )
                Draft202012Validator(request_schema).validate(request)
                response = await client.call_tool("evaluate_flexibility", request)
                if response.isError or response.structuredContent is None:
                    raise RuntimeError("The MCP evaluation failed")
                result = response.structuredContent
                Draft202012Validator(response_schema).validate(
                    {"operation": request["operation"], "result": result}
                )
                # A valid MCP response can still contain an incomplete solve.
                # This fixed demonstration must reproduce its documented outcomes.
                expected = {"existing": False, "battery": False, "hybrid": True}
                designs = {row["id"]: row for row in result["designs"]}
                if set(designs) != set(expected) or any(
                    designs[name]["status"] != "solved"
                    or designs[name].get("feasible") is not feasible
                    for name, feasible in expected.items()
                ) or result["recommended"] != "hybrid":
                    raise RuntimeError("The synthetic assessment did not reproduce its expected outcomes")
    return {
        "purpose": "Compare equipment options against a proposed import limit",
        "input_status": "synthetic demonstration, not a customer or operator offer",
        "transport": "MCP stdio",
        "server": initialized.serverInfo.name,
        "tools": [tool.name for tool in tools.tools],
        "resources": [str(resource.uri) for resource in resources.resources],
        "prompts": [prompt.name for prompt in prompts.prompts],
        "request_schema_id": request_schema["$id"],
        "response_schema_id": response_schema["$id"],
        "request": request,
        "result": result,
        "interpretation_limits": [
            "The numerical result uses modelled perfect foresight.",
            "Example costs are synthetic assumptions allocated to this horizon.",
            "Published network headroom is not an authorised site import limit.",
            "This result does not establish physical performance or connection approval.",
        ],
    }


if __name__ == "__main__":
    print(json.dumps(asyncio.run(assess()), indent=2, allow_nan=False))
