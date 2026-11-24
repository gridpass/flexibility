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
- Candidate IDs must not duplicate existing resources. Continuous capacities are shared across cases. Each case has its own operating schedule. Continuous sizing rejects discrete resources and capacity options; use explicit design comparison for mixed-integer equipment.
- All costs must be allocated to the same analysis horizon. The model does not guess project lifetime, discount rate, annualization, tariff changes or avoided connection delays.

The LP minimizes investment plus weighted operation. A feasible solution is independently replayed through the chronological evaluator. The result includes capacities, modeled cost, per-case feasibility, evidence hashes and solver version. This is finite-scenario planning with perfect foresight, not a causal robust dispatch policy. A solver timeout or replay failure is not a valid design.

The analytical example has a 2 MW reduction in two alternative durations of two and three hours. Ideal-efficiency storage with sufficient recharge and no reserve needs 2 MW / 6 MWh to cover both. The three-hour case is zero-weight, so feasibility cannot be bought by ignoring an expensive stress case.

## Finite equipment package selection

Run `gridpass-flexibility --size examples/capacity-candidates.json` or use
the same generic `size` operation. Supply optional `candidates` (1–16
explicit packages), each with an ID, `allocated_cost_eur` and up to 16
fixed cooling or flexible workload resources in the existing dispatch format.
Supply `options: []` for package-only selection, or add continuous battery
and generator options to optimize their shared capacity conditional on each
package. An empty resources array can represent no additional flexible load.
Candidate resource IDs may recur across packages but must be distinct from
the continuous options and existing resources in each scenario. Case-specific
`new_resource_availability` overrides apply to matching candidate resources
or continuous options; a resource absent from a package has no effect.

The existing hard-cap LP solves every package across all cases, including
zero-weight cases. Each feasible design is independently replayed. The
objective adds the explicit fixed allocated package cost to shared asset
investment and weighted operating cost. Allocate fixed O&M and investment
to the same horizon; the result's allocated capex field includes the supplied
package allocation. Fuel or carbon costs can be included in variable cost;
the separate lifecycle operation handles detailed NPV and connection timing.
The result lists all candidate results and selects the minimum cost among
the supplied feasible packages (lexical ID breaks an exact tie). Any failed
solve or replay blocks the entire recommendation; proven hard-cap
infeasibility excludes only that package. A single time budget covers all
solves and replays. The hosted adapter charges work for every candidate.

The synthetic example has a 2 MW cap reduction for one and two hours.
A zone with 1 MWh/K capacitance and a 2 K allowed temperature rise can
defer 2 MWh of cooling electricity at COP 1. It alone cannot pass the
two-hour event. A 1 MW workload adds 2 MWh shift capacity. The combined
package costs EUR 8,120 including weighted operation, versus EUR 8,200
for a 2 MW workload-only package. The two cheaper packages are infeasible.
No real site parameters are inferred.

This is exhaustive comparison of a finite declared catalog, not a
continuous optimum for cooling thermal parameters or workload capacities.
It uses independent perfect-foresight operating scenarios and the existing
linear dispatch model, not a robust causal policy. Discrete assets are
rejected in this continuous planning operation; use fixed design dispatch
for discrete unit commitment.

## Commitment evaluation

Run:

```sh
gridpass-flexibility --stress examples/annual-stress.json
```

The input contains a full 8,760-hour site baseline, a versioned profile and an optional list of resource IDs for outage tests. The profile defines required reduction MW, maximum notice time, required activation duration, annual activation hours and minimum recovery time.

The suite creates two schedules (evenly distributed calls and clustered calls) and a clustered schedule with each explicitly requested resource unavailable. The requested cap is conservative for each whole event. Annual hours round upward to the next interval. Event and recovery durations must align with the simulation time step; the step must satisfy any declared maximum interval. A too-short or impossible profile is rejected.

A passing result refers only to the modeled test cases. Response times shorter than the time step are not validated by this model. No certification, network connection approval, or guarantee about untested event sequences is implied. The example intentionally fails its generator-outage case.

## Open gaps

- The separate sampled causal replay evaluates uncertain event timing and outages; continuous capacity sizing itself remains perfect-foresight.
- Cooling and workload capacity selection uses finite supplied packages, not continuous thermal/workload optimization. Discrete generator start/run, forced-trip/restart replay and battery inverter modes are available in fixed-capacity dispatch.
- Site-specific financial analysis, reliability probabilities, data-driven validation and field acceptance.
