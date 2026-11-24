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
