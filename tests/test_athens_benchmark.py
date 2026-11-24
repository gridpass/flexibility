import importlib.util
from datetime import datetime, timedelta
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('athens', Path(__file__).resolve().parents[1]/'scripts/benchmark_athens.py')
a = importlib.util.module_from_spec(spec)
spec.loader.exec_module(a)


class AthensBenchmarkTest(unittest.TestCase):
    def fixture(self):
        start = datetime(2022,8,5)
        rows = [a.FIELDS]
        for i in range(9):
            active = i%2 == 1
            rows.append((start+timedelta(minutes=i),'COOL','BSPC' if active else 'OFF',
                         'BTES' if active else 'OFF',12,6,20,28,1 if active else 0,
                         1 if active else 0,2 if active else 0))
        return rows

    def test_energy_and_holdout(self):
        cycles = a.read_cycles(iter(self.fixture()), minutes=8)
        self.assertEqual(len(cycles),4)
        self.assertAlmostEqual(cycles[0]['cold_kwh'],6*1.163/60)
        self.assertAlmostEqual(cycles[0]['electric_kwh'],2/60)
        m = a.metrics(cycles)
        self.assertAlmostEqual(m['fit_cop'],3*1.163)
        self.assertAlmostEqual(m['holdout_mae_kwh_per_cycle'],0)
        self.assertFalse(m['mapping_verified'])

    def test_gap_and_invalid_data_rejected(self):
        rows = self.fixture()
        del rows[2]
        with self.assertRaises(ValueError): a.read_cycles(iter(rows), minutes=8)
        rows = self.fixture()
        rows[2] = (*rows[2][:-1],float('nan'))
        with self.assertRaises(ValueError): a.read_cycles(iter(rows), minutes=8)

    def test_holdout_does_not_change_fit(self):
        cycles = a.read_cycles(iter(self.fixture()), minutes=8)
        m = a.metrics(cycles)
        cycles[-1]['cold_kwh'] *= 2
        changed = a.metrics(cycles)
        self.assertEqual(m['fit_cop'],changed['fit_cop'])
        self.assertGreater(changed['holdout_mae_kwh_per_cycle'],0)
