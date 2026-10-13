"""Independent check of the round trip that does not use eppy or bdopt: a plain IDF tokenizer on both files.

usage: python raw_text_compare.py MODELS_DIR SAVED_DIR
Strips '!' comments, splits objects on ';' and fields on ',', and compares per class (case-insensitive): object counts,
then every field of every object in file order (strings equal after strip, or equal as floats). It also counts the
objects the file has per class so that a class eppy might drop (not in the IDD) cannot hide.
Works with any python 3; reads files as latin-1 (what bdopt writes).
"""
import collections, glob, os, sys


def parse(path):
    text = open(path, encoding='latin-1').read()
    clean = '\n'.join(l.split('!', 1)[0] for l in text.splitlines())
    out = []
    for chunk in clean.split(';'):
        chunk = chunk.strip()
        if not chunk:
            continue
        parts = [p.strip() for p in chunk.split(',')]
        out.append((parts[0].lower(), parts[1:]))
    return out


def same(a, b):
    if a == b:
        return True
    try:
        return float(a) == float(b)
    except ValueError:
        return False


def compare(pa, pb):
    A, B = parse(pa), parse(pb)
    ca, cb = collections.Counter(c for c, _ in A), collections.Counter(c for c, _ in B)
    res = {'objects': (len(A), len(B)), 'class_diffs': {c: (ca[c], cb[c]) for c in set(ca) | set(cb) if ca[c] != cb[c]}, 'field_diffs': []}
    byc_a, byc_b = collections.defaultdict(list), collections.defaultdict(list)
    for c, f in A: byc_a[c].append(f)
    for c, f in B: byc_b[c].append(f)
    fields = 0
    for c in byc_a:
        for i, (x, y) in enumerate(zip(byc_a[c], byc_b.get(c, []))):
            while x and x[-1] == '': x = x[:-1]
            while y and y[-1] == '': y = y[:-1]
            fields += max(len(x), len(y))
            if len(x) != len(y) or not all(same(p, q) for p, q in zip(x, y)):
                res['field_diffs'].append((c, i, x[:3], y[:3]))
    res['fields'] = fields
    res['classes'] = len(ca)
    return res


if __name__ == '__main__':
    for p in sorted(glob.glob(os.path.join(sys.argv[1], '*.idf'))):
        n = os.path.basename(p)
        r = compare(p, os.path.join(sys.argv[2], n))
        print('%-36s objects %5d -> %5d | classes %3d | class diffs %d | fields %6d | objects with field diffs %d' % (
            n, r['objects'][0], r['objects'][1], r['classes'], len(r['class_diffs']), r['fields'], len(r['field_diffs'])))
        for c, v in list(r['class_diffs'].items())[:5]: print('    class', c, v)
        for d in r['field_diffs'][:5]: print('    field', d)
