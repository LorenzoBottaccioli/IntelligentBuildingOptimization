"""The Model editor: read, add, change, rename and delete any object of the IDF.

Everything about a class (fields, types, keys, units, bounds, defaults, which
reference lists a field draws from) comes from the IDD through `idd_schema`;
nothing is transcribed per class. Writes go through `idf_session.mutate`, the one
path every other page uses, so the model the EMS, FMU and design pages see is the
model edited here. Validation runs before the write (mutate cannot roll back) and
only structural errors stop an edit: EnergyPlus decides what it accepts, so a
value outside a declared range, an unknown key or an unresolved reference is
returned as a warning.

Two guided views sit on the same machinery: thermal comfort (the People object's
comfort-model slots) and indoor CO2 (ZoneAirContaminantBalance and its inputs).
What they know beyond the IDD is in the tables below, each entry with its source.
"""

import glob
import os
import re
import shutil
import threading
import time

from flask import Blueprint, jsonify, request
from flask_cors import CORS

import fmu_roles
import idd_schema
import idf_session
import output_requests

IDD_PATH = os.environ.get('IDD_PATH', '/app/EnergyPlus-9-6-0/Energy+.idd')
SIMULATION_OUTPUTS = 'simulation_outputs'

idf_editor_bp = Blueprint('idf_editor', __name__)
CORS(idf_editor_bp)


class ApiError(Exception):
    def __init__(self, message, status=400):
        Exception.__init__(self, message)
        self.message = message
        self.status = status


@idf_editor_bp.errorhandler(ApiError)
def _api_error(error):
    return jsonify({'error': error.message}), error.status


@idf_editor_bp.errorhandler(idf_session.NoModelLoadedError)
def _no_model(error):
    return jsonify({'error': 'No IDF has been uploaded yet.'}), 400


# ---------------------------------------------------------------- helpers

def _schema():
    return idd_schema.load(IDD_PATH)


def _spec(name):
    spec = _schema().get(name or '')
    if spec is None:
        raise ApiError("'{}' is not a class of this EnergyPlus version.".format(name), 404)
    return spec


def _text(value):
    if value is None:
        return ''
    if isinstance(value, float):
        return format(value, '.15g')
    return str(value)


def _values(obj):
    return [_text(v) for v in obj.obj[1:]]


def _put(obj, index, value):
    """Set the 0-based field `index`, growing the object when it is shorter."""
    need = index + 2
    if len(obj.obj) < need:
        obj.obj.extend([''] * (need - len(obj.obj)))
    obj.obj[index + 1] = value


def _trim(obj, spec):
    """Drop trailing blank fields beyond the class's minimum field count."""
    floor = max(spec.min_fields, 0) + 1
    while len(obj.obj) > floor and _text(obj.obj[-1]) == '':
        obj.obj.pop()


def _bucket(idf, spec):
    return idf.idfobjects[spec.upper]


def _is_managed(spec, values):
    """Objects the platform itself writes (FMU/EMS plumbing): shown, with a warning."""
    first = values[0].lower() if values else ''
    return (first.startswith('sbep') or first == 'donothing'
            or spec.upper.startswith('EXTERNALINTERFACE')
            or (spec.upper == 'OUTPUT:VARIABLE' and first == 'ems')
            or (spec.upper == 'ENERGYMANAGEMENTSYSTEM:ACTUATOR' and first.endswith('_act')))


def _label(spec, values):
    if spec.unique:
        return spec.name
    return values[0] if values and values[0] else ''


def _object_json(spec, obj, index):
    values = _values(obj)
    return {'index': index, 'label': _label(spec, values), 'values': values,
            'managed': _is_managed(spec, values)}


def _json_body():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ApiError('A JSON body is required.')
    return data


def _check_generation(data):
    seen = data.get('generation')
    if seen is not None and seen != idf_session.generation():
        raise ApiError('The model changed since this page was loaded. Reload it and try again.', 409)


def _locate(idf, spec, data):
    """The object a request names, verified: its position and its name must agree."""
    try:
        index = int(data.get('index'))
    except (TypeError, ValueError):
        raise ApiError('index is required.')
    bucket = _bucket(idf, spec)
    if not 0 <= index < len(bucket):
        raise ApiError('That object no longer exists. Reload the page.', 409)
    obj = bucket[index]
    expected = data.get('label')
    if expected is not None and not spec.unique:
        values = _values(obj)
        if (values[0] if values else '') != expected:
            raise ApiError('That object changed. Reload the page.', 409)
    return obj, index


# ------------------------------------------------------ reference graph

def _consumers(schema):
    """{reference group: [(class UPPER, 0-based field index)]} of fields that draw from it."""
    cached = getattr(schema, '_consumers', None)
    if cached is None:
        cached = {}
        for cls in schema.classes.values():
            for f in cls.fields:
                for group in f.object_lists:
                    cached.setdefault(group, []).append((cls.upper, f.index))
        schema._consumers = cached
    return cached


_names_cache = {'generation': None, 'groups': {}}


def _group_names(idf, schema, group):
    """{lower-case name: name as written} of every object offered by a reference group."""
    generation = idf_session.generation()
    if _names_cache['generation'] != generation:
        _names_cache['generation'] = generation
        _names_cache['groups'] = {}
    if group not in _names_cache['groups']:
        names = {}
        for cls, index in schema.providers.get(group, []):
            for obj in idf.idfobjects[cls]:
                if len(obj.obj) > index + 1:
                    value = _text(obj.obj[index + 1])
                    if value:
                        names.setdefault(value.lower(), value)
        _names_cache['groups'][group] = names
    return _names_cache['groups'][group]


