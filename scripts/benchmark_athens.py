"""Conditional cooling-efficiency benchmark; no third-party samples redistributed."""
import argparse
from datetime import datetime, timedelta
import hashlib
import json
import math
from pathlib import Path

SHA256 = 'be6b34ac0ba9f8f4c908d74892b0e77fdb872fd114a674b3ce81309db3bec395'
SHEET = '05-Aug-2022 - Experiment'
# Approximate volumetric heat capacity of water, kWh/(m3 K).
WATER = 1.163
FIELDS = ('Date - Time', 'MODE', 'HP_Flag_exp', 'HP_Source_exp',
          'T_cd_in_exp [oC]', 'T_cd_out_exp [oC]', 'T_ev_in_exp [oC]',
          'T_ev_out_exp [oC]', 'VFR_cd_exp [m3/h]', 'VFR_ev_exp [m3/h]',
          'e_sysHP_exp [kW]')


def read_cycles(rows, start=datetime(2022, 8, 5), minutes=1440):
    """Use signed water-loop energy and total electrical energy, including startup."""
    header = next(rows)
    if any(header.count(f) != 1 for f in FIELDS):
        raise ValueError('Missing or duplicate measured column')
    idx = [header.index(f) for f in FIELDS]
    cycles, active = [], []
    count = 0
    for i, row in enumerate(rows):
        count += 1
        if i > minutes:
            raise ValueError('Extra sample')
        t, mode, flag, source, ci, co, hi, ho, cf, hf, p = [row[j] for j in idx]
        if t != start + timedelta(minutes=i) or mode != 'COOL':
            raise ValueError('Unexpected timestamp or mode')
        if not all(isinstance(v, (int, float)) and math.isfinite(v)
                   for v in (ci, co, hi, ho, cf, hf, p)) or min(cf, hf, p) < 0:
            raise ValueError('Invalid measurement')
        if flag == 'OFF' and source == 'OFF' and cf == hf == p == 0:
            if active:
                cycles.append(summarize(active))
                active = []
        elif flag == 'BSPC' and source == 'BTES' and min(cf, hf, p) > 0:
            if i in (0, minutes):
                raise ValueError('Partial cycle at boundary')
            # Workbook port names are reversed relative to thermodynamic roles
            # in this cooling mode. Treat the same-prefix flow pairing as a
            # hypothesis, not an independently established sensor mapping.
            active.append((WATER*cf*(ci-co)/60, WATER*hf*(ho-hi)/60, p/60))
        else:
            raise ValueError('Unknown mode, flow or electrical state')
    if count != minutes+1 or active:
        raise ValueError('Incomplete day or active cycle')
    return cycles


def summarize(samples):
    cold, hot, elec = (math.fsum(x) for x in zip(*samples))
    if min(cold, hot, elec) <= 0:
        raise ValueError('Non-positive cycle energy')
    return {'minutes': len(samples), 'cold_kwh': cold, 'hot_kwh': hot,
            'electric_kwh': elec, 'cop': cold/elec,
            'balance_residual_kwh': hot-cold-elec}


def metrics(cycles):
    if len(cycles) < 4:
        raise ValueError('Insufficient complete cycles')
    train, holdout = cycles[:len(cycles)//2], cycles[len(cycles)//2:]
    cop = sum(x['cold_kwh'] for x in train)/sum(x['electric_kwh'] for x in train)
    errors = [cop*x['electric_kwh']-x['cold_kwh'] for x in holdout]
    return {'fit_cycles': len(train), 'holdout_cycles': len(holdout),
            'fit_cop': cop, 'holdout_cop': sum(x['cold_kwh'] for x in holdout)/sum(x['electric_kwh'] for x in holdout),
            'holdout_mae_kwh_per_cycle': sum(map(abs,errors))/len(errors),
            'holdout_absolute_relative_energy_error': sum(map(abs,errors))/sum(x['cold_kwh'] for x in holdout),
            'all_electric_kwh': sum(x['electric_kwh'] for x in cycles),
            'all_cold_kwh': sum(x['cold_kwh'] for x in cycles),
            'active_minutes': sum(x['minutes'] for x in cycles),
            'max_abs_cycle_balance_residual_over_electric': max(abs(x['balance_residual_kwh'])/x['electric_kwh'] for x in cycles),
            'mapping_verified': False, 'site_control_validated': False}


def run(path):
    if path.stat().st_size > 2_000_000 or hashlib.sha256(path.read_bytes()).hexdigest() != SHA256:
        raise ValueError('Workbook checksum mismatch')
    from openpyxl import load_workbook
    workbook = load_workbook(path, read_only=True, data_only=True)
    try:
        cycles = read_cycles(iter(workbook[SHEET].values))
    finally:
        workbook.close()
    return {'source_doi': '10.5281/zenodo.8012958', 'license': 'CC-BY-4.0',
            'sha256': SHA256, 'water_kwh_m3_k': WATER, **metrics(cycles)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('workbook', type=Path)
    print(json.dumps(run(parser.parse_args().workbook), indent=2, sort_keys=True))
