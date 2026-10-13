"""Measure backend/floorplan.py on the geometry files of generate_geometry.py.

    python tests/floorplan/measure_floorplans.py --work %TEMP%\\geometry --out results.json [--gallery gallery.html]

Per model: the zones by kind (floor, derived, bbox, none), how many floor areas matched those of
EnergyPlus, the levels, and how much of the plan is covered by more than one zone (a grid of
GRID cells on the long side of each level). The models are then put in one class:

    complete   at least 95 % of the zones are `floor` and checked, no stacking;
    usable     at least 95 % of the zones have a place (floor, derived or bbox), no stacking;
    stacked    more than STACK_LIMIT of the covered plan is covered twice: zones drawn on top of each other;
    sparse     fewer than 95 % of the zones have a place;
    nothing    no zone at all, or no geometry file.
"""

import argparse
import importlib.util
import json
import os
import random
import sys

GRID = 120
STACK_LIMIT = 0.25                 # the corpus has a gap: 0.05 (an office inside a storage zone) and below, 0.55 (test rooms in a staircase)


def load_floorplan():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'backend', 'floorplan.py')
    spec = importlib.util.spec_from_file_location('floorplan', path)
    module = importlib.util.module_from_spec(spec)
    sys.modules['floorplan'] = module
    spec.loader.exec_module(module)
    return module


def _inside(x, y, poly):
    hit = False
    for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1]):
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            hit = not hit
    return hit


def stacked_share(plan, level):
    """Share of the covered cells of one level that more than one zone covers."""
    lv = next(l for l in plan['levels'] if l['index'] == level)
    x0, y0, x1, y1 = lv['bbox']
    size = max(x1 - x0, y1 - y0) / GRID
    if size <= 0:
        return 0.0
    count = {}
    for r in plan['zones']:
        if r['level'] != level:
            continue
        cells = set()
        for poly in r['polygons']:
            xs = [p[0] for p in poly]
            ys = [p[1] for p in poly]
            for i in range(int((min(xs) - x0) / size), int((max(xs) - x0) / size) + 1):
                for j in range(int((min(ys) - y0) / size), int((max(ys) - y0) / size) + 1):
                    if _inside(x0 + (i + .5) * size, y0 + (j + .5) * size, poly):
                        cells.add((i, j))
        for c in cells:
            count[c] = count.get(c, 0) + 1
    return sum(1 for n in count.values() if n > 1) / len(count) if count else 0.0


def measure(fp, folder):
    dxf, eio = os.path.join(folder, 'eplusout.dxf'), os.path.join(folder, 'eplusout.eio')
    if not (os.path.exists(dxf) and os.path.exists(eio)):
        return {'class': 'nothing', 'why': 'no geometry file'}
    plan = fp.build_plan(fp.read_dxf(dxf), fp.eio_tables(eio))
    zones = plan['zones']
    if not zones:
        return {'class': 'nothing', 'why': 'no zone'}, plan
    kinds = {k: sum(1 for z in zones if z['kind'] == k) for k in ('floor', 'derived', 'bbox', 'none')}
    checked = sum(1 for z in zones if z['checked'])
    stack = max([stacked_share(plan, l['index']) for l in plan['levels']] or [0.0])
    n = len(zones)
    placed = n - kinds['none']
    if stack > STACK_LIMIT:
        cls = 'stacked'
    elif placed < 0.95 * n:
        cls = 'sparse'
    elif checked >= 0.95 * n:
        cls = 'complete'
    else:
        cls = 'usable'
    per_level = [sum(1 for z in zones if z['level'] == l['index']) for l in plan['levels']]
    return {'class': cls, 'zones': n, 'kinds': kinds, 'checked': checked, 'levels': len(plan['levels']),
            'maxZonesPerLevel': max(per_level or [0]), 'stack': round(stack, 3),
            'unmatchedLayers': len(plan['unmatchedLayers'])}, plan


def gallery(fp, picks, plans, path):
    cells = []
    for name in picks:
        plan = plans[name]
        level = max(plan['levels'], key=lambda l: len(l['zones']))['index']
        cells.append('<figure><figcaption>{} ({} zones, {} levels)</figcaption>{}</figure>'.format(
            name, len(plan['zones']), len(plan['levels']), fp.plan_svg(plan, level, width=330, labels=False)))
    with open(path, 'w', encoding='utf-8') as handle:
        handle.write('<!doctype html><meta charset="utf-8"><style>body{font:12px sans-serif;display:flex;flex-wrap:wrap;'
                     'gap:10px;margin:10px}figure{margin:0;border:1px solid #ccc;padding:4px;width:340px}'
                     'figcaption{font-weight:600;margin-bottom:4px;overflow:hidden;text-overflow:ellipsis;'
                     'white-space:nowrap}svg{max-width:100%;height:auto}</style>' + ''.join(cells))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--work', required=True)
    parser.add_argument('--out', required=True)
    parser.add_argument('--gallery', default='')
    parser.add_argument('--picks', type=int, default=30)
    args = parser.parse_args()

    fp = load_floorplan()
    results, plans = {}, {}
    for name in sorted(os.listdir(args.work)):
        folder = os.path.join(args.work, name)
        if not os.path.isdir(folder):
            continue
        try:
            got = measure(fp, folder)
        except Exception as e:                                  # a file the reader cannot read is a result too
            results[name] = {'class': 'nothing', 'why': 'error: {}'.format(e)}
            continue
        if isinstance(got, tuple):
            results[name], plans[name] = got
        else:
            results[name] = got
    with open(args.out, 'w') as handle:
        json.dump(results, handle, indent=1)

    total = len(results)
    classes = {}
    for r in results.values():
        classes[r['class']] = classes.get(r['class'], 0) + 1
    print('{} models'.format(total))
    for cls in ('complete', 'usable', 'stacked', 'sparse', 'nothing'):
        print('  {:9s} {:4d}  {:5.1f} %'.format(cls, classes.get(cls, 0), 100 * classes.get(cls, 0) / total))
    drawn = [r for r in results.values() if 'zones' in r]
    zones = sum(r['zones'] for r in drawn)
    for kind in ('floor', 'derived', 'bbox', 'none'):
        print('  zones {:8s} {:6d}  {:5.1f} %'.format(kind, sum(r['kinds'][kind] for r in drawn),
                                                   100 * sum(r['kinds'][kind] for r in drawn) / zones))
    print('  floor areas matching EnergyPlus: {} of {} zones'.format(sum(r['checked'] for r in drawn), zones))
    levels = sorted(r['levels'] for r in drawn)
    per = sorted(r['maxZonesPerLevel'] for r in drawn)
    print('  levels per model: median {}, p90 {}, max {}'.format(levels[len(levels) // 2],
                                                                 levels[int(len(levels) * .9)], levels[-1]))
    print('  zones on the busiest level: median {}, p90 {}, max {}; above 40: {} models'.format(
        per[len(per) // 2], per[int(len(per) * .9)], per[-1], sum(1 for x in per if x > 40)))
    for cls in ('stacked', 'sparse', 'nothing'):
        names = [n for n, r in results.items() if r['class'] == cls]
        print('{}: {}'.format(cls, ', '.join(names[:25]) + (' ...' if len(names) > 25 else '')))
    if args.gallery:
        random.seed(1)
        pool = [n for n in plans if results[n]['class'] in ('complete', 'usable')]
        gallery(fp, sorted(random.sample(pool, min(args.picks, len(pool)))), plans, args.gallery)
        print('gallery:', args.gallery)


if __name__ == '__main__':
    main()