def _candidates(idf, schema, field):
    """What a field may hold: ('keys', [...]), ('objects', [...]) or ('free', [])."""
    if field.keys:
        return 'keys', list(field.keys)
    groups = [g for g in field.object_lists if schema.providers.get(g)]
    if groups:
        merged = {}
        for group in groups:
            merged.update(_group_names(idf, schema, group))
        return 'objects', sorted(merged.values(), key=str.lower)
    return 'free', []


def _referrers(idf, schema, spec, name):
    groups = set()
    for f in spec.fields:
        groups.update(f.references)
    found = []
    if not groups or not name:
        return found
    wanted = name.lower()
    done = set()
    consumers = _consumers(schema)
    for group in groups:
        for cls, index in consumers.get(group, []):
            if (cls, index) in done:
                continue
            done.add((cls, index))
            for position, obj in enumerate(idf.idfobjects[cls]):
                if len(obj.obj) > index + 1 and _text(obj.obj[index + 1]).lower() == wanted:
                    other = schema.classes[cls]
                    found.append({'class': other.name, 'index': position,
                                  'label': _text(obj.obj[1]) if len(obj.obj) > 1 else '',
                                  'field': other.fields[index].name, 'fieldIndex': index})
    return found


# ------------------------------------------------------------ validation

def _validate(idf, schema, spec, index, value):
    """(error, warnings, normalised value) for `value` in field `index` of `spec`."""
    field = spec.field_for_index(index)
    if field is None:
        return "Field {} does not exist in {}.".format(index + 1, spec.name), [], value
    text = _text(value).strip()
    warnings = []
    if text == '':
        if field.required:
            warnings.append('{} is required by the IDD.'.format(field.name))
        return None, warnings, ''
    low = text.lower()
    if field.letter == 'N' or field.type in ('real', 'integer'):
        if low in ('autosize', 'autocalculate'):
            allowed = field.autosizable if low == 'autosize' else field.autocalculatable
            if not allowed:
                warnings.append('{} does not declare {} in the IDD.'.format(field.name, low))
            return None, warnings, text
        try:
            number = float(text)
        except ValueError:
            return "{} must be a number (got '{}').".format(field.name, text), [], value
        if field.type == 'integer' and number != int(number):
            warnings.append('{} is an integer field.'.format(field.name))
        if field.minimum is not None and (number <= field.minimum if field.minimum_excl else number < field.minimum):
            warnings.append('{} is below the minimum {}{}.'.format(
                field.name, ('> ' if field.minimum_excl else '') + format(field.minimum, 'g'),
                ' ' + field.units if field.units else ''))
        if field.maximum is not None and (number >= field.maximum if field.maximum_excl else number > field.maximum):
            warnings.append('{} is above the maximum {}{}.'.format(
                field.name, ('< ' if field.maximum_excl else '') + format(field.maximum, 'g'),
                ' ' + field.units if field.units else ''))
        return None, warnings, text
    if field.keys:
        match = next((k for k in field.keys if k.lower() == low), None)
        if match is None:
            warnings.append("'{}' is not one of the keys of {}.".format(text, field.name))
            return None, warnings, text
        return None, warnings, match
    groups = [g for g in field.object_lists if schema.providers.get(g)]
    if groups:
        for group in groups:
            hit = _group_names(idf, schema, group).get(low)
            if hit is not None:
                return None, warnings, hit
        warnings.append("'{}' does not name an existing object ({}).".format(text, ', '.join(groups)))
    return None, warnings, text


def _validate_all(idf, schema, spec, changes):
    cleaned, warnings = {}, []
    for index, value in changes.items():
        error, found, normal = _validate(idf, schema, spec, index, value)
        if error:
            raise ApiError(error)
        warnings.extend(found)
        cleaned[index] = normal
    return cleaned, warnings


def _changes(data):
    raw = data.get('values')
    if not isinstance(raw, dict):
        raise ApiError('values must be an object {fieldIndex: value}.')
    try:
        return {int(k): v for k, v in raw.items()}
    except ValueError:
        raise ApiError('values keys must be field indexes.')


def _answer(extra=None, warnings=None):
    body = {'ok': True, 'generation': idf_session.generation(), 'warnings': warnings or []}
    if extra:
        body.update(extra)
    return jsonify(body), 200


# --------------------------------------------------------------- reading

@idf_editor_bp.route('/state', methods=['GET'])
def state():
    schema = _schema()
    path = idf_session.working_path()
    return jsonify({'hasModel': path is not None, 'file': os.path.basename(path) if path else '',
                    'generation': idf_session.generation(),
                    'idd': {'version': schema.version, 'build': schema.build}}), 200


@idf_editor_bp.route('/overview', methods=['GET'])
def overview():
    idf = idf_session.get()
    schema = _schema()
    counts = {key: len(items) for key, items in idf.idfobjects.items()}
    groups = []
    for group, classes in schema.groups:
        groups.append({'name': group, 'classes': [
            {'name': c.name, 'count': counts.get(c.upper, 0), 'unique': c.unique,
             'memo': c.memo[0] if c.memo else ''} for c in classes]})
    return jsonify({'generation': idf_session.generation(), 'groups': groups}), 200


