"""What the simulation reports: Output:Variable and Output:Meter requests, and what hangs on them.

The Model editor's Outputs tab lets the student decide which report variables and
meters EnergyPlus writes. This module reads those requests from the live IDF,
works out which of them the FMU interface or the EMS sits on, and adds, changes
and removes them. Field positions come from the IDD (through `idd_schema`), never
from memory; nothing here runs EnergyPlus.

Meters: `Output:Meter` writes to the .eso (with the report variables) and to the
.mtr; `Output:Meter:MeterFileOnly` only to the .mtr (IDD notes of both classes);
the `:Cumulative` pair accumulates instead of reporting the interval value.

What depends on a request, as the platform builds it (see `ems_chain`):
  * a *platform sensor*: EMS:Sensor + EMS:OutputVariable of the same name, which
    reads the request and republishes it as `Output:Variable EMS,<name>` plus a
    From:Variable. Removing the request removes that chain (the student chose
    "warn and cascade");
  * an *FMU output*: a From:Variable on the request itself (direct mode), or on
    an `Output:Variable EMS,...` request;
  * a *model sensor*: an EMS:Sensor of the model's own, with no such chain behind
    it. Its EMS programs are the model's design, so it is reported but left alone.
A request that is the only source of one of these is locked against edits: changing its key,
name, frequency or class would change what the dependant reads. One of several (a wildcard
request next to the FMU output's own, say) can change, as long as another one is left alone.
"""

import ems_chain

VARIABLE = 'Output:Variable'
METER = 'Output:Meter'
# (cumulative, meter file only) -> class
METER_CLASSES = {
    (False, False): 'Output:Meter',
    (False, True): 'Output:Meter:MeterFileOnly',
    (True, False): 'Output:Meter:Cumulative',
    (True, True): 'Output:Meter:Cumulative:MeterFileOnly',
}
_METER_OPTIONS = {name.upper(): options for options, name in METER_CLASSES.items()}

# What a new request reports at when none is given: the platform's own default (ems_chain), not the
# IDD's blank-means-Hourly, so that what the student adds is seen at every time step.
DEFAULT_FREQUENCY = ems_chain.DEFAULT_REPORTING_FREQUENCY

SENSOR = 'EnergyManagementSystem:Sensor'
EMS_OUTPUT = 'EnergyManagementSystem:OutputVariable'
FROM_VARIABLE = 'ExternalInterface:FunctionalMockupUnitExport:From:Variable'


class Conflict(ValueError):
    """The request is well formed but the model's state forbids it (HTTP 409)."""


# ---------------------------------------------------------------- helpers
# Same few lines as idf_editor (_text, _put, _trim): that module imports this one.

def _text(value):
    if value is None:
        return ''
    if isinstance(value, float):
        return format(value, '.15g')
    return str(value)


def _get(obj, index):
    return _text(obj.obj[index + 1]) if len(obj.obj) > index + 1 else ''


def _put(obj, index, value):
    need = index + 2
    if len(obj.obj) < need:
        obj.obj.extend([''] * (need - len(obj.obj)))
    obj.obj[index + 1] = value


def _trim(obj, spec):
    floor = max(spec.min_fields, 0) + 1
    while len(obj.obj) > floor and _text(obj.obj[-1]) == '':
        obj.obj.pop()


def _same(a, b):
    return a.strip().lower() == b.strip().lower()


def _index(spec, name):
    for field in spec.fields:
        if field.name == name:
            return field.index
    raise RuntimeError("{} has no field '{}' in this IDD.".format(spec.name, name))


