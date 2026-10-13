"""Build the dictionaries (RDD, MDD, EDD) of EnergyPlus' ExampleFiles, design days only.

Each model gets `Output:VariableDictionary, Regular` and `Output:EnergyManagementSystem,
Verbose, Verbose, Verbose` (replacing its own), is expanded (-x) and run with -D, which takes
about a second for most of the 685 models of EnergyPlus 9.6 and about two minutes for the
hospitals. 628 of them produce dictionaries; the 57 that do not need a file next to the
input (Window5DataFile.dat, schedule CSVs, a weather file) or are parametric templates.

    python tests/instrumentation/generate_dictionaries.py --eplus C:\\EnergyPlusV9-6-0 \\
        --work /tmp/dicts --out tests/fixtures/dictionaries/sample.json.gz --every 8

The result is the input of measure_dictionaries.py. The full run writes about 4 GB under
--work (the .edd also holds the EMS runtime trace of models that have programs): delete it
afterwards. Nothing here is imported by the platform.
"""

import argparse
import concurrent.futures as cf
import glob
import gzip
import json
import os
import re
import subprocess
import time

DROP = ('output:variabledictionary', 'output:energymanagementsystem')
ADD = ('Output:VariableDictionary, Regular;\n'
       'Output:EnergyManagementSystem, Verbose, Verbose, Verbose;\n')
UNITS = re.compile(r'^(.*?)\s*\[(.*?)\]\s*$')


def prepare(text):
    """The model without its own dictionary objects; ';' inside a comment is ignored."""
    flat = '\n'.join(line.split('!', 1)[0] for line in text.splitlines())
    kept = [o for o in re.split(r'(?<=;)', flat)
            if o.strip().split(',', 1)[0].strip().rstrip(';').lower() not in DROP]
    return ''.join(kept) + '\n' + ADD


def run_one(exe, idf, work):
    name = os.path.splitext(os.path.basename(idf))[0]
    out = os.path.join(work, name)
    if os.path.exists(os.path.join(out, 'eplusout.rdd')):
        return name, 'cached'
    os.makedirs(out, exist_ok=True)
    with open(idf, encoding='latin-1') as handle:
        text = handle.read()
    with open(os.path.join(out, 'in.idf'), 'w', encoding='latin-1') as handle:
        handle.write(prepare(text))
    try:
        subprocess.run([exe, '-D', '-x', '-d', out, os.path.join(out, 'in.idf')],
                       cwd=out, capture_output=True, timeout=240)
    except subprocess.TimeoutExpired:
        return name, 'timeout'
    return name, 'ok' if os.path.exists(os.path.join(out, 'eplusout.rdd')) else 'no dictionary'


def read_rdd(path):
    rows = []
    for line in open(path, encoding='latin-1'):
        if line.startswith(('Program', 'Var Type')):
            continue
        parts = line.rstrip('\r\n').rstrip(',').split(',', 2)
        if len(parts) == 3:
            m = UNITS.match(parts[2].split('!')[0].strip())
            if m:
                rows.append([parts[0], parts[1], m.group(1).strip(), m.group(2)])
    return rows


def read_edd(path):
    rows = []
    with open(path, encoding='latin-1') as handle:
        for line in handle:
            if line.startswith('EnergyManagementSystem:Actuator Available'):
                p = [x.strip() for x in line.rstrip('\r\n').split(',')]
                if len(p) >= 5:
                    rows.append([','.join(p[1:-3]), p[-3], p[-2], p[-1].strip('[]')])
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--eplus', default=r'C:\EnergyPlusV9-6-0')
    parser.add_argument('--work', required=True)
    parser.add_argument('--out', required=True)
    parser.add_argument('--every', type=int, default=1, help='keep every N-th model in the output')
    parser.add_argument('--workers', type=int, default=6)
    args = parser.parse_args()

    exe = os.path.join(args.eplus, 'energyplus.exe' if os.name == 'nt' else 'energyplus')
    files = sorted(glob.glob(os.path.join(args.eplus, 'ExampleFiles', '*.idf')))
    work = os.path.abspath(args.work)
    started = time.time()
    with cf.ThreadPoolExecutor(args.workers) as pool:
        status = list(pool.map(lambda f: run_one(exe, f, work), files))
    print('ran {} models in {:.0f} s'.format(len(status), time.time() - started))

    corpus = {}
    for name, state in status:
        out = os.path.join(work, name)
        if not os.path.exists(os.path.join(out, 'eplusout.rdd')):
            continue
        mdd = os.path.join(out, 'eplusout.mdd')
        edd = os.path.join(out, 'eplusout.edd')
        corpus[name] = {'rdd': read_rdd(os.path.join(out, 'eplusout.rdd')),
                        'mdd': read_rdd(mdd) if os.path.exists(mdd) else [],
                        'edd': read_edd(edd) if os.path.exists(edd) else []}
    kept = dict(list(sorted(corpus.items()))[::args.every])
    opener = gzip.open if args.out.endswith('.gz') else open
    with opener(args.out, 'wt', encoding='utf-8') as handle:
        json.dump(kept, handle, separators=(',', ':'))
    print('{} models with dictionaries, {} written to {}'.format(len(corpus), len(kept), args.out))


if __name__ == '__main__':
    main()
