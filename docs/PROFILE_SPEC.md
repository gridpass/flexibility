# Independent commitment profile, version 1

The GridPass profile is an open, technology-neutral **test contract** for a large load. The three main dimensions correspond to the public Flex MOSAIC description: advance warning, duration of each call, and annual use. GridPass additionally specifies the requested reduction, optional recovery interval and optional evaluation resolution. The schema and acceptance rules below are original GridPass definitions; they do not assign EPRI classes.

## Normative references for GridPass v1

- [JSON Schema](../src/gridpass_flexibility/schemas/profile-v1.json), Draft 2020-12, ID `urn:gridpass:flexibility:profile:v1`. The installed CLI exports it with `gridpass-flexibility --profile-schema`.
- This document defines cross-field and evidence semantics.
- [Conformance tests](../tests/test_profiles_v1.py) define reproducible positive and negative cases.

Conceptual references, checked 2026-11-24: [EPRI DCFlex deliverables](https://dcflex.epri.com/deliverables) (framework paper dated 2026-10-12); [NVIDIA DSX Flex architecture](https://docs.nvidia.com/dsx/flex/architecture) (table adapted from EPRI v1.0, accessed 2026-11-13). The numerical examples are not normative EPRI class definitions. No third-party source code or restricted materials are required.

## Profile fields

| Field | Units / meaning |
|---|---|
| schema_version | `gridpass-profile-v1`; omission is accepted for earlier v0.2/v0.3 profiles |
| id, version | Nonempty identifiers for the particular contract revision |
| reduction_mw | Positive requested import reduction relative to min(baseline demand, normal import cap) |
| notice_minutes | Contract's minimum advance notification. Tests use this much or less warning |
| activation_hours | Longest activation to demonstrate |
| annual_event_hours | Annual activation budget to demonstrate, not less than one activation |
| minimum_recovery_hours | Optional minimum interval guaranteed between calls; tests must include adjacent qualifying calls with this much or less recovery when the budget exceeds one activation |
| maximum_interval_minutes | Optional upper bound on model interval length; does not establish measured response latency |

All numeric fields must be finite. Unknown fields and unsupported schema versions are rejected. The baseline and normal cap must be explicit in each scenario; the contract does not infer a baseline from site telemetry. Event intervals are half-open.

## Coverage and decisions

A qualifying call must request the required reduction during its full duration and use no more than the specified notice. Annual hours count qualifying calls only.

A complete annual case must span 8,760 hours and satisfy all of the following jointly:

1. At least one qualifying activation meets or exceeds the specified duration.
2. Qualifying event hours meet or exceed the annual budget.
3. If a recovery interval is declared and more than one activation is needed, two qualifying calls have a gap no longer than the declared interval.
4. Interval length meets the declared resolution limit, if any.

Every supplied case must also satisfy the modeled import cap. A violation in a normal or recovery interval is a violation of the site schedule, even if the event interval itself passes. A shorter case can provide useful additional evidence but cannot fill a gap in annual coverage.

The result is one of `modeled_cases_pass`, `modeled_cases_fail`, `incomplete_coverage` or `evaluation_error`. Errors do not establish infeasibility. Incomplete tests do not establish capability. The result includes per-case coverage, interval length, shortest tested recovery gap, solver evidence, and SHA-256 digests of the normalized profile, scenario suite and complete result (excluding the result digest itself).

## Boundaries

The stress generator creates distributed and clustered annual schedules with optional explicit resource outages. It rejects unaligned activation/recovery durations and excessive utilization. The modeled schedules have perfect foresight and simplified equipment behavior. A 15-minute interval does not demonstrate a five-minute transient response. A full-year modeled pass does not prove all admissible event sequences, real-time controllability, field compliance, operator acceptance or EPRI certification.

## Reproduce

```sh
pip install ".[agent]"
gridpass-flexibility --profile-schema
gridpass-flexibility --stress examples/annual-stress.json
python -m unittest discover -s tests -p test_profiles_v1.py -v
```
