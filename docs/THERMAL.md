# Physical cooling and renewable generation (v0.3.4)

Use the ordinary chronological scenario and the existing `dispatch` or `causal` operation. No separate solver or MCP tool is required.

```sh
gridpass-flexibility --dispatch examples/thermal-dispatch.json
```

## Electrical boundary

The site baseline is gross electrical demand before the modeled generation or load adjustments. It includes baseline cooling. The new optional scenario-level `protected_load_mw` (number or interval array, default zero) is the portion of non-cooling demand that cannot be deferred. Baseline cooling and protected load must be disjoint and their sum must not exceed baseline demand. All workload-shift resources share the remaining demand limit. They cannot defer the protected or baseline cooling load. Protected demand can still be supplied by onsite generation and storage.

At each interval the model subtracts declared baseline cooling and adds the actual cooling electrical consumption, adds battery charging and workload recovery, and subtracts generation, battery discharge and approved workload shifting. Grid import must be nonnegative; export is not supported. A protected load is a scheduling constraint, not a redundant power-supply or uptime guarantee.

## Thermal resource

Choose resource kind `thermal_cooling`. The older `cooling` kind remains an energy-shifting proxy; it does not impose a temperature constraint.

Required resource fields:

| Field | Unit | Meaning |
|---|---|---|
| id | — | Unique resource identifier |
| power_mw | MW electrical | Rated cooling input power |
| baseline_cooling_mw | MW electrical | Cooling power already included in site baseline; scalar or time series |
| thermal_capacitance_mwh_per_k | MWh thermal/K | Effective lumped sensible heat capacitance |
| thermal_conductance_mw_per_k | MW thermal/K | Heat exchange with ambient; zero allowed |
| ambient_c | °C | Outside or boundary temperature; scalar or time series |
| heat_gain_mw | MW thermal | Internal sensible heat load; scalar or time series |
| cop | MW thermal/MW electrical | Heat removed per electrical input; scalar or time series |
| min_temp_c | °C | Lower operating temperature |
| max_temp_c | °C | Upper operating temperature |
| initial_temp_c | °C | Temperature at start of first interval |

Optional fields: `terminal_max_temp_c` (default initial temperature), `availability` (fraction of rated electrical input), `response_minutes` (delay before reducing cooling below baseline when available), and `variable_cost_eur_mwh` (non-electric marginal cost per MWh of actual cooling electricity). Electricity itself is included in the grid import cost. Zone temperature bounds are 0–100 °C, suitable for the intended sensible cooling abstraction; ambient input may be negative.

## Heat balance

For temperature T, ambient A, effective heat capacity C, thermal conductance U, heat gain Q, cooling electrical input P and coefficient of performance k:

```
C dT/dt = U (A - T) + Q - k P
a = exp(-U dt / C)
b = (1 - a) / U
T_next = a T + (1 - a) A + b (Q - k P)
```

For U = 0, a = 1 and b = dt/C. The implementation uses the numerically stable exponential formula. Inputs and electrical action are constant over each interval; exact integration then gives a linear equality in the shared HiGHS model. The temperature is monotonic within each such interval, so bounding both endpoints also bounds the modeled within-interval trajectory. This is not a guarantee for unobserved disturbances or equipment transients.

The cooling limit is rated MW multiplied by availability. Temperature bounds and terminal recovery are hard constraints in chronological dispatch. When a cooling outage makes the thermal bounds impossible, the solver reports failure; it does not silently violate the temperature constraint to meet an import cap. In causal replay, observed temperature carries between samples and ambient, internal gains, COP and baseline cooling use current-value persistence, not future measurements. The real terminal temperature target is checked separately; outside events the recovery objective includes thermal deficits scaled by capacitance (MWh thermal) together with electrical storage deficits (MWh electrical). These are policy weights, not a physical equivalence between heat and electricity. A failed forecast stops the replay with the last executed state; safe fallback remains open.

## Renewable resource

Choose `renewable` with rated `power_mw`, `availability` (exogenous interval capacity factor, 0–1), and optional variable cost per generated MWh. It has no modeled dispatchable fuel, ramp, start or response delay. Generation can be curtailed. Excess generation cannot be exported. Use a measured or modeled irradiance/wind-to-power trace for availability; this model does not infer weather. Causal replay sees only current availability and uses persistence. Outputs include generated and curtailed energy.

## Synthetic verification

