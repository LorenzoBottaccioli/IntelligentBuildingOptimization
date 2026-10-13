"""What the Sensors & actuators page needs beyond the single add/remove routes.

Three things:

* `GET  /model_editor/zones`              the zones of the model with the geometry EnergyPlus resolved
                                          (level, floor area, exterior walls by orientation);
* `POST /model_editor/actuator_defaults`  a proposed range for actuators, with where it comes from;
* `POST /model_editor/instrument_batch`   many additions in one go: one pass over the model, one save.

A model of a few hundred kB saves in about 0.1 s, a hospital of 4 MB in 3.4 s (eppy 0.5.63, measured):
ten additions one by one cost 41 s there, in a block 3.5 s. The batch also reports an error per item
instead of stopping at the first one.
"""

import os
import re

from flask import Blueprint, jsonify, request

import ems_chain
import fmu_roles
import idd_schema
import idf_reader
import idf_session
import instrument_kits

instrument_bp = Blueprint('instrument', __name__)

SIMULATION_OUTPUTS = 'simulation_outputs'
EIO = os.path.join(SIMULATION_OUTPUTS, 'eplusout.eio')
IDD_PATH = os.environ.get('IDD_PATH', '/app/EnergyPlus-9-6-0/Energy+.idd')

CARDINAL = (('N', 315, 45), ('E', 45, 135), ('S', 135, 225), ('W', 225, 315))


def _num(raw):
    try:
        return float(str(raw).strip())
    except (TypeError, ValueError):
        return None


def cardinal(azimuth):
    """North, east, south or west, in 90-degree sectors centred on each."""
    if azimuth is None:
        return ''
    a = azimuth % 360
    return 'N' if a >= 315 or a < 45 else 'E' if a < 135 else 'S' if a < 225 else 'W'


# ---- zones ------------------------------------------------------------------------

def _eio_tables(path=EIO):
    """{'zones': {UPPER name: {column: value}}, 'surfaces': {UPPER name: {column: value}}} from the .eio.

    Columns are found by the header the file itself writes, so a different order or an extra
    column does not shift anything.
    """
    zones, surfaces = {}, {}
    try:
        handle = open(path, encoding='latin-1')
    except OSError:
        return {'zones': zones, 'surfaces': surfaces}
    with handle:
        headers = {}
        for line in handle:
            cells = [c.strip() for c in line.rstrip('\r\n').split(',')]
            if not cells or not cells[0]:
                continue
            if cells[0] == '! <Zone Information>':
                headers['zone'] = cells
            elif cells[0] == '! <HeatTransfer Surface>':
                headers['surface'] = cells
            elif cells[0] == 'Zone Information' and 'zone' in headers:
                row = dict(zip(headers['zone'], cells))
                zones[row.get('Zone Name', '').upper()] = row
            elif cells[0] == 'HeatTransfer Surface' and 'surface' in headers:
                row = dict(zip(headers['surface'], cells))
                surfaces[row.get('Surface Name', '').upper()] = row
    return {'zones': zones, 'surfaces': surfaces}


def zones_overview(idf, eio=EIO):
    """Every zone of the model: name, level, floor area, volume and what its exterior walls face.

    The numbers are those EnergyPlus resolved (coordinate system, north axes, multipliers), read from
    the probe run's .eio rather than recomputed from the vertices. A model whose probe has no .eio
    still lists its zones, with `geometry` false.
    """
    tables = _eio_tables(eio)
    walls_of = {}
    for o in idf.idfobjects['BuildingSurface:Detailed']:
        row = tables['surfaces'].get(str(o.Name).upper())
        if not row or row.get('Surface Class', '').lower() != 'wall':
            continue
        if row.get('ExtBoundCondition', '').lower() != 'externalenvironment':
            continue
        area = _num(row.get('Area (Net) {m2}'))
        facing = cardinal(_num(row.get('Azimuth {deg}')))
        if facing and area is not None:
            by_facing = walls_of.setdefault(str(o.Zone_Name).upper(), {})
            by_facing[facing] = by_facing.get(facing, 0.0) + area

    out = []
    for zone in idf.idfobjects['Zone']:
        info = tables['zones'].get(str(zone.Name).upper())
        facings = sorted(walls_of.get(str(zone.Name).upper(), {}).items(), key=lambda kv: -kv[1])
        entry = {'name': zone.Name, 'geometry': bool(info)}
        if info:
            entry.update({
                'minZ': _num(info.get('Minimum Z {m}')),
                'maxZ': _num(info.get('Maximum Z {m}')),
                'floorArea': _num(info.get('Floor Area {m2}')),
                'volume': _num(info.get('Volume {m3}')),
                'exteriorWallArea': _num(info.get('Exterior Net Wall Area {m2}')),
                'windowArea': _num(info.get('Exterior Window Area {m2}')),
            })
        entry['facings'] = [{'facing': f, 'area': round(a, 2)} for f, a in facings]
        entry['mainFacing'] = facings[0][0] if facings else ''
        out.append(entry)

    # A level is a distinct height of the zone floor, counted from the lowest one.
    heights = sorted({round(z['minZ'], 1) for z in out if z.get('minZ') is not None})
    for z in out:
        if z.get('minZ') is not None:
            z['level'] = heights.index(round(z['minZ'], 1))
    return out


