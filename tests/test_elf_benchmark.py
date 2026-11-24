import importlib.util
import io
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('elf', Path(__file__).resolve().parents[1] / 'scripts/benchmark_elf.py')
elf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(elf)


class ElfBenchmarkTest(unittest.TestCase):
    def test_last_exceedance_and_censoring(self):
        old = [(t, 300, 200, 10) for t in range(0, 1100, 100)]
        new = [(t, 100, 101 if t not in (1100, 1400) else 110, 12)
               for t in range(1100, 2600, 100)]
        result = elf.downsteps(old + new)[0]
        self.assertEqual(result['observed_settling_ms'], 400)
        self.assertEqual(result['tail_iteration_ms'], 12)
        self.assertIsNone(elf.downsteps(old + new[:-1])[0]['observed_settling_ms'])

    def test_parser_rejects_bad_timing_and_nonfinite_power(self):
        header = ','.join(elf.FIELDS) + '\n'
        first = 'gpu,work,0,300,200,100,nan\n'
        for row in ('gpu,work,0,100,100,100,12\n',
                    'gpu,work,101,100,100,100,12\n',
                    'gpu,work,20,100,nan,100,12\n'):
            with self.subTest(row=row), self.assertRaises(ValueError):
                elf.read_runs(io.StringIO(header + first + row))
        self.assertEqual(len(elf.read_runs(io.StringIO(header + first))), 1)

    def test_observations_never_claim_field_validation(self):
        r = elf.evaluate({('gpu', 'work'): [(0, 300, 200, 10), (20, 100, 101, 12)]})
        self.assertEqual(r['censored_steps'], 1)
        self.assertFalse(r['facility_control_validated'])
        self.assertFalse(r['command_latency_measured'])
