"""Offline GPU power-cap telemetry benchmark; not a facility control model."""
import argparse
import csv
import hashlib
import io
import itertools
import json
import math
from pathlib import Path
from statistics import median
from zipfile import ZipFile

SHA256 = 'a80774e59e046a10857bf34b01a123931e231fcc2bc440480e270304d300a96a'
FIELDS = ['gpu', 'workload', 't_ms', 'cap_set_w', 'power_w', 'util', 'iter_ms']


def read_runs(stream):
    reader = csv.DictReader(stream)
    if reader.fieldnames != FIELDS:
        raise ValueError('unexpected trace schema')
    runs = {}
    for row in reader:
        key = (row['gpu'], row['workload'])
        if not all(key):
            raise ValueError('missing trace identity')
        t, cap, power, util = (float(row[k]) for k in FIELDS[2:6])
        latency = float(row['iter_ms'])
        if (not all(map(math.isfinite, (t, cap, power, util))) or t < 0 or
                cap <= 0 or power < 0 or not 0 <= util <= 100 or
                (not math.isnan(latency) and (not math.isfinite(latency) or latency <= 0))):
            raise ValueError('invalid measurement')
        run = runs.setdefault(key, [])
        if run and not 0 < t - run[-1][0] <= 100:
            raise ValueError('nonmonotonic timestamp or >100 ms sampling gap')
        run.append((t, cap, power, latency))
    if not runs:
        raise ValueError('empty trace')
    return runs


def downsteps(run):
    """First observed new cap to first sample after the final exceedance.

    A sustained one-second suffix is required; unresolved steps are censored.
    The command invocation time is not observed. No interpolation is made.
    """
    segments = [list(g) for _, g in itertools.groupby(run, key=lambda r: r[1])]
    result = []
    for old, new in zip(segments, segments[1:]):
        cap = new[0][1]
        if cap >= old[0][1]:
            continue
        t0 = new[0][0]
        tolerance = max(2.0, cap * 0.02)
        violations = [i for i, row in enumerate(new) if row[2] > cap + tolerance]
        first = violations[-1] + 1 if violations else 0
        settling = (new[first][0] - t0 if first < len(new) and
                    new[-1][0] - new[first][0] >= 1000 else None)
        def tail(segment, column):
            values = [r[column] for r in segment if segment[-1][0]-r[0] <= 1000
                      and math.isfinite(r[column])]
            return median(values) if values else None
        result.append({'cap_w': cap, 'tolerance_w': tolerance,
                       'observed_settling_ms': settling,
                       'observed_window_ms': new[-1][0]-t0,
                       'previous_tail_power_w': tail(old, 2), 'tail_power_w': tail(new, 2),
                       'previous_tail_iteration_ms': tail(old, 3), 'tail_iteration_ms': tail(new, 3)})
    return result


def evaluate(runs):
    steps = [{'gpu': gpu, 'workload': workload, **step}
             for (gpu, workload), run in sorted(runs.items()) for step in downsteps(run)]
    return {'source_doi': '10.5281/zenodo.23074732', 'license': 'CC-BY-4.0',
            'sha256': SHA256, 'samples': sum(map(len, runs.values())), 'steps': steps,
            'censored_steps': sum(s['observed_settling_ms'] is None for s in steps),
            'facility_control_validated': False, 'command_latency_measured': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    args = parser.parse_args()
    if hashlib.sha256(args.archive.read_bytes()).hexdigest() != SHA256:
        raise ValueError('archive checksum mismatch')
    with ZipFile(args.archive) as z:
        names = [n for n in z.namelist() if n.endswith('/data/reaction_time.csv')]
        if len(names) != 1:
            raise ValueError('missing or ambiguous reaction trace')
        with z.open(names[0]) as f:
            result = evaluate(read_runs(io.TextIOWrapper(f, encoding='utf-8')))
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))


if __name__ == '__main__':
    main()
