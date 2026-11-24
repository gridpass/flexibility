# Measured trace benchmark (v0.3.6)

The first reproducible measured-data experiment uses the HEATWISE AAU archive published on 16 September 2026 under CC BY 4.0. It does not distribute raw measurement data.

Source: Simon Pommerencke Melgaard, Thomas Juul, Jesper Ellerbæk Nielsen, Wojciech Szeliga, Ariel Oleksiak, Mustafa Kuzay and Ender Demirel, *Dataset for Field Validation of KPI-Informed Energy Efficiency Improvements in Two Small Data Centers*, [Zenodo DOI 10.5281/zenodo.22797095](https://doi.org/10.5281/zenodo.22797095). [Licence](https://creativecommons.org/licenses/by/4.0/).

Reproduce:

```sh
pip install ".[optimization]"
curl -fL https://zenodo.org/api/records/22797095/files/AAU.tar.xz/content -o /tmp/AAU.tar.xz
python scripts/benchmark_aau.py /tmp/AAU.tar.xz > /tmp/aau-results.json
```

The script checks the upstream MD5, records SHA-256, reads only named CSV members without extracting the archive, and rejects nonfinite values, gaps and impossible IT/total power relationships. It uses 16 separate 720-sample experiments, 11,520 observations in total.

## Held-out temperature prediction

Fit an empirical linear next-sample inlet-temperature predictor on 25%, 50%, and 75% IT load runs for each configuration. Predict the separate 100% run from current inlet temperature, cooling supply temperature and IT power only. No future observations or held-out samples determine the coefficients. Compare against persistence (current inlet temperature). No hyperparameter selection on held-out runs.

| Configuration | Held-out MAE (°C) | Persistence MAE (°C) |
|---|---:|---:|
| Baseline | 2.789 | 2.086 |
| Plate | 4.225 | 4.771 |
| Wall | 1.324 | 1.353 |
| Plate + wall | 1.204 | 1.338 |

The predictor fails to beat persistence in the baseline configuration. It must not be adopted as a safety controller or a calibrated physical model. The archive does not establish the time unit, power unit, isolated chiller electrical input or ambient boundary temperature. Thus it does not identify the physical thermal capacitance/conductance/COP parameters of the dispatch model. The calculated CoP column is not a substitute for measured chiller response.

## Measured variation replay

Use the four held-out total-site power traces, normalized to a median of 1 MW and **hypothetical** one-minute samples. Apply an illustrative 0.95 MW import cap for 120 samples. Compare no assets to an illustrative 0.5 MW / 1 MWh ideal battery with terminal recovery. The no-asset gap is cross-checked against direct numerical integration; the battery electrical and SOC balances are independently checked at every interval. The shared dispatch engine eliminates the gap within tolerance in all four modeled cases.

These are tests with measured demand variation and hypothetical units, equipment, tariffs and restrictions, not evidence that the AAU sites performed those flexibility actions. The committed [benchmark output](../benchmarks/aau-holdout-v1.json) contains only summary metrics, model coefficients, provenance and hashes, not raw observations.

The Frontier HPC archive metadata and CC BY 4.0 licence were reconfirmed, but the upstream download returned HTTP 403 on 24 November 2026. No Frontier result is reported. Physical parameter fitting with confirmed units and isolated measured actuator data, measured workload response, and actual site acceptance are still open.

## Physical-unit industrial demand replay

Source: Sathishkumar V E, Changsun Shin and Yongyun Cho (2021), *Steel Industry Energy Consumption*, [UCI DOI 10.24432/C52G8C](https://doi.org/10.24432/C52G8C), [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). The source identifies the steel facility in Gwangyang, South Korea; the 2018 dataset records 15-minute energy in kWh. The archive's midnight label is the final ordered reading of each source day (00:15 through 23:45 then 00:00); the importer checks the date and seconds-from-midnight against all 96 samples per day, without filling gaps. Convert each interval's energy to average MW using kWh / 1000 / 0.25 h. This is not instantaneous peak power.

Reproduce with an installed optimization environment:

```sh
curl -fL 'https://archive.ics.uci.edu/static/public/851/steel+industry+energy+consumption.zip' -o /tmp/steel.zip
python scripts/benchmark_steel.py /tmp/steel.zip
```

The pinned archive contains 35,040 intervals, 959.63671 MWh measured annual energy and 0.62872 MW maximum interval-average power. Replay the first seven days of each calendar month, 8,064 samples in total, with seven daily 10:00–14:00 restrictions per window at a hypothetical 0.15 MW cap. Use a hypothetical 0.3 MW / 0.6 MWh battery with 95% charge and discharge efficiency and full initial/terminal state of charge. Independent checks reconcile the measured energy, no-asset gap, every interval's electrical/SOC balance and battery limits, modeled gap, losses and terminal SOC. The baseline has 24.57368 MWh uncovered; the battery leaves 1.329863 MWh uncovered and meets all restrictions in only three of twelve windows. See [summary artifact](../benchmarks/steel-physical-v1.json). No raw measurements are distributed.

This is chronological perfect-foresight replay of measured demand, not measured battery response, a full-year dispatch test, a calibrated thermal model or field validation. The equipment, tariffs and grid restrictions are hypothetical, and no scale normalization is used. The physical-unit demand trace gate has evidence; actual actuator and workload calibration still require appropriate measurements.

## Physical-unit cooling equipment benchmark (conditional sensor mapping)

Source: Marika Pilou, George Kosmadakis and George Meramveliotakis (2023), *Measured data and calculations of pilot RES system for a 103-m2 building in Athens, Greece*, [Zenodo DOI 10.5281/zenodo.8012958](https://doi.org/10.5281/zenodo.8012958), [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). The related [pilot paper](https://doi.org/10.3390/en16124691) describes a reversible multi-source heat pump and water-side circuits. Reproduce using the exact checksum-pinned workbook:

```sh
pip install 'openpyxl>=3.1,<4'
curl -fL 'https://zenodo.org/api/records/8012958/files/Measured%20data%20and%20calculations%20of%20pilot%20RES%20system.xlsx/content' -o /tmp/athens.xlsx
python scripts/benchmark_athens.py /tmp/athens.xlsx
```

Use only the measured summer experiment sheet, not the simulation or demand input sheets. Validate all 1,441 one-minute timestamps including the end boundary, then integrate 24 complete active cycles (364 minutes). Total heat-pump electrical consumption, including auxiliaries and startup, is 13.476 kWh. Estimate signed water-side heat using 1.163 kWh/(m³ K) and volume flow times temperature difference. The workbook names the cold-side columns `cd` and hot-side columns `ev` in this cooling mode, opposite their thermodynamic roles. Pair flow and temperature by the workbook's common prefixes, explicitly as a conditional sensor-mapping hypothesis; do not silently reverse labels or treat the mapping as independently confirmed. No negative transient heat values are clipped. Maximum absolute hot-minus-cold-minus-electric cycle residual is 18.44% of electrical input; transient storage, auxiliary losses, sensor errors and mapping uncertainty are not resolved.

First 12 cycles fit one constant energy-weighted cooling COP (3.758); the remaining 12 yield a conditional COP of 3.792 and 1.515% aggregate absolute cycle-energy error (0.03486 kWh/cycle MAE). The fitted value is not used as a GridPass default. The [summary](../benchmarks/athens-cooling-v1.json) is reproducible and contains no raw measurements. This is a conditional equipment-level efficiency estimate from one day, not a zone thermal capacitance/conductance fit, a validated actuator map, a data-centre model or evidence of physical control. Confirm sensor mapping and collect independent measurements before operational use.

## ELF GPU actuation trace (offline benchmark)

Source: A. Apartsin and Y. Aperstein, ELF dataset v2.4, [Zenodo 23074732](https://doi.org/10.5281/zenodo.23074732), CSV data CC BY 4.0. Download `ELF_dataset.zip` from that record and run `python scripts/benchmark_elf.py ELF_dataset.zip`. The archive SHA-256 is pinned; no raw data or source measurement code is redistributed. The committed aggregate is `benchmarks/elf-actuation-v1.json`.

The 3,322 A10G telemetry samples cover ResNet50 and synthetic LLM decode workloads. For each downward cap change, measure elapsed time from the first sample reporting the new cap to the first sample after the final reading above cap plus max(2 W, 2%); require a subsequent observed suffix of at least one second. Censor incomplete steps. All six steps have sufficient observation; observed settling spans 101–1,893 ms. For the 105 W cap, observed settling is 1,125 ms for LLM decode and 1,893 ms for ResNet50. The respective final one-second median iteration times rise from 18.731 to 29.673 ms and 17.088 to 21.927 ms. These are descriptive single-run results, not a statistical bound or SLA. The source sampler updates its recorded cap after the command returns, so the command invocation-to-response latency is unknown. NVML board power is averaged telemetry; neither the instantaneous physical power nor site meter response is measured. Do not convert these values into a facility-wide reduction, a default ramp rate, an SLA guarantee or a field acceptance claim.
