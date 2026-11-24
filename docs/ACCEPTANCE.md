# Release acceptance criteria

Goal: an independently usable open-source large-load flexibility assessment workflow covering the publicly described functions of the EPRI Flex MOSAIC evaluator. Official equivalence and certification require authoritative criteria and independent validation.

## Verified in v0.3.0

- Installable Python package with optional optimization/agent dependencies.
- Static screening and chronological schedules use declared physical constraints and show uncovered energy.
- Continuous storage and generation sizing shares investments across scenario cases; a zero-weight case still enforces feasibility.
- Every selected design is replayed through the chronological evaluator.
- Versioned test profiles include a nonzero requested reduction and explicit annual event coverage; easy notice windows do not satisfy harder ones.
- Distributed and clustered annual cases and optional resource outages exercise the optimizer.
- Local MCP uses the official SDK and the same evaluation interface as CLI; real stdio initialize/list/call tests verify numeric parity and invalid-operation handling.
- No proprietary EPRI implementation, private deck or customer data is distributed.

## Verified in v0.3.1 (profile conformance)

- Public, versioned JSON Schema (Draft 2020-12) ships in the installed package; unknown fields, non-finite values and inconsistent annual budgets are rejected.
- One full-year case must jointly exercise target MW, notice, activation duration, annual use and the declared recovery and sampling constraints. Separate partial cases cannot combine into a false pass.
- Independent tests include a complete 35,040-interval (15-minute) synthetic year, recovery and resolution rejection, schema validation, and reproducible result hashes.
- EPRI's public October 12, 2026 description and NVIDIA's November 13, 2026 adaptation motivate the dimensions; no official class label or certification is asserted.
- v0.3.0 merge #6 retained the separate Guard reference demo and passed CI on Python 3.10 and 3.12. The public simplified calculator from private PR #79 was verified live on 2026-11-24.

## Verified in v0.3.2 (discrete equipment dispatch)

- Optional battery binary mode excludes simultaneous charge/discharge, including a regression case where the continuous relaxation can dissipate surplus generation artificially.
- Generator commitment enforces binary start/stop/online state, minimum output, interval-rounded minimum on/off time, initial dwell obligation, ramp, response and fuel limits. Startup and online costs are included in the reported cost.
- Independent exhaustive enumeration cross-checks the cost optimum for a five-interval commitment case. Half-hour notice/ramp and incompatible-outage regression tests pass.
- Continuous sizing rejects discrete assets/options; candidate design comparison retains the exact constraints. The local MCP rejects excessive binary-variable counts.
- 61 tests passed locally, including installed-package MCP roundtrip. Causal control, forced-trip/restart behavior, terminal dwell carryover and field validation remain open.

## Verified in v0.3.3 (causal sampled replay)

- One generic CLI/MCP `causal` operation uses observed demand, price, cap, availability and announced events, with persistence forecasts for unobserved future signals. It executes only the first action of each HiGHS plan.
- Prefix invariance tests change future demand, prices, caps, outages and unannounced events without changing preceding observations or actions. An initially empty 2 MW/4 MWh battery meets a notified restriction but misses the same surprise restriction by 4 MWh despite a feasible perfect-foresight schedule.
- Generator forced-trip, minimum downtime/restart, minimum-up carryover, remaining fuel, battery SOC and exact inverter mode are tested. Deferred workload energy carries its original FIFO deadlines; a failed recovery forecast returns a non-passing partial result rather than resetting backlog.
- Explicit terminal recovery checks, sampled-notice regression, bounded replay horizon and shared solver time budget, timeout error, and local MCP causal roundtrip are tested. All 75 tests passed locally.
- See [causal replay specification](CAUSAL.md). Calibrated thermal/workload models, fallback control after infeasible forecasts, sub-sample plant response, measured validation and hosted integration remain open.

## Verified in v0.3.4 (physical cooling and renewable resources)

- Single-zone sensible-heat state uses exact zero-order-hold discretization, temperature constraints, bounded cooling, variable COP, ambient and internal heat gain. An impossible thermal balance fails rather than relaxing temperature limits.
- Protected non-cooling loads and baseline cooling are excluded from aggregate workload deferral. Renewable capacity factors and curtailment are represented without grid export.
- Chronological and causal solvers use the same physical constraints. Observed temperature persists between replans; unknown future weather and renewable availability cannot affect preceding actions. Terminal thermal recovery is checked separately.
- Closed-form heat-balance, variable inputs, baseline/cost accounting, surprise event, thermal failure, recovery, protected-load and renewable-curtailment tests pass. Installed-package MCP numerical parity includes the new thermal example. 89 tests passed locally.
- [Thermal resource specification](THERMAL.md) records measured-data candidate licences and boundaries. No measured parameter fit or field-validation claim is made.

## Verified in v0.3.5 (lifecycle economics)

- Shared dispatch includes peak-import fee in the optimization objective; fuel efficiency, fuel cost, carbon and nonfuel costs use explicit factors. Independent component reconciliation checks reported annual costs.
- Complete operating-year comparisons use a common real-EUR discounted cashflow horizon with capex, fixed O&M, replacements, residual value, and explicit connection delays. Infeasible/non-operating alternatives are not ranked; incomplete solver comparisons cannot recommend a winner.
- Closed-form annual cost, fuel/emissions, NPV, time-to-power, reserve of feasible alternatives, peak-aware dispatch and reoptimized sensitivity tests exercise the shared CLI/MCP operation. See [economics specification](ECONOMICS.md).
- Monthly tariff schedules, seasonal commissioning, site-calibrated assumptions and causal/field validation remain outside this release.

