"""Replay a licensed, physical-unit industrial demand trace (no raw data committed)."""
import argparse
import csv
import hashlib
import io
import json
import math
from datetime import date, timedelta
from pathlib import Path
from zipfile import ZipFile

from gridpass_flexibility import __version__
from gridpass_flexibility.interface import evaluate_request

URL = "https://archive.ics.uci.edu/static/public/851/steel+industry+energy+consumption.zip"
SHA256 = "d82d28b33780ff1582507fcf08ae764ff648af459d58234370c551e62aadeaef"
DT = 0.25
CAP = 0.15
BATTERY = {"id":"battery","kind":"battery","power_mw":0.3,"energy_mwh":0.6,
           "charge_efficiency":0.95,"discharge_efficiency":0.95,
           "initial_mwh":0.6,"terminal_mwh":0.6}

def read_intervals(rows, start=date(2018,1,1), days=365):
    """Source labels 00:00 at the end of each day's 96 ordered readings."""
    values = []
    for i, row in enumerate(rows):
        if i >= days*96:
            raise ValueError("Extra interval")
        day = start + timedelta(days=i//96)
        seconds = ((i%96+1)*900)%86400
        expected = f"{day:%d/%m/%Y} {seconds//3600:02d}:{seconds%3600//60:02d}"
        if row["date"] != expected or int(row["NSM"]) != seconds:
            raise ValueError("Missing, duplicate or out-of-order interval")
        kwh = float(row["Usage_kWh"])
        if not math.isfinite(kwh) or kwh < 0:
            raise ValueError("Invalid interval energy")
        values.append(kwh)
    if len(values) != days*96:
        raise ValueError("Incomplete trace")
    return values

def read_archive(path):
    if path.stat().st_size > 1_000_000:
        raise ValueError("Archive too large")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != SHA256:
        raise ValueError("Archive checksum mismatch")
    with ZipFile(io.BytesIO(raw)) as z:
        entry = z.getinfo("Steel_industry_data.csv")
        if entry.file_size > 3_000_000:
            raise ValueError("CSV too large")
        with z.open(entry) as f:
            return read_intervals(csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig")))

def replay(kwh):
    if len(kwh) != 7*96:
        raise ValueError("Expected seven complete days")
    demand = [e / 1000 / DT for e in kwh]
    # Seven predetermined four-hour restrictions; no event selection from demand.
    events = [{"start":d*96+40,"end":d*96+56,"notice_minutes":0,"cap_mw":CAP}
              for d in range(7)]
    case = {"interval_hours":DT,"baseline_mw":demand,
            "normal_import_cap_mw":max(demand)+BATTERY["power_mw"],
            "price_eur_mwh":100,"events":events,"resources":[]}
    caps = [CAP if 40 <= i%96 < 56 else case["normal_import_cap_mw"]
            for i in range(len(demand))]
    expected = math.fsum(max(0,p-c)*DT for p,c in zip(demand,caps))
    bare = evaluate_request("dispatch",case)
    modeled = evaluate_request("dispatch",{**case,"resources":[BATTERY]})
    if bare["status"] != "solved" or modeled["status"] != "solved":
        raise RuntimeError("Dispatch did not solve")
    if abs(bare["uncovered_mwh"]-expected)>1e-6:
        raise RuntimeError("No-asset energy gap mismatch")
    schedule = modeled["schedule"]
    trace = schedule["resources"]["battery"]
    prev = BATTERY["initial_mwh"]
    gap = 0.0
    losses = 0.0
    for p,cap,grid,ch,dis,soc in zip(demand,caps,schedule["grid_import_mw"],
            trace["charge_mw"],trace["discharge_mw"],trace["soc_mwh"]):
        if (abs(grid+dis-ch-p)>1e-6 or
            abs(prev+DT*(ch*0.95-dis/0.95)-soc)>1e-6 or
            not -1e-6 <= soc <= 0.600001 or
            not -1e-6 <= ch <= 0.300001 or not -1e-6 <= dis <= 0.300001):
            raise RuntimeError("Physical balance or battery bound mismatch")
        gap += max(0,grid-cap)*DT
        losses += DT*(ch*(1-0.95)+dis*(1/0.95-1))
        prev = soc
    if abs(prev-0.6)>1e-6 or abs(gap-modeled["uncovered_mwh"])>1e-6:
        raise RuntimeError("Terminal SOC or gap mismatch")
    grid_energy = math.fsum(schedule["grid_import_mw"])*DT
    measured_energy = math.fsum(kwh)/1000
    if abs(grid_energy-measured_energy-losses)>1e-5:
        raise RuntimeError("Integrated measured energy mismatch")
    return {"measured_mwh":measured_energy,"peak_mw":max(demand),
            "no_asset_gap_mwh":expected,"battery_gap_mwh":gap,
            "battery_feasible":modeled["feasible"],"battery_losses_mwh":losses,
            "grid_mwh":grid_energy,"terminal_soc_mwh":prev,
            "baseline_evidence":bare["evidence"],"battery_evidence":modeled["evidence"]}

def benchmark(path):
    kwh = read_archive(path)
    windows = {}
    for month in range(1,13):
        day = date(2018,month,1)
        offset = (day-date(2018,1,1)).days*96
        windows[day.isoformat()] = replay(kwh[offset:offset+7*96])
    return {"benchmark_version":"steel-physical-v1","engine_version":__version__,
            "source":{"doi":"10.24432/C52G8C","url":URL,"sha256":SHA256,
                      "license":"CC BY 4.0","creators":"Sathishkumar V E, Changsun Shin, Yongyun Cho"},
            "annual_samples":len(kwh),"annual_measured_mwh":math.fsum(kwh)/1000,
            "annual_peak_interval_average_mw":max(kwh)/1000/DT,
            "interval_hours":DT,"simulated_cap_mw":CAP,"simulated_battery":BATTERY,
            "windows":windows,
            "limitations":"Measured demand only; first seven days of each month, hypothetical battery, cap and tariffs, perfect foresight. No measured flexibility response, physical thermal calibration or field acceptance."}

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive",type=Path)
    print(json.dumps(benchmark(parser.parse_args().archive),sort_keys=True,indent=2,allow_nan=False))
