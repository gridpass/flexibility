import copy
import json
from pathlib import Path
import unittest

try:
    import cryptography
except ImportError:
    cryptography = None

if cryptography is not None:
    from gridpass_flexibility.guard import Bounds, Contract, Guard, Meter, SimSite, sign_message, verify_trace
    from gridpass_flexibility.guard_demo import demo_key, run


@unittest.skipUnless(cryptography is not None, "install the guard extra")
class TestGuard(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = json.loads((Path(__file__).resolve().parents[1] /
                                  "examples/guard-site.json").read_text())

    def test_fixture_expected_results(self):
        trace = run(self.fixture)
        self.assertEqual(trace, run(self.fixture))
        for spec, record in zip(self.fixture["steps"], trace["records"], strict=True):
            with self.subTest(case=spec["case"]):
                for k, v in spec["expect"].items():
                    self.assertEqual(record[k], v, k)
                if record["requested_w"] is not None:
                    self.assertLessEqual(record["allowed_w"], record["effective_bounds"]["max_w"])
                    self.assertGreaterEqual(record["allowed_w"], record["effective_bounds"]["min_w"])

    def test_trace_modified_truncated_and_wrong_key(self):
        trace = run(self.fixture)
        ctx = trace["checkpoint"]["context"]
        pub = demo_key("evidence").public_key()
        self.assertTrue(verify_trace(trace, ctx, pub))
        modified = copy.deepcopy(trace)
        modified["records"][0]["allowed_w"] += 1
        self.assertFalse(verify_trace(modified, ctx, pub))
        truncated = copy.deepcopy(trace)
        truncated["records"].pop()
        self.assertFalse(verify_trace(truncated, ctx, pub))
        self.assertFalse(verify_trace(trace, ctx, demo_key("untrusted").public_key()))
        self.assertFalse(verify_trace(trace, {}, pub))

    def test_invalid_contract(self):
        with self.assertRaises(ValueError):
            Bounds(-1, -2)
        with self.assertRaises(ValueError):
            Bounds(False, 3)
        with self.assertRaises(ValueError):
            Contract("x", Bounds(-10, 100), Bounds(-20, 50), 0)
        with self.assertRaises(ValueError):
            Contract("x", Bounds(-10, 100), Bounds(-5, 50), 51)

    def test_message_tamper_and_monotonic_restart(self):
        operator, ems = demo_key("operator"), demo_key("ems")
        c = Contract("x", Bounds(-100, 100), Bounds(0, 30), 0)
        g = Guard(c, operator.public_key(), ems.public_key())
        good = sign_message(operator, site="x", role="operator", seq=1,
                            issued_s=0, expires_s=10, payload={"min_w": -50, "max_w": 50})
        bad = copy.deepcopy(good)
        bad["body"]["payload"]["max_w"] = 90
        plant = SimSite(0, 100, 100)
        r = g.tick(now=0, operator=bad, ems=None, link_up=True, meter=Meter(0, 0), site=plant)
        self.assertEqual(r["policy_status"], "invalid_signature")
        r = g.tick(now=1, operator=good, ems=None, link_up=True, meter=Meter(0, 1), site=plant)
        self.assertEqual(r["policy_status"], "accepted")
        g = g.restart()
        with self.assertRaises(ValueError):
            g.tick(now=1, operator=good, ems=None, link_up=True, meter=Meter(0, 1), site=plant)
        r = g.tick(now=2, operator=good, ems=None, link_up=True, meter=Meter(0, 2), site=plant)
        self.assertEqual(r["policy_status"], "replay")

    def test_roles_require_distinct_keys(self):
        key = demo_key("operator").public_key()
        with self.assertRaises(ValueError):
            Guard(Contract("x", Bounds(0, 100), Bounds(0, 30), 0), key, key)
