import unittest
from unittest.mock import patch
import numpy as np
from scipy.optimize import OptimizeResult
from scipy.sparse import csc_matrix
from gridpass_flexibility.validation import checked_solution, solution_residuals
from gridpass_flexibility.dispatch import evaluate
from gridpass_flexibility.planning import size_capacity

class NumericalValidation(unittest.TestCase):
    def test_each_constraint_and_nonfinite(self):
        args = ([(0, 3), (0, 1)], csc_matrix([[1, 0]]), np.array([2]),
                csc_matrix([[1, 1]]), np.array([2.5]), [0, 1])
        for x, key in [([1.9, 0], "equality"), ([2, 1], "inequality"),
                       ([2, -0.1], "bounds"), ([2, .2], "integrality")]:
            with self.subTest(key=key):
                self.assertGreater(solution_residuals(x, *args)[key], 1e-5)
                sol = checked_solution(OptimizeResult(success=True, x=x, fun=0), *args)
                self.assertFalse(sol.success)
                self.assertEqual(sol.status, 4)
        for x in ([2, float("nan")], [2], [2, float("inf")]):
            self.assertIsNone(solution_residuals(x, *args))
        good = OptimizeResult(success=True, x=[2, 0], fun=0)
        self.assertIs(checked_solution(good, *args), good)
        self.assertFalse(checked_solution(OptimizeResult(success=True,x=[2,0],fun=float("nan")), *args).success)

    def test_dispatch_rejects_false_solver_success(self):
        scenario={"interval_hours":1,"baseline_mw":[10],"normal_import_cap_mw":12,
                  "price_eur_mwh":1,"resources":[]}
        with patch("scipy.optimize.linprog", return_value=OptimizeResult(success=True,x=[0,0],fun=0)):
            result=evaluate(scenario)
        self.assertEqual(result["status"], "solver_failed")
        self.assertEqual(result["solver_status"], 4)
        self.assertNotIn("schedule", result)

    def test_capacity_rejects_false_solver_success(self):
        from scipy.optimize import linprog
        scenario={"interval_hours":1,"baseline_mw":[10],"normal_import_cap_mw":9,
                  "price_eur_mwh":1,"resources":[]}
        option={"id":"g","kind":"generator","max_power_mw":2,"cost_eur_per_mw":10}
        def corrupt(*a, **kw):
            result=linprog(*a, **kw)
            self.assertTrue(result.success)
            result.x[:]=0
            return result
        with patch("scipy.optimize.linprog", side_effect=corrupt):
            result=size_capacity([{"id":"one","scenario":scenario}],[option])
        self.assertEqual(result["status"], "solver_failed")
        self.assertNotIn("capacities", result)

    def test_second_resolution_ramp_and_notice(self):
        scenario={"interval_hours":1/3600,"baseline_mw":[2]*6,"normal_import_cap_mw":2,
                  "price_eur_mwh":1,"resources":[{"id":"g","kind":"generator",
                  "power_mw":1,"ramp_mw_per_hour":1800,"response_minutes":2/60,
                  "variable_cost_eur_mwh":10}],
                  "events":[{"start":1,"end":5,"notice_minutes":0,"cap_mw":1}]}
        r=evaluate(scenario)
        self.assertEqual(r["status"],"solved")
        self.assertFalse(r["feasible"])
        self.assertAlmostEqual(r["uncovered_mwh"],2.5/3600,places=8)
        for actual, expected in zip(r["schedule"]["uncovered_mw"][1:5],[1,1,.5,0]):
            self.assertAlmostEqual(actual,expected,places=5)
