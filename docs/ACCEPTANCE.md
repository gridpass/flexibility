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
- This is an offline degraded workload policy only. Thermal plant fallback and operator-approved live protection, calibration and field acceptance remain external or separate engineering gates. Production v0.3.8 verified 2026-11-24: main and tag CI green; all eight standard operations plus the temporary workload outage case match exactly across public browser API, MCP and local engine. The degraded case executes all eight samples, reports 4 MWh missed deadlines and zero terminal backlog, and remains non-passing. Upstream remains loopback-only with unauthenticated 401, DynamicUser, 2 GiB service memory and one-CPU quota. No sustained-load or field validation claim.

## Verified physical-unit industrial trace benchmark (v0.3.8 engine)

- UCI CC BY 4.0 steel industry archive checksum pinned; all 35,040 ordered 15-minute kWh intervals validated (959.63671 MWh, peak interval-average 0.62872 MW). Canonical dispatch replays 8,064 measured intervals across twelve fixed seven-day windows, with independent energy, gap, SOC, efficiency, equipment bound and terminal checks. Hypothetical 0.3 MW / 0.6 MWh battery reduces uncovered energy from 24.57368 to 1.329863 MWh and passes only three windows. See [measured benchmark](MEASURED.md). No raw data committed; no actual flexibility response or thermal parameter fit claimed.

## Verified conditional cooling equipment benchmark

- A checksum-pinned CC BY 4.0 Athens pilot workbook supplies one-minute measured water-loop temperatures, flows and total heat-pump electrical input. A chronological 12/12 complete-cycle split estimates conditional COP 3.758 and 1.515% aggregate absolute held-out cycle-energy error. Workbook cold/hot port naming is inconsistent with thermodynamic roles; same-prefix flow pairing remains a hypothesis, and maximum energy-balance residual is 18.44% of electrical input. See [benchmark and limitations](MEASURED.md). No calibrated zone model, confirmed sensor mapping, field acceptance or default COP is claimed.

## Verified monthly peak tariff optimization

- Twelve calendar-month demand rates are optimized in the same sparse HiGHS dispatch model; independent accounting reconciles each month’s sampled peak and total costs. A synthetic January/February case dispatches generation only for the expensive January peak, producing EUR 6,200 demand charges and EUR 4,800 nonfuel generation cost. Invalid rates, overlapping annual/monthly tariff specifications and samples spanning month boundaries are rejected; generic interface parity tested. No production deployment or seasonal commissioning claim.

## Verified seasonal commissioning cost allocation

- Optional calendar-month allocation uses the same optimized annual schedule and reconciles monthly energy, fuel, carbon, variable, commitment and peak charges to the annual total. A July start excludes January demand charges and uses actual modeled July–December energy cost. Whole-month delays, explicit monthly tariff and boolean opt-in are required. Full-year and generator-cost accounting and generic interface parity tested. Initial commissioning state and partial-year redispatch remain unvalidated; no production deployment claim.

## Verified partial-year commissioning redispatch

- Seasonal alternatives solve the active calendar suffix from the declared initial battery, generator and thermal states, zero backlog and no pre-service notice. Monthly costs reconcile and the partial-year result participates in eligibility and solver completeness. A synthetic July opening with an empty 24 MWh battery misses 24 MWh of required reduction even though the full-year schedule can precharge and pass. The alternative cannot win. Event clipping and time-series slicing tested; hosted complexity accounting reserves a second solve. Inter-year state continuity, actual commissioning assumptions and field response remain unverified.

## Verified conservative inter-year state check

- Repeated annual schedules and commissioning-to-full-year transitions require matching storage energy, thermal state, generator output and commitment/dwell, and zero workload backlog at the declared state boundary. A mismatch blocks eligibility and a complete recommendation when the traces are otherwise feasible; no free state reset is assumed. Fuel is explicitly assumed replenished. A synthetic last-day restriction depletes 24 MWh from an initially full battery and blocks a multi-year recommendation despite a feasible single-year schedule. A restored battery passes. Generator dwell, thermal and backlog mismatches are independently tested. No claim of continuous multiyear reoptimization or site validation.

## Verified GPU workload actuation benchmark

- Pinned CC BY 4.0 ELF trace: 3,322 samples, six downward A10G cap steps across two workloads. Observed post-cap-label settling ranges from 101 to 1,893 ms, with final-window iteration latency reported and incomplete steps censored. Regression tests reject nonmonotonic/gapped and nonfinite measurements. See [benchmark](MEASURED.md). Command invocation latency, facility power, workload SLA and site response remain external evidence; no engine defaults changed.

## Verified independent numerical solution checks and one-second sampled response

- Each successful LP/MILP dispatch stage (including lexicographic objective-lock rows) and the shared capacity LP is checked against the original sparse equality/inequality matrices, variable bounds and integer constraints. Nonfinite or malformed vectors and residuals above an absolute 1e-5 in native row units return solver failure, not infeasibility or a recommendation. This is a numerical threshold, not a contractual meter tolerance or proof of optimality.
- Fault-injected solver success with an invalid point is rejected in both dispatch and sizing. A six-second synthetic dispatch with two seconds of response delay and 0.5 MW/s generator ramp produces per-event-sample gaps of 1, 1, 0.5 and 0 MW; independent integration gives 2.5 MW-s (0.00069444 MWh). This checks modeled one-second behavior, not subinterval or physical equipment response.

## Verified offline thermal parameter identification

