"""Versioned structural contracts for the canonical evaluation JSON interface.

Schema checks do not replace the engine's physical, cross-field and budget checks.
They are opt-in so existing clients and dependency-free screening remain compatible.
"""
from importlib.resources import files
import json


def evaluation_schema(direction: str) -> dict:
    if direction not in ('request', 'response'):
        raise ValueError('Expected request or response schema')
    return json.loads(files('gridpass_flexibility').joinpath(
        'schemas', f'evaluation-{direction}-v1.json').read_text(encoding='utf-8'))


def validate_evaluation(direction: str, operation: str, value: dict) -> None:
    """Check strict JSON and its operation-specific structural contract."""
    from jsonschema import Draft202012Validator
    key = 'payload' if direction == 'request' else 'result'
    envelope = {'operation': operation, key: value}
    # Reject NaN and infinity, which JSON Schema's number type alone accepts.
    envelope = json.loads(json.dumps(envelope, allow_nan=False))
    schema = evaluation_schema(direction)
    # Select the tagged branch for useful errors rather than a generic oneOf error.
    for branch in schema['oneOf']:
        if branch['properties']['operation']['const'] == operation:
            Draft202012Validator({**branch, '$defs': schema.get('$defs', {})}).validate(envelope)
            return
    raise ValueError('Unsupported evaluation operation')
