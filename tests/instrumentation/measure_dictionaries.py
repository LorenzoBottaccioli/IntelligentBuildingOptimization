"""Measure the EnergyPlus dictionaries (RDD, MDD, EDD) of a corpus of models.

Research tool for the Sensors & actuators redesign: it answers, with numbers from real
files, how long the lists the picker would show are, which units and name tokens the
grouping rules must cover, and where those rules fail. Nothing here is imported by the
platform; the rules proved here are meant to be ported to frontend/src/outputGroups.js.

Input: a JSON (optionally .gz) file {model: {"rdd": [[varType, reportType, name, units]],
"mdd": [...same...], "edd": [[component, type, control, units]]}} built by
tests/instrumentation/generate_dictionaries.py from EnergyPlus' ExampleFiles.

    python tests/instrumentation/measure_dictionaries.py tests/fixtures/dictionaries/sample.json.gz

The IDD (for the meter vocabularies) is read with backend/idd_schema.py; give its path
with --idd or the IDD_PATH environment variable.
"""

import argparse
import collections
import gzip
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'backend'))

# Unit string of the RDD -> quantity. The strings are exactly those of
# OutputProcessor::Unit in EnergyPlus 9.6 (SetupOutputVariables.csv in the install
# directory lists the enum of every SetupOutputVariable call; the join by variable name
# gave one enum per string on 628 models).
KIND_OF_UNIT = {}
for _kind, _units in (
    ('Temperature', ('C', 'deltaC')),
    ('Power and energy', ('W', 'J', 'W/m2', 'J/m2')),
    ('Flow and speed', ('m3/s', 'kg/s', 'kgWater/s', 'kmol/s', 'ach', 'kg/m2-s', 'm/s', 'rev/min')),
    ('Humidity and CO2', ('kgWater/kgDryAir', '%', 'ppm', 'kg/kg')),
    ('Light', ('lux', 'cd/m2', 'lum/W')),
    ('Time and angle', ('hr', 'min', 's', 'deg', 'rad')),
    ('Mass, volume, pressure', ('m3', 'kg', 'L', 'Pa', 'kg/m3', 'm', 'm2')),
    ('Coefficients', ('W/m2-K', 'W/K', 'W/W', 'J/kg', 'J/kg-K', 'W/m-K', 'K/m', 'clo', 'J/kgWater',
                     'K/W', 'W/m2-C', 'Btu/h-W')),
    ('Electrical', ('A', 'V', 'Ah')),
    ('Status and counts', ('', 'ON/OFF')),
):
    for _u in _units:
        KIND_OF_UNIT[_u] = _kind

# EDD unit strings are not those of the RDD ('[ ]', 'fraction', 'on/off', 'unknown'...).
EDD_KIND_OF_UNIT = {
    'C': 'Temperature', 'W': 'Power', 'W/m2': 'Power', 'kg/s': 'Flow', 'm3/s': 'Flow',
    'm/s': 'Weather and wind', 'deg': 'Weather and wind', 'degree': 'Weather and wind',
    'kgWater/kgDryAir': 'Humidity', '%': 'Humidity', 'each': 'People and counts',
    'W/m2-K': 'Surface properties', 'W/m-K': 'Surface properties', 'J/kg-C': 'Surface properties',
    'Pa': 'Pressure', 'W/W': 'Efficiency', 'fraction': 'Fractions and status', 'Fraction': 'Fractions and status',
    'on/off': 'Fractions and status', 'ShadeStatus': 'Fractions and status', 'integer': 'Fractions and status',
    'degrees': 'Weather and wind',
    '': 'Needs control type', ' ': 'Needs control type', 'unknown': 'Needs control type',
}


def stem_groups(variables):
    """{key: [(name, units)]}: a Rate [W] and its Energy [J] (and Rate per Area [W/m2]) share a key.

    "Rate" is also the suffix of flows (m3/s, kg/s, kgWater/s) and of air changes (ach), so the
    suffix alone does not make a pair: the units must be W / J / W/m2.
    """
    groups = collections.defaultdict(list)
    for name, units in variables:
        key = name
        if units == 'W' and name.endswith(' Rate'):
            key = name[:-len(' Rate')]
        elif units == 'J' and name.endswith(' Energy'):
            key = name[:-len(' Energy')]
        elif units == 'W/m2' and name.endswith(' Rate per Area'):
            key = name[:-len(' Rate per Area')]
        groups[key].append((name, units))
    return groups


def leaves(items, limit, prefix='', depth=1, headers=0, out=None):
    """Split sorted word-tuples by common prefix until each leaf has at most `limit` items.

    Returns [(prefix, size, headers)]. A level where every item shares the same word
    adds no header (the prefix just grows).
    """
    if out is None:
        out = []
    if len(items) <= limit or depth > 10:
        out.append((prefix, len(items), headers))
        return out
    groups = collections.defaultdict(list)
    for words in items:
        groups[words[depth - 1] if len(words) >= depth else ''].append(words)
    if len(groups) == 1:
        return leaves(items, limit, prefix, depth + 1, headers, out)
    for word, members in sorted(groups.items()):
        leaves(members, limit, (prefix + ' ' + word).strip(), depth + 1, headers + 1, out)
    return out


