"""Offline identification of the canonical single-zone thermal model.

Use only time-aligned, independently measured heat flows, not IT power or
calculated COP proxies. No fitted parameter is installed as a default.
"""
import argparse
import csv
import json
import math
from pathlib import Path

import numpy as np
from gridpass_flexibility.thermal import next_temperature

FIELDS = ("elapsed_s", "zone_c", "ambient_c", "heat_gain_mw", "heat_removed_mw")


def calibrate(rows, *, split, max_holdout_error_c):
    """Fit on the first split intervals; independently roll out the remainder."""
    data = np.asarray(rows, dtype=float)
    if data.ndim != 2 or data.shape[1] != 5 or not np.isfinite(data).all():
        raise ValueError("Expected finite time, zone, ambient and measured thermal MW")
    if type(split) is not int or split < 8 or len(data)-1-split < 8:
        raise ValueError("Need at least eight fit and eight holdout intervals")
    if not math.isfinite(max_holdout_error_c) or max_holdout_error_c <= 0:
        raise ValueError("Specify a positive holdout error limit in degrees Celsius")
    time, temp, ambient, heat, cooling = data.T
    steps = np.diff(time)
    if time[0] != 0 or steps[0] <= 0 or not np.all(steps == steps[0]):
        raise ValueError("Expected a complete uniformly sampled trace starting at zero")
    if (heat < 0).any() or (cooling < 0).any() or (temp < 0).any() or (temp > 100).any() or (abs(ambient) > 100).any():
        raise ValueError("Measurements outside model domain")
    dt = steps[0]/3600
    # delta T = (1-a)*(ambient-T) + b*(heat-cooling).
    # Normalize columns before SVD so units do not determine rank.
    x = np.column_stack((ambient[:-1]-temp[:-1], heat[:-1]-cooling[:-1]))[:split]
    y = np.diff(temp)[:split]
    scale = np.linalg.norm(x, axis=0)
    if np.any(scale <= 1e-12):
        raise ValueError("Insufficient independent thermal excitation")
    beta, _, rank, singular = np.linalg.lstsq(x/scale, y, rcond=None)
    if rank != 2 or singular[0]/singular[-1] > 1e4:
        raise ValueError("Thermal parameters are not independently identifiable")
    decay_loss, gain = beta/scale
    if not -1e-12 <= decay_loss < 1 or gain <= 0:
        raise ValueError("Nonphysical thermal fit")
    decay_loss = max(0., float(decay_loss))
    conductance = decay_loss/gain
    capacitance = dt/gain if decay_loss == 0 else -conductance*dt/math.log1p(-decay_loss)
    if not 1e-6 <= capacitance <= 1e8 or not math.isfinite(conductance):
        raise ValueError("Thermal fit outside evaluator domain")
    predicted = float(temp[split])
    errors, persistence_errors = [], []
    for i in range(split, len(data)-1):
        predicted = next_temperature(predicted, ambient[i], heat[i], cooling[i], 1.,
                                     capacitance, conductance, dt)
        errors.append(predicted-temp[i+1])
        persistence_errors.append(temp[split]-temp[i+1])
    max_error = float(np.max(np.abs(errors)))
    rmse = float(np.sqrt(np.mean(np.square(errors))))
    baseline = float(np.sqrt(np.mean(np.square(persistence_errors))))
    return {
        "thermal_capacitance_mwh_per_k": float(capacitance),
        "thermal_conductance_mw_per_k": float(conductance),
        "fit_intervals": split, "holdout_intervals": len(errors),
        "sample_seconds": float(steps[0]),
        "normalized_condition_number": float(singular[0]/singular[-1]),
        "fit_rmse_c": float(np.sqrt(np.mean(np.square(x @ (beta/scale)-y)))),
        "holdout_rollout_rmse_c": rmse, "holdout_rollout_max_error_c": max_error,
        "holdout_persistence_rmse_c": baseline,
        "holdout_error_limit_c": max_holdout_error_c,
        "holdout_pass": max_error <= max_holdout_error_c and rmse < baseline,
        "field_validated": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path)
    parser.add_argument("--split", type=int, required=True)
    parser.add_argument("--max-holdout-error-c", type=float, required=True)
    args = parser.parse_args()
    with args.csv.open(newline="") as f:
        reader = csv.reader(f)
        if tuple(next(reader, ())) != FIELDS:
            raise ValueError("Unexpected thermal calibration columns or units")
        rows = list(reader)
    result = calibrate(rows, split=args.split, max_holdout_error_c=args.max_holdout_error_c)
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0 if result["holdout_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
