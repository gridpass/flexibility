"""Shared, read-only evaluation interface for CLI and MCP.

The solver never controls live equipment, submits an enquiry, or receives
personal data as a required input. Hosted integrations should authenticate
users, enforce their own request budgets, and isolate solver processes.
"""
from __future__ import annotations

from .screening import assess

OPERATIONS = ("screen", "dispatch", "compare_designs", "profile", "size", "stress", "causal")

def evaluate_request(operation: str, payload: dict) -> dict:
    """Execute one operation on a JSON-compatible payload."""
    if not isinstance(payload, dict):
        raise ValueError("payload must be an object")
    if operation == "screen":
        return assess(payload)
    if operation == "dispatch":
        from .dispatch import evaluate
        return evaluate(payload)
    if operation == "compare_designs":
        from .dispatch import compare_designs
        return compare_designs(payload["scenario"], payload["designs"])
    if operation == "profile":
        from .profiles import evaluate_profile
        return evaluate_profile(payload["profile"], payload["scenarios"])
    if operation == "size":
        from .planning import size_capacity
        return size_capacity(payload["cases"], payload["options"], payload.get("time_limit_s", 60))
    if operation == "stress":
        from .stress import test_commitment
        return test_commitment(payload["site"], payload["profile"], payload.get("outage_ids", []))
    if operation == "causal":
        from .causal import replay
        return replay(payload["scenario"], payload.get("lookahead_intervals",24), payload.get("time_limit_s",60))
    raise ValueError(f"Unsupported evaluation operation: {operation}")
