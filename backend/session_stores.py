"""The two external stores a session carries: InfluxDB data and Grafana dashboards.

sessions.py snapshots the working directories itself; this module adds the
state that lives in other containers. Every function returns a list of warning
strings instead of raising, so a failing store never costs the folder snapshot.

InfluxDB (1.x). The two databases keep their fixed names (base_building,
controlled_building) so the students' code never changes. A snapshot is an
`influxd backup -portable -db <db>` executed in the influxdb container (the
backend has the Docker CLI and socket); the backup directory is written under
the state directory through the shared mount ./backend/sessions, which is
/app/sessions in the backend and /sessions in influxdb. A restore drops both
databases and `influxd restore -portable`s the ones that have a backup; the
others are created empty.

Grafana. Dashboards and folders are exported/imported through the HTTP API
with the admin account. Provisioned dashboards (files) are left alone; the
datasources and users are shared by all sessions.

Layout inside <state>/:

    influx/<db>/...               portable backup of <db> (absent = empty)
    grafana/folders.json          [{uid, title}, ...]
    grafana/dashboards/<uid>.json {"dashboard": ..., "folderUid": ...}
"""

import json
import logging
import os
import shutil
import subprocess

import requests

log = logging.getLogger(__name__)

# direct_building is written by direct_run.py (EnergyPlus alone), not by the students' code.
INFLUX_DATABASES = ('base_building', 'controlled_building', 'direct_building')
SESSIONS_DIR = 'sessions'              # relative to the backend working dir (/app)
INFLUX_MOUNT = '/sessions'             # the same directory inside the influxdb container
INFLUX_CONTAINER = 'influxdb'
TIMEOUT = 20
DOCKER_TIMEOUT = 600


# ------------------------------------------------------------------- InfluxDB

def _influx_query(query, db=None, post=False):
    base = os.environ.get('INFLUX_URL', 'http://influxdb:8086')
    user = os.environ.get('INFLUX_USERNAME', '')
    auth = (user, os.environ.get('INFLUX_PASSWORD', '')) if user else None
    params = {'q': query}
    if db:
        params['db'] = db
    send = requests.post if post else requests.get
    response = send(f'{base}/query', params=params, auth=auth, timeout=TIMEOUT)
    response.raise_for_status()
    body = response.json()
    for result in body.get('results', []):
        if result.get('error'):
            raise RuntimeError(result['error'])
    return body


def _influx_has_data(db):
    """True when the database exists and holds at least one measurement."""
    body = _influx_query('SHOW DATABASES')
    values = body['results'][0].get('series', [{}])[0].get('values', [])
    if db not in [row[0] for row in values]:
        return False
    body = _influx_query('SHOW MEASUREMENTS', db=db)
    return bool(body['results'][0].get('series'))


def _container_path(path):
    """Path of a directory under backend/sessions as influxdb sees it."""
    rel = os.path.relpath(os.path.abspath(path), os.path.abspath(SESSIONS_DIR))
    if rel.startswith('..'):
        raise ValueError(f'{path} is outside {SESSIONS_DIR}/')
    return INFLUX_MOUNT + '/' + rel.replace(os.sep, '/')


def _docker_exec(*args):
    result = subprocess.run(['docker', 'exec', INFLUX_CONTAINER, *args],
                            capture_output=True, text=True, timeout=DOCKER_TIMEOUT)
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout).strip()[-400:] or 'docker exec failed')


def influx_snapshot(sid, state_dir):
    """Back up the non-empty databases into <state_dir>/influx/<db>.

    `state_dir` must be inside sessions/ (the temp dir sessions.py builds is).
    `sid` is only used in log messages.
    """
    warnings = []
    root = os.path.join(state_dir, 'influx')
    shutil.rmtree(root, ignore_errors=True)
    for db in INFLUX_DATABASES:
        try:
            if not _influx_has_data(db):
                continue
            target = os.path.join(root, db)
            os.makedirs(target, exist_ok=True)
            os.chmod(target, 0o777)  # influxd runs as an unprivileged user in its container
            _docker_exec('influxd', 'backup', '-portable', '-db', db, _container_path(target))
        except Exception as exc:
            log.warning('session %s: InfluxDB backup of %s failed: %s', sid, db, exc)
            warnings.append(f'InfluxDB data of {db} could not be saved: {exc}')
            shutil.rmtree(os.path.join(root, db), ignore_errors=True)
    return warnings