The example starts at 22 °C, includes 2 MW baseline cooling in a 10 MW facility, and uses a 4 MW chiller, COP 2, 4 MW heat gain and 2 MWh/K capacitance. It can pre-cool to 20 °C, then switch cooling off for two one-hour intervals at an 8 MW import cap. Temperature rises to 24 °C and the schedule restores 22 °C by the end. The exact heat balance, import balance, energy consumption, response delay, protected load accounting, outage failure and recovery checks are tested. A causal test with no spare import headroom before an unannounced event reports a 2 MWh gap instead of claiming perfect-foresight feasibility.

These are synthetic checks of equations and implementation. Actual calibration requires a control-volume definition, temperature measurements, electrical cooling input, ambient or boundary temperature, internal heat generation, and operating regime with independent validation. Workload heat gains are exogenous here; they do not automatically fall when workload is deferred. There is no airflow, humidity, liquid-loop, thermal-gradient, chiller cycling, changing setpoint or protected IT service model. COP and heat gain are input traces, not inferred. Do not substitute this single-zone abstraction for a facility thermal safety assessment.

## Public measured validation candidates

The upstream metadata of [Frontier HPC & Facility Data v4](https://doi.org/10.6084/m9.figshare.24391240.v4) identifies CC BY 4.0, a 20,164,974-byte XLSX file and MD5 f1832f7215e529f12f38d4087620d6e2. The [associated paper](https://doi.org/10.1038/s41597-024-03913-w) describes 10-minute measured compute/accessory power, coolant temperatures and flow; approximately 440 hours of the year are missing. This is a candidate for measured demand replay, not a measured single-zone chiller step-response dataset.

[Field Validation of KPI-Informed Energy Efficiency Improvements in Two Small Data Centers](https://doi.org/10.5281/zenodo.22797095) (Zenodo metadata checked 2026-11-24, CC BY 4.0) includes measured AAU inlet/outlet/supply/return temperatures and IT and total-site power across configurations. It also contains calculated COP and KPIs. Check measurement cadence, units, cooling electrical boundary, heat gains and ambient data before attempting physical calibration. No third-party data have been redistributed or used to fit this release. Measured calibration and held-out replay remain release gates.

## Offline parameter identification

`scripts/calibrate_thermal.py` estimates the same single-zone model's C and U from a uniformly sampled, time-aligned control-volume trace. Install the optimization extra. Supply a CSV with header `elapsed_s,zone_c,ambient_c,heat_gain_mw,heat_removed_mw`. Temperature is measured at the interval boundary; both heat flows and ambient temperature describe the following interval under the zero-order-hold approximation. Heat flows are **thermal MW**, not IT electrical load, electrical cooling input or an inferred COP. The final row supplies the terminal measured temperature (all fields must be finite). The user must independently establish the sensor mapping, units and heat-flow boundary.

```sh
python scripts/calibrate_thermal.py trace.csv --split 24 --max-holdout-error-c 0.5
```

Choose the split and error threshold before inspecting holdout outcomes. Regress the measured temperature increment on ambient-minus-zone temperature and net heat input, using only the first split intervals. SVD checks the column-normalized design matrix for rank and a condition number no greater than 10,000. Reject nonphysical coefficients instead of forcing them to a physical value (except roundoff at zero conductance). Transform the exact discrete coefficients to C and U. Starting once from the measured split boundary, roll out the canonical heat balance with held-out measured disturbances, never resetting to held-out temperature samples. Report fit error, holdout maximum error and RMSE, and persistence RMSE. A holdout pass needs both the declared error tolerance and improvement over persistence. This is a prediction test with known exogenous inputs, not a causal forecast or a safety bound. The script exits nonzero on failed validation. There are no production defaults or new MCP operations.

Independent analytic fixtures recover 1.7 MWh/K and 0.35 MW/K, and the zero-conductance case. Tests reject rank deficiency, gaps, nonfinite measurements and negative heat gain coefficients, and verify that holdout drift cannot change the fit or pass validation.

The available AAU, Athens and Melbourne traces do not establish all the independent heat-flow and boundary-temperature channels needed here. In particular, [Melbourne cloud telemetry](https://doi.org/10.5281/zenodo.10069402) (CC BY 4.0, Shashikant Ilager et al., UCC 2023) provides host IPMI power and server temperatures, not measured zone cooling heat flow. Do not infer a facility C or U from it. No measured zone calibration is claimed; a suitable physical trace and independent field validation remain required.