ZONE_LISTS = ('ZoneNames', 'ZoneAndZoneListNames')


def owners_of(idf, schema=None):
    """{UPPER object name: [zones]} for the objects that point at a zone, from the IDD alone.

    A class qualifies when one of its fields has an object-list of zone names (the IDD says
    "this object is about this zone", whatever its name), so People, Lights, equipment,
    infiltration, thermostats and the like are found without a list of classes. A zone list is
    expanded; a window belongs to the zone of its base surface; surfaces carry their zone field.
    Equipment reached only through a connection object (ZoneHVAC:EquipmentConnections) is not
    followed: its owner stays unknown and the page then offers it without a zone.
    """
    schema = schema or _schema()
    zone_names = {str(z.Name).upper(): str(z.Name) for z in idf.idfobjects['Zone']}
    lists = {str(z.obj[1]).strip().upper(): [str(v).strip() for v in z.obj[2:] if str(v).strip()]
             for z in idf.idfobjects['ZoneList']}

    def expand(value):
        value = str(value).strip()
        if value.upper() in zone_names:
            return [zone_names[value.upper()]]
        return [zone_names.get(v.upper(), v) for v in lists.get(value.upper(), [])]

    owners = {name.upper(): [name] for name in zone_names.values()}
    for cls_upper, cls in schema.classes.items():
        if cls.name.lower() in ('zone', 'zonelist') or not cls.fields or cls.fields[0].name != 'Name':
            continue
        field = next((f for f in cls.fields if any(o in ZONE_LISTS for o in f.object_lists)), None)
        if field is None:
            continue
        for o in idf.idfobjects[cls_upper]:
            if len(o.obj) <= field.index + 1:
                continue
            zs = expand(o.obj[field.index + 1])
            if zs and str(o.obj[1]).strip():
                owners[str(o.obj[1]).strip().upper()] = zs
    for o in idf.idfobjects['FenestrationSurface:Detailed']:
        base = owners.get(str(o.Building_Surface_Name).strip().upper())
        if base:
            owners[str(o.Name).strip().upper()] = base
    return owners


@instrument_bp.route('/zones', methods=['GET'])
def zones():
    try:
        if not idf_session.has_model():
            return jsonify({'zones': [], 'geometry': False, 'owners': {}}), 200
        idf = idf_session.get()
        rows = zones_overview(idf)
        return jsonify({'zones': rows, 'geometry': any(r['geometry'] for r in rows),
                        'owners': owners_of(idf)}), 200
    except Exception as e:
        return jsonify({'error': 'Failed to read the zones.', 'details': str(e)}), 500


# ---- range of an actuator ---------------------------------------------------------

# Bounds that follow from the unit of the EDD (hard physical limits), as (min, max); None = open.
UNIT_BOUNDS = {
    '%': (0, 100), 'fraction': (0, 1), 'Fraction': (0, 1), 'on/off': (0, 1),
    'deg': (0, 360), 'degree': (0, 360), 'degrees': (0, 360),
    'kg/s': (0, None), 'm3/s': (0, None), 'kgWater/kgDryAir': (0, None), 'each': (0, None),
    'W': (0, None), 'W/m2': (0, None),
}
SETPOINT_DEFAULT = (10, 30)  # a temperature setpoint, when nothing else says better
WIDE_SETPOINT_SPAN = 60      # K: wider than this, the type limits say nothing about a setpoint

_NORM = re.compile(r'[^a-z0-9]')


def _norm(text):
    return _NORM.sub('', str(text).lower())


def _schema():
    return idd_schema.load(IDD_PATH)


