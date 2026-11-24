"""Offline, reproducible HEATWISE AAU empirical holdout and normalized dispatch.

No data download occurs implicitly. No raw data are written to the repository.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import tarfile

import numpy as np
from gridpass_flexibility.interface import evaluate_request
from gridpass_flexibility import __version__

MD5 = "13d33d17938006a0055d79652c982dd9"
DOI = "10.5281/zenodo.22797095"
CONFIGS = ("Baseline", "Plate", "Wall", "PlateWall")
LOADS = (25, 50, 75, 100)
FIELDS = ("time", "Inlet Temp Avg", "Cooling Supply Average", "P_IT", "P_DC")
URL = "https://zenodo.org/api/records/22797095/files/AAU.tar.xz/content"

def read_runs(path):
    raw = Path(path).read_bytes()
    if hashlib.md5(raw).hexdigest() != MD5:
        raise ValueError("AAU archive checksum does not match the pinned dataset")
    runs = {}
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:xz") as archive:
        for config in CONFIGS:
            for load in LOADS:
                member = archive.getmember(f"AAU/{config}Test_{load}percent.csv")
                if not member.isfile() or member.size > 1_000_000:
                    raise ValueError("Invalid archive member")
                with archive.extractfile(member) as stream:
                    rows = list(csv.DictReader(io.TextIOWrapper(stream, encoding="utf-8-sig")))
                matrix = np.asarray([[float(row[k]) for k in FIELDS] for row in rows])
                validate_run(matrix)
                runs[(config,load)] = matrix
    return runs, hashlib.sha256(raw).hexdigest()

def validate_run(a):
    if a.shape != (720,5) or not np.isfinite(a).all():
        raise ValueError("Expected 720 finite measurements and five columns")
    if not np.array_equal(a[:,0],np.arange(720)*2):
        raise ValueError("Unexpected sample index spacing; do not silently fill gaps")
    if np.any(a[:,3] < 0) or np.any(a[:,4] <= 0) or np.any(a[:,3] > a[:,4]):
        raise ValueError("Invalid IT/site power relationship")

def features(a,scale):
    # Only contemporaneous features. Predict next observation, never use it as an input.
    return np.column_stack((np.ones(len(a)-1), a[:-1,1], a[:-1,2],a[:-1,3]/scale)),a[1:,1]

def fit_holdout(train,test):
    scale = float(np.median(np.concatenate([a[:,4] for a in train])))
    X,y = zip(*(features(a,scale) for a in train))
    design = np.concatenate(X)
    target = np.concatenate(y)
    weights,_,rank,_ = np.linalg.lstsq(design,target,rcond=None)
    if rank != design.shape[1]:
        raise ValueError("Empirical temperature predictors are not identifiable")
    xx,yy = features(test,scale)
    errors=xx@weights-yy
    persistence=test[:-1,1]-yy
    return {"training_samples":len(target),"heldout_samples":len(yy),
            "coefficients":weights.tolist(),"training_site_power_median_source_units":scale,
            "heldout_mae_c":float(np.mean(np.abs(errors))),
            "heldout_rmse_c":float(np.sqrt(np.mean(errors**2))),
            "persistence_mae_c":float(np.mean(np.abs(persistence))),
            "persistence_rmse_c":float(np.sqrt(np.mean(persistence**2)))}

def normalized_dispatch(a):
    # Upstream record does not specify physical power units or time unit.
    # Preserve measured variation, but use an explicitly hypothetical scale/time.
    normalized = a[:,4] / float(np.median(a[:,4]))
    dt = 1/60
    cap = 0.95
    start,end=240,360
    case={"interval_hours":dt,"baseline_mw":normalized.tolist(),
          "normal_import_cap_mw":float(max(normalized))+0.5,"price_eur_mwh":100,
          "events":[{"start":start,"end":end,"notice_minutes":0,"cap_mw":cap}],
          "resources":[]}
    expected=float(np.maximum(0,normalized[start:end]-cap).sum()*dt)
    bare=evaluate_request("dispatch",case)
    if bare["status"]!="solved" or not math.isclose(bare["uncovered_mwh"],expected,abs_tol=1e-6):
        raise RuntimeError("Independent no-resource energy balance failed")
    battery={"id":"battery","kind":"battery","power_mw":0.5,"energy_mwh":1,
             "charge_efficiency":1,"discharge_efficiency":1,"initial_mwh":1,"terminal_mwh":1}
    modeled=evaluate_request("dispatch",{**case,"resources":[battery]})
    if modeled["status"]!="solved":raise RuntimeError("Modeled dispatch failed")
    # Verify physical electrical balance and state progression independently.
    trace=modeled["schedule"]["resources"]["battery"];prev=1.0
    for demand,grid,charge,discharge,soc in zip(normalized,modeled["schedule"]["grid_import_mw"],
            trace["charge_mw"],trace["discharge_mw"],trace["soc_mwh"]):
        if abs(grid+discharge-charge-demand)>1e-5 or abs(prev+dt*(charge-discharge)-soc)>1e-5:
            raise RuntimeError("Battery replay conservation failed")
        prev=soc
    return {"sample_count":len(a),"assumed_interval_hours":dt,"assumed_median_mw":1,
            "event_start_sample":start,"event_end_sample_exclusive":end,"assumed_cap_mw":cap,
            "no_asset_uncovered_mwh":bare["uncovered_mwh"],"independent_uncovered_mwh":expected,
            "battery_uncovered_mwh":modeled["uncovered_mwh"],"battery_feasible":modeled["feasible"],
            "baseline_evidence":bare["evidence"],"battery_evidence":modeled["evidence"]}

def benchmark(path):
    runs,sha=read_runs(path)
    holdouts={}
    dispatch={}
    for config in CONFIGS:
        test=runs[config,100]
        holdouts[config]=fit_holdout([runs[config,l] for l in LOADS[:-1]],test)
        dispatch[config]=normalized_dispatch(test)
    return {"benchmark_version":"aau-holdout-v1","engine_version":__version__,
            "source":{"doi":DOI,"url":URL,"license":"CC BY 4.0","md5":MD5,"sha256":sha,
                      "creators":"Simon Pommerencke Melgaard, Thomas Juul, Jesper Ellerbæk Nielsen, Wojciech Szeliga, Ariel Oleksiak, Mustafa Kuzay, Ender Demirel"},
            "split":"Separate runs: 25/50/75% IT load training; 100% held out per configuration.",
            "measured_samples":sum(len(a) for a in runs.values()),"temperature_holdouts":holdouts,
            "normalized_dispatch":dispatch,
            "limitations":"Empirical one-sample temperature prediction, not identification of physical capacitance, COP or conductance. Source time and power units unconfirmed. Dispatch preserves measured variation but uses hypothetical 1 MW median and one-minute intervals, assets and caps. No measured response to flexibility events or field validation."}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("archive",type=Path)
    args=p.parse_args()
    print(json.dumps(benchmark(args.archive),indent=2,sort_keys=True,allow_nan=False))

if __name__=="__main__":main()
