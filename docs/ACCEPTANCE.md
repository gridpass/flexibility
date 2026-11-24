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

## Remaining release gates

| Gate | Acceptance evidence |
|---|---|
| Profile interoperability | Versioned public specification, traceable normative references, explicit limits and an independent conformance suite |
| Operational feasibility | Causal/receding-horizon schedule with unknown future events, failure/recovery tests, fine time-step response checks, storage mode and generator start/run constraints |
| Resource models | Calibrated workload and thermal constraints, renewables, protected loads, real measured traces with clear reuse permissions |
| Economics | Consistent horizon, capital and fixed costs, fuel, maintenance, tariffs, emissions, connection-delay value and sensitivity; independently check numerical examples |
| Validation | Closed-form cases, solver cross-checks, full-year 15-minute case, failure injection, numerical tolerance, install/CI and repeatable benchmark artifacts |
| Hosted parity | Public website and existing MCP use this canonical engine, provide a simple entry point plus advanced operations; authenticated or resource-bounded optimization; live endpoint tests, no customer data leakage |
| Usability | Documented examples, versioned request/response schema, clear error states, inspectable schedules, exportable results and limitations |

Do not mark a gate complete based on documentation alone. Keep the five open issues current and close only after tested acceptance evidence. Never claim certification or commercial reuse of third-party restricted software without explicit rights.
