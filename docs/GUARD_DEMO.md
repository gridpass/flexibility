# GridPass Guard reference demo

This is a simulator-only reference, not a production controller, approved fallback,
or grid certification. Positive integer watts are import; negative are export.
The plant is a synthetic target-tracking device with an available reduction/increase
range. It has no battery energy, ramp, latency, protection or thermal dynamics.

## Reuse decision

An internal controller inventory found existing Python envelope, measurement,
command, simulation/Modbus adapter, EMS supervision and Ed25519 evidence interfaces.
The new public reference uses the same conceptual boundaries and the same mature
cryptography library; it adds independent authorization and policy checks without
copying internal code or introducing a Rust production runtime. Keep the optimizer
separate. An adapter to the existing controller is a future integration task.
No live network or site I/O is included here.

## Run

```sh
python -m pip install '.[guard]'
python -m gridpass_flexibility.guard_demo examples/guard-site.json > trace.json
python -m unittest discover -s tests -p test_guard.py -v
```

The fixture covers signed operator limits, separately signed EMS requests, clipping
import/export requests, wrong-role signatures, wrong audience, invalid policy
bounds, replay after a simulated restart, expired commands and policy, lost link,
stale/missing meter samples, insufficient controllable capacity and actuator failure.
Compare requested, allowed, acknowledged and observed power independently.
A measured excursion is reported even when the actuator accepted a target.

The demo keys are deterministic, public, and unsuitable for any deployment.
Messages bind schema, audience, role, sequence, validity window and payload.
The simulator assumes pre-provisioned distinct trusted public keys, valid local
monotonic time and one fresh request per tick. Restart copies a trusted in-memory
checkpoint, not durable anti-rollback storage. On lost authority or invalid
measurement it requests the configured fallback within the last known restriction.
No claim is made that the fallback is appropriate for a real site.

The exact trace, fixture digest, contract and record count are bound to an
Ed25519-signed hash-chain checkpoint. Verification needs an independently trusted
key and expected context; the demo key offers reproducibility, not authenticity
against a real adversary. It does not prove completeness across multiple runs or
truth of a meter. An unverified state is not a compliance pass.

## Remaining release gates

Durable protected replay state and trusted clock; real operator-approved policy
and fallback; authenticated transport and key rotation; actuator/meter identity,
measurement timing and independent verification; real battery constraints and
response timing; dependency audit and GEISA mapping. Any real hardware operation
requires a separate site-specific commissioning and protection plan.