def quantile(values, p):
    values = sorted(values)
    return values[min(len(values) - 1, int(p * len(values)))]


def summary(values):
    return 'min {} · median {} · p90 {} · max {}'.format(
        min(values), quantile(values, .5), quantile(values, .9), max(values))


def load(path):
    opener = gzip.open if path.endswith('.gz') else open
    with opener(path, 'rt', encoding='utf-8') as handle:
        return json.load(handle)


def report_variables(corpus):
    print('\n== SENSORS (RDD)')
    unit_count = collections.Counter()
    unknown = collections.Counter()
    rows = []
    for model, entry in corpus.items():
        variables = [(n, u) for _t, rt, n, u in entry['rdd'] if rt != 'Meter']
        if not variables:
            continue
        for _n, u in variables:
            unit_count[u] += 1
            if u not in KIND_OF_UNIT:
                unknown[u] += 1
        groups = stem_groups(variables)
        by_kind = collections.defaultdict(set)
        for key, members in groups.items():
            by_kind[KIND_OF_UNIT.get(members[0][1], 'Unclassified')].add(tuple(key.split()))
        row = {'model': model, 'variables': len(variables), 'rows': len(groups),
               'kind_longest': max(len(s) for s in by_kind.values()),
               'status_share': sum(1 for _n, u in variables if u == '') / len(variables)}
        for limit in (25, 40, 60):
            lv = [x for kind, s in by_kind.items() for x in leaves(sorted(s), limit)]
            row[limit] = (len(lv), max(x[1] for x in lv), max(x[2] for x in lv))
        # What the first draft assumed: subject = first two words, per quantity.
        two = collections.defaultdict(set)
        for kind, s in by_kind.items():
            for words in s:
                two[(kind, ' '.join(words[:2]))].add(words)
        row['two_word_longest'] = max(len(s) for s in two.values())
        rows.append(row)
    print('models: {}; variables per model: {}'.format(len(rows), summary([r['variables'] for r in rows])))
    print('rows per model after Rate/Energy pairing: {}'.format(summary([r['rows'] for r in rows])))
    print('distinct unit strings: {}; units without a kind: {}'.format(len(unit_count), dict(unknown) or 'none'))
    print('longest list with the quantity filter alone: {}'.format(summary([r['kind_longest'] for r in rows])))
    print('longest list with quantity + first two words as subject: {}; models above 25: {} of {}'.format(
        summary([r['two_word_longest'] for r in rows]),
        sum(1 for r in rows if r['two_word_longest'] > 25), len(rows)))
    for limit in (25, 40, 60):
        print('recursive prefix split, limit {}: lists per model {} · largest list {} · header levels {}'.format(
            limit, summary([r[limit][0] for r in rows]), summary([r[limit][1] for r in rows]),
            summary([r[limit][2] for r in rows])))
    print('share of rows with no unit (status, counts, ratios): {}'.format(summary(
        [round(r['status_share'] * 100) for r in rows])) + ' %')
    share = collections.Counter()
    for entry in corpus.values():
        for n, u in ((n, u) for _t, rt, n, u in entry['rdd'] if rt != 'Meter'):
            share[KIND_OF_UNIT.get(u, 'Unclassified')] += 1
    whole = float(sum(share.values()))
    print('variables by quantity:', [(k, round(100 * v / whole, 1)) for k, v in share.most_common()])
    print('units by frequency:', unit_count.most_common())
    worst = sorted(rows, key=lambda r: -r['two_word_longest'])[:5]
    print('worst for the two-word subject:', [(r['model'], r['two_word_longest']) for r in worst])


def report_pairs(corpus):
    print('\n== RATE / ENERGY PAIRS')
    shape = collections.Counter()
    rate_other_unit = collections.Counter()
    for entry in corpus.values():
        variables = [(n, u) for _t, rt, n, u in entry['rdd'] if rt != 'Meter']
        for key, members in stem_groups(variables).items():
            shape[tuple(sorted(u for _n, u in members))] += 1
        for n, u in variables:
            if n.endswith(' Rate') and u != 'W':
                rate_other_unit[u] += 1
    total = sum(shape.values())
    for units, count in shape.most_common(6):
        print('  {:>7}  {:5.1f} %  rows made of {}'.format(count, 100.0 * count / total, list(units)))
    print('names ending in " Rate" whose unit is not W (so never a pair):', dict(rate_other_unit))


