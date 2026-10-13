"""Saved sessions: name the working state, park it, come back to it later.

The platform has ONE working state per student group, spread over directories
that are bind-mounted into several containers. A session is a named snapshot of
that state:

    uploads, originals           the working IDF/EPW, fmu_roles.json, the pristine upload
    simulation_outputs           probe simulation (.edd/.rdd/.mdd, keys/variable_keys.json)
    user_files                   anything the student produced (FMUs, parameters, ...)
    simulation_notebooks, surrogate_notebooks,
    field (FMUs, parameters.py, points.yaml)
                                 the student's notebooks (shared with Jupyter)
    workspace                    the student's BMS code (devices/, iot/, ai/); not
                                 logs/ and not the teacher's .emergency flag
    openhab_conf (generated)     only the Things/Items/Sitemap that
                                 openhab_provisioner writes, not the rest of the
                                 openHAB configuration

    InfluxDB (base_building, controlled_building)
                                 portable backup made with `influxd backup -portable`
                                 inside the influxdb container (docker exec), written
                                 through the shared mount ./backend/sessions =
                                 /sessions there; restored with `influxd restore`
    Grafana dashboards, folders  exported/imported through the Grafana HTTP API
                                 (see session_stores.py)

The database names stay fixed, so the students' code never changes: opening a
session drops both databases and restores that session's data, a new session
starts with both empty. Still shared by all sessions: the Grafana datasources
(file-provisioned) and users. Provisioned dashboards are not touched. Saving
InfluxDB while the building runs would not be consistent, so a new or opened
session is refused (409) while the retained building process state is "running".
A failing InfluxDB/Grafana step never loses the folder snapshot: it is reported
as "warnings". flask_session (the browser cookie store) and notebook_templates
(read-only) are not part of a session either.

The surrogate notebook is written for one library (SURROGATE_ENGINE: BESOS or
bdopt, see engine.py and inject_data.py) and cannot run on the other one's image. A
session saved with the other flavour is opened with the current flavour's template
instead (the model of the session injected as at upload) and its own notebook is
kept beside it as SurrogateNotebook_<flavour>_backup.ipynb; the warning says so.

Layout under sessions/ (bind-mounted at /app/sessions):

    current.json                  {"id": ...}; absent = workspace in no session yet
    <id>/meta.json                {id, name, created, saved, idf, epw}
    <id>/state/<dirname>/...      the snapshot

The workspace directories are bind-mount roots shared with other containers:
they are only ever emptied and refilled, never removed or renamed. A snapshot,
by contrast, is built in a temporary directory and swapped in with os.replace,
so an interrupted save never leaves a half-written session.
"""

import glob
import json
import os
import re
import secrets
import shutil
import subprocess
import threading
import time
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request
from flask_cors import CORS

import idf_session
import inject_data
import openhab_provisioner
import session_stores
from engine import surrogate_engine

sessions_bp = Blueprint('sessions', __name__)
CORS(sessions_bp)

SESSIONS_DIR = 'sessions'
CURRENT_FILE = os.path.join(SESSIONS_DIR, 'current.json')

WORKSPACE_DIRS = [
    'uploads', 'originals', 'simulation_outputs', 'user_files',
    'simulation_notebooks', 'surrogate_notebooks',
    'workspace', 'field',
]

# Pre-workspace snapshots kept the student's BMS code here.
LEGACY_CONTROLLER_DIR = 'controller_notebooks'

# Teacher state living in the workspace root: never snapshotted, never emptied.
KEEP_IN_WORKSPACE = ('.emergency',)

# Files openhab_provisioner generates, relative to its conf root.
OPENHAB_GENERATED = [
    os.path.join('things', 'simbuilding.things'),
    os.path.join('items', 'simbuilding.items'),
    os.path.join('sitemaps', f'{openhab_provisioner.SITEMAP_NAME}.sitemap'),
]
OPENHAB_STATE_DIR = 'openhab_conf'

