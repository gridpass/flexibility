import importlib.util
import json
from pathlib import Path
import sys
import unittest

import gridpass_flexibility
from gridpass_flexibility.interface import OPERATIONS, evaluate_request
from gridpass_flexibility.interface_schema import evaluation_schema, validate_evaluation


@unittest.skipUnless(importlib.util.find_spec("mcp"), "Install agent extra")
class MCPDiscoveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_discovery_to_evaluation(self):
        import anyio
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        from mcp.shared.exceptions import McpError

        server = StdioServerParameters(
            command=sys.executable, args=["-m", "gridpass_flexibility.mcp_server"],
            env={"PYTHONPATH": str(Path(gridpass_flexibility.__file__).resolve().parent.parent)},
        )
        with anyio.fail_after(60):
            async with stdio_client(server) as (read, write):
                async with ClientSession(read, write) as client:
                    await client.initialize()
                    tools = (await client.list_tools()).tools
                    self.assertEqual([tool.name for tool in tools], ["evaluate_flexibility"])
                    self.assertTrue(tools[0].annotations.readOnlyHint)
                    self.assertFalse(tools[0].annotations.destructiveHint)
                    self.assertTrue(tools[0].annotations.idempotentHint)
                    self.assertFalse(tools[0].annotations.openWorldHint)
                    resources = (await client.list_resources()).resources
                    self.assertEqual({str(r.uri) for r in resources}, {
                        "gridpass://evaluation/guide", "gridpass://evaluation/schema/request",
                        "gridpass://evaluation/schema/response",
                    })
                    templates = (await client.list_resource_templates()).resourceTemplates
                    self.assertEqual([t.uriTemplate for t in templates],
                                     ["gridpass://evaluation/examples/{operation}"])
                    guide = await client.read_resource("gridpass://evaluation/guide")
                    self.assertEqual(guide.contents[0].mimeType, "text/markdown")
                    for direction in ("request", "response"):
                        resource = await client.read_resource(f"gridpass://evaluation/schema/{direction}")
                        self.assertEqual(json.loads(resource.contents[0].text), evaluation_schema(direction))
                    for operation in OPERATIONS:
                        resource = await client.read_resource(f"gridpass://evaluation/examples/{operation}")
                        request = json.loads(resource.contents[0].text)
                        self.assertEqual(request["operation"], operation)
                        validate_evaluation("request", operation, request["payload"])
                    # A discovered chronological request reaches the existing solver unchanged.
                    resource = await client.read_resource("gridpass://evaluation/examples/dispatch")
                    request = json.loads(resource.contents[0].text)
                    result = await client.call_tool("evaluate_flexibility", request)
                    self.assertFalse(result.isError)
                    validate_evaluation("response", "dispatch", result.structuredContent)
                    self.assertEqual(result.structuredContent,
                                     json.loads(json.dumps(evaluate_request(**request), allow_nan=False)))
                    for uri in ("gridpass://evaluation/examples/unknown",
                                "gridpass://evaluation/examples/..%2Fguard-site.json",
                                "gridpass://evaluation/schema/unknown"):
                        with self.subTest(uri=uri), self.assertRaises(McpError):
                            await client.read_resource(uri)
                    prompts = (await client.list_prompts()).prompts
                    self.assertEqual([prompt.name for prompt in prompts], ["assess_connection"])
                    self.assertFalse(prompts[0].arguments)
                    prompt = await client.get_prompt("assess_connection")
                    self.assertEqual(prompt.messages[0].role, "user")
                    self.assertIn("gridpass://evaluation/schema/request", prompt.messages[0].content.text)
