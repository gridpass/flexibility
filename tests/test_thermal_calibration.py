import importlib.util
import math
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("calibrate_thermal", Path(__file__).resolve().parents[1]/"scripts/calibrate_thermal.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class ThermalCalibrationTest(unittest.TestCase):
    def fixture(self, conductance=.35):
        # Independent closed form, 15-minute samples, known physical units.
        t, c, dt = 22., 1.7, .25
        rows = []
        for i in range(49):
            a, q, p = 28+3*math.sin(i*.4), 2+.4*math.cos(i*.7), 1.4+.9*(i%3)
            rows.append([i*900, t, a, q, p])
            if conductance:
                equilibrium = a+(q-p)/conductance
                t = equilibrium+(t-equilibrium)*math.exp(-conductance*dt/c)
            else:
                t += (q-p)*dt/c
        return rows

    def test_known_parameters_and_zero_conductance(self):
        for u in (.35, 0.):
            fit = m.calibrate(self.fixture(u), split=24, max_holdout_error_c=.01)
            self.assertAlmostEqual(fit["thermal_capacitance_mwh_per_k"], 1.7)
            self.assertAlmostEqual(fit["thermal_conductance_mw_per_k"], u)
            self.assertTrue(fit["holdout_pass"])
            self.assertFalse(fit["field_validated"])

    def test_holdout_cannot_change_fit_or_hide_drift(self):
        rows = self.fixture()
        initial = m.calibrate(rows, split=24, max_holdout_error_c=.1)
        for i in range(25, 49):
            rows[i][1] += (i-24)*.1
        altered = m.calibrate(rows, split=24, max_holdout_error_c=.1)
        self.assertEqual(initial["thermal_capacitance_mwh_per_k"], altered["thermal_capacitance_mwh_per_k"])
        self.assertFalse(altered["holdout_pass"])

    def test_reject_rank_deficient_and_gaps(self):
        rows = self.fixture()
        for row in rows:
            row[4] = row[3]
        with self.assertRaisesRegex(ValueError, "excitation"):
            m.calibrate(rows, split=24, max_holdout_error_c=.1)
        rows = self.fixture()
        del rows[10]
        with self.assertRaisesRegex(ValueError, "uniformly"):
            m.calibrate(rows, split=24, max_holdout_error_c=.1)

    def test_reject_nonfinite_and_nonphysical_fit(self):
        rows = self.fixture()
        rows[2][3] = float("nan")
        with self.assertRaises(ValueError):
            m.calibrate(rows, split=24, max_holdout_error_c=.1)
        rows = self.fixture()
        # Reverse heat input relative to temperature response.
        for row in rows:
            row[3], row[4] = row[4], row[3]
        with self.assertRaisesRegex(ValueError, "Nonphysical"):
            m.calibrate(rows, split=24, max_holdout_error_c=.1)
