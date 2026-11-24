# Capacity and commitment planning

## Capacity sizing

Run:

```sh
gridpass-flexibility --size examples/capacity-sizing.json
```

The input contains a list of cases and a list of investable options.

- Each case has a unique ID, a chronological scenario, an optional nonnegative operating-cost weight and optional availability overrides for new assets. All cases enforce their grid import limits. Zero weight means the case is enforced but contributes no operating cost to the objective.
- A battery option has maximum MW and MWh, allocated EUR per MW and per MWh, charge/discharge efficiency, reserve, initial and terminal SOC fractions, and charging-to-discharge power ratio.
- A generator option has maximum MW, allocated EUR per MW, variable EUR/MWh, response time, ramp fraction per hour and optional fuel-energy budget.
- Candidate IDs must not duplicate existing resources. Continuous capacities are shared across cases. Each case has its own operating schedule.
- All costs must be allocated to the same analysis horizon. The model does not guess project lifetime, discount rate, annualization, tariff changes or avoided connection delays.

The LP minimizes investment plus weighted operation. A feasible solution is independently replayed through the chronological evaluator. The result includes capacities, modeled cost, per-case feasibility, evidence hashes and solver version. This is finite-scenario planning with perfect foresight, not a causal robust dispatch policy. A solver timeout or replay failure is not a valid design.

The analytical example has a 2 MW reduction in two alternative durations of two and three hours. Ideal-efficiency storage with sufficient recharge and no reserve needs 2 MW / 6 MWh to cover both. The three-hour case is zero-weight, so feasibility cannot be bought by ignoring an expensive stress case.

## Commitment evaluation

Run:

```sh
gridpass-flexibility --stress examples/annual-stress.json
```

The input contains a full 8,760-hour site baseline, a versioned profile and an optional list of resource IDs for outage tests. The profile defines required reduction MW, maximum notice time, required activation duration, annual activation hours and minimum recovery time.

The suite creates two schedules (evenly distributed calls and clustered calls) and a clustered schedule with each explicitly requested resource unavailable. The requested cap is conservative for each whole event. Annual hours round upward to the next interval. Event and recovery durations must align with the simulation time step; the step must satisfy any declared maximum interval. A too-short or impossible profile is rejected.

A passing result refers only to the modeled test cases. Response times shorter than the time step are not validated by this model. No certification, network connection approval, or guarantee about untested event sequences is implied. The example intentionally fails its generator-outage case.

## Open gaps

- Causal dispatch with uncertain event timing and outages rather than perfect foresight.
- Equipment-specific nonlinear thermal and workload behavior, minimum run times, starts and binary inverter modes.
- Site-specific financial analysis, reliability probabilities, data-driven validation and field acceptance.
