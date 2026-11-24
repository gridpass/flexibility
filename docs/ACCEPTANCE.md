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

## Remaining release gates

| Gate | Acceptance evidence |
|---|---|
| Profile interoperability | Independent schema and conformance tests now implemented; obtain authoritative EPRI class semantics and operator-specific rules before any formal mapping |
| Operational feasibility | Sampled causal replay, discrete dispatch, forced-trip/restart and state carryover implemented; remaining fallback control, calibrated plant response, finer response checks and independent field validation |
| Resource models | Calibrated workload and thermal constraints, renewables, protected loads, real measured traces with clear reuse permissions |
| Economics | Consistent horizon, capital and fixed costs, fuel, maintenance, tariffs, emissions, connection-delay value and sensitivity; independently check numerical examples |
| Validation | Closed-form and synthetic full-year 15-minute cases implemented; a small exhaustive commitment cost cross-check is implemented; sampled failure injection and prefix invariance now tested; remaining real trace replay, finer numerical tolerance and repeatable benchmark artifacts |
| Hosted parity | Public website and existing MCP use this canonical engine, provide a simple entry point plus advanced operations; authenticated or resource-bounded optimization; live endpoint tests, no customer data leakage |
| Usability | Documented examples, versioned request/response schema, clear error states, inspectable schedules, exportable results and limitations |

Do not mark a gate complete based on documentation alone. Keep the five open issues current and close only after tested acceptance evidence. Never claim certification or commercial reuse of third-party restricted software without explicit rights.
