import copy
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

from gridpass_flexibility.budget import check_budget
from gridpass_flexibility.interface import evaluate_request
from gridpass_flexibility.interface_schema import validate_evaluation
from gridpass_flexibility.planning import size_capacity

EXAMPLE = Path(__file__).resolve().parents[1] / "examples/capacity-candidates.json"

class CapacityCandidates(unittest.TestCase):
    def setUp(self):
        self.payload = json.loads(EXAMPLE.read_text())

    def test_analytical_selection_and_wire(self):
        p = self.payload
        validate_evaluation("request", "size", p)
        r = evaluate_request("size", p)
        validate_evaluation("response", "size", r)
        self.assertTrue(r["comparison_complete"])
        self.assertEqual(r["selected_candidate_id"], "combined")
        self.assertEqual([x["status"] for x in r["candidates"]],
                         ["infeasible", "infeasible", "solved", "solved"])
        self.assertAlmostEqual(r["total_cost_eur"], 8120, places=4)
        self.assertAlmostEqual(r["candidates"][3]["total_cost_eur"], 8200, places=4)
        self.assertAlmostEqual(r["allocated_capex_eur"], 120)
        self.assertTrue(all(c["feasible"] for c in r["cases"]))
        self.assertEqual(r["cases"][1]["weight"], 0)
        proc = subprocess.run([sys.executable, "-m", "gridpass_flexibility",
                               "--size", str(EXAMPLE)], capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(proc.stdout), r)

    def test_zero_weight_long_case_changes_winner(self):
        self.payload["cases"].pop()
        r = evaluate_request("size", self.payload)
        self.assertEqual(r["selected_candidate_id"], "cooling-only")

    def test_no_feasible_package(self):
        self.payload["candidates"] = self.payload["candidates"][:2]
        r = evaluate_request("size", self.payload)
        self.assertEqual(r["status"], "infeasible")
        self.assertTrue(r["comparison_complete"])
        self.assertIsNone(r["selected_candidate_id"])
        validate_evaluation("response", "size", r)

    def test_hybrid_outage_shared_battery(self):
        p = self.payload
        p["candidates"] = [p["candidates"][2]]
        p["options"] = [{"id":"b","kind":"battery","max_power_mw":4,"max_energy_mwh":8,
                         "cost_eur_per_mw":100,"cost_eur_per_mwh":100,
                         "charge_efficiency":1,"discharge_efficiency":1}]
        # Cooling cannot be unavailable for the full horizon: isolate its
        # flexibility by keeping it available and losing only workload.
        p["cases"][1]["new_resource_availability"] = {"work":0}
        r = evaluate_request("size", p)
        self.assertEqual(r["status"], "solved")
        self.assertAlmostEqual(r["capacities"]["b"]["power_mw"], 1, places=5)
        self.assertAlmostEqual(r["capacities"]["b"]["energy_mwh"], 2, places=5)
        self.assertAlmostEqual(r["allocated_capex_eur"], 420, places=4)

    def test_incomplete_replay_never_recommends(self):
        from gridpass_flexibility import planning
        real = planning.evaluate
        def fail_last(scenario, **kwargs):
            if any(r["id"] == "work" and r["power_mw"] == 2 for r in scenario["resources"]):
                return {"status":"solver_failed", "evidence":{"engine_version":"test"}}
            return real(scenario, **kwargs)
        with patch.object(planning, "evaluate", side_effect=fail_last):
            r = evaluate_request("size", self.payload)
        self.assertEqual(r["status"], "solver_failed")
        self.assertFalse(r["comparison_complete"])
        self.assertIsNone(r["selected_candidate_id"])
        self.assertNotIn("capacities", r)
        validate_evaluation("response", "size", r)

    def test_shared_deadline_exhausted(self):
        with patch("gridpass_flexibility.planning.monotonic", side_effect=[0]+[100]*20):
            r = evaluate_request("size", self.payload)
        self.assertEqual(r["status"], "solver_failed")
        self.assertIsNone(r["selected_candidate_id"])
        self.assertTrue(all(c["status"]=="solver_failed" for c in r["candidates"]))

    def test_budget_counts_packages(self):
        p = copy.deepcopy(self.payload)
        p["cases"] = [p["cases"][0]]
        p["cases"][0]["scenario"]["baseline_mw"] = [10]*10000
        p["candidates"] *= 4
        with self.assertRaisesRegex(ValueError, "resource-interval"):
            check_budget("size", p)
        check_budget("size", self.payload)

    def test_invalid_overrides_and_ids(self):
        p = self.payload
        p["cases"][0]["new_resource_availability"] = {"typo":0}
        with self.assertRaisesRegex(ValueError, "Unknown"):
            evaluate_request("size", p)
        del p["cases"][0]["new_resource_availability"]
        p["candidates"][1]["id"] = p["candidates"][0]["id"]
        with self.assertRaisesRegex(ValueError, "unique"):
            evaluate_request("size", p)

    def test_legacy_empty_options_rejected(self):
        with self.assertRaises(ValueError):
            size_capacity(self.payload["cases"], [])