# What the students build in the two operator panels belongs to the session: the demo has its page and its
# entities, a new project starts empty. Both services read their files only when they start, so applying a
# state stops the container, swaps the files and starts it again (the platform has the docker socket).
HMI_STATE_DIR = 'hmi'
HMI_TARGETS = {
    'openhab': {
        'live': 'openhab_jsondb',            # ./openhab/jsondb: pages, things, items made in the Main UI
        'container': 'openhab',
        'globs': ['*.json'],
        'skip': ('users.json',),
        'defaults': {},
    },
    'homeassistant': {
        'live': 'homeassistant_config',      # ./homeassistant/config
        'container': 'homeassistant',
        # www/floorplan: the picture-elements of the plan dashboard point at /local/floorplan/*.svg
        'globs': ['mqtt.yaml', '.storage/lovelace*', 'www/floorplan/*.svg'],
        'skip': (),
        'defaults': {'mqtt.yaml': b'{}\n'},   # no MQTT entities
    },
    # The plan page of openHAB shows html/floorplan/plan.svg from the conf folder, which is not under jsondb.
    'openhab_plan': {
        'live': 'openhab_conf',              # ./openhab/conf
        'container': 'openhab',
        'globs': ['html/floorplan/*.svg'],
        'skip': (),
        'defaults': {},
    },
}
HMI_DOCKER_TIMEOUT = 90

_ID_RE = re.compile(r'^[a-z0-9][a-z0-9-]*$')
_lock = threading.RLock()


class SessionError(Exception):
    def __init__(self, message, code=400):
        super().__init__(message)
        self.code = code


# ---------------------------------------------------------------- small helpers

def _now():
    # Explicit UTC offset: the container clock is UTC, the browser shows local time.
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def _write_json(path, data):
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as handle:
        json.dump(data, handle, indent=2)
    os.replace(tmp, path)


def _read_json(path):
    try:
        with open(path, encoding='utf-8') as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def _session_dir(sid):
    if not isinstance(sid, str) or not _ID_RE.match(sid):
        raise SessionError('Unknown session.', 404)
    return os.path.join(SESSIONS_DIR, sid)


def _meta(sid):
    return _read_json(os.path.join(_session_dir(sid), 'meta.json'))


def _require(sid):
    meta = _meta(sid)
    if not meta:
        raise SessionError('Unknown session.', 404)
    return meta


def _current_id():
    pointer = _read_json(CURRENT_FILE)
    sid = pointer.get('id') if pointer else None
    if isinstance(sid, str) and _ID_RE.match(sid) and _meta(sid):
        return sid
    return None


def _set_current(sid):
    _write_json(CURRENT_FILE, {'id': sid})


def _new_id(name):
    slug = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')[:40].strip('-') or 'session'
    while True:
        sid = f'{slug}-{secrets.token_hex(3)}'
        if not os.path.exists(os.path.join(SESSIONS_DIR, sid)):
            return sid


def _clean_name(value):
    name = value.strip() if isinstance(value, str) else ''
    return name[:80]


def _workspace_names():
    """(idf, epw) basenames currently in uploads/, '' when absent."""
    idf = idf_session.working_path()
    epws = sorted(glob.glob(os.path.join(idf_session.UPLOAD_FOLDER, '*.epw')))
    return (os.path.basename(idf) if idf else '',
            os.path.basename(epws[0]) if idf and epws else '')


def _list_payload():
    metas = []
    if os.path.isdir(SESSIONS_DIR):
        for entry in os.listdir(SESSIONS_DIR):
            if _ID_RE.match(entry):
                meta = _read_json(os.path.join(SESSIONS_DIR, entry, 'meta.json'))
                if meta:
                    metas.append(meta)
    metas.sort(key=lambda m: m.get('saved', ''), reverse=True)
    return {'current': _current_id(), 'sessions': metas}


# ------------------------------------------------------- empty / copy workspace

def _empty_dir(path, keep=()):
    """Remove the contents of a bind-mount root, keeping the directory, any Dockerfile and `keep`."""
    os.makedirs(path, exist_ok=True)
    for entry in os.listdir(path):
        if entry == 'Dockerfile' or entry in keep:
            continue
        full = os.path.join(path, entry)
        if os.path.isdir(full) and not os.path.islink(full):
            shutil.rmtree(full)
        else:
            os.remove(full)


def _ignore_junk(directory, names):
    skip = [n for n in names if n in ('.ipynb_checkpoints', '__pycache__')]
    # Runtime logs of the student's BMS services and the teacher's emergency flag
    # are not part of a snapshot.
    if os.path.basename(os.path.normpath(directory)) == 'workspace':
        skip += [n for n in names if n == 'logs' or n in KEEP_IN_WORKSPACE]
    return skip


