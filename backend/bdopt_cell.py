"""The students' "Define the problem" cell, written for bdopt.

A pure function from the problem definition (what ``problem.json`` holds) to the text of a notebook cell. It
imports nothing from bdopt and nothing from the rest of the backend: the backend never runs the library, it only
writes the code a student will read, run and change. Valid on Python 3.9 (the backend's), written for 3.11 (the
students' image).

What the cell defines, in this order: the imports it needs from bdopt, (the blind rewrite, when a glazing swap needs
it), ``parameters`` (a list of ``Parameter``), ``objectives``, ``problem``, ``sim_idf``, ``evaluator`` and
``samples`` (a table of 20 Latin hypercube rows). It uses two names that an earlier cell defines: ``idf``
(``bdopt.load_idf`` of the uploaded model) and ``epw_file`` (the weather file's path).

Mapping, one variable of the definition to one ``Parameter`` (one column of ``samples``):

    targets ["*"]                          FieldSelector(class, "*", field)
    one object                             FieldSelector(class, object, field)
    several objects, one class and field   MultiSelector.from_targets([names], class_name=, field_name=)
    several objects, mixed class or field  MultiSelector.from_targets([{class, object, field | field_index}, ...])
    "minimize" / "maximize"                a meter name / MeterReader(meter, direction="max")
    option coding 1..N of problem.json     a comment: bdopt keeps the option itself in the column

A field is written by its IDD name (``Construction Name``) when the definition carries it (``iddField``, schema 2),
and by position (``field_index``) when the IDD only numbers it (Schedule:Compact: "Field 4"). A definition of
schema 1 has neither; the field is then taken from the name eppy uses (underscores to spaces; Schedule:Compact
``Field_N`` is the position N + 1), which the field sweep in tests/backend checks on every field the panel can offer.

``evaluator`` is built from ``sim_idf``, a copy of ``idf`` without its Output:Variable objects, so that ``idf`` stays
the model to save when the design is chosen.
"""

import json
import re
import textwrap

# Field 4 of a Schedule:Compact says nothing: what it means depends on the lines before it. Such a field is written
# by its position, with a comment saying which one it is. (So is any field the IDD does not list by name, such as the
# Value 10 of a Schedule:Day:List: a definition of schema 2 has no iddField for it.)
_POSITIONAL = re.compile(r'^Field \d+$')
_EPPY_POSITIONAL = re.compile(r'^Field_(\d+)$')

# Positions of the two WindowShadingControl fields the blind rewrite writes, in the IDD of EnergyPlus 9.6 (read with
# the backend's eppy and compared with bdopt's IDD parser by the tests). A definition of schema 2 carries them.
SHADING_CONSTRUCTION_INDEX = 4
SHADING_MATERIAL_INDEX = 10

NUM_SAMPLES = 20
WIDTH = 100


def _q(text):
    """A Python string literal (JSON strings are valid Python ones, and double quotes read like bdopt's docs)."""
    return json.dumps(str(text), ensure_ascii=False)


def _num(x):
    """A number as short as it can be without changing it (12 significant digits, no trailing .0)."""
    x = float(x)
    if x != x or x in (float('inf'), float('-inf')):
        raise ValueError('%r is not a number a range can have' % x)
    return '%.12g' % x


def _one_line(text):
    """Free text (a name the person typed) that cannot end the comment it is written in."""
    return ' '.join(str(text).split())


def _slug(name, i, used):
    base = re.sub(r'[^a-z0-9]+', '_', str(name).lower()).strip('_')[:28].strip('_') or 'p%d' % i
    if base[0].isdigit():
        base = 'p_' + base
    var, n = base, 1
    while var in used:  # two names that start alike: windows_construction_b, windows_construction_b_2, ...
        n += 1
        var = '%s_%d' % (base, n)
    used.add(var)
    return var