class Layout(object):
    """Field positions of every class this module touches, read from the IDD."""

    def __init__(self, schema):
        self.schema = schema
        self.variable = schema.get(VARIABLE)
        self.v_key = _index(self.variable, 'Key Value')
        self.v_name = _index(self.variable, 'Variable Name')
        self.v_freq = _index(self.variable, 'Reporting Frequency')
        self.v_schedule = _index(self.variable, 'Schedule Name')
        self.meters = {}
        for options, name in METER_CLASSES.items():
            spec = schema.get(name)
            self.meters[name.upper()] = (spec, _index(spec, 'Key Name'), _index(spec, 'Reporting Frequency'))
        sensor = schema.get(SENSOR)
        self.s_name = _index(sensor, 'Name')
        self.s_key = _index(sensor, 'Output:Variable or Output:Meter Index Key Name')
        self.s_source = _index(sensor, 'Output:Variable or Output:Meter Name')
        ems = schema.get(EMS_OUTPUT)
        self.e_name = _index(ems, 'Name')
        self.e_variable = _index(ems, 'EMS Variable Name')
        fv = schema.get(FROM_VARIABLE)
        self.f_key = _index(fv, 'Output:Variable Index Key Name')
        self.f_name = _index(fv, 'Output:Variable Name')
        self.f_fmu = _index(fv, 'FMU Variable Name')

    def frequencies(self, spec_name):
        spec = self.schema.get(spec_name)
        keys = spec.fields[_index(spec, 'Reporting Frequency')].keys
        return [k for n, k in enumerate(keys) if k not in keys[:n]]


def shown_frequency(layout, class_name, value):
    """The IDD's spelling of a frequency the file may write in any case; blank is the IDD default."""
    spec = layout.schema.get(class_name)
    field = spec.fields[_index(spec, 'Reporting Frequency')]
    text = _text(value).strip() or field.default or ''
    return next((k for k in field.keys if k.lower() == text.lower()), _text(value))


def frequency_key(layout, class_name, value):
    """The IDD's spelling of a reporting frequency, or ValueError."""
    keys = layout.frequencies(class_name)
    low = _text(value).strip().lower()
    for key in keys:
        if key.lower() == low:
            return key
    raise ValueError("'{}' is not a reporting frequency of {}.".format(value, class_name))


# ---------------------------------------------------------------- reading

def _chain_names(idf, layout):
    """Names of the sensor chains the platform builds: a sensor and an EMS output of one name."""
    outputs = {}
    for obj in idf.idfobjects[EMS_OUTPUT.upper()]:
        outputs[_get(obj, layout.e_name).lower()] = _get(obj, layout.e_variable).lower()
    return {_get(s, layout.s_name).lower() for s in idf.idfobjects[SENSOR.upper()]
            if outputs.get(_get(s, layout.s_name).lower()) == _get(s, layout.s_name).lower()}


def _dependants(idf, layout):
    chains = _chain_names(idf, layout)
    from_variables = [(_get(f, layout.f_key), _get(f, layout.f_name), _get(f, layout.f_fmu))
                      for f in idf.idfobjects[FROM_VARIABLE.upper()]]
    found = []
    for s in idf.idfobjects[SENSOR.upper()]:
        name = _get(s, layout.s_name)
        platform = name.lower() in chains
        found.append({
            'kind': 'platform-sensor' if platform else 'model-sensor', 'name': name, 'cascade': platform,
            'srcKey': _get(s, layout.s_key), 'srcName': _get(s, layout.s_source),
            'fmu': [f for k, n, f in from_variables if k.lower() == ems_chain.EMS_KEY.lower() and n.lower() == name.lower()],
        })
    for key, name, fmu in from_variables:
        found.append({'kind': 'fmu-output', 'name': fmu, 'cascade': True, 'fromKey': key, 'fromName': name,
                      'fmu': [fmu], 'chain': name.lower() in chains and key.lower() == ems_chain.EMS_KEY.lower()})
    return found


def _covers(request_key, dependant_key):
    """A request on key K serves a reader of key K; `*` (or blank, the IDD default) serves every key."""
    r = request_key.strip().lower()
    return r in ('', '*') or r == dependant_key.strip().lower()


def _reads_variable(dep, key, name):
    if dep['kind'] == 'fmu-output':
        if dep['fromKey'].lower() == ems_chain.EMS_KEY.lower():
            return key.lower() == ems_chain.EMS_KEY.lower() and dep['fromName'].lower() == name.lower()
        return dep['fromName'].lower() == name.lower() and _covers(key, dep['fromKey'])
    return key.lower() != ems_chain.EMS_KEY.lower() and dep['srcName'].lower() == name.lower() \
        and _covers(key, dep['srcKey'])


def _reads_meter(dep, name):
    return dep['kind'] != 'fmu-output' and dep['srcName'].lower() == name.lower()


