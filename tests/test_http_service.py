import importlib.util
import json
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from gridpass_flexibility.interface import evaluate_request
from gridpass_flexibility import __version__

EXAMPLES=Path(__file__).resolve().parents[1]/"examples"
TOKEN="test-token-only-"+"x"*32
HEADERS={"Authorization":"Bearer "+TOKEN}
def fixture(name):
    return json.loads((EXAMPLES/name).read_text())

@unittest.skipUnless(importlib.util.find_spec("fastapi"),"Install host extra")
class HttpTests(unittest.TestCase):
    def setUp(self):
        from fastapi.testclient import TestClient
        from gridpass_flexibility.http_service import create_app
        self.client=TestClient(create_app(TOKEN))
    def post(self,operation,payload):
        return self.client.post("/evaluate",headers=HEADERS,json={"operation":operation,"payload":payload})
    def test_auth(self):
        self.assertEqual(self.client.post("/evaluate",json={}).status_code,401)
        self.assertEqual(self.client.post("/evaluate",headers={"Authorization":"Bearer wrong"},json={}).status_code,401)
        from gridpass_flexibility.http_service import create_app
        with self.assertRaises(ValueError):create_app("short")
    def test_health(self):
        self.assertEqual(self.client.get("/health").json()["engine_version"],__version__)
    def test_parity_real_child(self):
        for op,name in [("screen","data-centre.json"),("dispatch","chronological.json"),("size","capacity-sizing.json")]:
            with self.subTest(op=op):
                p=fixture(name);r=self.post(op,p)
                self.assertEqual(r.status_code,200,r.text)
                self.assertEqual(r.json()["result"],evaluate_request(op,p))
                self.assertEqual(r.headers["cache-control"],"no-store")
    def test_invalid_request(self):
        self.assertEqual(self.post("no-such-operation",{}).status_code,400)
        r=self.post("dispatch",{"private":"customer secret"})
        self.assertEqual(r.status_code,422)
        self.assertNotIn("customer secret",r.text)
        r=self.client.post("/evaluate",headers={**HEADERS,"Content-Type":"application/json"},
                           content='{"operation":"screen","payload":{"load":NaN}}')
        self.assertEqual(r.status_code,400)
    def test_input_limit(self):
        from gridpass_flexibility.http_service import MAX_REQUEST
        r=self.client.post("/evaluate",headers={**HEADERS,"Content-Type":"application/json"},content=b"x"*(MAX_REQUEST+1))
        self.assertEqual(r.status_code,413)
    def test_budget_limit(self):
        r=self.post("dispatch",{"baseline_mw":[1]*35040,"resources":[{}]*16})
        self.assertEqual(r.status_code,422)
    def test_timeout_kills_real_child(self):
        from gridpass_flexibility.http_service import _child
        body=json.dumps({"operation":"dispatch","payload":fixture("chronological.json")}).encode()
        self.assertEqual(_child(body,timeout=.001),(504,{"error":"evaluation_timeout"}))
    def test_busy_slot_and_recovery(self):
        start=threading.Event(); release=threading.Event()
        def child(*args):
            start.set(); release.wait(5)
            return 200,{"result":{"valid":True}}
        with patch("gridpass_flexibility.http_service._child",side_effect=child):
            results=[]
            t=threading.Thread(target=lambda:results.append(self.post("screen",{}).status_code))
            t.start()
            try:
                self.assertTrue(start.wait(5))
                self.assertEqual(self.post("screen",{}).status_code,429)
            finally:
                release.set();t.join(5)
            self.assertEqual(results,[200])
            self.assertEqual(self.post("screen",{}).status_code,200)