def _wrap(items, indent, width=WIDTH):
    """Comma-separated items packed into lines of at most ``width`` characters, each indented by ``indent``."""
    pad = ' ' * indent
    lines, cur = [], ''
    for item in items:
        piece = item + ','
        if cur and len(pad) + len(cur) + 1 + len(piece) > width:
            lines.append(pad + cur)
            cur = piece
        else:
            cur = (cur + ' ' + piece) if cur else piece
    if cur:
        lines.append(pad + cur)
    return lines


def _call(head, args):
    """``head(arg, arg)`` on one line when it fits, otherwise one argument per line."""
    one = head + '(' + ', '.join(args) + ')'
    if len(one) <= WIDTH:
        return [one]
    return [head + '('] + ['    ' + a + ',' for a in args] + [')']


def _comment(text, indent='#   '):
    return textwrap.wrap(text, WIDTH, initial_indent=indent, subsequent_indent=indent + '  ',
                         break_long_words=False, break_on_hyphens=False)


def _comment_items(head, items, indent='#   '):
    """A comment line ``head`` followed by the items, packed into lines without cutting an item in two."""
    keep = chr(0xE000)  # a private-use character standing in for a space that textwrap must not break at
    text = ', '.join(i.replace(' ', keep) for i in items)
    lines = textwrap.wrap(text, WIDTH, initial_indent=indent + '  ', subsequent_indent=indent + '  ',
                          break_long_words=False, break_on_hyphens=False)
    return [indent + head] + [l.replace(keep, ' ') for l in lines]


# -- where a value is written -----------------------------------------------------------------------------------

def _targets(v):
    """The variable's targets as dicts with everything a selector needs, whatever the schema they come in."""
    out = []
    for t in v.get('targets') or []:
        entry = dict(t) if isinstance(t, dict) else {'object': t}
        for key in ('className', 'field'):
            if entry.get(key) in (None, ''):
                entry[key] = v.get(key)
        if entry.get('field') == v.get('field'):  # what the variable says about its field holds for the target
            for key in ('fieldIndex', 'iddField', 'iddClass'):
                if entry.get(key) in (None, ''):
                    entry[key] = v.get(key)
        if not _class_of(entry) or (not entry.get('field') and entry.get('fieldIndex') is None):
            raise ValueError('%s: a target needs a class and a field' % v.get('name'))
        out.append(entry)
    return out


def _class_of(t):
    return t.get('iddClass') or t.get('className')


def _field_of(t):
    """How the field is written: ``('name', 'Construction Name')`` or ``('index', 5)``."""
    idd, index, eppy = t.get('iddField'), t.get('fieldIndex'), t.get('field') or ''
    if idd and not _POSITIONAL.match(idd):
        return 'name', idd
    if index is not None:
        return 'index', int(index)
    m = _EPPY_POSITIONAL.match(eppy)
    if m and (_class_of(t) or '').lower() == 'schedule:compact':
        return 'index', int(m.group(1)) + 1  # schema 1: Name, Schedule Type Limits Name, then Field 1 at position 2
    return 'name', idd or eppy.replace('_', ' ')


def _field_label(t):
    """The field as a person would name it: the IDD name, or eppy's with spaces."""
    return t.get('iddField') or (t.get('field') or '').replace('_', ' ') or 'field %s' % t.get('fieldIndex')


def _field_args(t):
    """The keyword argument that names the field, and the note to leave next to it when it is a position."""
    how, value = _field_of(t)
    if how == 'name':
        return 'field_name=' + _q(value), None
    label = _field_label(t)
    note = None
    if not label.startswith('field '):  # a name is known, only the IDD does not list it at this position
        note = '%s fields are numbered, not named: field_index=%d is its "%s".' % (_class_of(t), value, label)
    return 'field_index=%d' % value, note