@idf_editor_bp.route('/class', methods=['GET'])
def class_spec():
    upto = request.args.get('upto', type=int)
    return jsonify(_spec(request.args.get('name')).to_json(upto=upto)), 200


@idf_editor_bp.route('/objects', methods=['GET'])
def objects():
    idf = idf_session.get()
    spec = _spec(request.args.get('class'))
    offset = max(request.args.get('offset', 0, type=int), 0)
    limit = min(max(request.args.get('limit', 200, type=int), 1), 1000)
    query = (request.args.get('q') or '').strip().lower()
    rows = []
    for index, obj in enumerate(_bucket(idf, spec)):
        entry = _object_json(spec, obj, index)
        if query and query not in ' '.join(entry['values']).lower():
            continue
        rows.append(entry)
    return jsonify({'class': spec.name, 'total': len(rows), 'generation': idf_session.generation(),
                    'objects': rows[offset:offset + limit]}), 200


@idf_editor_bp.route('/candidates', methods=['GET'])
def candidates():
    idf = idf_session.get()
    spec = _spec(request.args.get('class'))
    index = request.args.get('field', type=int)
    field = spec.field_for_index(index) if index is not None else None
    if field is None:
        raise ApiError('field is required.')
    kind, values = _candidates(idf, _schema(), field)
    return jsonify({'kind': kind, 'values': values}), 200


@idf_editor_bp.route('/referrers', methods=['GET'])
def referrers():
    idf = idf_session.get()
    spec = _spec(request.args.get('class'))
    obj, _ = _locate(idf, spec, {'index': request.args.get('index'), 'label': request.args.get('label')})
    values = _values(obj)
    return jsonify({'referrers': _referrers(idf, _schema(), spec, values[0] if values else '')}), 200


# --------------------------------------------------------------- writing

@idf_editor_bp.route('/object', methods=['POST'])
def create_object():
    data = _json_body()
    spec = _spec(data.get('class'))
    idf = idf_session.get()
    _check_generation(data)
    if spec.unique and len(_bucket(idf, spec)):
        raise ApiError('{} may appear only once, and it already exists.'.format(spec.name), 409)
    changes, warnings = _validate_all(idf, _schema(), spec, _changes(data))
    box = {}

    def apply(model):
        obj = model.newidfobject(spec.upper, defaultvalues=False)
        for index in sorted(changes):
            _put(obj, index, changes[index])
        _trim(obj, spec)
        box['index'] = len(_bucket(model, spec)) - 1

    idf_session.mutate(apply)
    return _answer({'index': box['index']}, warnings)


@idf_editor_bp.route('/object', methods=['PATCH'])
def update_object():
    data = _json_body()
    spec = _spec(data.get('class'))
    idf = idf_session.get()
    _check_generation(data)
    obj, _ = _locate(idf, spec, data)
    changes, warnings = _validate_all(idf, _schema(), spec, _changes(data))
    for index, value in changes.items():
        field = spec.field_for_index(index)
        if index == 0 and field is not None and field.references and value:
            clash = _group_names(idf, _schema(), field.references[0]).get(value.lower())
            current = _text(obj.obj[1]) if len(obj.obj) > 1 else ''
            if clash is not None and clash.lower() != current.lower():
                warnings.append("Another object is already named '{}'.".format(clash))
    if _is_managed(spec, _values(obj)):
        warnings.append('The platform manages this object; the FMU/EMS pages may rewrite it.')

    def apply(model):
        target = _bucket(model, spec)[int(data['index'])]
        for index in sorted(changes):
            _put(target, index, changes[index])
        _trim(target, spec)

    idf_session.mutate(apply)
    return _answer(warnings=warnings)


@idf_editor_bp.route('/object', methods=['DELETE'])
def delete_object():
    data = _json_body()
    spec = _spec(data.get('class'))
    idf = idf_session.get()
    _check_generation(data)
    obj, _ = _locate(idf, spec, data)
    values = _values(obj)
    warnings = []
    dependants = _referrers(idf, _schema(), spec, values[0] if values else '')
    if dependants:
        warnings.append('{} object(s) still refer to {}: {}.'.format(
            len(dependants), values[0],
            ', '.join(sorted({'{} / {}'.format(d['class'], d['field']) for d in dependants}))))
    if _is_managed(spec, values):
        warnings.append('This object was written by the platform; the FMU/EMS pages may recreate it.')

    def apply(model):
        model.removeidfobject(_bucket(model, spec)[int(data['index'])])

    idf_session.mutate(apply)
    return _answer(warnings=warnings)


@idf_editor_bp.route('/object/duplicate', methods=['POST'])
def duplicate_object():
    data = _json_body()
    spec = _spec(data.get('class'))
    idf = idf_session.get()
    _check_generation(data)
    if spec.unique:
        raise ApiError('{} may appear only once.'.format(spec.name), 409)
    obj, _ = _locate(idf, spec, data)
    box = {}

    def apply(model):
        source = _bucket(model, spec)[int(data['index'])]
        copy = model.copyidfobject(source)
        first = spec.fields[0] if spec.fields else None
        if first is not None and first.references and len(copy.obj) > 1:
            taken = set()
            for group in first.references:
                taken.update(_group_names(model, _schema(), group))
            base, n = _text(copy.obj[1]), 2
            candidate = base + ' copy'
            while candidate.lower() in taken:
                candidate = '{} copy {}'.format(base, n)
                n += 1
            copy.obj[1] = candidate
        box['index'] = len(_bucket(model, spec)) - 1

    idf_session.mutate(apply)
    return _answer({'index': box['index']})


