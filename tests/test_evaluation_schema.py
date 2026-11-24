import json
from pathlib import Path
import subprocess
import sys
import unittest

from jsonschema import Draft202012Validator, ValidationError
from gridpass_flexibility.interface import OPERATIONS, evaluate_request
from gridpass_flexibility.interface_schema import evaluation_schema, validate_evaluation
from gridpass_flexibility.profiles import profile_schema
from gridpass_flexibility.screening import SCHEMA

EXAMPLES = Path(__file__).resolve().parents[1] / 'examples'
CASES = dict(zip(OPERATIONS, ['data-centre.json', 'chronological.json',
    'design-comparison.json', 'profile-check.json', 'capacity-sizing.json',
    'annual-stress.json', 'causal-replay.json', 'lifecycle-economics.json']))


def example(operation):
    return json.loads((EXAMPLES / CASES[operation]).read_text())


class EvaluationSchemaTests(unittest.TestCase):
    def test_contracts_and_existing_schemas(self):
        for direction in ('request', 'response'):
            schema = evaluation_schema(direction)
            Draft202012Validator.check_schema(schema)
            self.assertEqual({b['properties']['operation']['const'] for b in schema['oneOf']}, set(OPERATIONS))
            self.assertEqual(schema, json.loads(subprocess.check_output([sys.executable, '-m',
                'gridpass_flexibility', '--evaluation-schema', direction])))
        request = evaluation_schema('request')
        self.assertEqual(request['oneOf'][0]['properties']['payload'], SCHEMA)
        self.assertEqual(request['$defs']['profile'], {k:v for k,v in profile_schema().items() if k not in ('$schema','$id')})

    def test_all_operations_and_cli_result(self):
        for op in OPERATIONS:
            with self.subTest(operation=op):
                payload = example(op)
                validate_evaluation('request', op, payload)
                result = evaluate_request(op, payload)
                validate_evaluation('response', op, result)
                args = [] if op == 'screen' else ['--' + op.replace('_','-')]
                proc = subprocess.run([sys.executable,'-m','gridpass_flexibility', *args,
                    str(EXAMPLES / CASES[op])], capture_output=True, text=True, check=True)
                self.assertEqual(json.loads(proc.stdout), json.loads(json.dumps(result,allow_nan=False)))

    def test_reject_unknown_and_wrong_nested_fields(self):
        for op in OPERATIONS:
            with self.subTest(operation=op):
                bad = example(op)
                bad['typo'] = 1
                with self.assertRaises(ValidationError):
                    validate_evaluation('request', op, bad)
        for key, value in [('energy_mwh', '12'), ('charge_efficiency', 1.1), ('discrete', 1), ('typo', 1)]:
            with self.subTest(field=key):
                bad = example('dispatch')
                bad['resources'][0][key] = value
                with self.assertRaises(ValidationError):
                    validate_evaluation('request','dispatch',bad)
        bad = example('dispatch'); del bad['resources'][0]['energy_mwh']
        with self.assertRaises(ValidationError): validate_evaluation('request','dispatch',bad)
        bad = example('dispatch'); bad['events'][0]['start'] = True
        with self.assertRaises(ValidationError): validate_evaluation('request','dispatch',bad)
        bad = example('economics'); bad['alternatives'][0]['tariff']['monthly_peak_eur_mw'] = [0]*11
        with self.assertRaises(ValidationError): validate_evaluation('request','economics',bad)
        bad = example('dispatch'); bad['baseline_mw'][0] = float('nan')
        with self.assertRaises(ValueError): validate_evaluation('request','dispatch',bad)
        with self.assertRaises(ValueError): validate_evaluation('request','unknown',{})

    def test_response_failure_and_corrupted_result(self):
        validate_evaluation('response','screen',evaluate_request('screen',{}))
        valid = evaluate_request('dispatch',example('dispatch'))
        for key, value in [('feasible','true'),('schedule',{}),('evidence',{'engine_version':'0.3.9','result_sha256':'bad'})]:
            bad = {**valid,key:value}
            with self.assertRaises(ValidationError): validate_evaluation('response','dispatch',bad)
        validate_evaluation('response','dispatch',{'status':'solver_failed','solver_status':2,'message':'infeasible','evidence':{'engine_version':'0.3.9'}})
        validate_evaluation('response','size',{'status':'infeasible','message':'infeasible','evidence':{'engine_version':'0.3.9'}})
        with self.assertRaises(ValidationError): validate_evaluation('response','dispatch',{'status':'solved','feasible':True})

    def test_cross_field_validation_is_separate(self):
        bad = example('dispatch')
        bad['price_eur_mwh'] = [1]
        validate_evaluation('request','dispatch',bad)
        with self.assertRaisesRegex(ValueError,'expected 12 intervals'):
            evaluate_request('dispatch',bad)