def _rows(idf, layout):
    """Every request, as {kind, cls, obj, index, ...}, in file order per class."""
    rows = []
    for index, obj in enumerate(idf.idfobjects[layout.variable.upper]):
        rows.append({'kind': 'variable', 'cls': VARIABLE, 'obj': obj, 'index': index,
                     'key': _get(obj, layout.v_key), 'name': _get(obj, layout.v_name),
                     'frequency': shown_frequency(layout, VARIABLE, _get(obj, layout.v_freq)), 'schedule': _get(obj, layout.v_schedule)})
    for options, name in METER_CLASSES.items():
        spec, name_at, freq_at = layout.meters[name.upper()]
        for index, obj in enumerate(idf.idfobjects[spec.upper]):
            rows.append({'kind': 'meter', 'cls': name, 'obj': obj, 'index': index,
                         'name': _get(obj, name_at),
                         'frequency': shown_frequency(layout, name, _get(obj, freq_at)),
                         'cumulative': options[0], 'fileOnly': options[1]})
    return rows


def _analyse(idf, layout):
    """Rows with `usedBy`: the dependants that read each one, and whether it is their only source."""
    rows = _rows(idf, layout)
    deps = _dependants(idf, layout)
    readers = []
    for row in rows:
        if row['kind'] == 'variable':
            readers.append([d for d in deps if _reads_variable(d, row['key'], row['name'])])
        else:
            readers.append([d for d in deps if _reads_meter(d, row['name'])])
    for row, mine in zip(rows, readers):
        row['usedBy'] = []
        for dep in mine:
            sources = sum(1 for other in readers if any(d is dep for d in other))
            row['usedBy'].append({'kind': dep['kind'], 'name': dep['name'], 'fmu': dep['fmu'],
                                  'cascade': dep['cascade'], 'sole': sources == 1, 'dep': dep,
                                  'readers': [id(o['obj']) for o, mine_ in zip(rows, readers)
                                              if any(d is dep for d in mine_)]})
        row['platform'] = row['kind'] == 'variable' and bool(
            [d for d in mine if d['kind'] == 'fmu-output' and d.get('chain')])
    return rows


def _public(row):
    out = {k: v for k, v in row.items() if k not in ('obj', 'usedBy', 'cls')}
    out['class'] = row['cls']
    out['usedBy'] = [{k: v for k, v in u.items() if k not in ('dep', 'readers')} for u in row['usedBy']]
    # Locked: it is the only request something reads. A request that is one of several can change
    # while another still serves the reader.
    out['locked'] = any(u['sole'] for u in row['usedBy'])
    return out


def read(idf, layout):
    rows = _analyse(idf, layout)
    return {
        'variables': [_public(r) for r in rows if r['kind'] == 'variable'],
        'meters': [_public(r) for r in rows if r['kind'] == 'meter'],
        'frequencies': {'variable': layout.frequencies(VARIABLE), 'meter': layout.frequencies(METER)},
        'meterClasses': {'{}|{}'.format(int(c), int(f)): n for (c, f), n in METER_CLASSES.items()},
    }


# ---------------------------------------------------------------- locating

def locate(idf, layout, refs):
    """The request objects `refs` name, checked: class, position, key and name must still agree."""
    if not isinstance(refs, list) or not refs:
        raise ValueError('requests must list the outputs to act on.')
    found = []
    for ref in refs:
        if not isinstance(ref, dict):
            raise ValueError('Each request must be an object.')
        class_name = _text(ref.get('class'))
        if _same(class_name, VARIABLE):
            spec, name_at, key_at = layout.variable, layout.v_name, layout.v_key
        elif class_name.upper() in layout.meters:
            spec, name_at, key_at = layout.meters[class_name.upper()][0], layout.meters[class_name.upper()][1], None
        else:
            raise ValueError("'{}' is not an output request class.".format(class_name))
        bucket = idf.idfobjects[spec.upper]
        try:
            index = int(ref.get('index'))
        except (TypeError, ValueError):
            raise ValueError('index is required.')
        if not 0 <= index < len(bucket):
            raise Conflict('That output no longer exists. Reload the page.')
        obj = bucket[index]
        if 'name' in ref and _get(obj, name_at) != _text(ref['name']):
            raise Conflict('That output changed. Reload the page.')
        if key_at is not None and 'key' in ref and _get(obj, key_at) != _text(ref['key']):
            raise Conflict('That output changed. Reload the page.')
        if not any(o is obj for o in found):
            found.append(obj)
    return found


