"""Offline reference for an authenticated site power constraint boundary.

No network, actuator drivers, physical protection or deployment approval.
All power values are integer W; positive import, negative export.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey, Ed25519PublicKey,
)

SCHEMA = "gridpass.guard.v0.1"
MAX_W = 1_000_000_000
GENESIS = "0" * 64


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")


def integer(value: object, low: int, high: int) -> bool:
    return type(value) is int and low <= value <= high


@dataclass(frozen=True)
class Bounds:
    min_w: int
    max_w: int

    def __post_init__(self):
        if not (integer(self.min_w, -MAX_W, 0) and integer(self.max_w, 0, MAX_W)):
            raise ValueError("invalid import/export bounds")

    def intersect(self, other: Bounds) -> Bounds:
        return Bounds(max(self.min_w, other.min_w), min(self.max_w, other.max_w))

    def clamp(self, value: int) -> int:
        return min(self.max_w, max(self.min_w, value))


@dataclass(frozen=True)
class Contract:
    site: str
    limits: Bounds
    fallback: Bounds
    fallback_target_w: int
    max_message_age_s: int = 30
    max_meter_age_s: int = 2

    def __post_init__(self):
        if not isinstance(self.site, str) or not self.site:
            raise ValueError("site required")
        if self.fallback.intersect(self.limits) != self.fallback:
            raise ValueError("fallback exceeds connection limits")
        if not integer(self.fallback_target_w, self.fallback.min_w, self.fallback.max_w):
            raise ValueError("fallback target outside fallback envelope")
        if not (integer(self.max_message_age_s, 1, 3600)
                and integer(self.max_meter_age_s, 0, 60)):
            raise ValueError("invalid freshness limits")


def sign_message(key: Ed25519PrivateKey, *, site: str, role: str,
                 seq: int, issued_s: int, expires_s: int, payload: dict) -> dict:
    body = dict(schema=SCHEMA, site=site, role=role, seq=seq,
                issued_s=issued_s, expires_s=expires_s, payload=payload)
    return {"body": body, "signature": key.sign(canonical(body)).hex()}


@dataclass(frozen=True)
class Meter:
    w: int | None
    sampled_s: int

    def valid(self, now: int, max_age: int) -> bool:
        return integer(self.w, -MAX_W, MAX_W) and integer(
            self.sampled_s, max(0, now - max_age), now)


@dataclass(frozen=True)
class SimSite:
    """Synthetic target-tracking device, not a battery dynamics model."""
    baseline_w: int
    reduction_w: int
    increase_w: int
    ack: bool = True
    meter_available: bool = True

    def __post_init__(self):
        if not (integer(self.baseline_w, -MAX_W, MAX_W)
                and integer(self.reduction_w, 0, MAX_W)
                and integer(self.increase_w, 0, MAX_W)):
            raise ValueError("invalid synthetic plant")
        if not (-MAX_W <= self.baseline_w - self.reduction_w
                <= self.baseline_w + self.increase_w <= MAX_W):
            raise ValueError("synthetic plant range exceeds model bounds")
        if type(self.ack) is not bool or type(self.meter_available) is not bool:
            raise ValueError("invalid synthetic plant status")

    def apply(self, target_w: int, now: int) -> tuple[int | None, Meter]:
        applied = min(self.baseline_w + self.increase_w,
                      max(self.baseline_w - self.reduction_w, target_w))
        actual = applied if self.ack else self.baseline_w
        return (applied if self.ack else None,
                Meter(actual if self.meter_available else None, now))


class Guard:
    """Pure simulator policy boundary. Keys are pre-provisioned trust anchors."""

    def __init__(self, contract: Contract, operator: Ed25519PublicKey,
                 ems: Ed25519PublicKey):
        if operator.public_bytes_raw() == ems.public_bytes_raw():
            raise ValueError("operator and EMS identities must differ")
        self.contract = contract
        self.keys = {"operator": operator, "ems": ems}
        self.last_seq = {"operator": -1, "ems": -1}
        self.last_now = -1
        self.dynamic: Bounds | None = None
        self.policy_expiry = -1

    def _accept(self, msg: dict | None, role: str, now: int) -> tuple[dict | None, str]:
        if msg is None:
            return None, "absent"
        if not isinstance(msg, dict) or set(msg) != {"body", "signature"}:
            return None, "malformed"
        body = msg["body"]
        if not isinstance(body, dict) or set(body) != {
            "schema", "site", "role", "seq", "issued_s", "expires_s", "payload"
        }:
            return None, "malformed"
        if (body["schema"], body["site"], body["role"]) != (
            SCHEMA, self.contract.site, role
        ):
            return None, "wrong_authority_or_audience"
        try:
            if not isinstance(msg["signature"], str) or len(msg["signature"]) != 128:
                return None, "invalid_signature"
            self.keys[role].verify(bytes.fromhex(msg["signature"]), canonical(body))
        except (InvalidSignature, ValueError, TypeError, OverflowError):
            return None, "invalid_signature"
        if not integer(body["seq"], 0, 2**63 - 1):
            return None, "invalid_sequence"
        if body["seq"] <= self.last_seq[role]:
            return None, "replay"
        if not (integer(body["issued_s"], max(0, now-self.contract.max_message_age_s), now)
                and integer(body["expires_s"], now + 1, 2**63 - 1)
                and body["expires_s"] - body["issued_s"] <= self.contract.max_message_age_s):
            return None, "stale_or_invalid_time"
        p = body["payload"]
        if not isinstance(p, dict):
            return None, "invalid_payload"
        if role == "operator":
            if set(p) != {"min_w", "max_w"}:
                return None, "invalid_payload"
            try:
                candidate = Bounds(**p)
            except (ValueError, TypeError):
                return None, "invalid_payload"
            if candidate.intersect(self.contract.limits) != candidate:
                return None, "outside_contract"
            self.dynamic = candidate
            self.policy_expiry = body["expires_s"]
        elif set(p) != {"target_w"} or not integer(p.get("target_w"), -MAX_W, MAX_W):
            return None, "invalid_payload"
        self.last_seq[role] = body["seq"]
        return p, "accepted"

    def restart(self) -> Guard:
        """Simulate restart with trusted checkpoint; NOT durable anti-rollback."""
        g = Guard(self.contract, self.keys["operator"], self.keys["ems"])
        g.last_seq = self.last_seq.copy()
        g.last_now = self.last_now
        g.dynamic = self.dynamic
        g.policy_expiry = self.policy_expiry
        return g

    def tick(self, *, now: int, operator: dict | None, ems: dict | None,
             link_up: bool, meter: Meter, site: SimSite) -> dict:
        if not integer(now, max(0, self.last_now + 1), 2**63 - 1):
            raise ValueError("non-monotonic simulation time")
        if type(link_up) is not bool:
            raise ValueError("link status must be boolean")
        self.last_now = now
        _, policy_status = self._accept(operator, "operator", now) if link_up else (
            None, "link_down")
        request, request_status = self._accept(ems, "ems", now) if link_up else (
            None, "link_down")
        current = self.contract.limits
        if self.dynamic is not None:
            current = current.intersect(self.dynamic)
        meter_ok = meter.valid(now, self.contract.max_meter_age_s)
        policy_ok = self.dynamic is not None and now < self.policy_expiry
        reasons = []
        if not link_up:
            reasons.append("link_down")
        if not policy_ok:
            reasons.append("no_current_policy")
        if not meter_ok:
            reasons.append("meter_invalid_or_stale")
        if request is None:
            reasons.append("no_authorized_request")
        degraded = bool(reasons)
        # Never relax the last known restriction merely because its validity elapsed.
        effective = current.intersect(self.contract.fallback) if degraded else current
        requested = request["target_w"] if request is not None else None
        target = effective.clamp(self.contract.fallback_target_w if degraded else requested)
        applied, observed = site.apply(target, now)
        if applied is None:
            reasons.append("actuator_unacknowledged")
        elif applied != target:
            reasons.append("insufficient_controllable_capacity")
        observed_ok = observed.valid(now, self.contract.max_meter_age_s)
        excursion = (observed.w != effective.clamp(observed.w)) if observed_ok else None
        if not observed_ok:
            reasons.append("no_valid_post_command_measurement")
        if excursion:
            reasons.append("observed_limit_excursion")
        state = ("unverified" if not meter_ok or not observed_ok or applied is None
                 or applied != target or excursion else "fallback" if degraded else "normal")
        return dict(schema=SCHEMA, site=self.contract.site, now_s=now,
                    policy_status=policy_status, request_status=request_status,
                    effective_bounds=asdict(effective), requested_w=requested,
                    allowed_w=target, acknowledged_w=applied,
                    pre_meter_w=meter.w if meter_ok else None,
                    observed_w=observed.w if observed_ok else None,
                    observed_excursion=excursion, state=state, reasons=reasons,
                    policy_seq=self.last_seq["operator"], ems_seq=self.last_seq["ems"])


def seal_trace(records: list[dict], context: dict, key: Ed25519PrivateKey) -> dict:
    """Sign an exact, complete synthetic trace; verifier must trust key and context."""
    head = GENESIS
    for record in records:
        head = hashlib.sha256(bytes.fromhex(head) + canonical(record)).hexdigest()
    checkpoint = dict(schema=SCHEMA, head=head, count=len(records), context=context)
    return dict(records=records, checkpoint=checkpoint,
                signature=key.sign(canonical(checkpoint)).hex())


def verify_trace(trace: dict, context: dict, key: Ed25519PublicKey) -> bool:
    try:
        if set(trace) != {"records", "checkpoint", "signature"}:
            return False
        records, cp = trace["records"], trace["checkpoint"]
        if not isinstance(records, list) or not records:
            return False
        head = GENESIS
        for record in records:
            head = hashlib.sha256(bytes.fromhex(head) + canonical(record)).hexdigest()
        if cp != dict(schema=SCHEMA, head=head, count=len(records), context=context):
            return False
        key.verify(bytes.fromhex(trace["signature"]), canonical(cp))
        return True
    except (InvalidSignature, ValueError, TypeError, KeyError, OverflowError):
        return False
