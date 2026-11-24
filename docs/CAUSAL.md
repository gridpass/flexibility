# Causal operating replay (v0.3.8)

The chronological planner knows the complete supplied scenario. A feasible
planning schedule is not proof that a site can respond to an unexpected
restriction or an equipment outage. The causal operation evaluates a separate
sampled feedback policy using the same sparse physical constraints and
SciPy/HiGHS LP/MILP solver.

Run:

```sh
pip install ".[agent]"
gridpass-flexibility --causal examples/causal-replay.json
```

The same payload is accepted by the local MCP `evaluate_flexibility` tool with
operation `causal`.

## Input contract

Supply an object with:

- `scenario`: the ordinary chronological scenario, including actual baseline
  MW, prices, normal cap, event windows, and resource availability time series.
- `lookahead_intervals`: optional integer from 1 to 96 (default 24).
- `time_limit_s`: optional replay-wide solver budget, 0.1 to 600 seconds
  (default 60). The CLI accepts at most 672 executed intervals; MCP accepts
  at most 96 and a 60-second budget plus its resource-interval guard.

All values are hypothetical observations. The simulator has the full input
trace for scoring, but the policy does not receive its unobserved future.
At sample t, it observes current demand, ordinary cap, price and asset
availability, protected load and current thermal inputs. Future values of these signals are forecast by persistence.
An event's start, end and restricted cap become visible only when its notice
is issued. Notice is rounded down to the time actually available on the
sample grid. Event windows already announced are retained. An event announced
before the start of the replay is known at the first sample. Only the first
action of each new forecast plan is executed.

The policy first minimizes the current sample's import-cap gap, then the
sum of forecast gaps, then battery and thermal recovery deficits outside event windows,
then operating costs. Gap optimization uses MW units internally, avoiding
a time-step-dependent feasibility tolerance. The result reports MWh using
the declared interval length. It assumes instantaneous observation at each
sample and execution of the calculated interval-average action.

## State and failures

- Battery: carry actual state of charge between solves, with charge/discharge
  efficiency, reserve, power and optional exact inverter mode. A recovery
  target defaults to the starting SOC or the supplied `terminal_mwh`. Recovery
  outside announced restrictions is prioritized without deliberately exceeding
  a cap. Failure to restore the target by replay end is separately reported.
- Generator: carry prior output, on/off state, elapsed dwell and remaining
  fuel. An observed outage or derating that makes the prior state physically
  incompatible forces a trip, resets downtime and prevents restart in that
  sample. Restart is constrained by the carried minimum-down time. Forced
  trips are recorded separately from commanded shutdowns. A running unit
  may retain its observed output during the notification delay; it cannot
  increase it until ready. Unit startup, minimum run time and ramp are sampled
  constraints, not a calibrated mechanical model.
- Thermal cooling: observed zone temperature carries forward; ambient, internal heat gain, baseline cooling and COP use persistence. Hard temperature bounds and terminal recovery are enforced as described in [THERMAL.md](THERMAL.md). An impossible forecast returns a non-passing partial replay.
- Renewable: only current availability is observed; generation can be curtailed and no export is allowed.
- Workload, cooling proxy and flexible load: carry outstanding deferred MWh
  as FIFO entries with their original deadlines. Recovery does not reset
  deadlines at each solve. The existing energy-equivalent resource model
  requires the forecast window to recover its backlog. If the forecast
  becomes infeasible, the solver may retry a single observed interval if
  workload resources exist. The fallback disables new deferrals and relaxes
  only workload deadline and terminal-backlog equality constraints. It retains
  all physical constraints and first minimizes the current import-cap gap,
  then outstanding deferred MWh, other recovery deficits and cost. FIFO work
  remains due at its original deadline; each newly missed MWh is counted once
  and remains outstanding until actually recovered. Normal forecast planning
  resumes on the next sample. Timeouts and other solver failures are not
  retried. If the fallback itself fails, the replay stops without inventing
  an action. This is a simulated degraded workload policy, not a plant
  fail-safe or an operator-approved fallback.

The example has an unexpected trip of a 2 MW generator during a 2 MW reduction
commitment. The generator remains offline for two intervals due to its minimum
down time, then restarts. All eight samples are executed; the gap is 4 MWh.
The output is deliberately **not feasible**. A separate test contrasts a
two-hour announced event with the same surprise event: an initially empty
2 MW/4 MWh battery can precharge for the announced event but cannot anticipate
the surprise. The perfect-foresight planner can pass both; causal replay
correctly fails the unannounced case.

## Result and limits

The JSON includes observations visible to the policy at each executed sample,
resource schedules, import caps, gap MW/MWh, realized operating cost,
forced trips, terminal state, recovery shortfalls, executed interval count,
policy identifier, input/output SHA-256 and engine version. `status=solved`
means the complete sampled replay ran; `feasible=true` additionally requires
no cap gap above tolerance, no outstanding terminal recovery obligations,
no missed workload deadlines, and no invocation of the degraded fallback.
A complete degraded replay reports `status=solved` but is non-passing even
if late work is ultimately recovered. `fallbacks` records each attempt,
`missed_deadlines` records newly overdue MWh per resource and interval, and
`missed_deadline_mwh` is their sum (not a time integral of backlog).
`status=replay_failed` means a solve, forecast feasibility or time budget
failed and only the prefix is evidence. It cannot pass. A negative result
for this policy is not a proof that all other causal policies fail.

The per-solve time limit uses the remaining replay budget; Python model
construction and native solver cleanup may add overhead. The local server
is not a public multi-tenant worker. The replay does not validate sub-sample
response, continuous-time protection, stochastic guarantees, physical plant
failures, communication latency or actual grid acceptance. In particular,
event duration is assumed known at notification, and event-window forecasts
are not proof of future operator behavior.
