import importlib.util
from pathlib import Path
import unittest
from gridpass_flexibility.interface import evaluate_request
from gridpass_flexibility.interface_schema import validate_evaluation

spec = importlib.util.spec_from_file_location('verify_hosted', Path(__file__).resolve().parents[1] / 'scripts/verify_hosted.py')
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


class ReleaseProbeTests(unittest.TestCase):
    def test_release_fixtures_and_independent_assertions(self):
        for name, (operation, payload) in probe.release_cases().items():
            with self.subTest(name=name):
                validate_evaluation('request', operation, payload)
                result = evaluate_request(operation, payload)
                validate_evaluation('response', operation, result)
                probe.assert_release_case(name, result)

    def test_corrupted_interyear_cost_is_rejected(self):
        operation, payload = probe.release_cases()['interyear']
        result = evaluate_request(operation, payload)
        result['cases'][0]['alternatives'][0]['operating_years'][1]['annual_operating_cost_eur'] += 1
        with self.assertRaisesRegex(RuntimeError, 'recharge cost'):
            probe.assert_release_case('interyear', result)

    def test_wrong_candidate_winner_is_rejected(self):
        operation, payload = probe.release_cases()['capacity_candidates']
        result = evaluate_request(operation, payload)
        result['selected_candidate_id'] = 'large-work'
        with self.assertRaisesRegex(RuntimeError, 'package acceptance'):
            probe.assert_release_case('capacity_candidates', result)
