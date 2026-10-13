"""Step 2 of the round trip (runs in backend:latest, python 3.9, eppy 0.5.63, IDD 9.6 -- the Model Editor stack).

usage: python roundtrip_compare.py MODELS_DIR SAVED_DIR [REPORT.json] [NAME_SUBSTRING]
(run with a hard time limit inside the container: timeout 900 python ...)
For every model: load the original and the bdopt-saved file with eppy (the way idf_session.py does), then compare
 - the number of objects per class (all classes),
 - every field of every object, class by class, objects paired by position within the class
   (a value counts as equal if the strings match after strip, or both parse as floats and are equal;
   trailing empty fields are ignored),
 - the same pairing by multiset when the order changed.
Classes the Model Editor reads or writes are flagged EDITOR in the report.
"""
import sys, os, glob, json, collections, time, gc
from eppy.modeleditor import IDF

IDD = os.environ.get('IDD_PATH', '/app/EnergyPlus-9-6-0/Energy+.idd')
IDF.setiddname(IDD)

EDITOR_PREFIXES = ('OUTPUT:', 'ENERGYMANAGEMENTSYSTEM:', 'EXTERNALINTERFACE', 'SCHEDULE', 'MATERIAL', 'WINDOWMATERIAL',
                   'CONSTRUCTION', 'WINDOWSHADINGCONTROL', 'BUILDINGSURFACE', 'FENESTRATIONSURFACE', 'LIGHTS',
                   'ELECTRICEQUIPMENT', 'PEOPLE', 'ZONEINFILTRATION', 'ZONEVENTILATION', 'ZONECONTROL', 'HVACTEMPLATE',
                   'ZONEHVAC', 'THERMOSTAT', 'DESIGNSPECIFICATION', 'ZONELIST', 'ZONE', 'SHADING', 'RUNPERIOD',
                   'TIMESTEP', 'BUILDING', 'SIMULATIONCONTROL', 'SITE:', 'GLOBALGEOMETRYRULES', 'VERSION')


def is_editor(cls):
    return cls.upper().startswith(EDITOR_PREFIXES)


def norm(v):
    if isinstance(v, str):
        return v.strip()
    return v


def same(a, b):
    a, b = norm(a), norm(b)
    if a == b:
        return True
    if isinstance(a, str) and isinstance(b, str) and a.upper() == b.upper() and False:
        return True
    try:
        return float(a) == float(b)
    except (TypeError, ValueError):
        return False


def rows(idf):
    out = collections.OrderedDict()
    for cls, objs in idf.idfobjects.items():
        if len(objs):
            out[cls.upper()] = [list(o.obj)[1:] for o in objs]
    return out


def trim(vals):
    vals = list(vals)
    while vals and (vals[-1] in ('', None)):
        vals.pop()
    return vals


def compare(path_a, path_b):
    t = time.time()
    # one IDF in memory at a time: two eppy models of the larger files do not fit in 1 GB together
    a = IDF(path_a); ra = rows(a); del a; gc.collect()
    b = IDF(path_b); rb = rows(b); del b; gc.collect()
    rep = {'load_s': round(time.time() - t, 1), 'objects_a': sum(map(len, ra.values())), 'objects_b': sum(map(len, rb.values())),
           'class_count_diffs': [], 'field_diffs': [], 'order_only_classes': [], 'fields_compared': 0, 'objects_compared': 0}
    for cls in sorted(set(ra) | set(rb)):
        na, nb = len(ra.get(cls, [])), len(rb.get(cls, []))
        if na != nb:
            rep['class_count_diffs'].append({'class': cls, 'original': na, 'saved': nb, 'editor': is_editor(cls)})
            continue
        la, lb = ra[cls], rb[cls]
        mismatched = False
        for i, (x, y) in enumerate(zip(la, lb)):
            x, y = trim(x), trim(y)
            rep['objects_compared'] += 1
            n = max(len(x), len(y))
            rep['fields_compared'] += n
            if len(x) != len(y) or any(not same(p, q) for p, q in zip(x, y)):
                mismatched = True
                bad = [(k, x[k] if k < len(x) else None, y[k] if k < len(y) else None) for k in range(n)
                       if k >= len(x) or k >= len(y) or not same(x[k], y[k])]
                rep['field_diffs'].append({'class': cls, 'index': i, 'name': x[0] if x else None, 'editor': is_editor(cls),
                                           'fields': [{'field': k, 'original': p, 'saved': q} for k, p, q in bad[:6]], 'n_bad': len(bad)})
        if mismatched:
            key = lambda v: json.dumps([str(norm(s)).upper() for s in trim(v)])
            if sorted(map(key, la)) == sorted(map(key, lb)):
                rep['order_only_classes'].append(cls)
    return rep


if __name__ == '__main__':
    src, dst = sys.argv[1], sys.argv[2]
    result = {}
    only = sys.argv[4] if len(sys.argv) > 4 else ''
    for p in sorted(glob.glob(os.path.join(src, '*.idf'))):
        if only not in os.path.basename(p):
            continue
        name = os.path.basename(p)
        q = os.path.join(dst, name)
        if not os.path.exists(q):
            print('MISSING saved file for', name)
            result[name] = {'error': 'saved file missing'}
            continue
        r = compare(p, q)
        result[name] = r
        ed = [d for d in r['field_diffs'] if d['editor']]
        print('%-40s objs %d -> %d | class count diffs %d (editor %d) | objects with field diffs %d (editor %d) | order-only classes %d | fields compared %d | load %.1fs'
              % (name, r['objects_a'], r['objects_b'], len(r['class_count_diffs']), sum(d['editor'] for d in r['class_count_diffs']),
                 len(r['field_diffs']), len(ed), len(r['order_only_classes']), r['fields_compared'], r['load_s']), flush=True)
    if len(sys.argv) > 3:
        with open(sys.argv[3], 'w') as h:
            json.dump(result, h, indent=1, default=str)
