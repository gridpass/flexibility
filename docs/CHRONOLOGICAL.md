# Chronological evaluator

The optional optimization extra uses SciPy's HiGHS linear programming backend. No solver is reimplemented. Install with `pip install ".[optimization]"` (or `uv pip install ".[optimization]"`).

Run:

```sh
gridpass-flexibility --dispatch examples/chronological.json
gridpass-flexibility --compare-designs examples/design-comparison.json
gridpass-flexibility --profile examples/profile-check.json
```

## Inputs

A scenario contains a baseline demand array (MW), interval duration (hours), normal import capacity and electricity prices (scalar or interval array), non-overlapping events, and resource objects. Events specify start and end indices (start inclusive, end exclusive), notice in minutes, and import cap in MW. The maximum horizon is 8,760 hours and 35,040 intervals. Availability is a fraction of rated power per interval. Input files should describe only assets and power levels the operator is allowed to use.

Resource fields:

- Generator: power, response delay, ramp MW/h, initial output, maximum electrical energy from the available fuel, variable cost.
- Battery: power, charging power, energy, initial and terminal state of charge, reserve, charge/discharge efficiency and variable cost.
- Flexible load, workload or cooling proxy: reduction MW, response delay, shift budget in MWh, maximum recovery delay in hours, recovery MW and variable cost. Deferred energy has to be restored; the cooling proxy is not a temperature or chiller model.

The evaluator minimizes uncovered import-cap energy first and then minimizes operating cost. It uses an explicit interval energy balance, storage trajectories and workload recovery obligations. The default resource model is continuous/divisible. Optional discrete generator and battery modes use SciPy/HiGHS mixed-integer optimization, described below. Every schedule still has perfect foresight; it is not a causal dispatch policy. Emissions and fuel supply contracts are not modeled. Event readiness and ramp are simplified planning assumptions. No weather, grid AC flow, protection, fault response or equipment certification is inferred.

Results include the interval schedule, peak and total unmet reduction, event-level violations, modeled operating cost, observed limiting resource bounds and input/result hashes with software and solver version. Evidence is explicitly labeled modelled perfect foresight. It is not a signed field test.

## Discrete equipment operation

Set `discrete: true` on an existing battery or generator to select the mixed-integer model. The continuous default remains suitable for fast planning and capacity sizing.

- Battery: one binary charging-mode variable per interval prevents simultaneous charging and discharging, including artificial energy dissipation through round-trip losses.
- Generator: binary online, startup and shutdown variables; optional `minimum_output_mw`, `minimum_up_hours`, `minimum_down_hours`, `startup_cost_eur`, and `online_cost_eur_per_hour`. The initial state is given by `initial_on`, `initial_mw`, and `initial_state_hours`. If omitted, the state follows positive initial output and is assumed to have lasted long enough for all dwell requirements.
- The initial generator state must agree with its minimum output. Dwell times are rounded upward to complete intervals. Start and stop obligations are enforced within the simulation horizon; remaining obligations beyond its end are not modeled.
- Ramp and response limits still apply. An outage that contradicts an existing must-run or ramp obligation can make the model infeasible. This is reported as a solver failure with no pass; explicit forced trips and restart recovery are future work.
- Generator startup and online cost contribute to the objective and to reported operating cost. Solver timeout or failure never gives a positive result.
- Continuous capacity sizing rejects discrete options or assets rather than silently ignoring their constraints. Compare explicit equipment designs when commitment constraints matter.

Run `gridpass-flexibility --dispatch examples/discrete-dispatch.json`. The mixed-integer solver has a 60-second limit per solve. The local MCP also bounds binary-variable count. Hosted execution requires separate worker isolation and aggregate resource limits.

## Design comparisons

Supply a scenario and a list of candidate additions. Each candidate has a unique ID, additional resource objects, and fixed cost allocated to the modeled horizon. The evaluator ranks feasible options by modeled total cost and infeasible options by uncovered energy. This compares explicit candidate designs. Use the separate continuous sizing operation for capacity expansion; neither operation produces bankable annual economics without site-specific evidence.

## Test profiles

A profile includes its ID/version, target reduction MW, notice time, required activation duration, and annual event hours. Each scenario is assessed using the same optimizer. A single full-year scenario must jointly cover notice, duration, annual use, and any declared recovery and resolution limits. See [the v1 profile specification](PROFILE_SPEC.md). Qualifying event caps must request at least the target reduction relative to baseline/normal import for the whole event. A positive result refers only to the supplied modeled cases; it is not a certification or a guarantee against other event sequences.

Example profiles are independent, editable finite test envelopes, not official EPRI classification rules. The public EPRI materials describe the dimensions; NVIDIA's published November 13, 2026 adaptation of Flex MOSAIC v1.0 is a useful comparison reference (https://docs.nvidia.com/dsx/flex/architecture). Confirm EPRI's authoritative version and test methodology before claiming formal class mapping.

## Next engineering steps

Explicit trips and restart recovery, calibrated workload and thermal models, sampled causal replay is available separately (see [CAUSAL.md](CAUSAL.md)); remaining stochastic/robust policies and additional stress event sequences, measured field replay, report export, and the GridPass public MCP/website integration. Keep the zero-dependency screening calculator for quick cases; advanced numerical work runs with an established solver.
