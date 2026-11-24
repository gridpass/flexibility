import importlib.util
import json
import sys
import unittest
from pathlib import Path

from gridpass_flexibility.interface import evaluate_request
from gridpass_flexibility.screening import FIELDS

BASE={k:v for k,(_,v) in FIELDS.items()}
EXAMPLES=Path(__file__).resolve().parents[1]/"examples"

class InterfaceTests(unittest.TestCase):
    def test_screen(self):
        self.assertTrue(evaluate_request("screen",BASE)["valid"])
    def test_invalid_operation(self):
        with self.assertRaises(ValueError):evaluate_request("unknown",{})
    def test_dispatch(self):
        case=json.loads((EXAMPLES/"chronological.json").read_text())
        self.assertTrue(evaluate_request("dispatch",case)["feasible"])

@unittest.skipUnless(importlib.util.find_spec("mcp"),"Install agent extra")
class AgentTests(unittest.IsolatedAsyncioTestCase):
    async def test_stdio_roundtrip(self):
        import anyio
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        server=StdioServerParameters(command=sys.executable,args=["-m","gridpass_flexibility.mcp_server"])
        with anyio.fail_after(30):
            async with stdio_client(server) as (read,write):
                async with ClientSession(read,write) as client:
                    await client.initialize()
                    tools=await client.list_tools()
                    self.assertEqual([t.name for t in tools.tools],["evaluate_flexibility"])
                    for operation,payload in [("screen",BASE),("dispatch",json.loads((EXAMPLES/"chronological.json").read_text())),("causal",json.loads((EXAMPLES/"causal-replay.json").read_text())),("dispatch",json.loads((EXAMPLES/"thermal-dispatch.json").read_text())),("economics",json.loads((EXAMPLES/"lifecycle-economics.json").read_text()))]:
                        result=await client.call_tool("evaluate_flexibility",{"operation":operation,"payload":payload})
                        self.assertFalse(result.isError)
                        self.assertEqual(result.structuredContent,evaluate_request(operation,payload))
                    invalid=await client.call_tool("evaluate_flexibility",{"operation":"unknown","payload":{}})
                    self.assertTrue(invalid.isError)

    def test_discrete_budget(self):
        from gridpass_flexibility.mcp_server import _check_budget
        with self.assertRaisesRegex(ValueError,"binary variables"):
            _check_budget("dispatch",{"baseline_mw":[1]*5000,"resources":[{"kind":"generator","discrete":True}]})

    def test_causal_budget_rejection(self):
        from gridpass_flexibility.mcp_server import _check_budget
        with self.assertRaisesRegex(ValueError,"96 steps"):
            _check_budget("causal",{"scenario":{"baseline_mw":[1]*97}})
        with self.assertRaisesRegex(ValueError,"60 seconds"):
            _check_budget("causal",{"scenario":{"baseline_mw":[1]},"time_limit_s":61})

    def test_budget_rejection(self):
        from gridpass_flexibility.mcp_server import _check_budget
        with self.assertRaises(ValueError):
            _check_budget("dispatch",{"baseline_mw":[1]*35040,"resources":[{}]*16})
