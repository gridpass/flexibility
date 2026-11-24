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

## Current scope

- Site power gap in MW and energy demand in MWh per restriction.
- Eligibility of flexible demand and on-site generation against notice and duration requirements.
- Battery energy, power and recharge constraints.
- Minimum variable-cost allocation across the eligible resources under constant, repeated-event assumptions.
- Annual event hours, estimated variable costs and unserved reduction.
- Machine-readable JSON inputs and outputs.

This is a first-pass screening model, not chronological dispatch optimisation, a network study or field validation. It assumes a full battery at the first event, identical non-overlapping events, constant site load and available resources. It excludes detailed ramp and rebound models, fuel constraints beyond the entered duration, correlated failures, capex, fixed costs, protection and network flows.

## Roadmap

See [research and implementation scope](docs/RESEARCH.md) and [model details](docs/MODEL.md). We plan to reuse mature open optimisation libraries rather than develop a solver from scratch.

## GridPass services

Use the [free hosted calculator](https://gridpass.co/tools/flexibility-assessment/) or [agent interface](https://gridpass.co/agents/). The open model is intended to remain inspectable and independently runnable; paid site engineering, integrations, validated studies and operational support are separate services.

## Licence

Apache-2.0 for the original GridPass source in this repository. Third-party publications, brands and datasets retain their respective rights. No EPRI code, restricted material or private customer data is included.
