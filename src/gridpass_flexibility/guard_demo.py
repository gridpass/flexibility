"""Run a reproducible, simulator-only secure-grid-connection demonstration."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from .guard import Bounds, Contract, Guard, Meter, SimSite, canonical, seal_trace, sign_message, verify_trace

# Fixed synthetic fixture keys: deliberately public and NOT for production.
def demo_key(label: str) -> Ed25519PrivateKey:
    return Ed25519PrivateKey.from_private_bytes(hashlib.sha256(
        ("gridpass-public-demo-only:" + label).encode()).digest())


def run(fixture: dict) -> dict:
    c = fixture["contract"]
    contract = Contract(site=c["site"], limits=Bounds(**c["limits"]),
                        fallback=Bounds(**c["fallback"]),
                        fallback_target_w=c["fallback_target_w"],
                        max_message_age_s=c.get("max_message_age_s", 30),
                        max_meter_age_s=c.get("max_meter_age_s", 2))
    keys = {role: demo_key(role) for role in ("operator", "ems", "untrusted", "evidence")}
    guard = Guard(contract, keys["operator"].public_key(), keys["ems"].public_key())
    records = []

    def message(spec, role, t):
        if spec is None:
            return None
        return sign_message(keys[spec.get("signer", role)], site=spec.get("site", contract.site),
                            role=spec.get("role", role), seq=spec["seq"],
                            issued_s=spec.get("issued_s", t), expires_s=spec.get("expires_s", t + 10),
                            payload=spec["payload"])

    for step in fixture["steps"]:
        t = step["now_s"]
        if step.get("restart", False):
            guard = guard.restart()
        record = guard.tick(now=t, operator=message(step.get("operator"), "operator", t),
                            ems=message(step.get("ems"), "ems", t),
                            link_up=step.get("link_up", True), meter=Meter(**step["meter"]),
                            site=SimSite(**step["plant"]))
        record["case"] = step["case"]
        records.append(record)

    context = {"fixture_sha256": hashlib.sha256(canonical(fixture)).hexdigest(),
               "contract": asdict(contract), "scope": "synthetic_only",
               "evidence_key": "public_demo_key_not_a_trust_anchor"}
    trace = seal_trace(records, context, keys["evidence"])
    assert verify_trace(trace, context, keys["evidence"].public_key())
    return trace


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fixture", type=Path)
    args = parser.parse_args()
    print(json.dumps(run(json.loads(args.fixture.read_text())), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