def influx_restore(state_dir):
    """Replace both databases with the ones in <state_dir>/influx; empty when absent or None."""
    warnings = []
    for db in INFLUX_DATABASES:
        try:
            _influx_query(f'DROP DATABASE "{db}"', post=True)
        except Exception as exc:
            log.warning('InfluxDB: dropping %s failed: %s', db, exc)
            warnings.append(f'InfluxDB database {db} could not be cleared: {exc}')
            continue
        backup = os.path.join(state_dir, 'influx', db) if state_dir else None
        try:
            if backup and os.path.isdir(backup) and os.listdir(backup):
                _docker_exec('influxd', 'restore', '-portable', '-db', db, '-newdb', db,
                             _container_path(backup))
            else:
                _influx_query(f'CREATE DATABASE "{db}"', post=True)
        except Exception as exc:
            log.warning('InfluxDB: restoring %s failed: %s', db, exc)
            warnings.append(f'InfluxDB data of {db} could not be restored: {exc}')
            try:  # the database must exist anyway: the students' code writes to it
                _influx_query(f'CREATE DATABASE "{db}"', post=True)
            except Exception:
                pass
    return warnings


# -------------------------------------------------------------------- Grafana

def _grafana(method, path, **kwargs):
    base = os.environ.get('GRAFANA_URL', 'http://grafana:3000')
    auth = (os.environ.get('GRAFANA_ADMIN_USER', 'admin'),
            os.environ.get('GRAFANA_ADMIN_PASSWORD', ''))
    response = requests.request(method, base + path, auth=auth, timeout=TIMEOUT, **kwargs)
    response.raise_for_status()
    return response.json() if response.content else None


def _check_auth():
    # Grafana allows anonymous Viewer access: wrong credentials are not rejected
    # on GET, they silently read as anonymous, and only a write fails with 403.
    _grafana('GET', '/api/user')


def _write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as handle:
        json.dump(data, handle, indent=2)


def grafana_snapshot(state_dir):
    """Export folders and non-provisioned dashboards into <state_dir>/grafana."""
    warnings = []
    root = os.path.join(state_dir, 'grafana')
    shutil.rmtree(root, ignore_errors=True)
    try:
        _check_auth()
        folders = _grafana('GET', '/api/folders') or []
        _write(os.path.join(root, 'folders.json'),
               [{'uid': f['uid'], 'title': f['title']} for f in folders])
        found = _grafana('GET', '/api/search', params={'type': 'dash-db', 'limit': 5000}) or []
    except Exception as exc:
        log.warning('Grafana: listing failed: %s', exc)
        shutil.rmtree(root, ignore_errors=True)
        return [f'Grafana dashboards could not be saved: {exc}']
    exported = set()
    for item in found:
        uid = item.get('uid')
        try:
            full = _grafana('GET', f'/api/dashboards/uid/{uid}')
            meta = full.get('meta', {})
            if meta.get('provisioned'):
                continue
            _write(os.path.join(root, 'dashboards', f'{uid}.json'),
                   {'dashboard': full['dashboard'], 'folderUid': meta.get('folderUid', '')})
            exported.add(uid)
        except Exception as exc:
            log.warning('Grafana: dashboard %s not exported: %s', uid, exc)
            warnings.append(f'Grafana dashboard "{item.get("title", uid)}" could not be saved: {exc}')
    try:  # the dashboard Grafana opens on: a preference of the organisation, not part of any dashboard
        home = (_grafana('GET', '/api/org/preferences') or {}).get('homeDashboardUID') or ''
        if home in exported:
            _write(os.path.join(root, 'preferences.json'), {'homeDashboardUID': home})
    except Exception as exc:
        log.warning('Grafana: home dashboard not saved: %s', exc)
    return warnings