def _migrate_legacy_controller(src, dest):
    """Old snapshot (controller_notebooks/) -> workspace/ layout."""
    for entry in os.listdir(src):
        full = os.path.join(src, entry)
        if entry in ('logs', '.ipynb_checkpoints', '__pycache__'):
            continue
        if os.path.isdir(full):
            shutil.copytree(full, os.path.join(dest, entry), dirs_exist_ok=True,
                            ignore=shutil.ignore_patterns('.ipynb_checkpoints', '__pycache__'))
            continue
        if entry == 'integration.py':  # old name of the student's subscriber
            target = os.path.join(dest, 'iot')
            os.makedirs(target, exist_ok=True)
            shutil.copy2(full, os.path.join(target, 'subscriber.py'))
            continue
        elif entry == 'controller.py' or entry.endswith('.ipynb'):
            sub = 'ai'
        else:
            sub = ''
        target = os.path.join(dest, sub) if sub else dest
        os.makedirs(target, exist_ok=True)
        shutil.copy2(full, os.path.join(target, entry))


def _openhab_files():
    root = openhab_provisioner.OPENHAB_CONF_PATH
    return [(rel, os.path.join(root, rel)) for rel in OPENHAB_GENERATED]


def _remove_openhab_generated():
    for _rel, full in _openhab_files():
        if os.path.isfile(full):
            os.remove(full)


def _hmi_live_files(target):
    """{relative path: full path} of the session files of one operator panel, as they are now."""
    found = {}
    for pattern in target['globs']:
        for full in glob.glob(os.path.join(target['live'], pattern)):
            if os.path.isfile(full) and os.path.basename(full) not in target['skip']:
                found[os.path.relpath(full, target['live']).replace(os.sep, '/')] = full
    return found


def _hmi_wanted(target, name, state):
    """{relative path: bytes} the panel must have: its defaults, then the session's files over them."""
    wanted = dict(target['defaults'])
    root = os.path.join(state, HMI_STATE_DIR, name) if state else None
    if root and os.path.isdir(root):
        for folder, _dirs, files in os.walk(root):
            for entry in files:
                full = os.path.join(folder, entry)
                with open(full, 'rb') as handle:
                    wanted[os.path.relpath(full, root).replace(os.sep, '/')] = handle.read()
    return wanted


def _docker(*args):
    result = subprocess.run(['docker', *args], capture_output=True, text=True, timeout=HMI_DOCKER_TIMEOUT)
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout).strip()[-300:] or f'docker {args[0]} failed')


def _hmi_apply(state):
    """Give openHAB and Home Assistant the state of a session (state=None: an empty project).

    Nothing is touched, and nothing restarted, when a panel already has exactly that state.
    Returns warnings; a failing restart never fails the session (the files are in place for the next start).
    """
    plans = []
    for name, target in HMI_TARGETS.items():
        if not os.path.isdir(target['live']):
            continue
        wanted = _hmi_wanted(target, name, state)
        current = {}
        for rel, full in _hmi_live_files(target).items():
            with open(full, 'rb') as handle:
                current[rel] = handle.read()
        if wanted != current:
            plans.append((name, target, wanted))
    if not plans:
        return []
    warnings = []
    containers = list(dict.fromkeys(target['container'] for _n, target, _w in plans))
    stopped = False
    try:
        _docker('stop', *containers)
        stopped = True
    except Exception as exc:
        warnings.append(f'Could not stop {", ".join(containers)}: {exc}. The panels show the new session after a restart of them.')
    for name, target, wanted in plans:
        for full in _hmi_live_files(target).values():
            os.remove(full)
        for rel, content in wanted.items():
            full = os.path.join(target['live'], rel)
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, 'wb') as handle:
                handle.write(content)
    if stopped:
        try:
            _docker('start', *containers)
        except Exception as exc:
            warnings.append(f'Could not start {", ".join(containers)} again: {exc}')
    return warnings


