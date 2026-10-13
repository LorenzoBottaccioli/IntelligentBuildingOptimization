"""What each FMU variable is for: observation, reward, or an action with limits.

The roles live in a JSON sidecar next to the working IDF, not in the browser.
They have to survive a page refresh, and they are part of the model's FMU
interface (the notebooks and the exported parameters.py are built from them),
not UI state. Beside the model they also die with it: a new upload, a session
reset or a revert clears them, and removing an FMU variable drops its entry.

    { "<fmuVariableName>": {"role": "observation" | "reward"} }   From:Variable
    { "<fmuVariableName>": {"min": number, "max": number} }       To:Actuator/Variable/Schedule
"""

import json
import os
import tempfile
import threading

import idf_session

FILE_NAME = 'fmu_roles.json'

_lock = threading.RLock()


def _path():
    """Sidecar path, or None when no working IDF exists."""
    idf_path = idf_session.working_path()
    if not idf_path:
        return None
    return os.path.join(os.path.dirname(idf_path) or '.', FILE_NAME)


def load():
    path = _path()
    if not path or not os.path.isfile(path):
        return {}
    with _lock:
        try:
            with open(path, 'r', encoding='utf-8') as handle:
                data = json.load(handle)
        except (OSError, ValueError):
            return {}
    return data if isinstance(data, dict) else {}


def save(roles):
    """Write atomically: a temp file in the same directory, then os.replace."""
    path = _path()
    if not path:
        return
    with _lock:
        directory = os.path.dirname(path) or '.'
        handle, temp = tempfile.mkstemp(dir=directory, prefix='.fmu_roles_', suffix='.tmp')
        try:
            with os.fdopen(handle, 'w', encoding='utf-8') as out:
                json.dump(roles, out, indent=2)
            os.replace(temp, path)
        except Exception:
            if os.path.exists(temp):
                os.remove(temp)
            raise


def set_entry(name, role=None, min=None, max=None):
    """Merge role and/or limits into the entry for `name`; returns all roles."""
    with _lock:
        roles = load()
        entry = dict(roles.get(name, {}))
        if role is not None:
            entry['role'] = role
        if min is not None:
            entry['min'] = min
        if max is not None:
            entry['max'] = max
        roles[name] = entry
        save(roles)
        return roles


def set_many(updates):
    """Merge {name: {role, min, max}} into the sidecar with ONE read and ONE write."""
    with _lock:
        roles = load()
        for name, fields in updates.items():
            entry = dict(roles.get(name, {}))
            entry.update({k: v for k, v in fields.items() if k in ('role', 'min', 'max') and v is not None})
            roles[name] = entry
        save(roles)
        return roles


def drop(name):
    with _lock:
        roles = load()
        if name in roles:
            del roles[name]
            save(roles)
        return roles


def clear():
    path = _path()
    if path and os.path.isfile(path):
        with _lock:
            try:
                os.remove(path)
            except OSError:
                pass