def _set_home_dashboard(uid):
    """Make `uid` the dashboard Grafana opens on ('' = the default). Raises on failure."""
    _grafana('PATCH', '/api/org/preferences', json={'homeDashboardUID': uid})


def grafana_restore(state_dir):
    """Delete the user's dashboards and folders, then import those in <state_dir>/grafana."""
    warnings = []
    try:
        _check_auth()
        for item in _grafana('GET', '/api/search', params={'type': 'dash-db', 'limit': 5000}) or []:
            uid = item.get('uid')
            try:
                full = _grafana('GET', f'/api/dashboards/uid/{uid}')
                if full.get('meta', {}).get('provisioned'):
                    continue
                _grafana('DELETE', f'/api/dashboards/uid/{uid}')
            except Exception as exc:
                warnings.append(f'Grafana dashboard "{item.get("title", uid)}" could not be removed: {exc}')
        for folder in _grafana('GET', '/api/folders') or []:
            try:
                _grafana('DELETE', f'/api/folders/{folder["uid"]}')
            except Exception as exc:
                warnings.append(f'Grafana folder "{folder.get("title", "")}" could not be removed: {exc}')
    except Exception as exc:
        log.warning('Grafana: clearing failed: %s', exc)
        return warnings + [f'Grafana dashboards could not be cleared: {exc}']

    root = os.path.join(state_dir, 'grafana') if state_dir else None
    if not root or not os.path.isdir(root):
        return warnings + _restore_home(None)
    try:
        with open(os.path.join(root, 'folders.json'), encoding='utf-8') as handle:
            folders = json.load(handle)
    except (OSError, ValueError):
        folders = []
    for folder in folders:
        try:
            _grafana('POST', '/api/folders', json={'uid': folder['uid'], 'title': folder['title']})
        except Exception as exc:
            warnings.append(f'Grafana folder "{folder.get("title", "")}" could not be restored: {exc}')
    ddir = os.path.join(root, 'dashboards')
    for name in sorted(os.listdir(ddir)) if os.path.isdir(ddir) else []:
        try:
            with open(os.path.join(ddir, name), encoding='utf-8') as handle:
                saved = json.load(handle)
            dashboard = dict(saved['dashboard'], id=None)
            body = {'dashboard': dashboard, 'overwrite': True}
            if saved.get('folderUid'):
                body['folderUid'] = saved['folderUid']
            _grafana('POST', '/api/dashboards/db', json=body)
        except Exception as exc:
            log.warning('Grafana: importing %s failed: %s', name, exc)
            warnings.append(f'Grafana dashboard {name} could not be restored: {exc}')
    return warnings + _restore_home(os.path.join(root, 'preferences.json'))


def _restore_home(path):
    """Set (or, with no file, clear) the dashboard Grafana opens on."""
    uid = ''
    try:
        with open(path, encoding='utf-8') as handle:
            uid = (json.load(handle) or {}).get('homeDashboardUID') or ''
    except (OSError, TypeError, ValueError):
        pass
    try:
        _set_home_dashboard(uid)
    except Exception as exc:
        log.warning('Grafana: home dashboard not set: %s', exc)
        return [f'Grafana home dashboard could not be set: {exc}']
    return []


# ------------------------------------------------------------ the stores of a new instance

def ready():
    """True when InfluxDB and Grafana both answer."""
    try:
        _influx_query('SHOW DATABASES')
        _check_auth()
        return True
    except Exception:
        return False


def pristine():
    """True when nobody has put anything in the stores: no data in the databases, no dashboard of the user.

    A session is restored over the stores only when this holds, so opening the demo of a new instance can
    never drop what an older installation left in them.
    """
    try:
        if any(_influx_has_data(db) for db in INFLUX_DATABASES):
            return False
        for item in _grafana('GET', '/api/search', params={'type': 'dash-db', 'limit': 5000}) or []:
            full = _grafana('GET', f'/api/dashboards/uid/{item.get("uid")}')
            if not full.get('meta', {}).get('provisioned'):
                return False
        return True
    except Exception:
        return False