def _idd_bounds(component_type, control_type):
    """min/max of the IDD field an actuator overrides, when the type names a class and the control a field.

    Strict on purpose: the component type must be an IDD class and the control type the name of one of
    its fields (or "Surface Property <field>"). On the 178 action kinds of the EnergyPlus examples this
    finds a field for 7 and bounds for 6 (absorptances, number of people, autosized flows): a thin
    source, shown as `idd` only when it fires.
    """
    schema = _schema()
    wanted = _norm(component_type)
    cls = next((c for c in schema.classes.values() if _norm(c.name) == wanted), None)
    if cls is None:
        return None
    control = _norm(control_type)
    control = control[len('surfaceproperty'):] if control.startswith('surfaceproperty') else control
    for f in cls.fields:
        if _norm(f.name) == control and (f.minimum is not None or f.maximum is not None):
            return f.minimum, f.maximum, f.name
    return None


def _limits_by_name(idf):
    out = {}
    for lim in idf_reader.schedule_type_limits(idf):
        lo, hi = _num(lim['lowerLimitValue']), _num(lim['upperLimitValue'])
        if lo is not None and hi is not None:
            out[str(lim['name']).upper()] = (lo, hi)
    return out


def suggest_ranges(idf, items, schedules, thermostats):
    """One {min, max, source, note} per {component, type, control, units}.

    Order of the sources: the model (the type limits of the thermostat's schedule, or of the schedule
    itself), then the IDD field, then the unit's own bounds, and only last a default for the quantity.
    """
    limits = _limits_by_name(idf)
    schedule_limits = {s['name'].upper(): s.get('limits', '') for s in schedules}

    def from_schedule(name):
        pair = limits.get(str(schedule_limits.get(str(name).upper(), '')).upper())
        return pair

    out = []
    for item in items:
        component = str(item.get('component', ''))
        ctype = str(item.get('type', ''))
        control = str(item.get('control', ''))
        units = str(item.get('units', '')).strip()
        result = {'min': None, 'max': None, 'source': 'none', 'note': ''}

        # 1. the model
        pair = None
        if re.fullmatch(r'zone temperature control', ctype, re.I) and re.search(r'(heating|cooling) setpoint', control, re.I):
            role = 'heating' if control.lower().startswith('heating') else 'cooling'
            for t in thermostats:
                if not any(z.upper() == component.upper() for z in t.get('zones', [])):
                    continue
                for c in t.get('controls', []):
                    pair = from_schedule((c.get('schedules') or {}).get(role, ''))
                    if pair:
                        break
                if pair:
                    break
            note = 'type limits of the thermostat schedule'
        elif ctype.lower().startswith('schedule:') and control.lower() == 'schedule value':
            pair = from_schedule(component)
            note = 'type limits of the schedule'
        if pair:
            span = pair[1] - pair[0]
            if units == 'C' and span > WIDE_SETPOINT_SPAN:
                # The type limits of a temperature schedule are often -60..200: true, and of no use as the
                # range of an action. Say so and start from a usual setpoint range.
                result.update(min=SETPOINT_DEFAULT[0], max=SETPOINT_DEFAULT[1], source='default',
                              note='the type limits ({:g}..{:g}) are too wide for a setpoint: a usual range, check it'.format(*pair))
            else:
                result.update(min=pair[0], max=pair[1], source='model', note=note)
            out.append(result)
            continue

        # 2. the IDD field
        bounds = _idd_bounds(ctype, control)
        if bounds:
            result.update(min=bounds[0], max=bounds[1], source='idd', note='IDD field "{}"'.format(bounds[2]))
            out.append(result)
            continue

        # 3. the unit
        if units in UNIT_BOUNDS:
            lo, hi = UNIT_BOUNDS[units]
            result.update(min=lo, max=hi, source='unit', note='bounds of [{}]'.format(units))
            out.append(result)
            continue

        # 4. a default for the quantity, last
        if units == 'C' and re.search(r'setpoint', control, re.I):
            result.update(min=SETPOINT_DEFAULT[0], max=SETPOINT_DEFAULT[1], source='default',
                          note='a usual setpoint range: check it')
        out.append(result)
    return out


@instrument_bp.route('/actuator_defaults', methods=['POST'])
def actuator_defaults():
    try:
        if not idf_session.has_model():
            return jsonify({'error': 'No IDF has been uploaded yet.'}), 400
        import model_editor
        import schedule_model
        data = request.get_json(silent=True) or {}
        idf = idf_session.get()
        rows = suggest_ranges(idf, data.get('items', []), model_editor._schedule_candidates(),
                              schedule_model.thermostats(idf))
        return jsonify({'ranges': rows}), 200
    except Exception as e:
        return jsonify({'error': 'Failed to propose the ranges.', 'details': str(e)}), 500


# ---- writes in a block -------------------------------------------------------------