def _snapshot(sid):
    """Copy the workspace into sessions/<sid>/state, swapped in atomically.

    Returns the InfluxDB/Grafana warnings. The temporary directory lives in
    sessions/<sid>/ so that influxdb can write its backup into it through the mount.
    """
    warnings = []
    base = _session_dir(sid)
    os.makedirs(base, exist_ok=True)
    tmp = os.path.join(base, f'.state-{secrets.token_hex(4)}.tmp')
    old = os.path.join(base, f'.state-{secrets.token_hex(4)}.old')
    state = os.path.join(base, 'state')
    try:
        os.makedirs(tmp)
        for name in WORKSPACE_DIRS:
            if os.path.isdir(name):
                shutil.copytree(name, os.path.join(tmp, name), ignore=_ignore_junk)
        for rel, full in _openhab_files():
            if os.path.isfile(full):
                dest = os.path.join(tmp, OPENHAB_STATE_DIR, rel)
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                shutil.copy2(full, dest)
        for name, target in HMI_TARGETS.items():
            for rel, full in _hmi_live_files(target).items():
                dest = os.path.join(tmp, HMI_STATE_DIR, name, rel)
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                shutil.copy2(full, dest)
        warnings += session_stores.influx_snapshot(sid, tmp)
        warnings += session_stores.grafana_snapshot(tmp)
        if os.path.isdir(state):
            os.replace(state, old)
        os.replace(tmp, state)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        shutil.rmtree(old, ignore_errors=True)
    # An interrupted swap (state moved to .old, new not yet in place) is the only
    # window without a state/; it is a rename apart, not a copy.
    return warnings


def _align_surrogate_notebook():
    """Make the restored surrogate notebook the flavour of the active engine.

    A notebook of the other flavour (BESOS in a bdopt platform or the reverse) is replaced
    by the template of the active engine, with the restored model injected the way an
    upload does it; the old notebook stays beside it. Returns warnings.
    """
    engine = surrogate_engine()
    try:
        action, backup = inject_data.align_notebook(engine, create=False)
        if action in ('kept', 'missing'):
            return []
        idf, epw = _workspace_names()
        if idf and epw:
            inject_data.inject_file(
                os.path.join(inject_data.NOTEBOOK_DIR, inject_data.NOTEBOOK_NAME),
                engine, idf, epw)
    except Exception as exc:  # the restore itself succeeded: report, do not fail
        return [f'The surrogate notebook could not be checked against the {engine} flavour: {exc}']
    if action == 'replaced':
        return [f'The surrogate notebook of this session was written for another library than '
                f'the one in use ({engine}). It was replaced by the {engine} notebook; '
                f'the old one is kept as {backup}.']
    return []


def _restore(sid):
    """Empty the workspace directories and copy the snapshot in. Returns warnings."""
    state = os.path.join(_session_dir(sid), 'state')
    for name in WORKSPACE_DIRS:
        _empty_dir(name, keep=KEEP_IN_WORKSPACE if name == 'workspace' else ())
        src = os.path.join(state, name)
        if os.path.isdir(src):
            shutil.copytree(src, name, dirs_exist_ok=True)
            if name == 'workspace':  # snapshot from before integration.py became subscriber.py
                old = os.path.join(name, 'iot', 'integration.py')
                new = os.path.join(name, 'iot', 'subscriber.py')
                if os.path.isfile(old) and not os.path.exists(new):
                    os.replace(old, new)
        elif name == 'workspace':
            legacy = os.path.join(state, LEGACY_CONTROLLER_DIR)
            if os.path.isdir(legacy):
                _migrate_legacy_controller(legacy, name)
    os.makedirs(os.path.join('workspace', 'logs'), exist_ok=True)
    _remove_openhab_generated()
    for rel, full in _openhab_files():
        src = os.path.join(state, OPENHAB_STATE_DIR, rel)
        if os.path.isfile(src):
            os.makedirs(os.path.dirname(full), exist_ok=True)
            shutil.copy2(src, full)
    return _hmi_apply(state) + _align_surrogate_notebook()


def _write_meta(sid, name, created=None):
    idf, epw = _workspace_names()
    now = _now()
    _write_json(os.path.join(_session_dir(sid), 'meta.json'), {
        'id': sid, 'name': name, 'created': created or now,
        'saved': now, 'idf': idf, 'epw': epw,
    })


def _save_into(sid):
    meta = _require(sid)
    warnings = _snapshot(sid)
    _write_meta(sid, meta['name'], meta.get('created'))
    return warnings


