"""Kits: a list of choices for Sensors & actuators, by name, applicable to any model.

A kit says "the mean air temperature of every zone, the outdoor temperature, the heating setpoint of every
zone" and not "these 4 FMU variables": it is resolved on the model that is open, and what the model does not
have is reported instead of invented. Two sources:

* the kits the platform provides (below), always there;
* the kits of the session, saved from a selection, in uploads/instrument_kits.json: the folder a session
  snapshots and restores, and that Reset session empties, so a project carries its own and a new one starts
  with the provided ones only.

An entry: {"tab": "sensors"|"meters"|"actuators"|"schedules", "title": the row's title (the variable without
its Rate/Energy suffix, the meter without its scope, the control type, the schedule name), "type": the
component type (actuators), "where": "scope" (the zones of the page) | "all" | "default" (the whole building
for a meter) | [labels], "role": "observation"|"reward", "min"/"max": a range, "variants": [variable names]}.
"""

import json
import os
import tempfile
import threading

import idf_session

FILE_NAME = 'instrument_kits.json'
TABS = ('sensors', 'meters', 'actuators', 'schedules')
WHERE = ('scope', 'all', 'default')
MAX_ENTRIES = 500
_lock = threading.RLock()

PROVIDED = [
    {
        'name': 'Comfort control',
        'description': 'The air temperature and humidity of every zone, the outdoor temperature, and the heating '
                       'and cooling setpoints of every zone as inputs.',
        'entries': [
            {'tab': 'sensors', 'title': 'Zone Mean Air Temperature', 'where': 'scope', 'role': 'observation'},
            {'tab': 'sensors', 'title': 'Zone Air Relative Humidity', 'where': 'scope', 'role': 'observation'},
            {'tab': 'sensors', 'title': 'Site Outdoor Air Drybulb Temperature', 'where': 'all', 'role': 'observation'},
            {'tab': 'actuators', 'title': 'Heating Setpoint', 'type': 'Zone Temperature Control', 'where': 'scope'},
            {'tab': 'actuators', 'title': 'Cooling Setpoint', 'type': 'Zone Temperature Control', 'where': 'scope'},
        ],
    },
    {
        'name': 'Energy',
        'description': 'What the building consumes (electricity, gas, district heating and cooling, for the whole '
                       'building) and the weather that drives it.',
        'entries': [
            {'tab': 'meters', 'title': 'Electricity', 'where': 'default', 'role': 'observation'},
            {'tab': 'meters', 'title': 'NaturalGas', 'where': 'default', 'role': 'observation'},
            {'tab': 'meters', 'title': 'DistrictHeating', 'where': 'default', 'role': 'observation'},
            {'tab': 'meters', 'title': 'DistrictCooling', 'where': 'default', 'role': 'observation'},
            {'tab': 'sensors', 'title': 'Site Outdoor Air Drybulb Temperature', 'where': 'all', 'role': 'observation'},
            {'tab': 'sensors', 'title': 'Site Direct Solar Radiation', 'where': 'all', 'role': 'observation'},
        ],
    },
]


def _path():
    folder = idf_session.UPLOAD_FOLDER
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, FILE_NAME)


def check_kit(kit):
    """The kit cleaned up, or ValueError saying what is wrong."""
    if not isinstance(kit, dict):
        raise ValueError('A kit is an object.')
    name = str(kit.get('name', '')).strip()
    if not name or len(name) > 60:
        raise ValueError('A kit needs a name of 1 to 60 characters.')
    if any(name.lower() == p['name'].lower() for p in PROVIDED):
        raise ValueError('"{}" is a kit of the platform: choose another name.'.format(name))
    entries = kit.get('entries')
    if not isinstance(entries, list) or not entries:
        raise ValueError('A kit needs at least one entry.')
    if len(entries) > MAX_ENTRIES:
        raise ValueError('A kit holds at most {} entries.'.format(MAX_ENTRIES))
    clean = []
    for e in entries:
        if not isinstance(e, dict) or e.get('tab') not in TABS or not str(e.get('title', '')).strip():
            raise ValueError('Every entry needs a tab ({}) and a title.'.format(', '.join(TABS)))
        where = e.get('where', 'scope')
        if not (where in WHERE or (isinstance(where, list) and all(isinstance(w, str) for w in where))):
            raise ValueError('"where" is one of {} or a list of names.'.format(', '.join(WHERE)))
        item = {'tab': e['tab'], 'title': str(e['title']).strip(), 'where': where}
        for key in ('type', 'role'):
            if e.get(key):
                item[key] = str(e[key])
        if e.get('variants'):
            item['variants'] = [str(v) for v in e['variants']]
        if e.get('min') is not None and e.get('max') is not None:
            item['min'], item['max'] = float(e['min']), float(e['max'])
            if item['min'] > item['max']:
                raise ValueError('min must not exceed max.')
        clean.append(item)
    return {'name': name, 'description': str(kit.get('description', ''))[:300], 'entries': clean}


def load_saved():
    with _lock:
        try:
            with open(_path(), encoding='utf-8') as handle:
                data = json.load(handle)
        except (OSError, ValueError):
            return []
    return [k for k in data if isinstance(k, dict) and k.get('name')] if isinstance(data, list) else []


def _write(kits):
    path = _path()
    handle, temp = tempfile.mkstemp(dir=os.path.dirname(path), prefix='.kits_', suffix='.tmp')
    try:
        with os.fdopen(handle, 'w', encoding='utf-8') as out:
            json.dump(kits, out, indent=2)
        os.replace(temp, path)
    except Exception:
        if os.path.exists(temp):
            os.remove(temp)
        raise


def save(kit):
    """Save (or replace, by name) a kit of the session; returns the saved ones."""
    clean = check_kit(kit)
    with _lock:
        kits = [k for k in load_saved() if k['name'].lower() != clean['name'].lower()]
        kits.append(clean)
        _write(kits)
        return kits


def delete(name):
    with _lock:
        kits = [k for k in load_saved() if k['name'].lower() != str(name).lower()]
        _write(kits)
        return kits


def all_kits():
    return {'provided': [dict(p, provided=True) for p in PROVIDED], 'saved': load_saved()}
