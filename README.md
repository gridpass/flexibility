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
PYTHONPATH=src python -m unittest discover -s tests -v
```

Alternatively install locally with `pip install .` and use the `gridpass-flexibility` command.

The example is a synthetic 20 MW data centre facing a 15 MW import cap for four hours. It has 1.5 MW of flexible load, 2 MW of available generation and a 3 MW / 8 MWh battery. The model evaluates whether the resources can sustain the requested reduction, considering notice, duration, annual event count, recovery time and variable costs.

## Advanced evaluation

The optional optimization engine uses SciPy/HiGHS to create chronological operating schedules, model battery SOC and recovery, constrain generation output and ramp, model deferred workloads and cooling, evaluate defined event profiles, and compare candidate resource additions.

```sh
pip install ".[optimization]"
gridpass-flexibility --dispatch examples/chronological.json
gridpass-flexibility --compare-designs examples/design-comparison.json
gridpass-flexibility --profile examples/profile-check.json
```

Read the [chronological evaluation specification](docs/CHRONOLOGICAL.md) for assumptions, schema, economics, and evidence boundaries. The example profile check is intentionally incomplete because it does not cover a full year. The implementation does not claim EPRI certification or equivalence to its tool.

## Screening model scope

- Site power gap in MW and energy demand in MWh per restriction.
- Eligibility of flexible demand and on-site generation against notice and duration requirements.
- Battery energy, power and recharge constraints.
- Minimum variable-cost allocation across the eligible resources under constant, repeated-event assumptions.
- Annual event hours, estimated variable costs and unserved reduction.
- Machine-readable JSON inputs and outputs.

The zero-dependency screening model is not chronological dispatch optimisation, a network study or field validation. It assumes a full battery at the first event, identical non-overlapping events, constant site load and available resources. It excludes detailed ramp and rebound models, fuel constraints beyond the entered duration, correlated failures, capex, fixed costs, protection and network flows.

## Roadmap

See [research and implementation scope](docs/RESEARCH.md) and [model details](docs/MODEL.md). The advanced evaluator already reuses SciPy/HiGHS; see the remaining capability gaps in the roadmap.

## Secure grid connections (proposal)

See the [GridPass Guard specification and release gates](docs/SECURE_GRID_CONNECTIONS.md) for the proposed independent site-side enforcement and evidence layer. The current evaluator remains an offline planning tool; no live-control or certification claim is made. Run the [simulator-only Guard reference demo](docs/GUARD_DEMO.md) to reproduce authorization, fallback, and measurement-failure tests. Build and run the [Bosch Rexroth ctrlX COREvirtual developer SNAP](docs/CTRLX_GUARD.md) using the same open-source implementation.

## GridPass services

Use the [free hosted calculator](https://gridpass.co/tools/flexibility-assessment/) or [agent interface](https://gridpass.co/agents/). The open model is intended to remain inspectable and independently runnable; paid site engineering, integrations, validated studies and operational support are separate services.

## Licence

Apache-2.0 for the original GridPass source in this repository. Third-party publications, brands and datasets retain their respective rights. No EPRI code, restricted material or private customer data is included.