def _selector(var, targets, lines):
    """Append the lines that define ``<var>_sel``; return the notes for positional fields and the class used."""
    first = targets[0]
    cls, (field_arg, note) = _class_of(first), _field_args(first)
    same = all(_class_of(t) == cls and _field_args(t)[0] == field_arg for t in targets)
    name = var + '_sel'
    if same and len(targets) == 1:
        lines += _call(name + ' = FieldSelector', ['class_name=' + _q(cls), 'object_name=' + _q(first['object']),
                                                   field_arg])
        return ([note] if note else []), 'FieldSelector'
    if same:
        lines.append(name + ' = MultiSelector.from_targets(')
        lines.append('    [')
        lines += _wrap([_q(t['object']) for t in targets], 8)
        lines.append('    ],')
        lines.append('    class_name=%s, %s,' % (_q(cls), field_arg))
        lines.append(')')
        return ([note] if note else []), 'MultiSelector'
    notes, items = [], []
    for t in targets:
        arg, n = _field_args(t)
        if n and n not in notes:
            notes.append(n)
        key, value = arg.split('=', 1)
        items.append('{"class": %s, "object": %s, "%s": %s}' % (
            _q(_class_of(t)), _q(t['object']), 'field' if key == 'field_name' else 'field_index', value))
    lines.append(name + ' = MultiSelector.from_targets([')
    lines += _wrap(items, 4, 120)
    lines.append('])')
    return notes, 'MultiSelector'


def _where_text(targets):
    """What the parameter writes, for the comment above it."""
    classes, fields = [], []
    for t in targets:
        c = _class_of(t)
        if c not in classes:
            classes.append(c)
        f = _field_label(t)
        if f not in fields:
            fields.append(f)
    which = ('every %s object' % classes[0]) if len(targets) == 1 and targets[0]['object'] == '*' else \
        '%d %s object%s' % (len(targets), ' / '.join(classes), '' if len(targets) == 1 else 's')
    return 'writes %s, field%s %s' % (which, '' if len(fields) == 1 else 's', ' / '.join('"%s"' % f for f in fields))


# -- the cell ---------------------------------------------------------------------------------------------------------

def _shading(rewrites):
    """The blind block. ``rewrites`` are {control, material[, materialIndex, constructionIndex, ...]}."""
    first = rewrites[0]
    m_idx = first.get('materialIndex')
    c_idx = first.get('constructionIndex')
    m_idx = SHADING_MATERIAL_INDEX if m_idx is None else m_idx
    c_idx = SHADING_CONSTRUCTION_INDEX if c_idx is None else c_idx
    m_name = first.get('materialField') or 'Shading Device Material Name'
    c_name = first.get('constructionField') or 'Construction with Shading Name'
    pairs = ['(%s, %s)' % (_q(r['control']), _q(r['material'])) for r in rewrites]
    lines = [
        '# The blinds over the windows whose construction changes. A blind given as a shaded construction only fits',
        '# the glazing it was built with; given as a material it fits whichever glazing a sample picks.',
        '# WindowShadingControl, by position in the IDD (the name is field 0):',
        '#   field %d is "%s", field %d is "%s".' % (c_idx, c_name, m_idx, m_name),
        'for control, blind in [',
    ]
    lines += _wrap(pairs, 4)
    lines += [
        ']:',
        '    shading = idf.find("WindowShadingControl", control)[0]',
        '    shading.set(%d, blind)' % m_idx,
        '    shading.set(%d, "")' % c_idx,
        '',
    ]
    return lines


def _objective(o):
    name = o['name'] if isinstance(o, dict) else o
    direction = (o.get('direction') if isinstance(o, dict) else None) or 'minimize'
    return name, ('max' if str(direction).lower().startswith('max') else 'min')


def _import_lines(names):
    one = 'from bdopt import ' + ', '.join(names)
    if len(one) <= WIDTH:
        return [one]
    return ['from bdopt import (', *_wrap(names, 4), ')']


