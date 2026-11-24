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

## Implementation checkpoint (2026-11-24, v0.2.0)

The chronological evaluator now uses SciPy/HiGHS with explicit interval balance, storage SOC, generation ramp and fuel budget, deferred work recovery and deadlines, event notice, target MW, cap violations, operating cost, and input/output hashes. A candidate-design comparison ranks feasible additions and reports observed constraint saturation. Independent profiles report incomplete coverage rather than automatically awarding classes. The following gaps remain: robust and stochastic operation, continuous expansion, binary unit commitment, calibrated thermal and workload models, normative classification and field verification, public MCP integration. See [chronological evaluator](CHRONOLOGICAL.md).

## Implementation checkpoint (2026-11-24, v0.3.0)

Continuous battery MW/MWh and generator MW sizing now shares a single design across a finite set of hard-cap scenarios. The chosen capacities are independently replayed through the chronological engine. The commitment test suite generates distributed and clustered annual events and optional resource outages. The official MCP SDK exposes the same six operations as the CLI through a single read-only tool. See [acceptance criteria](ACCEPTANCE.md) for the remaining work. The advanced solver is not yet integrated into the existing public GridPass website/MCP.

## Implementation checkpoint (2026-11-24, v0.3.1)

Independent profile schema v1 is packaged and validated. Annual, duration, notice, recovery and optional resolution requirements must be covered in one full-year case. Result hashes bind the normalized profile and scenario suite. Full-year 15-minute synthetic conformance and negative tests pass. Public comparison sources were checked on 2026-11-24: EPRI deliverables (2026-10-12 paper) and NVIDIA DSX Flex Architecture (adaptation of v1.0 accessed 2026-11-13). These are conceptual references, not normative GridPass dependencies or evidence of official EPRI conformance. See [independent profile specification](PROFILE_SPEC.md).

## Implementation checkpoint (2026-11-24, v0.3.3)

A sampled causal policy now re-plans against observed conditions and announced events; unobserved future demand, availability, price and ordinary cap are persistence forecasts. The same LP/MILP physical model carries battery SOC, generator fuel and dwell time, and deferred workload deadlines. Tests distinguish perfect-foresight feasibility from surprise-event performance and reproduce forced-trip/restart constraints. The causal operation is available locally via CLI and the single MCP tool, with bounded solver time and explicit partial failure. See [CAUSAL.md](CAUSAL.md). This is modeled evidence, not equipment or grid acceptance.

## Implementation checkpoint (v0.3.4)

The physical resource model now includes exact sampled single-zone sensible heat balance, renewable generation and curtailment, and aggregate protected-load accounting. The same constraints are used by causal replay and chronological dispatch. See [thermal specification](THERMAL.md) for equations, source dataset candidates, and explicit calibration limits. No measured dataset was fitted or republished in this revision.

## v0.3.5 lifecycle economics

The shared chronological engine now supports an annual peak charge alongside explicit energy/fuel/carbon costs, with transparent component reconciliation. The financial layer compares feasible alternatives using a common real-EUR horizon and explicit connection delays. See [ECONOMICS.md](ECONOMICS.md) and [ACCEPTANCE.md](ACCEPTANCE.md). No site economics or measured validation inferred.