- Offline identification uses the canonical exact sampled heat balance, independent thermal MW inputs, chronological fit/holdout split, rank and conditioning checks and rejection of nonphysical fits. A free-running holdout must beat persistence and satisfy a predeclared maximum temperature error. Independent analytic fixtures recover 1.7 MWh/K and 0.35 MW/K, including a zero-conductance limit; injected drift, missing samples and invalid measurements are rejected. See [thermal calibration](THERMAL.md#offline-parameter-identification).
- Available measured traces do not contain all independently confirmed thermal input and zone boundary channels. No measured zone parameter fit, operational default or field validation is asserted. The independently testable calibration method is implemented; actual site-specific calibration requires suitable measurements.

## Remaining release gates

| Gate | Acceptance evidence |
|---|---|
| Profile interoperability | Independent schema and conformance tests now implemented; obtain authoritative EPRI class semantics and operator-specific rules before any formal mapping |
| Operational feasibility | Sampled causal replay, discrete dispatch, forced-trip/restart and state carryover implemented; sampled degraded workload recovery implemented; remaining plant-specific fallback control, calibrated plant response, finer response checks and independent field validation |
| Resource models | Temperature-constrained cooling, protected loads and renewable curtailment implemented; offline thermal parameter identification and held-out validation implemented; remaining measured site-specific thermal and workload parameters with clear provenance |
| Economics | Common real-EUR NPV, investment/fixed costs, replacement, fuel, emissions, annual or calendar-month peak tariffs, connection-delay value and reoptimized sensitivity implemented and analytically checked; remaining real-site assumptions, utility-specific tariff rules, opt-in sequential inter-year redispatch for nonmatching states (implemented; joint multi-year optimization not claimed), real commissioning-state inputs, causal evidence |
| Validation | Closed-form and synthetic full-year 15-minute cases implemented; a small exhaustive commitment cost cross-check is implemented; sampled failure injection and prefix invariance now tested; first normalized measured trace replay and repeatable benchmark artifact implemented; physical-unit measured demand replay implemented; independent native-unit numerical residual checks and one-second synthetic response implemented; remaining physical actuator/thermal calibration and independent field response evidence |
| Hosted parity | Initial dedicated authenticated deployment and all eight operation browser/MCP/local parity verified; local busy/timeout tests pass. Production sustained-load, availability monitoring and external security review remain separate operational validation |
| Usability | Documented examples, versioned request and stable-core response schemas, CLI export, real CLI/MCP conformance and live wire checks implemented; schema validation is opt-in; preserve legacy wire compatibility and clear error states |

Do not mark a gate complete based on documentation alone. Keep issues #1–5 current and close only after tested acceptance evidence. Never claim certification or commercial reuse of third-party restricted software without explicit rights.

## Consolidated v0.3.9 release candidate

- Collects the monthly tariff, seasonal commissioning, state-boundary, numerical validation and offline calibration changes above. The opt-in hosted probe adds the synthetic July commissioning case: the annual trace is feasible but the opening-day restriction leaves 24 MWh uncovered and must prevent a recommendation. Deployment and live parity are not assumed by this version bump.

## Verified in production on 2026-11-24 (v0.3.9)

- Tagged commit 3af96dc; 150 installed-package tests and Python 3.10/3.12 PR, branch, main and tag CI passed. Existing isolated service upgraded with pinned NumPy 2.5.5 and SciPy 1.18.1; no new infrastructure or gateway changes.
- All eight canonical operations and the new July commissioning case matched exactly as JSON across public browser API, MCP and local engine. The latter independently asserts full-year feasibility, 24 MWh uncovered at commissioning, and no eligible recommendation. Initial smoke comparison found Python tuple versus wire JSON array representations of peak periods; deployment was rolled back, the probe corrected to compare strict JSON, then redeployed and verified. No numerical or evidence-hash mismatch remained.
- Calculator HTTP 200, invalid advanced input 422, consent rejection and unauthenticated upstream 401; service active, loopback-only, DynamicUser, 2 GiB memory, one CPU. No sustained-load, external security audit, field validation or official equivalence claim. Independently testable remaining work includes nonmatching inter-year reoptimization and explicit usability/schema checks; site-specific commissioning, protection/fallback settings and measured plant acceptance are external inputs.

## Verified evaluation interface conformance (v0.3.9 wire format)

- Packaged Draft 2020-12 request and stable-core response schemas cover all eight generic operations; CLI exports both versioned contracts without solver startup. Requests include nested resource variants, events, sizing, fuel and tariff fields. Response checks distinguish valid, infeasible and solver-failure outcomes, require core schedules and evidence, and allow additive diagnostics. Strict JSON validation rejects nonfinite numbers, unknown request fields and malformed nested values; semantic cross-field and hosted budget checks remain separate.
- Installed-package tests exercise all eight CLI and real stdio MCP operations, strict schema rejection, failure-result variants and independent cross-field rejection. The read-only hosted probe validates nine synthetic requests and all 27 local/browser/MCP results against the contracts before exact wire parity comparison; all pass against deployed v0.3.9 on 2026-11-24. No runtime or gateway change. Schema conformance is an opt-in client/verification contract, not a claim that the current service rejects every schema-invalid request or that all nested diagnostic fields are frozen.

## Verified sequential operating-year redispatch

- Opt-in lifecycle mode carries battery SOC, zone temperature, generator output/commitment age and original terminal targets into the next active year using the same dispatch solver. Workload backlog must close each year; fuel replenishment is explicit. Actual service-year costs feed NPV, including calendar commissioning. Shared time budget and hosted complexity bounds account for repeated solves.
- Analytic daily case: a 24 MWh battery ends year one empty; the following year incurs EUR 2,400 additional recharge cost at EUR 100/MWh and passes. Removing recharge headroom leaves 24 MWh uncovered and excludes the design. July commissioning carries the actual empty terminal battery into the next year. State extraction, failed second solve, request/response schema and budget tests included.
- This is sequential yearly redispatch, not joint multi-year optimization, a causal policy, or field calibration. No production deployment claimed.
