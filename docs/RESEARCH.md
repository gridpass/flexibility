# Research scope: large-load flexibility

## Why EPRI developed DCFlex

The Electric Power Research Institute is a nonprofit, collaborative energy R&D institution founded in 1972. It brings utilities, customers, technology vendors and researchers together to solve common problems. DCFlex addresses the tension between growth in large loads and constrained grid infrastructure: establish comparable flexibility requirements, test feasible response and reduce bespoke interconnection work.

EPRI generally funds collaborative research through annual membership and supplemental projects. Research funding does not automatically confer redistribution rights. A September 2025 DCFlex prospectus describes a three-year programme running from late 2024 through 2027 and lists contribution tiers for different participant types. Do not treat those historical tiers as a current quote or a price for the evaluation tool.

## Distinguish three layers

1. Framework: Flex MOSAIC is a technology-neutral classification of large-load flexibility based on notice, activation duration and annual utilisation.
2. Evaluation software: EPRI describes an evaluation tool that coordinates workloads, generation, storage and cooling; produces schedules; identifies constraints and useful resource additions; compares economics; and assesses modelled class capability.
3. Acceptance: actual utility connection terms, commissioning, protection, telemetry, and field evidence. A model result does not grant an interconnection.

The public October 12, 2026 framework paper is the target reference. Earlier presentations and summaries describe evolving class definitions. Do not freeze historical A–E thresholds or claim official classification until the current authoritative definitions and applicable terms are checked. The public product page describes features, not a grant of source-code or redistribution rights.

## Capability matrix

| Capability | Initial GridPass release | Next step |
|---|---|---|
| Notification, duration, utilisation | Implemented, scenario-level | Versioned operator event profiles, exact timing |
| Baseline and import cap | Constant power | Meter time series and interval-dependent caps |
| Resource inventory | Flexible load, generation, storage | Cooling/thermal models, renewable availability, workload types |
| Feasible operating schedule | Constant repeated-event allocation | Chronological LP/MILP, energy balance and recovery |
| Battery | Power, usable discharge energy, recharge, efficiency | SOC trajectory, degradation, reserve and availability |
| Generation | Available MW, notice, duration, variable cost | Ramp rates, start/stop, minimum run, fuel and emissions |
| Workloads | Approved load reduction, notice/duration, cost | Deadlines, workload backlog, rebound, SLAs, opt-in |
| Economics | Variable dispatch cost | Capital sizing, fixed O&M, tariff and time-to-power comparisons |
| Resource expansion | Not implemented | Least-cost capacity increments and bottleneck diagnostics |
| Classification | No class claim | Versioned test vectors against authoritative published definitions; independent validation |
| Reliability | Deterministic assumptions | Uncertainty, outages, correlated events, reserve and worst-case coverage |
| Interconnection evidence | Screening JSON | Reproducible reports, provenance, operator-specific evidence and acceptance criteria |
| Network headroom | Not implemented | Import operator-provided constraints; network-side studies with appropriate data |
| Agent interface | Hosted MCP uses same screening algorithm | Package integration and contract tests; no live site control |

## Reuse, not reinvention

The initial zero-dependency screening model is a small transparent baseline. For chronological resource scheduling and expansion, evaluate PyPSA (MIT), Linopy and HiGHS; PyPSA already supports storage, dispatch, unit commitment and capacity expansion. Start with a single site bus and time-varying import cap; add explicit load-shift obligations and resource constraints. Benchmark against analytical cases, synthetic schedules, independently licensed measured datasets and operator acceptance scenarios. Use a versioned schema and reproducible solver settings.

The repository must not contain EPRI member-only materials, private correspondence, customer datasets or copied proprietary implementations. Obtain written permission before reusing third-party code or restricted test specifications. Reference EPRI's marks descriptively only.

## Public primary references

- EPRI institutional background: https://europe.epri.com/about
- DCFlex project, workstreams and contacts: https://dcflex.epri.com/about-us
- Flex MOSAIC framework and evaluation tool: https://dcflex.epri.com/flex-mosaic
- DCFlex deliverables, including October 12, 2026 framework paper: https://dcflex.epri.com/deliverables
- EPRI product reference 3002036874: https://www.epri.com/research/products/000000003002036874
- EPRI funding model: https://distribution.epri.com/resources/quickref/
- DCFlex project prospectus, September 2025: https://restservice.epri.com/publicdownload/000000003002031004/0/Product
- PyPSA documentation and licence: https://github.com/PyPSA/PyPSA

Open verification questions: current evaluator access/price/licence, complete official class test protocol, validation programme requirements, and operator acceptance criteria. Seek clarification from DCFlex's technical team before claiming conformance. This document is a research baseline, not an exhaustive review of member-only information.