def _row_of(rows, obj):
    return next(r for r in rows if r['obj'] is obj)


# ---------------------------------------------------------------- adding

def check_variable(idf, layout, key, name, frequency, schedule=''):
    name = _text(name).strip()
    if not name:
        raise ValueError('The variable name is required.')
    key = _text(key).strip() or '*'
    frequency = frequency_key(layout, VARIABLE, frequency or DEFAULT_FREQUENCY)
    for row in _rows(idf, layout):
        if (row['kind'] == 'variable' and _same(row['key'] or '*', key) and _same(row['name'], name)
                and _same(row['frequency'], frequency)):
            raise Conflict('{} / {} is already reported {}.'.format(key, name, frequency))
    return {'key': key, 'name': name, 'frequency': frequency, 'schedule': _text(schedule).strip()}


def add_variable(model, layout, checked):
    obj = model.newidfobject(layout.variable.upper, defaultvalues=False)
    _put(obj, layout.v_key, checked['key'])
    _put(obj, layout.v_name, checked['name'])
    _put(obj, layout.v_freq, checked['frequency'])
    if checked['schedule']:
        _put(obj, layout.v_schedule, checked['schedule'])
    _trim(obj, layout.variable)
    return len(model.idfobjects[layout.variable.upper]) - 1


def check_meter(idf, layout, name, frequency, cumulative=False, file_only=False):
    name = _text(name).strip()
    if not name:
        raise ValueError('The meter name is required.')
    class_name = METER_CLASSES[(bool(cumulative), bool(file_only))]
    frequency = frequency_key(layout, METER, frequency or DEFAULT_FREQUENCY)
    for row in _rows(idf, layout):
        if row['kind'] == 'meter' and row['cls'] == class_name and _same(row['name'], name) \
                and _same(row['frequency'], frequency):
            raise Conflict('{} is already reported {} ({}).'.format(name, frequency, class_name))
    return {'class': class_name, 'name': name, 'frequency': frequency}


def add_meter(model, layout, checked):
    spec, name_at, freq_at = layout.meters[checked['class'].upper()]
    obj = model.newidfobject(spec.upper, defaultvalues=False)
    _put(obj, name_at, checked['name'])
    _put(obj, freq_at, checked['frequency'])
    _trim(obj, spec)
    return len(model.idfobjects[spec.upper]) - 1


# ---------------------------------------------------------------- changing

_VARIABLE_FIELDS = {'key', 'name', 'frequency', 'schedule'}
_METER_FIELDS = {'name', 'frequency', 'cumulative', 'fileOnly'}


def plan_changes(idf, layout, objs, changes, strict):
    """Which of `objs` can take `changes`: ([(row, normalised)], [(row, why skipped)]).

    One target (strict) fails on a locked or invalid request; many targets skip the
    locked ones, so a bulk frequency change does not stop at the first sensor.
    """
    if not isinstance(changes, dict) or not changes:
        raise ValueError('changes must say what to set.')
    rows = _analyse(idf, layout)
    plan, skipped, approved = [], [], set()
    for obj in objs:
        row = _row_of(rows, obj)
        allowed = _VARIABLE_FIELDS if row['kind'] == 'variable' else _METER_FIELDS
        unknown = sorted(set(changes) - allowed)
        if unknown:
            if strict:
                raise ValueError('{} cannot take: {}.'.format(row['cls'], ', '.join(unknown)))
            skipped.append((row, 'not applicable'))
            continue
        blocked = [u for u in row['usedBy']
                   if not any(r != id(obj) and r not in approved for r in u['readers'])]
        if blocked:
            why = 'the only request read by ' + ', '.join(sorted({u['name'] for u in blocked}))
            if strict:
                raise Conflict('{} is {}; change that first (removing it can cascade).'.format(row['name'], why))
            skipped.append((row, why))
            continue
        new = {}
        if 'frequency' in changes:
            new['frequency'] = frequency_key(layout, VARIABLE if row['kind'] == 'variable' else METER,
                                             changes['frequency'])
        if row['kind'] == 'variable':
            if 'key' in changes:
                new['key'] = _text(changes['key']).strip() or '*'
            if 'name' in changes:
                new['name'] = _text(changes['name']).strip()
                if not new['name']:
                    raise ValueError('The variable name is required.')
            if 'schedule' in changes:
                new['schedule'] = _text(changes['schedule']).strip()
        else:
            if 'name' in changes:
                new['name'] = _text(changes['name']).strip()
                if not new['name']:
                    raise ValueError('The meter name is required.')
            if 'cumulative' in changes:
                new['cumulative'] = bool(changes['cumulative'])
            if 'fileOnly' in changes:
                new['fileOnly'] = bool(changes['fileOnly'])
        approved.add(id(obj))
        plan.append((row, new))
    return plan, skipped


