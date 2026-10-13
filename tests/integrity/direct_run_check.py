"""EnergyPlus-only run: does the run IDF the platform builds change the physics?

Runs inside the backend container (cwd /app, the energyplus sidecar reachable), from the repo root:

    docker cp tests/integrity/direct_run_check.py backend:/app/direct_run_check.py
    docker exec backend python direct_run_check.py [MODEL.idf] [WEATHER.epw] [REFERENCE.sql]

For one model it builds the run IDF of backend/direct_run.py in several variants, runs each in the
energyplus sidecar and compares every stored point, step by step:

    week_prune        days 0-7, the model's own output requests dropped (what the Control room does)
    week_full         days 0-7, every output request of the model kept
    year_prune        days 0-365, the first week of it
    week_prune_1step  days 0-7 with Timestep 1 (a different timestep must give a different, never a failing, run)

Everything is compared with week_full; with REFERENCE.sql (an eplusout.sql of EnergyPlus run on the
untouched model for the same week, e.g. tests/integrity/ems_fidelity.py's) every variant is compared to
that too. A difference above TOL is printed as FAIL. The 10 Oct 2026 results are in results/.
"""
import glob
import os
import subprocess
import sys
import time

import direct_run
import idf_session

TOL = 1e-9
ENERGYPLUS = direct_run.ENERGYPLUS_BIN
WORK = os.path.join('simulation_outputs', 'direct_check')

model = sys.argv[1] if len(sys.argv) > 1 else idf_session.working_path()
epw = sys.argv[2] if len(sys.argv) > 2 else (sorted(glob.glob('uploads/*.epw')) or [None])[0]
reference = sys.argv[3] if len(sys.argv) > 3 else None
name = os.path.splitext(os.path.basename(model))[0]

VARIANTS = [
    ('week_prune', dict(timestep=6, startDay=0, warmupDays=0, endDay=7), True),
    ('week_full', dict(timestep=6, startDay=0, warmupDays=0, endDay=7), False),
    ('year_prune', dict(timestep=6, startDay=0, warmupDays=0, endDay=365), True),
    ('week_prune_1step', dict(timestep=1, startDay=0, warmupDays=0, endDay=7), True),
]


def run(tag, period, prune):
    folder = os.path.join(WORK, tag)
    os.makedirs(folder, exist_ok=True)
    target = os.path.join(folder, 'model.idf')
    plan = direct_run.build_run_idf(model, target, period, name, prune=prune)
    observable = [p for p in plan if p.get('query')]
    started = time.time()
    proc = subprocess.run(
        ['docker', 'exec', '-u', 'root', 'energyplus', ENERGYPLUS, '-d', '/workspace/' + folder.replace(os.sep, '/'),
         '-w', '/workspace/' + epw.replace(os.sep, '/'), '/workspace/' + target.replace(os.sep, '/')],
        capture_output=True, text=True)
    elapsed = time.time() - started
    severe, lines = direct_run._err_summary(os.path.join(folder, 'eplusout.err'))
    series, missing, _units = direct_run.read_series(os.path.join(folder, 'eplusout.sql'), observable)
    print('{:18s} exit {} {:5.1f}s severe {} points {}/{} not-reported {} not-observable {}'.format(
        tag, proc.returncode, elapsed, severe, len(series), len(observable), missing,
        [p['id'] for p in plan if not p.get('query')]))
    for line in lines:
        print('    ', line)
    return {pid: [v for *_, v in rows] for pid, rows in series.items()}, plan


def reference_series(plan, sql):
    series, _, _ = direct_run.read_series(sql, [p for p in plan if p.get('query')])
    return {pid: [v for *_, v in rows] for pid, rows in series.items()}


def compare(label, a, b, limit=None):
    worst, ok = 0.0, True
    for pid in sorted(set(a) & set(b)):
        n = min(len(a[pid]), len(b[pid])) if limit is None else limit
        if limit is None and len(a[pid]) != len(b[pid]):
            print('  {} {}: {} vs {} rows'.format(label, pid, len(a[pid]), len(b[pid])))
            ok = False
        diff = max((abs(x - y) for x, y in zip(a[pid][:n], b[pid][:n])), default=0.0)
        worst = max(worst, diff)
    print('  {:34s} max |diff| {:.3g}  {}'.format(label, worst, 'ok' if ok and worst <= TOL else 'FAIL'))
    return ok and worst <= TOL


results, plans = {}, {}
for tag, period, prune in VARIANTS:
    results[tag], plans[tag] = run(tag, period, prune)

base = results['week_full']
week = 7 * 24 * 6
print('\nagainst week_full:')
compare('week_prune', results['week_prune'], base)
compare('year_prune (first week)', {k: v[:week] for k, v in results['year_prune'].items()}, base)
if reference:
    ref = reference_series(plans['week_full'], reference)
    print('\nagainst the untouched model ({}):'.format(os.path.basename(reference)))
    for tag in ('week_prune', 'week_full'):
        compare(tag, results[tag], ref)
    compare('year_prune (first week)', {k: v[:week] for k, v in results['year_prune'].items()}, ref)