@idf_editor_bp.route('/object/rename', methods=['POST'])
def rename_object():
    data = _json_body()
    spec = _spec(data.get('class'))
    idf = idf_session.get()
    schema = _schema()
    _check_generation(data)
    obj, _ = _locate(idf, spec, data)
    new = (data.get('newName') or '').strip()
    if not new:
        raise ApiError('newName is required.')
    first = spec.fields[0] if spec.fields else None
    if first is None or not first.references:
        raise ApiError('{} objects are not referred to by name; edit the field instead.'.format(spec.name))
    old = _text(obj.obj[1])
    for group in first.references:
        clash = _group_names(idf, schema, group).get(new.lower())
        if clash is not None and clash.lower() != old.lower():
            raise ApiError("'{}' is already used by another object.".format(clash), 409)
    dependants = _referrers(idf, schema, spec, old)

    def apply(model):
        _bucket(model, spec)[int(data['index'])].obj[1] = new
        for dep in dependants:
            target = idf_session.get().idfobjects[dep['class'].upper()][dep['index']]
            target.obj[dep['fieldIndex'] + 1] = new

    idf_session.mutate(apply)
    return _answer({'updated': len(dependants)})


# ----------------------------------------------------------- guided views

# Variables each comfort model reports, with units. Source: SetupOutputVariables.csv
# of the EnergyPlus 9.6.0 install, ThermalComfort.cc rows 3478-3516. A model key is
# only offered if the IDD still lists it; a variable only becomes a sensor once
# "Check model" finds it in the .rdd.
COMFORT_VARIABLES = {
    'Fanger': [('Zone Thermal Comfort Fanger Model PMV', ''), ('Zone Thermal Comfort Fanger Model PPD', '%')],
    'Pierce': [('Zone Thermal Comfort Pierce Model Effective Temperature PMV', ''),
               ('Zone Thermal Comfort Pierce Model Standard Effective Temperature PMV', ''),
               ('Zone Thermal Comfort Pierce Model Discomfort Index', ''),
               ('Zone Thermal Comfort Pierce Model Thermal Sensation Index', ''),
               ('Zone Thermal Comfort Pierce Model Standard Effective Temperature', 'C')],
    'KSU': [('Zone Thermal Comfort KSU Model Thermal Sensation Vote', '')],
    'AdaptiveASH55': [('Zone Thermal Comfort ASHRAE 55 Adaptive Model 90% Acceptability Status', ''),
                      ('Zone Thermal Comfort ASHRAE 55 Adaptive Model 80% Acceptability Status', ''),
                      ('Zone Thermal Comfort ASHRAE 55 Adaptive Model Running Average Outdoor Air Temperature', 'C'),
                      ('Zone Thermal Comfort ASHRAE 55 Adaptive Model Temperature', 'C')],
    'AdaptiveCEN15251': [('Zone Thermal Comfort CEN 15251 Adaptive Model Category I Status', ''),
                         ('Zone Thermal Comfort CEN 15251 Adaptive Model Category II Status', ''),
                         ('Zone Thermal Comfort CEN 15251 Adaptive Model Category III Status', ''),
                         ('Zone Thermal Comfort CEN 15251 Adaptive Model Running Average Outdoor Air Temperature', 'C'),
                         ('Zone Thermal Comfort CEN 15251 Adaptive Model Temperature', 'C')],
    'CoolingEffectASH55': [('Zone Thermal Comfort ASHRAE 55 Elevated Air Speed Cooling Effect', 'C'),
                           ('Zone Thermal Comfort ASHRAE 55 Elevated Air Speed Cooling Effect Adjusted PMV', ''),
                           ('Zone Thermal Comfort ASHRAE 55 Elevated Air Speed Cooling Effect Adjusted PPD', '')],
    'AnkleDraftASH55': [('Zone Thermal Comfort ASHRAE 55 Ankle Draft PPD', '')],
}
COMFORT_COMMON_VARIABLES = [('Zone Thermal Comfort Mean Radiant Temperature', 'C'),
                            ('Zone Thermal Comfort Operative Temperature', 'C'),
                            ('Zone Thermal Comfort Clothing Value', 'clo')]
# SetupOutputVariables.csv, ZoneContaminantPredictorCorrector.cc rows 4061 and 4064,
# InternalHeatGains.cc row 1592.
CO2_VARIABLES = [('Zone Air CO2 Concentration', 'ppm'),
                 ('Zone Air CO2 Internal Gain Volume Flow Rate', 'm3/s'),
                 ('Zone Contaminant Source or Sink CO2 Gain Volume Flow Rate', 'm3/s')]
# Report keys offered by name; the IDD decides which exist.
COMFORT_REPORTS = ['AdaptiveComfortSummary', 'ComfortReportSimple55Monthly', 'ThermalResilienceSummary']
CO2_REPORTS = ['CO2ResilienceSummary']

_ONLY_REQUIRED = re.compile(r'only required for runs of thermal comfort models:?\s*([^)]*)', re.I)