def apply_changes(model, layout, plan):
    """Write the planned changes; a meter whose options change moves to the matching class."""
    moved = []
    for row, new in plan:
        obj = row['obj']
        if row['kind'] == 'variable':
            if 'key' in new:
                _put(obj, layout.v_key, new['key'])
            if 'name' in new:
                _put(obj, layout.v_name, new['name'])
            if 'frequency' in new:
                _put(obj, layout.v_freq, new['frequency'])
            if 'schedule' in new:
                _put(obj, layout.v_schedule, new['schedule'])
            _trim(obj, layout.variable)
            continue
        options = (new.get('cumulative', row['cumulative']), new.get('fileOnly', row['fileOnly']))
        target = METER_CLASSES[options]
        name = new.get('name', row['name'])
        frequency = new.get('frequency', row['frequency'])
        if target == row['cls']:
            spec, name_at, freq_at = layout.meters[target.upper()]
            _put(obj, name_at, name)
            _put(obj, freq_at, frequency)
            continue
        spec, name_at, freq_at = layout.meters[target.upper()]
        fresh = model.newidfobject(spec.upper, defaultvalues=False)
        _put(fresh, name_at, name)
        _put(fresh, freq_at, frequency)
        _trim(fresh, spec)
        model.removeidfobject(obj)
        moved.append(target)
    return moved


# ---------------------------------------------------------------- removing

def removal_dependants(idf, layout, objs):
    """What removing `objs` would take away: platform chains and FMU outputs whose every source is among
    `objs`, and (reported, never removed) the model's own sensors that read only them."""
    rows = _analyse(idf, layout)
    chosen = {id(o) for o in objs}
    readers = {}
    for row in rows:
        for use in row['usedBy']:
            readers.setdefault(id(use['dep']), (use, []))[1].append(id(row['obj']))
    cascade, informed = [], []
    for use, sources in readers.values():
        if not any(s in chosen for s in sources) or not all(s in chosen for s in sources):
            continue
        public = {k: v for k, v in use.items() if k not in ('dep', 'sole', 'readers')}
        (cascade if use['cascade'] else informed).append(public)
    return cascade, informed


def _present(idf, obj):
    return any(o is obj for o in idf.idfobjects[obj.key.upper()])


def remove(idf, layout, objs):
    """Remove the requests, taking the platform chains and FMU outputs that rest on them first.

    Returns the FMU variable names that went (their roles are dropped by the caller).
    """
    dropped = []
    for obj in objs:
        if not _present(idf, obj):
            continue
        rows = _analyse(idf, layout)
        for use in _row_of(rows, obj)['usedBy']:
            if not (use['cascade'] and use['sole']):
                continue
            dep = use['dep']
            dropped.extend(dep['fmu'])
            if dep['kind'] == 'platform-sensor':
                ems_chain.remove_monitored_quantity(idf, dep['name'])
            elif dep.get('chain'):
                ems_chain.remove_monitored_quantity(idf, dep['fromName'])
            elif dep['fromKey'].lower() == ems_chain.EMS_KEY.lower():
                for export in list(idf.idfobjects[FROM_VARIABLE.upper()]):
                    if _get(export, layout.f_fmu) == dep['name']:
                        idf.removeidfobject(export)
            else:
                ems_chain.remove_direct_variable(idf, dep['name'])
        if _present(idf, obj):
            idf.removeidfobject(obj)
    return dropped