def _rebuild_memory():
    """Re-derive the in-memory state upload_files builds, from the restored files.

    Returns a list of warnings (empty when everything was rebuilt).
    """
    import model_editor
    warnings = []
    idf_session.invalidate()
    model_editor._PROBE_CACHE.clear()
    model_editor._KEYS_CACHE.update({'key': None, 'value': {}, 'tried': None})
    path = idf_session.working_path()
    if not path:
        return warnings
    try:
        idf_session.get()
    except Exception as exc:  # unreadable IDF: surface it, keep the rest usable
        warnings.append(f'The model could not be parsed: {exc}')
        return warnings
    try:
        # The SQL tables the edit routes read live inside the container and are
        # not in the snapshot; they are filled from the restored IDF exactly as
        # at upload, minus the probe simulation (simulation_outputs is restored)
        # and the notebook path injection (the notebooks are restored).
        model_editor.populate_tables(path)
    except Exception as exc:
        model_editor.db.session.rollback()
        warnings.append(f'The editor tables could not be rebuilt: {exc}')
    return warnings


def _empty_workspace():
    import model_editor
    model_editor.clear_workspace()
    _remove_openhab_generated()


def _payload(**extra):
    payload = _list_payload()
    payload.update(extra)
    return payload


def _autosave_current(except_id=None):
    sid = _current_id()
    if sid and sid != except_id:
        return _save_into(sid)
    return []


def _require_building_stopped():
    """409 while the building runs: its InfluxDB writes would be cut mid-run."""
    import bms_api
    bms_api._ensure_client()
    deadline = time.time() + 3
    while bms_api._building['process'] is None and time.time() < deadline:
        time.sleep(0.1)
    process = bms_api._building['process']
    if isinstance(process, dict) and process.get('state') == 'running':
        raise SessionError('The building is running: stop it in the Control room first.', 409)
    import direct_run
    if direct_run.is_active():
        raise SessionError('A direct EnergyPlus run is writing to InfluxDB: wait for it in the Control room.', 409)


def _with_warnings(warnings):
    return {'warnings': warnings} if warnings else {}


# ----------------------------------------------------------------------- routes

def _guarded(fn):
    def wrapper(*args, **kwargs):
        try:
            with _lock:
                return fn(*args, **kwargs)
        except SessionError as exc:
            return jsonify({'error': str(exc)}), exc.code
        except Exception as exc:
            return jsonify({'error': str(exc)}), 500
    wrapper.__name__ = fn.__name__
    return wrapper


@sessions_bp.route('', methods=['GET'])
@sessions_bp.route('/', methods=['GET'])
@_guarded
def list_sessions():
    return jsonify(_list_payload()), 200


@sessions_bp.route('/save', methods=['POST'])
@_guarded
def save_session():
    data = request.get_json(silent=True) or {}
    sid = _current_id()
    warnings = []
    if sid:
        warnings = _save_into(sid)
    else:
        name = _clean_name(data.get('name'))
        if not name:
            raise SessionError('A name is required to save the first session.')
        sid = _new_id(name)
        os.makedirs(_session_dir(sid))
        warnings = _snapshot(sid)
        _write_meta(sid, name)
        _set_current(sid)
    return jsonify(_payload(**_with_warnings(warnings))), 200


@sessions_bp.route('/new', methods=['POST'])
@_guarded
def new_session():
    data = request.get_json(silent=True) or {}
    name = _clean_name(data.get('name'))
    if not name:
        raise SessionError('A name is required.')
    _require_building_stopped()
    warnings = _autosave_current()
    _empty_workspace()
    warnings += _hmi_apply(None)
    warnings += session_stores.influx_restore(None)
    warnings += session_stores.grafana_restore(None)
    sid = _new_id(name)
    os.makedirs(_session_dir(sid))
    warnings += _snapshot(sid)
    _write_meta(sid, name)
    _set_current(sid)
    _rebuild_memory()
    return jsonify(_payload(**_with_warnings(warnings))), 200


def _open(sid, check_building=True, restore_stores=True):
    """Make session `sid` the working state: autosave the current one, restore this one. Returns warnings.

    restore_stores=False leaves InfluxDB and Grafana as they are (used when the platform opens the demo by
    itself at start: the databases may not be up yet and may hold data of a building that ran without a model).
    """
    _require(sid)
    if not os.path.isdir(os.path.join(_session_dir(sid), 'state')):
        raise SessionError('This session has no saved state.', 404)
    if check_building:
        _require_building_stopped()
    warnings = _autosave_current(except_id=sid)
    _empty_workspace()
    warnings += _restore(sid)
    state = os.path.join(_session_dir(sid), 'state')
    if restore_stores:
        warnings += session_stores.influx_restore(state)
        warnings += session_stores.grafana_restore(state)
    _set_current(sid)
    warnings += _rebuild_memory()
    return warnings