def _finite(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and x == x and abs(x) != float('inf')


def apply_op(idf, op):
    """Apply one operation to the live model; returns {'fmuVariableName', ...}. Raises on a bad one."""
    kind = op.get('op')
    if kind == 'variable':
        if op.get('mode', 'direct') == 'ems':
            return ems_chain.add_monitored_quantity(
                idf, source_type='variable', source_name=op['variableName'], name=op['name'],
                index_key=op.get('indexKey', ''), fmu_variable_name=op.get('fmuVariableName'))
        return ems_chain.add_direct_variable(idf, op['indexKey'], op['variableName'], op['fmuVariableName'])
    if kind == 'meter':
        return ems_chain.add_monitored_quantity(
            idf, source_type='meter', source_name=op['meterName'], name=op['name'], index_key='',
            fmu_variable_name=op.get('fmuVariableName'))
    if kind == 'actuator':
        adder = ems_chain.add_controlled_actuator if op.get('mode') == 'program' else ems_chain.add_direct_actuator
        extra = {'monitor_status': op.get('monitorStatus', True)} if op.get('mode') == 'program' else {}
        return adder(idf, name=op['name'], component_name=op['component'], component_type=op['type'],
                     control_type=op['control'], fmu_variable_name=op.get('fmuVariableName'),
                     initial_value=op.get('initial', 0) or 0, **extra)
    if kind == 'schedule':
        return ems_chain.add_direct_schedule(
            idf, schedule_name=op['scheduleName'], fmu_variable_name=op.get('fmuVariableName'),
            initial_value=op.get('initial'))
    raise ValueError('unknown operation {!r}'.format(kind))


def check_op(op):
    """Why an operation cannot be applied, or None."""
    if not isinstance(op, dict):
        return 'not an object'
    role, low, high = op.get('role'), op.get('min'), op.get('max')
    if role is not None and role not in ('observation', 'reward'):
        return 'role must be "observation" or "reward"'
    if low is not None or high is not None:
        if not (_finite(low) and _finite(high)):
            return 'min and max must both be numbers'
        if low > high:
            return 'min must not exceed max'
    return None


def run_batch(ops):
    """Apply every valid operation in ONE pass over the model; one error per rejected one.

    Roles and ranges are written to the sidecar after the model, in one write.
    """
    results = [None] * len(ops)
    todo = []
    for i, op in enumerate(ops):
        problem = check_op(op)
        if problem:
            results[i] = {'index': i, 'ok': False, 'error': problem}
        else:
            todo.append((i, op))

    def apply_all(idf):
        for i, op in todo:
            try:
                got = apply_op(idf, op)
                results[i] = {'index': i, 'ok': True, 'fmuVariableName': got.get('fmuVariableName'),
                              'name': got.get('name')}
            except Exception as e:
                results[i] = {'index': i, 'ok': False, 'error': str(e) or e.__class__.__name__}

    if todo:
        idf_session.mutate(apply_all)

    updates = {}
    for i, op in todo:
        r = results[i]
        if r and r['ok'] and r.get('fmuVariableName'):
            entry = {}
            if op.get('role') is not None:
                entry['role'] = op['role']
            if op.get('min') is not None:
                entry['min'], entry['max'] = op['min'], op['max']
            if entry:
                updates[r['fmuVariableName']] = entry
    if updates:
        fmu_roles.set_many(updates)
    return results


@instrument_bp.route('/instrument_batch', methods=['POST'])
def instrument_batch():
    try:
        if not idf_session.has_model():
            return jsonify({'error': 'No IDF has been uploaded yet.'}), 400
        ops = (request.get_json(silent=True) or {}).get('ops')
        if not isinstance(ops, list) or not ops:
            return jsonify({'error': 'ops must be a non-empty list.'}), 400
        results = run_batch(ops)
        failed = sum(1 for r in results if not r['ok'])
        return jsonify({'results': results, 'added': len(results) - failed, 'failed': failed}), 200
    except Exception as e:
        return jsonify({'error': 'Failed to apply the batch.', 'details': str(e)}), 500


# ---- kits -----------------------------------------------------------------------

@instrument_bp.route('/kits', methods=['GET'])
def kits_get():
    return jsonify(instrument_kits.all_kits()), 200


@instrument_bp.route('/kits', methods=['POST'])
def kits_save():
    try:
        return jsonify({'saved': instrument_kits.save(request.get_json(silent=True))}), 200
    except ValueError as e:
        return jsonify({'error': str(e)}), 400


@instrument_bp.route('/kits', methods=['DELETE'])
def kits_delete():
    name = (request.get_json(silent=True) or {}).get('name', '')
    return jsonify({'saved': instrument_kits.delete(name)}), 200