def _comfort_layout(schema):
    people = schema.get('People')
    if people is None:
        raise ApiError('This IDD has no People class.', 500)
    slots = [f.index for f in people.fields if re.match(r'^Thermal Comfort Model \d+ Type$', f.name)]
    if not slots:
        raise ApiError('This IDD lists no thermal comfort model fields in People.', 500)
    keys = list(people.fields[slots[0]].keys)
    needed_by = {}
    for f in people.fields:
        for note in f.notes:
            m = _ONLY_REQUIRED.search(note)
            if m:
                words = set(w.lower() for w in re.findall(r'[A-Za-z0-9]+', m.group(1)))
                needed_by[f.index] = [k for k in keys if k.lower() in words]
    start = next((f.index for f in people.fields if 'comfort' in f.name.lower()), slots[0])
    return people, slots, keys, needed_by, start


def _key_in(keys, value):
    low = value.strip().lower()
    return next((k for k in keys if k.lower() == low), None)


def _existing_outputs(idf):
    seen = set()
    for obj in idf.idfobjects['OUTPUT:VARIABLE']:
        if len(obj.obj) > 2:
            seen.add((_text(obj.obj[1]).lower(), _text(obj.obj[2]).lower()))
    return seen


def _has_output(seen, name):
    return any(n == name.lower() for _, n in seen)


@idf_editor_bp.route('/comfort', methods=['GET'])
def comfort():
    idf = idf_session.get()
    schema = _schema()
    people, slots, keys, needed_by, start = _comfort_layout(schema)
    seen = _existing_outputs(idf)
    mrt_field = next((f.index for f in people.fields if f.name == 'Mean Radiant Temperature Calculation Type'), None)
    angle_field = next((f.index for f in people.fields if 'Angle Factor List' in f.name), None)
    rows = []
    for position, obj in enumerate(_bucket(idf, people)):
        values = _values(obj)
        values += [''] * (len(people.fields) - len(values))
        chosen, unknown = [], []
        for slot in slots:
            raw = values[slot].strip()
            if raw:
                key = _key_in(keys, raw)
                (chosen if key else unknown).append(key or raw)
        active = [k for k in chosen]
        missing = []
        for index, models in needed_by.items():
            # The surface / angle-factor field is read only when the radiant
            # temperature is not zone averaged (Input Output Reference, People,
            # "Mean Radiant Temperature Calculation Type", p. 516): E+'s own
            # comfort example leaves it blank with ZoneAveraged.
            if index == angle_field and (mrt_field is None or
                                         values[mrt_field].strip().lower() not in ('surfaceweighted', 'anglefactor')):
                continue
            if not values[index].strip():
                users = [m for m in models if m in active]
                if users:
                    missing.append({'field': index, 'name': people.fields[index].name, 'neededBy': users})
        rows.append({
            'index': position, 'name': values[0], 'zone': values[1], 'values': values,
            'models': active, 'unknownModels': unknown,
            'duplicates': sorted({k for k in active if active.count(k) > 1}),
            'missing': missing,
        })
    models = []
    for key in keys:
        models.append({'key': key, 'variables': [
            {'name': n, 'units': u, 'present': _has_output(seen, n)} for n, u in COMFORT_VARIABLES.get(key, [])]})
    present_reports = _present_reports(idf)
    control = [{'class': c.name, 'count': len(idf.idfobjects[c.upper])}
               for c in schema.classes.values() if 'ThermalComfort' in c.name and len(idf.idfobjects[c.upper])]
    return jsonify({
        'generation': idf_session.generation(), 'models': models, 'people': rows,
        'common': [{'name': n, 'units': u, 'present': _has_output(seen, n)} for n, u in COMFORT_COMMON_VARIABLES],
        'slots': slots, 'fieldsFrom': start, 'dependencies': {str(k): v for k, v in needed_by.items()},
        'class': people.to_json(), 'reports': _report_options(schema, COMFORT_REPORTS, present_reports),
        'controlObjects': control,
        'source': 'Variable names: SetupOutputVariables.csv, EnergyPlus 9.6.0 (ThermalComfort.cc). '
                  'Requirements: the IDD notes of the People class.',
    }), 200


def _summary_spec(schema):
    return schema.get('Output:Table:SummaryReports')


def _present_reports(idf):
    present = set()
    for obj in idf.idfobjects['OUTPUT:TABLE:SUMMARYREPORTS']:
        present.update(_text(v).lower() for v in obj.obj[1:] if _text(v))
    return present


def _report_options(schema, wanted, present):
    spec = _summary_spec(schema)
    listed = set(k.lower() for k in spec.fields[0].keys) if spec and spec.fields else set()
    return [{'key': k, 'present': k.lower() in present} for k in wanted if k.lower() in listed]