## Verified in v0.3.6 (measured trace benchmark)

- Downloaded and checksum-verified CC BY 4.0 HEATWISE AAU archive, 16 runs and 11,520 observations. The reproducible offline benchmark uses separate 100% load runs as holdouts, reports errors against persistence, and independently checks the canonical dispatch model on normalized measured demand variation.
- The empirical predictor beats persistence in three of four configurations, but fails in the baseline configuration. It is not a calibrated physical thermal model or safe control policy. Source power/time units remain unconfirmed; dispatch uses explicitly hypothetical scales. No raw third-party data are committed.
- See [measured benchmark](MEASURED.md). Physical calibration with known units and isolated actuator data, workload measurements, real response and independent field evidence remain open.

## Verified locally in v0.3.7 (bounded HTTP evaluation)

- One authenticated loopback HTTP service uses the canonical eight-operation interface and the same complexity guard as MCP. Every accepted evaluation runs in a fresh child process with input/output size, memory, CPU and wall limits; bounded concurrency rejects excess work. Invalid inputs and failures return generic errors with no submitted content.
- Real child parity for screening, dispatch and sizing; invalid authorization, complexity/size limits, nonfinite JSON, busy/recovery and process timeout tests pass. See [HTTP service specification](HTTP.md).
- This is a deployable upstream component, not yet a deployed public service. Existing website and public MCP routing, credential provisioning, isolated service deployment and live parity remain open.

## Verified in production on 2026-11-24 (v0.3.7)

- Installed the tagged engine at commit ca3313d in a dedicated unprivileged system service, loopback-only bind, independent upstream credential, TLS proxy, one concurrent solver, service-level 2 GiB memory and one-CPU quota. Other services retained their routes.
- The deployed browser API and existing MCP endpoint returned exactly the same JSON (including evidence) as the installed canonical evaluator for all eight synthetic examples: screen, dispatch, compare designs, profile, size, stress, causal and economics. Reproduce with `python scripts/verify_hosted.py` from an installed checkout of the deployed version and matching solver version.
- Legacy three-input calculator and screening API remained available. Unauthorized upstream returned 401; invalid advanced input returned 422; consent-free review was rejected; private contacts returned 401.
- Local tests establish busy, timeout, and process recovery behavior; no intentional production outage or sustained load test was performed. This is a resource-bounded initial deployment, not an independently audited security or availability guarantee. External field acceptance and calibrated plant response remain separate gates.

## Verified locally in v0.3.8 (degraded workload recovery)

- A proven infeasible forecast can retry one observed sample using the same LP/MILP. No new workload deferral, no reset of existing FIFO deadlines, no relaxation of physical, power, temperature, or equipment constraints. Minimize current cap gap, then residual workload energy, other recovery deficits and cost. Timeouts are not retried; an infeasible fallback stops the replay.
- Permanent synthetic recovery outage: all eight samples execute, 4 MWh miss their original deadlines and remain outstanding. Temporary outage: 4 MWh miss deadlines and are subsequently recovered; the replay remains non-passing. Prefix invariance after an outage, timeout rejection and hard thermal limit preservation tested. 120 installed-package tests passed.
- This is an offline degraded workload policy only. Thermal plant fallback and operator-approved live protection, calibration and field acceptance remain external or separate engineering gates. Production currently runs v0.3.7; repeat hosted parity after deployment of this version.

## Remaining release gates

| Gate | Acceptance evidence |
|---|---|
| Profile interoperability | Independent schema and conformance tests now implemented; obtain authoritative EPRI class semantics and operator-specific rules before any formal mapping |
| Operational feasibility | Sampled causal replay, discrete dispatch, forced-trip/restart and state carryover implemented; sampled degraded workload recovery implemented; remaining plant-specific fallback control, calibrated plant response, finer response checks and independent field validation |
| Resource models | Temperature-constrained cooling, protected loads and renewable curtailment implemented; remaining calibrated thermal and workload parameters and real measured traces with clear reuse permissions |
| Economics | Common real-EUR NPV, investment/fixed costs, replacement, fuel, emissions, single annual peak tariff, connection-delay value and reoptimized sensitivity implemented and analytically checked; remaining real-site assumptions, finer tariff/seasonal resolution, causal evidence |
| Validation | Closed-form and synthetic full-year 15-minute cases implemented; a small exhaustive commitment cost cross-check is implemented; sampled failure injection and prefix invariance now tested; first normalized measured trace replay and repeatable benchmark artifact implemented; remaining physical-unit trace replay, finer numerical tolerance and independent field response evidence |
| Hosted parity | Initial dedicated authenticated deployment and all eight operation browser/MCP/local parity verified; local busy/timeout tests pass. Production sustained-load, availability monitoring and external security review remain separate operational validation |
| Usability | Documented examples, versioned request/response schema, clear error states, inspectable schedules, exportable results and limitations |

Do not mark a gate complete based on documentation alone. Keep the five open issues current and close only after tested acceptance evidence. Never claim certification or commercial reuse of third-party restricted software without explicit rights.
