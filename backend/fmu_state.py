"""What the exported FMU was built from, and whether the model still says the same.

The export records the interface of the FMU (every output and input, with its role or range, and
the timesteps per hour) in Field/export_info.json. The Control room compares it with the model as
it is now and tells the student how many choices came after the last export, instead of leaving
the FMU silently out of date.
"""

import json
import os

import fmu_roles

INFO_FILE = 'export_info.json'
_FMU = 'ExternalInterface:FunctionalMockupUnitExport:'


def interface(idf, timestep=None):
    """{'timestep': n, 'entries': {fmu name: {kind, what, role, min, max}}} for the model as it is now."""
    roles = fmu_roles.load()
    entries = {}

    def add(name, kind, what):
        r = roles.get(name, {})
        entries[str(name)] = {'kind': kind, 'what': what, 'role': r.get('role'), 'min': r.get('min'), 'max': r.get('max')}

    for o in idf.idfobjects[_FMU + 'From:Variable']:
        add(o.FMU_Variable_Name, 'output', '{} at {}'.format(o.OutputVariable_Name, o.OutputVariable_Index_Key_Name))
    for o in idf.idfobjects[_FMU + 'To:Actuator']:
        add(o.FMU_Variable_Name, 'input', '{} of {}'.format(o.Actuated_Component_Control_Type, o.Actuated_Component_Unique_Name))
    for o in idf.idfobjects[_FMU + 'To:Variable']:
        add(o.FMU_Variable_Name, 'input', 'variable {}'.format(o.Name))
    for o in idf.idfobjects[_FMU + 'To:Schedule']:
        add(o.FMU_Variable_Name, 'input', 'schedule {}'.format(o.Schedule_Name))
    if timestep is None:
        ts = idf.idfobjects['TIMESTEP']
        raw = str(ts[0].Number_of_Timesteps_per_Hour).strip() if ts else ''
        timestep = int(float(raw)) if raw else 6
    return {'timestep': timestep, 'entries': entries}


def diff(before, now):
    """What changed between two interfaces, as lists of FMU names (plus whether the timestep did)."""
    a, b = before.get('entries', {}), now.get('entries', {})
    changed = sorted(n for n in a if n in b and a[n] != b[n])
    return {
        'added': sorted(n for n in b if n not in a),
        'removed': sorted(n for n in a if n not in b),
        'changed': changed,
        'timestep': before.get('timestep') != now.get('timestep') and before.get('timestep') is not None,
    }


def saved(field_dir):
    """The export_info.json of the last export, or {}."""
    try:
        with open(os.path.join(field_dir, INFO_FILE), encoding='utf-8') as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def status(field_dir, idf):
    """The state the Control room shows: never exported, exported before tracking, up to date, or N changes."""
    info = saved(field_dir)
    if not info:
        return {'exported': False}
    out = {'exported': True, 'exportedAt': info.get('exported_at'), 'fmu': info.get('fmu')}
    before = info.get('interface')
    if not before:
        out['tracked'] = False
        return out
    d = diff(before, interface(idf))
    n = len(d['added']) + len(d['removed']) + len(d['changed']) + (1 if d['timestep'] else 0)
    out.update(tracked=True, upToDate=n == 0, changes=n, **d)
    return out