@idf_editor_bp.route('/comfort/models', methods=['POST'])
def set_comfort_models():
    """Give the listed People objects exactly these comfort models, in IDD key order, no gaps."""
    data = _json_body()
    idf = idf_session.get()
    schema = _schema()
    _check_generation(data)
    people, slots, keys, needed_by, start = _comfort_layout(schema)
    wanted = data.get('models')
    if not isinstance(wanted, list):
        raise ApiError('models must be a list of model keys.')
    chosen = []
    for item in wanted:
        key = _key_in(keys, str(item))
        if key is None:
            raise ApiError("'{}' is not a comfort model of this EnergyPlus version.".format(item))
        if key not in chosen:
            chosen.append(key)
    chosen = [k for k in keys if k in chosen]
    if len(chosen) > len(slots):
        raise ApiError('A People object has {} comfort model slots.'.format(len(slots)))
    targets = data.get('indexes')
    bucket = _bucket(idf, people)
    if not isinstance(targets, list) or not targets:
        raise ApiError('indexes must list the People objects to change.')
    for t in targets:
        if not isinstance(t, int) or not 0 <= t < len(bucket):
            raise ApiError('That People object no longer exists. Reload the page.', 409)

    def apply(model):
        items = _bucket(model, people)
        for t in targets:
            obj = items[t]
            for n, slot in enumerate(slots):
                _put(obj, slot, chosen[n] if n < len(chosen) else '')
            _trim(obj, people)
        if data.get('addOutputs'):
            _add_outputs(model, [n for k in chosen for n, _ in COMFORT_VARIABLES.get(k, [])],
                         data.get('frequency') or 'Timestep')

    idf_session.mutate(apply)
    return _answer({'models': chosen})


def _add_outputs(model, names, frequency):
    spec = _schema().get('Output:Variable')
    by_name = {f.name: f for f in spec.fields}
    freq = by_name.get('Reporting Frequency')
    if freq is not None and freq.keys:
        match = _key_in(freq.keys, frequency)
        if match is None:
            raise ApiError("'{}' is not a reporting frequency.".format(frequency))
        frequency = match
    seen = _existing_outputs(model)
    added = 0
    for name in names:
        if _has_output(seen, name):
            continue
        obj = model.newidfobject(spec.upper, defaultvalues=False)
        _put(obj, by_name['Key Value'].index, '*')
        _put(obj, by_name['Variable Name'].index, name)
        _put(obj, by_name['Reporting Frequency'].index, frequency)
        seen.add(('*', name.lower()))
        added += 1
    return added


def _add_reports(model, schema, keys):
    spec = _summary_spec(schema)
    listed = spec.fields[0].keys
    objects_ = _bucket(model, spec)
    obj = objects_[0] if len(objects_) else model.newidfobject(spec.upper, defaultvalues=False)
    present = set(_text(v).lower() for v in obj.obj[1:] if _text(v))
    for key in keys:
        match = _key_in(listed, key)
        if match is None:
            raise ApiError("'{}' is not a summary report of this EnergyPlus version.".format(key))
        if match.lower() not in present:
            obj.obj.append(match)
            present.add(match.lower())


@idf_editor_bp.route('/outputs/add', methods=['POST'])
def add_outputs():
    data = _json_body()
    idf_session.get()
    _check_generation(data)
    names = data.get('variables') or []
    reports = data.get('reports') or []
    if not isinstance(names, list) or not isinstance(reports, list):
        raise ApiError('variables and reports must be lists.')
    box = {}

    def apply(model):
        box['added'] = _add_outputs(model, [str(n) for n in names], data.get('frequency') or 'Timestep')
        if reports:
            _add_reports(model, _schema(), reports)

    idf_session.mutate(apply)
    return _answer({'added': box['added']})


# ----------------------------------------------------- the Outputs tab
# What the simulation reports. The work is in output_requests; these routes validate
# first and write after (idf_session.mutate cannot roll back).

def _outputs_layout():
    schema = _schema()
    layout = getattr(schema, '_output_layout', None)
    if layout is None:
        layout = output_requests.Layout(schema)
        schema._output_layout = layout
    return layout


def _checked(fn, *args):
    try:
        return fn(*args)
    except output_requests.Conflict as error:
        raise ApiError(str(error), 409)
    except ValueError as error:
        raise ApiError(str(error))


_SCHEDULE_WARNING = ('An Output:Variable with a schedule stops the BESOS design evaluator from reading its '
                     'results (the design page counts these).')


@idf_editor_bp.route('/outputs', methods=['GET'])
def outputs():
    idf = idf_session.get()
    body = output_requests.read(idf, _outputs_layout())
    body['generation'] = idf_session.generation()
    return jsonify(body), 200


@idf_editor_bp.route('/outputs/variable', methods=['POST'])
def add_output_variable():
    data = _json_body()
    idf = idf_session.get()
    _check_generation(data)
    layout = _outputs_layout()
    checked = _checked(output_requests.check_variable, idf, layout, data.get('key'), data.get('name'),
                       data.get('frequency'), data.get('schedule'))
    box = {}
    idf_session.mutate(lambda model: box.update(index=output_requests.add_variable(model, layout, checked)))
    return _answer({'index': box['index']}, [_SCHEDULE_WARNING] if checked['schedule'] else None)


@idf_editor_bp.route('/outputs/meter', methods=['POST'])
def add_output_meter():
    data = _json_body()
    idf = idf_session.get()
    _check_generation(data)
    layout = _outputs_layout()
    checked = _checked(output_requests.check_meter, idf, layout, data.get('name'), data.get('frequency'),
                       data.get('cumulative'), data.get('fileOnly'))
    box = {}
    idf_session.mutate(lambda model: box.update(index=output_requests.add_meter(model, layout, checked)))
    return _answer({'index': box['index'], 'class': checked['class']})