def report_actuators(corpus):
    print('\n== ACTUATORS (EDD)')
    unit_actions = collections.Counter()
    rows = []
    needs = collections.defaultdict(set)
    families = collections.Counter()
    for model, entry in corpus.items():
        edd = entry['edd']
        if not edd:
            continue
        actions = collections.Counter((t, c, u) for _n, t, c, u in edd)
        for (t, c, u) in actions:
            unit_actions[u] += 1
            if EDD_KIND_OF_UNIT.get(u) == 'Needs control type':
                needs[(t, c)].add(model)
            families[t.split(' ')[0] if t.startswith('Plant Component') else t] += 1
        rows.append((len(actions), max(collections.Counter(t for _n, t, _c, _u in edd).values()),
                     max(Counter_values(actions, edd))))
    print('models with actuators: {}; actions per model: {}'.format(len(rows), summary([r[0] for r in rows])))
    print('largest component list of one component type: {}'.format(summary([r[1] for r in rows])))
    print('largest component list of one action: {}'.format(summary([r[2] for r in rows])))
    print('unit strings seen:', unit_actions.most_common())
    unmapped = [u for u in unit_actions if u not in EDD_KIND_OF_UNIT]
    print('units without a kind:', unmapped or 'none')
    print('actions whose unit does not decide (need the control type), by (type, control), models:')
    for key, models in sorted(needs.items(), key=lambda x: -len(x[1]))[:12]:
        print('   {:<70} {}'.format(str(key), len(models)))


def Counter_values(actions, edd):
    """Sizes of the component list of each action (the 'Where?' menu)."""
    per = collections.Counter((t, c, u) for _n, t, c, u in edd)
    return per.values()


def report_meters(corpus, idd_path):
    print('\n== METERS (MDD)')
    import idd_schema
    schema = idd_schema.load(idd_path)
    print('IDD', schema.version)
    resources = set(next(f for f in schema.get('EnergyManagementSystem:MeteredOutputVariable').fields
                         if f.name == 'Resource Type').keys)
    resources |= set(next(f for f in schema.get('Meter:Custom').fields if f.name == 'Resource Type').keys)
    resources |= set(next(f for f in schema.get('LifeCycleCost:UsePriceEscalation').fields
                          if f.name == 'Resource').keys)
    end_uses = set(next(f for f in schema.get('EnergyManagementSystem:MeteredOutputVariable').fields
                        if f.name == 'End-Use Category').keys)
    scopes = {'Facility', 'Building', 'HVAC', 'Plant', 'Zone', 'SpaceType', 'System'}
    sizes = []
    totals = collections.Counter()
    leftovers = collections.Counter()
    for entry in corpus.values():
        names = [n for _t, _rt, n, _u in entry['mdd']]
        if not names:
            continue
        sizes.append(len(names))
        for name in names:
            tokens = set(name.split(':'))
            totals['meters'] += 1
            if tokens & resources:
                totals['has a resource token'] += 1
            if tokens & end_uses:
                totals['has an end-use token'] += 1
            if tokens & scopes:
                totals['has a scope token'] += 1
            if not (tokens & resources or tokens & end_uses):
                leftovers[re.split(r'[:#]', name)[0]] += 1
    print('models: {}; meters per model: {}'.format(len(sizes), summary(sizes)))
    for key in ('has a resource token', 'has an end-use token', 'has a scope token'):
        print('  {:<24} {:5.1f} % of {} meters'.format(key, 100.0 * totals[key] / totals['meters'], totals['meters']))
    print('  neither resource nor end use: {} meters; first tokens {}'.format(
        sum(leftovers.values()), leftovers.most_common(12)))
    print('resource vocabulary:', len(resources), '· end-use vocabulary:', len(end_uses))
    shapes = collections.Counter()
    for entry in corpus.values():
        for _t, _rt, name, _u in entry['mdd']:
            parts = name.split(':')
            shape = []
            for i, p in enumerate(parts):
                if p in resources:
                    shape.append('Resource')
                elif p in end_uses:
                    shape.append('EndUse')
                elif p in scopes:
                    shape.append(p)
                elif i > 0 and parts[i - 1] in ('Zone', 'SpaceType'):
                    shape.append('<name>')
                else:
                    shape.append('?')
            shapes[':'.join(shape)] += 1
    print('meter name shapes (token classes joined by ":"), most frequent:')
    for shape, count in shapes.most_common(16):
        print('   {:>6}  {}'.format(count, shape))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('dictionaries')
    parser.add_argument('--idd', default=os.environ.get('IDD_PATH', r'C:\EnergyPlusV9-6-0\Energy+.idd'))
    args = parser.parse_args()
    corpus = load(args.dictionaries)
    print('corpus:', args.dictionaries, '·', len(corpus), 'models')
    report_variables(corpus)
    report_pairs(corpus)
    report_actuators(corpus)
    report_meters(corpus, args.idd)


if __name__ == '__main__':
    main()