@sessions_bp.route('/open', methods=['POST'])
@_guarded
def open_session():
    data = request.get_json(silent=True) or {}
    warnings = _open(data.get('id'))
    return jsonify(_payload(**_with_warnings(warnings))), 200


# ------------------------------------------------------- sessions shipped with the platform

# Sessions that come with the platform (teaching sessions): folders of the same layout as a saved
# session, kept in the image under seed_sessions/ because sessions/ itself is a bind mount that is
# not part of the repository.
SEED_DIR = 'seed_sessions'
SEEDED_FILE = os.path.join(SESSIONS_DIR, '.seeded.json')
DEMO_ID = 'bdopt-demo'


def seed_sessions_if_missing(seed_dir=None):
    """Copy the shipped sessions into sessions/, once each. Returns the ids copied.

    Never overwrites: a session that exists keeps its (possibly edited) state. An id that was
    copied before is not copied again, so a seed the user deleted does not come back.
    """
    seed_dir = seed_dir or SEED_DIR
    if not os.path.isdir(seed_dir):
        return []
    copied = []
    with _lock:
        done = set((_read_json(SEEDED_FILE) or {}).get('ids', []))
        os.makedirs(SESSIONS_DIR, exist_ok=True)
        for entry in sorted(os.listdir(seed_dir)):
            source = os.path.join(seed_dir, entry)
            if not (_ID_RE.match(entry) and os.path.isfile(os.path.join(source, 'meta.json'))):
                continue
            target = os.path.join(SESSIONS_DIR, entry)
            if entry in done or os.path.exists(target):
                done.add(entry)
                continue
            tmp = target + '.seed-tmp'      # a name _ID_RE refuses: never listed as a session
            shutil.rmtree(tmp, ignore_errors=True)
            shutil.copytree(source, tmp)
            os.replace(tmp, target)
            done.add(entry)
            copied.append(entry)
        _write_json(SEEDED_FILE, {'ids': sorted(done)})
    return copied


STORES_WAIT_SECONDS = 90


def _stores_for_demo(wait=STORES_WAIT_SECONDS):
    """True when the demo may be restored over InfluxDB and Grafana: both answer (they start with the backend,
    so wait a little) and nobody has put anything in them. Otherwise the demo opens without its data and
    dashboards, as before: what an older installation left in the stores is never dropped."""
    deadline = time.time() + wait
    while not session_stores.ready():
        if time.time() >= deadline:
            return False
        time.sleep(2)
    return session_stores.pristine()


def open_demo_if_empty(demo_id=DEMO_ID):
    """On a fresh instance (no current session, no model uploaded) open the demo session.

    Returns the warnings of the opening, or None when nothing was done. An instance that already
    has a current session or a model is not touched.
    """
    with _lock:
        if _current_id() or idf_session.working_path():
            return None
        if not _meta(demo_id):
            return None
        # Only the demo ever opens by itself, whatever else is shipped (the Lab is listed in the Sessions menu).
        stores = _stores_for_demo()
        warnings = list(_open(demo_id, check_building=False, restore_stores=stores))
        if not stores:
            warnings.append('InfluxDB and Grafana were left as they are: they did not answer in time or already hold data.')
        return warnings


@sessions_bp.route('/rename', methods=['POST'])
@_guarded
def rename_session():
    data = request.get_json(silent=True) or {}
    sid = data.get('id')
    meta = _require(sid)
    name = _clean_name(data.get('name'))
    if not name:
        raise SessionError('A name is required.')
    meta['name'] = name
    _write_json(os.path.join(_session_dir(sid), 'meta.json'), meta)
    return jsonify(_payload()), 200


@sessions_bp.route('/<sid>', methods=['DELETE'])
@_guarded
def delete_session(sid):
    _require(sid)
    if sid == _current_id():
        raise SessionError('The current session cannot be deleted.')
    shutil.rmtree(_session_dir(sid))
    return jsonify(_payload()), 200