@idf_editor_bp.route('/outputs/request', methods=['PATCH'])
def change_output_requests():
    """Set frequency / key / name / schedule (variables) or frequency / name / cumulative / file only
    (meters) on one or several requests. One request that cannot take it is an error; among several,
    the ones a sensor or FMU output reads are skipped and reported."""
    data = _json_body()
    idf = idf_session.get()
    _check_generation(data)
    layout = _outputs_layout()
    objs = _checked(output_requests.locate, idf, layout, data.get('requests'))
    changes = data.get('changes')
    plan, skipped = _checked(output_requests.plan_changes, idf, layout, objs, changes, len(objs) == 1)
    if plan:
        idf_session.mutate(lambda model: output_requests.apply_changes(model, layout, plan))
    warnings = [_SCHEDULE_WARNING] if (changes or {}).get('schedule') else []
    return _answer({'changed': len(plan),
                    'skipped': [{'name': row['name'], 'why': why} for row, why in skipped]}, warnings)


@idf_editor_bp.route('/outputs/request', methods=['DELETE'])
def remove_output_requests():
    """Remove requests. A sensor chain or FMU output that reads one of them as its only source goes
    with it, but only with `cascade: true`; without it the answer lists them (409)."""
    data = _json_body()
    idf = idf_session.get()
    _check_generation(data)
    layout = _outputs_layout()
    objs = _checked(output_requests.locate, idf, layout, data.get('requests'))
    cascade, informed = output_requests.removal_dependants(idf, layout, objs)
    if cascade and not data.get('cascade'):
        return jsonify({'error': 'Something reads these outputs; removing them removes that too.',
                        'needsCascade': True, 'dependants': cascade}), 409
    dropped = idf_session.mutate(lambda model: output_requests.remove(model, layout, objs))
    for name in dropped:
        fmu_roles.drop(name)
    warnings = ["The model's own EMS sensor '{}' reads a removed output; it was left as it is.".format(
        u['name']) for u in informed]
    return _answer({'removed': len(objs), 'cascaded': cascade}, warnings)


@idf_editor_bp.route('/co2', methods=['GET'])
def co2():
    idf = idf_session.get()
    schema = _schema()
    balance = schema.get('ZoneAirContaminantBalance')
    people = schema.get('People')
    rate = next((f for f in people.fields if f.name == 'Carbon Dioxide Generation Rate'), None)
    flag = next((f for f in balance.fields if f.name == 'Carbon Dioxide Concentration'), None)
    outdoor = next((f for f in balance.fields if f.name.startswith('Outdoor Carbon Dioxide')), None)
    if rate is None or flag is None or outdoor is None:
        raise ApiError('This IDD does not describe the CO2 fields the editor expects.', 500)
    existing = _bucket(idf, balance)
    state_ = None
    if len(existing):
        values = _values(existing[0]) + [''] * len(balance.fields)
        state_ = {'enabled': values[flag.index].strip().lower() == 'yes', 'flag': values[flag.index],
                  'schedule': values[outdoor.index]}
    seen = _existing_outputs(idf)
    outdoor_schedule = None
    if state_ and state_['schedule']:
        constant = schema.get('Schedule:Constant')
        hourly = next((f for f in constant.fields if f.name.startswith('Hourly Value')), None)
        for position, obj in enumerate(_bucket(idf, constant)):
            values = _values(obj)
            if values and values[0].lower() == state_['schedule'].lower() and hourly is not None:
                users = _referrers(idf, schema, constant, values[0])
                outdoor_schedule = {'index': position, 'label': values[0], 'valueIndex': hourly.index,
                                    'value': values[hourly.index] if len(values) > hourly.index else '',
                                    'sharedWith': len(users) - 1}
                break
    sources = schema.get('ZoneContaminantSourceAndSink:CarbonDioxide')
    controller = schema.get('ZoneControl:ContaminantController')
    ventilation = schema.get('Controller:MechanicalVentilation')
    rows = []
    for position, obj in enumerate(_bucket(idf, people)):
        values = _values(obj) + [''] * len(people.fields)
        rows.append({'index': position, 'name': values[0], 'zone': values[1],
                     'rate': values[rate.index], 'values': values[:len(people.fields)]})
    return jsonify({
        'generation': idf_session.generation(),
        'balance': state_,
        'outdoorSchedule': outdoor_schedule,
        'balanceClass': balance.to_json(),
        'flagIndex': flag.index, 'scheduleIndex': outdoor.index,
        'rateField': rate.to_json(), 'people': rows,
        'sourceClass': sources.name if sources else None,
        'sourceCount': len(idf.idfobjects[sources.upper]) if sources else 0,
        'controllerCount': len(idf.idfobjects[controller.upper]) if controller else 0,
        'ventilationCount': len(idf.idfobjects[ventilation.upper]) if ventilation else 0,
        'variables': [{'name': n, 'units': u, 'present': _has_output(seen, n)} for n, u in CO2_VARIABLES],
        'reports': _report_options(schema, CO2_REPORTS, _present_reports(idf)),
        'source': 'Variable names: SetupOutputVariables.csv, EnergyPlus 9.6.0. Fields and notes: the IDD.',
    }), 200


