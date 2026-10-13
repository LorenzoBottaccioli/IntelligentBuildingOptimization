"""Write the geometry files (DXF and EIO) of EnergyPlus' ExampleFiles, design days only.

Each model gets `Output:Surfaces:Drawing, DXF, Triangulate3DFace` and `Output:Surfaces:List,
Details` (replacing its own), is expanded (-x) and run with -D. The platform's floor plan reads
exactly these two files (backend/floorplan.py). Only eplusout.dxf, eplusout.eio and the last lines
of eplusout.err are kept, so the work directory stays small.

    python tests/floorplan/generate_geometry.py --eplus C:\\EnergyPlusV9-6-0 --work %TEMP%\\geometry

The state of every model is written to <work>/status.json. Nothing here is imported by the platform.
"""

import argparse
import concurrent.futures as cf
import glob
import json
import os
import re
import shutil
import subprocess
import time

DROP = ('output:surfaces:drawing', 'output:surfaces:list')
ADD = ('Output:Surfaces:Drawing, DXF, Triangulate3DFace;\n'
       'Output:Surfaces:List, Details;\n')
KEEP = ('eplusout.dxf', 'eplusout.eio', 'eplusout.err')
DATA = ('.csv', '.dat', '.txt', '.cfg', '.epw', '.ddy', '.xml', '.json', '.tmy3')      # files an example reads next to itself
WEATHER = 'USA_CO_Golden-NREL.724666_TMY3.epw'      # models whose design days come from a weather file need one


def prepare(text):
    """The model without its own surface reports; ';' inside a comment is ignored."""
    flat = '\n'.join(line.split('!', 1)[0] for line in text.splitlines())
    kept = [o for o in re.split(r'(?<=;)', flat)
            if o.strip().split(',', 1)[0].strip().rstrip(';').lower() not in DROP]
    return ''.join(kept) + '\n' + ADD


def stage(eplus, idf, out, run_dir):
    """What an example finds around it in the install: `..\datasets` and the data files next to it."""
    datasets = os.path.join(out, 'datasets')
    if not os.path.exists(datasets):
        subprocess.run(['cmd', '/c', 'mklink', '/J', datasets, os.path.join(eplus, 'DataSets')],
                       capture_output=True) if os.name == 'nt' else os.symlink(os.path.join(eplus, 'DataSets'), datasets)
    src = os.path.dirname(idf)
    for f in os.listdir(src):
        if f.lower().endswith(DATA) and os.path.isfile(os.path.join(src, f)):
            shutil.copy(os.path.join(src, f), run_dir)


def run_one(eplus, exe, idf, work, retry):
    name = os.path.splitext(os.path.basename(idf))[0]
    out = os.path.join(work, name)
    marker = os.path.join(out, 'done')
    if os.path.exists(marker) and not (retry and open(marker).read() != 'ok'):
        return name, open(marker).read()
    os.makedirs(out, exist_ok=True)
    with open(idf, encoding='latin-1') as handle:
        text = handle.read()
    run_dir = os.path.join(out, 'run')
    os.makedirs(run_dir, exist_ok=True)
    stage(eplus, idf, out, run_dir)
    with open(os.path.join(run_dir, 'in.idf'), 'w', encoding='latin-1') as handle:
        handle.write(prepare(text))
    state = 'ok'
    try:
        subprocess.run([exe, '-D', '-x', '-w', os.path.join(eplus, 'WeatherData', WEATHER), '-d', run_dir,
                        os.path.join(run_dir, 'in.idf')],
                       cwd=run_dir, capture_output=True, timeout=300)
    except subprocess.TimeoutExpired:
        state = 'timeout'
    for f in KEEP:
        src = os.path.join(run_dir, f)
        if os.path.exists(src):
            shutil.copy(src, os.path.join(out, f))
    shutil.rmtree(run_dir, ignore_errors=True)
    if not os.path.exists(os.path.join(out, 'eplusout.dxf')):
        state = state if state != 'ok' else 'no dxf'
    elif not os.path.exists(os.path.join(out, 'eplusout.eio')):
        state = 'no eio'
    open(os.path.join(out, 'done'), 'w').write(state)
    return name, state


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--eplus', default=r'C:\EnergyPlusV9-6-0')
    parser.add_argument('--work', required=True)
    parser.add_argument('--workers', type=int, default=8)
    parser.add_argument('--limit', type=int, default=0, help='only the first N models (a trial)')
    parser.add_argument('--retry', action='store_true', help='run again the models that did not give a DXF last time')
    args = parser.parse_args()

    exe = os.path.join(args.eplus, 'energyplus.exe' if os.name == 'nt' else 'energyplus')
    files = sorted(glob.glob(os.path.join(args.eplus, 'ExampleFiles', '*.idf')))
    if args.limit:
        files = files[:args.limit]
    work = os.path.abspath(args.work)
    os.makedirs(work, exist_ok=True)
    started = time.time()
    status = {}
    with cf.ThreadPoolExecutor(args.workers) as pool:
        for i, (name, state) in enumerate(pool.map(lambda f: run_one(args.eplus, exe, f, work, args.retry), files), 1):
            status[name] = state
            if i % 25 == 0:
                print('{} / {} models, {:.0f} s'.format(i, len(files), time.time() - started), flush=True)
    with open(os.path.join(work, 'status.json'), 'w') as handle:
        json.dump(status, handle, indent=1)
    counts = {}
    for state in status.values():
        counts[state] = counts.get(state, 0) + 1
    print('ran {} models in {:.0f} s: {}'.format(len(status), time.time() - started, counts))


if __name__ == '__main__':
    main()
