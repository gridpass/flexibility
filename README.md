# GridPass Flexibility

An independent, open-source evaluation engine for data centres and other large electricity consumers that need to operate within a grid import constraint.

The project is inspired by the public large-load flexibility problem described by EPRI's DCFlex initiative and Flex MOSAIC framework. It is not EPRI software, is not affiliated with or endorsed by EPRI, and does not issue Flex MOSAIC certifications or connection approvals.

## Try it

Requires Python 3.10+. No third-party runtime dependencies for the initial screening model.

```sh
git clone https://github.com/gridpass/flexibility.git
cd flexibility
PYTHONPATH=src python -m gridpass_flexibility examples/data-centre.json
PYTHONPATH=src python -m gridpass_flexibility --schema
pip install ".[agent]"
python -m unittest discover -s tests -v
```

Alternatively install locally with `pip install .` and use the `gridpass-flexibility` command.

The example is a synthetic 20 MW data centre facing a 15 MW import cap for four hours. It has 1.5 MW of flexible load, 2 MW of available generation and a 3 MW / 8 MWh battery. The model evaluates whether the resources can sustain the requested reduction, considering notice, duration, annual event count, recovery time and variable costs.

## Advanced evaluation

The optional optimization engine uses SciPy/HiGHS LP/MILP to create chronological operating schedules with optional binary battery modes and generator commitment, model battery SOC and recovery, constrain generation output and ramp, model deferred workloads, temperature-constrained cooling and renewable availability, evaluate defined event profiles, and compare candidate resource additions.

```sh
pip install ".[optimization]"
gridpass-flexibility --dispatch examples/chronological.json
gridpass-flexibility --dispatch examples/discrete-dispatch.json
gridpass-flexibility --dispatch examples/thermal-dispatch.json
gridpass-flexibility --compare-designs examples/design-comparison.json
gridpass-flexibility --profile-schema
gridpass-flexibility --profile examples/profile-check.json
gridpass-flexibility --size examples/capacity-sizing.json
gridpass-flexibility --size examples/capacity-candidates.json
gridpass-flexibility --stress examples/annual-stress.json
gridpass-flexibility --causal examples/causal-replay.json
```

Read the [chronological evaluation specification](docs/CHRONOLOGICAL.md) for assumptions, schema, economics, and evidence boundaries. The example profile check is intentionally incomplete because it does not cover a full year. The implementation does not claim EPRI certification or equivalence to its tool.

## Physical resource models

The single-zone cooling model uses an exact sampled sensible-heat balance, temperature limits, heat gains, ambient temperature, COP, and terminal recovery. Renewable availability limits generation; curtailment is allowed. The site model reserves explicitly protected non-cooling load and prevents workload deferral from double-counting baseline cooling. See [thermal and renewable resources](docs/THERMAL.md). Parameters still require site-specific calibration.

## Capacity planning and commitment stress tests

Size battery power, battery energy and generation capacity across several alternative connection scenarios. The optimizer chooses one shared design, minimizes explicitly weighted operating cost plus allocated investment cost, and replays the design in each case. A zero-weight stress case still has to be feasible. Explicit cooling and workload packages can also be compared across the same cases, optionally with shared battery and generator sizing. An incomplete candidate comparison returns no recommendation.

Generate distributed and clustered annual restrictions from a defined commitment. Optionally test whole-horizon resource outages. A passing scenario is not proof of performance under all future event sequences; the model uses independent perfect-foresight schedules.

See [capacity and commitment planning](docs/PLANNING.md), the [v1 commitment profile specification](docs/PROFILE_SPEC.md) and the example JSON inputs.

## Causal replay

Run a sampled receding-horizon policy using only observed resource states and announced events. Future unobserved signals use persistence forecasts. Battery SOC, generator fuel and dwell time, cooling temperature, and workload recovery deadlines carry across solves. The replay reports forced trips, unmet caps, costs, recovery shortfalls and partial failures separately from perfect-foresight feasibility. See [causal replay](docs/CAUSAL.md).

## MCP for agents

```sh
pip install ".[agent]"
gridpass-flexibility-mcp
```

The default transport is stdio. The read-only `evaluate_flexibility` tool accepts an operation (`screen`, `dispatch`, `compare_designs`, `profile`, `size`, `stress`, `causal`, or `economics`) and the corresponding example JSON payload. For a local HTTP client, run `gridpass-flexibility-mcp --transport streamable-http` and connect to `http://127.0.0.1:8765/mcp`. See [agent integration](docs/MCP.md).

Use it to assess whether a site's load and equipment can meet a proposed grid
import limit. Agents can discover the existing input/output schemas and synthetic
examples through MCP resources, or start with the `assess_connection` prompt.
Run `python scripts/demo_connection_assessment.py` after installing the agent
extra to reproduce a complete equipment comparison through MCP.

## Screening model scope

- Site power gap in MW and energy demand in MWh per restriction.
- Eligibility of flexible demand and on-site generation against notice and duration requirements.
- Battery energy, power and recharge constraints.
- Minimum variable-cost allocation across the eligible resources under constant, repeated-event assumptions.
- Annual event hours, estimated variable costs and unserved reduction.
- Machine-readable JSON inputs and outputs.

The zero-dependency screening model is not chronological dispatch optimisation, a network study or field validation. It assumes a full battery at the first event, identical non-overlapping events, constant site load and available resources. It excludes detailed ramp and rebound models, fuel constraints beyond the entered duration, correlated failures, capex, fixed costs, protection and network flows.

## Roadmap

See [research and implementation scope](docs/RESEARCH.md) and [model details](docs/MODEL.md). The advanced evaluator reuses SciPy/HiGHS. See [release acceptance criteria](docs/ACCEPTANCE.md) and the remaining issues.

## Secure grid connections (proposal)

See the [GridPass Guard specification and release gates](docs/SECURE_GRID_CONNECTIONS.md) for the proposed independent site-side enforcement and evidence layer. The current evaluator remains an offline planning tool; no live-control or certification claim is made. Run the [simulator-only Guard reference demo](docs/GUARD_DEMO.md) to reproduce authorization, fallback, and measurement-failure tests.

## GridPass services

Use the [free hosted calculator](https://gridpass.co/tools/flexibility-assessment/) or [agent interface](https://gridpass.co/agents/). The open model is intended to remain inspectable and independently runnable; paid site engineering, integrations, validated studies and operational support are separate services.

## Licence

Apache-2.0 for the original GridPass source in this repository. Third-party publications, brands and datasets retain their respective rights. No EPRI code, restricted material or private customer data is included.

## Lifecycle economics

Compare full-year connection alternatives using the same dispatch model, real-EUR cashflows, capital and fixed costs, fuel, carbon, peak tariff and connection delays. Run `gridpass-flexibility --economics examples/lifecycle-economics.json` or use the generic MCP operation `economics`. See [assumptions and inputs](docs/ECONOMICS.md).

## Measured validation

See the [reproducible AAU measured trace benchmark](docs/MEASURED.md), including held-out prediction errors, dispatch balance checks and explicit limits on physical calibration.

## Bounded HTTP service

Use the optional Linux `host` extra for an authenticated, process-bounded upstream exposing the same evaluation operations. See [HTTP service setup and limits](docs/HTTP.md). Public deployment is not implied.