@idf_editor_bp.route('/co2/balance', methods=['POST'])
def set_co2_balance():
    """Switch the CO2 balance on or off; create the object and, if asked, a constant outdoor schedule."""
    data = _json_body()
    idf = idf_session.get()
    schema = _schema()
    _check_generation(data)
    balance = schema.get('ZoneAirContaminantBalance')
    flag = next(f for f in balance.fields if f.name == 'Carbon Dioxide Concentration')
    outdoor = next(f for f in balance.fields if f.name.startswith('Outdoor Carbon Dioxide'))
    enabled = bool(data.get('enabled'))
    schedule = (data.get('schedule') or '').strip()
    create = data.get('createSchedule')
    yes = _key_in(flag.keys, 'Yes')
    no = _key_in(flag.keys, 'No')
    if yes is None or no is None:
        raise ApiError('The IDD no longer lists Yes/No for the CO2 flag.', 500)
    constant = schema.get('Schedule:Constant')
    if create:
        if constant is None:
            raise ApiError('This IDD has no Schedule:Constant.', 500)
        try:
            level = float(create.get('value'))
        except (TypeError, ValueError):
            raise ApiError('The outdoor CO2 level must be a number.')
        name = (create.get('name') or '').strip()
        if not name:
            raise ApiError('The new schedule needs a name.')
        if _group_names(idf, schema, 'ScheduleNames').get(name.lower()):
            raise ApiError("A schedule named '{}' already exists.".format(name), 409)
        schedule = name
    elif enabled and not schedule:
        raise ApiError('Choose the outdoor CO2 schedule (values in ppm), or create one.')
    elif schedule:
        hit = _group_names(idf, schema, 'ScheduleNames').get(schedule.lower())
        if hit is None:
            raise ApiError("'{}' is not an existing schedule.".format(schedule))
        schedule = hit

    def apply(model):
        if create:
            sched = model.newidfobject(constant.upper, defaultvalues=False)
            _put(sched, 0, schedule)
            hourly = next(f for f in constant.fields if f.name.startswith('Hourly Value'))
            _put(sched, hourly.index, format(level, 'g'))
        items = _bucket(model, balance)
        obj = items[0] if len(items) else model.newidfobject(balance.upper)
        _put(obj, flag.index, yes if enabled else no)
        if schedule:
            _put(obj, outdoor.index, schedule)

    idf_session.mutate(apply)
    return _answer()


# ---------------------------------------------------------- check model

_job = {'state': 'idle', 'started': None, 'finished': None, 'result': None}
_job_lock = threading.Lock()

_ERR_START = re.compile(r'^\s+\*\*\s+(Severe|Warning|Fatal)\s+\*\*(.*)$')
_ERR_MORE = re.compile(r'^\s+\*\*\s+~~~\s+\*\*(.*)$')


def _read_err(path):
    found = {'Severe': [], 'Warning': [], 'Fatal': []}
    last = None
    try:
        with open(path, encoding='latin-1') as handle:
            for line in handle:
                m = _ERR_START.match(line.rstrip('\r\n'))
                if m:
                    last = [m.group(2).strip()]
                    found[m.group(1)].append(last)
                    continue
                m = _ERR_MORE.match(line.rstrip('\r\n'))
                if m and last is not None:
                    last.append(m.group(1).strip())
    except OSError:
        pass
    return {kind: [' '.join(parts) for parts in items] for kind, items in found.items()}


def _run_check():
    import methods
    started = time.time()
    result = {'ok': False}
    try:
        source = idf_session.working_path()
        epws = sorted(glob.glob(os.path.join(idf_session.UPLOAD_FOLDER, '*.epw')))
        if not source or not epws:
            raise RuntimeError('The model or its weather file is missing.')
        probe = os.path.join(SIMULATION_OUTPUTS, 'ems_' + os.path.basename(source))
        shutil.copyfile(source, probe)
        methods.modify_idf_for_one_day_simulation(probe)
        methods.add_verbose(probe)
        methods.add_surface_details(probe)
        methods.delete_external_interface(probe)
        success = methods.run_energyplus_simulation(probe, epws[0])
        issues = _read_err(os.path.join(SIMULATION_OUTPUTS, 'eplusout.err'))
        result = {'ok': bool(success), 'severe': issues['Severe'], 'warnings': issues['Warning'],
                  'fatal': issues['Fatal']}
        if success:
            keys = methods.probe_variable_keys(probe, epws[0])
            result['variableKeys'] = len(keys)
    except Exception as error:  # reported to the page, not raised in a thread
        result = {'ok': False, 'severe': [], 'warnings': [], 'fatal': [str(error)]}
    result['seconds'] = round(time.time() - started, 1)
    with _job_lock:
        _job.update(state='done', finished=time.time(), result=result)


@idf_editor_bp.route('/check', methods=['POST'])
def check_model():
    """Run the model for one day, report EnergyPlus' errors and refresh the variable catalogue."""
    idf_session.get()
    with _job_lock:
        if _job['state'] == 'running':
            raise ApiError('A check is already running.', 409)
        _job.update(state='running', started=time.time(), finished=None, result=None)
    threading.Thread(target=_run_check, daemon=True).start()
    return jsonify({'state': 'running'}), 202


@idf_editor_bp.route('/check/status', methods=['GET'])
def check_status():
    with _job_lock:
        body = {'state': _job['state'], 'result': _job['result']}
        if _job['state'] == 'running':
            body['elapsed'] = round(time.time() - _job['started'], 1)
    return jsonify(body), 200