def notebook_cell(variables, objectives):
    """The "Define the problem" cell for bdopt: ``variables`` and ``objectives`` as ``problem.json`` holds them."""
    rewrites = list({r['control']: r for v in variables for r in v.get('shading') or []}.values())
    objs = [_objective(o) for o in objectives]

    used_classes = {'EnergyPlusEvaluator', 'Parameter', 'Problem'}
    body, names = [], set()
    for i, v in enumerate(variables):
        var = _slug(v['name'], i, names)
        targets = _targets(v)
        if not targets:
            raise ValueError('%s: no object to write to' % v.get('name'))
        sel = []
        notes, selector_class = _selector(var, targets, sel)
        used_classes.add(selector_class)
        body.append('# %s' % _one_line(v['name']))
        body += _comment(_where_text(targets))
        for n in notes:
            body += _comment(n)
        if v['type'] == 'range':
            descriptor = 'RangeParameter(%s, %s)' % (_num(v['min']), _num(v['max']))
            used_classes.add('RangeParameter')
        else:
            body += _comment_items('The column holds the option itself; problem.json numbered the options:',
                                   ['%d = %s' % (k, _one_line(o)) for k, o in enumerate(v['options'], 1)])
        body += sel
        if v['type'] != 'range':
            descriptor = var + '_options'
            used_classes.add('CategoryParameter')
            body.append('%s = CategoryParameter([' % descriptor)
            body += _wrap([_q(o) for o in v['options']], 4)
            body.append('])')
        args = ['selector=%s_sel' % var, 'value_descriptor=' + descriptor, 'name=' + _q(v['name'])]
        one = 'parameters.append(Parameter(%s))' % ', '.join(args)
        if len(one) <= WIDTH:
            body.append(one)
        else:
            body += ['parameters.append(Parameter('] + ['    %s,' % a for a in args] + ['))']
        body.append('')
    if any(d == 'max' for _, d in objs):
        used_classes.add('MeterReader')

    plural = '' if len(variables) == 1 else 's'
    lines = [
        '# Define the problem: what to vary (parameters), what to improve (objectives), how EnergyPlus is run.',
        '# Written by the platform from the problem you defined; change it as you like.',
        '# It needs two names from the cell above: idf (the model, bdopt.load_idf) and epw_file (the weather file).',
        '# Every selector is checked against the model when the evaluator is created, with suggestions for a typo.',
    ]
    lines += _import_lines(sorted(used_classes))
    lines.append('from bdopt.sampling import lhs')
    lines.append('')
    if rewrites:
        lines += _shading(rewrites)
    lines.append('# %d parameter%s = %d column%s of `samples`, however many objects each one writes.' % (
        len(variables), plural, len(variables), plural))
    lines.append('parameters = []')
    lines.append('')
    lines += body
    lines.append('# Objectives: meters, summed over the run period, in joules.')
    lines.append('# A plain name is minimised; MeterReader(name, direction="max") maximises.')
    lines.append('objectives = [')
    for name, direction in objs:
        lines.append('    %s,' % (_q(name) if direction == 'min' else 'MeterReader(%s, direction="max")' % _q(name)))
    lines.append(']')
    lines.append('problem = Problem(parameters, objectives)')
    lines.append('')
    lines += [
        '# EnergyPlus writes every Output:Variable the model asks for into its results database, and a detailed model',
        '# asks for hundreds. The objectives are meters, which the evaluator requests by itself, so none of those',
        '# variables is needed: they are removed from the copy that is simulated (idf itself is left as it is).',
        '# An objective that reads a variable, e.g. VariableReader, makes the evaluator request that variable itself.',
        'sim_idf = idf.copy()',
        'sim_idf.remove(sim_idf.by_class("Output:Variable"))',
        'evaluator = EnergyPlusEvaluator(',
        '    problem, sim_idf, epw_file,',
        '    out_dir="/tmp/bdopt_runs",  # run folders on the container\'s own disk: much faster than a shared folder',
        '    err_dir="outputdir",        # a run that fails is kept here, with EnergyPlus\' error file',
        '    processes=2,                # EnergyPlus runs in parallel',
        ')',
        '',
        'samples = lhs(problem, %d)  # %d Latin hypercube samples: a row per design, a column per parameter' % (
            NUM_SAMPLES, NUM_SAMPLES),
        '# lhs(problem, %d, seed=1) gives the same samples every time, and runs already done are not repeated (the cache lives in /tmp/bdopt_runs, so until the container is recreated).' % (
            NUM_SAMPLES),
    ]
    return '\n'.join(lines)
