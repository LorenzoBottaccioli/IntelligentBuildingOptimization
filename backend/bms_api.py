"""HTTP face of the BMS control room: run the students' services and the building.

The students' services (Workspace/devices, iot, ai) and the building simulation are
run by the platform supervisor, which talks MQTT. This blueprint only publishes
control messages and keeps a cache, filled by one paho thread subscribed to '#',
of what is on the broker:

    platform/services/<folder>/<file>/control   {"cmd": "start|stop|restart"}   (published here)
    platform/services/<folder>/<file>/status    retained service state
    platform/building/control                   {"cmd": "start", run, mode, step_seconds} | {"cmd": "stop"}
    platform/building/process                   retained process state of the building run
    platform/building/status                    retained progress, published by building.py
    $SYS/broker/clients/connected               retained number of broker clients

Everything outside platform/ and $SYS/ is the students' own traffic: they choose
their topics, so there is no fixed namespace to filter on.

GET /bms/state returns the whole picture in one call.
"""

import collections
import datetime
import json
import os
import re
import threading
import time

from flask import Blueprint, current_app, jsonify, request
from flask_cors import CORS

bms_bp = Blueprint('bms', __name__)
CORS(bms_bp)

RUNS = ('baseline', 'controlled')
MODES = ('fast', 'scaled', 'sync')
ACTIONS = ('start', 'stop', 'restart')
SERVICE_RE = re.compile(r'^(devices|iot|ai)/[A-Za-z0-9_.-]+\.py$')
BROKER_HOST = os.environ.get('MQTT_BROKER_URL', 'mosquitto')
BROKER_PORT = int(os.environ.get('MQTT_BROKER_PORT', '1883'))

SERVICES_PREFIX = 'platform/services/'
CLIENTS_TOPIC = '$SYS/broker/clients/connected'

_lock = threading.RLock()
_client = None
_started = False
_connected = False
_services = {}           # name -> status payload
_building = {'process': None, 'status': None}
_clients = None
_trace = collections.deque(maxlen=60)
# Topics outside platform/ and $SYS/: the students' own namespace.
_student_topics = {}
_building_started_at = 0.0
STUDENT_TOPICS_MAX = 200


# ------------------------------------------------------------------ MQTT side
def _on_connect(client, userdata, *args):
    global _connected
    _connected = True
    client.subscribe('#')
    client.subscribe(CLIENTS_TOPIC)  # '#' does not match $SYS topics


def _on_disconnect(client, userdata, *args):
    global _connected
    _connected = False


def _short(raw, limit=120):
    text = raw.decode('utf-8', 'replace') if raw else ''
    return text if len(text) <= limit else text[:limit] + '…'


def _json(raw):
    """Decoded JSON payload; None for an empty payload (a removed retained message)."""
    if not raw:
        return None
    try:
        return json.loads(raw.decode('utf-8'))
    except (ValueError, UnicodeDecodeError):
        return {'raw': raw.decode('utf-8', 'replace')}


def _on_message(client, userdata, msg):
    global _clients
    topic = msg.topic
    if topic == CLIENTS_TOPIC:
        try:
            with _lock:
                _clients = int(msg.payload.decode('utf-8'))
        except (ValueError, UnicodeDecodeError):
            pass
        return
    if topic.startswith('$'):
        return
    if topic.startswith('platform/'):
        payload = _json(msg.payload)
        with _lock:
            if topic.startswith(SERVICES_PREFIX) and topic.endswith('/status'):
                name = topic[len(SERVICES_PREFIX):-len('/status')]
                if payload is None:
                    _services.pop(name, None)
                elif isinstance(payload, dict):
                    _services[name] = payload
            elif topic == 'platform/building/process':
                _building['process'] = payload
            elif topic == 'platform/building/status':
                _building['status'] = payload
        return
    with _lock:
        _trace.append({'topic': topic, 'payload': _short(msg.payload),
                       'at': datetime.datetime.now().strftime('%H:%M:%S.%f')[:-3]})
        if topic in _student_topics or len(_student_topics) < STUDENT_TOPICS_MAX:
            _student_topics[topic] = {'payload': _short(msg.payload), 'at': time.time()}


def _make_client(on_connect, on_disconnect, on_message):
    import paho.mqtt.client as mqtt
    try:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id='backend-bms-api')
    except AttributeError:  # paho < 2
        client = mqtt.Client(client_id='backend-bms-api')
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message
    return client


def _ensure_client():
    """Start the MQTT thread once per process (lazily, on the first request)."""
    global _client, _started
    with _lock:
        if _started:
            return _client
        _started = True
        try:
            _client = _make_client(_on_connect, _on_disconnect, _on_message)
            _client.reconnect_delay_set(min_delay=1, max_delay=10)
            _client.connect_async(BROKER_HOST, BROKER_PORT, keepalive=30)
            _client.loop_start()
        except Exception as exc:  # the API still answers, with connected: false
            current_app.logger.warning('bms_api: MQTT client not started: %s', exc)
        return _client


def _publish(topic, payload):
    client = _ensure_client()
    # The first request starts the client: give the connection a moment instead
    # of dropping the command the student just pressed.
    deadline = time.time() + 5
    while client is not None and not _connected and time.time() < deadline:
        time.sleep(0.1)
    if client is None or not _connected:
        return False
    info = client.publish(topic, json.dumps(payload), qos=1)
    return info.rc == 0


# ----------------------------------------------------------------- storage side
# The database of each run (Grafana has one datasource each). What is inside is the
# students' schema, written by their own code: the panel only reports it.
RUN_DATABASES = {'baseline': 'base_building', 'controlled': 'controlled_building',
                 'direct': 'direct_building'}  # direct: written by direct_run.py, not by the students
STORAGE_TTL = 5.0
_storage = {}


def _influx_query(db, query):
    import base64
    import urllib.parse
    import urllib.request
    base = os.environ.get('INFLUX_URL', 'http://influxdb:8086')
    url = '{}/query?{}'.format(base, urllib.parse.urlencode({'db': db, 'q': query}))
    req = urllib.request.Request(url)
    user, pwd = os.environ.get('INFLUX_USERNAME', ''), os.environ.get('INFLUX_PASSWORD', '')
    if user:
        token = base64.b64encode('{}:{}'.format(user, pwd).encode()).decode()
        req.add_header('Authorization', 'Basic ' + token)
    with urllib.request.urlopen(req, timeout=3) as resp:
        data = json.load(resp)
    rows = []
    for result in data.get('results', []):
        if result.get('error'):
            raise RuntimeError(result['error'])
        for series in result.get('series', []) or []:
            rows += [dict(zip(series.get('columns', []), v), _name=series.get('name'))
                     for v in series.get('values', [])]
    return rows


def _storage_info(run):
    """{db, measurements: [{name, series}], error} for the run's database (cached a few seconds)."""
    db = RUN_DATABASES[run]
    hit = _storage.get(run)
    if hit and time.time() - hit[0] < STORAGE_TTL:
        return hit[1]
    info = {'db': db, 'measurements': [], 'error': None}
    try:
        names = [r.get('name') for r in _influx_query(db, 'SHOW MEASUREMENTS')]
        counts = {}
        for r in _influx_query(db, 'SHOW SERIES'):
            key = str(r.get('key', ''))
            meas = key.split(',', 1)[0]
            counts[meas] = counts.get(meas, 0) + 1
        info['measurements'] = [{'name': n, 'series': counts.get(n, 0)} for n in names if n]
        if run == 'direct' and names:
            # The dates the stored data span: what a student building a multi-year dataset needs to see.
            first = _influx_query(db, 'SELECT FIRST("value") FROM "points"')
            last = _influx_query(db, 'SELECT LAST("value") FROM "points"')
            if first and last:
                info['from'], info['to'] = first[0].get('time'), last[0].get('time')
    except Exception as exc:  # InfluxDB down or the database not created yet
        info['error'] = str(exc)
    _storage[run] = (time.time(), info)
    return info


# ---------------------------------------------------------------------- routes
_SERVICE_FIELDS = ('state', 'pid', 'started', 'exit_code', 'restarts', 'log_tail')


@bms_bp.route('/state', methods=['GET'])
def state():
    _ensure_client()
    with _lock:
        services = [dict({'name': name}, **{k: status.get(k) for k in _SERVICE_FIELDS})
                    for name, status in sorted(_services.items())]
        process = dict(_building['process']) if isinstance(_building['process'], dict) else None
        status = dict(_building['status']) if isinstance(_building['status'], dict) else None
        trace = list(_trace)
        since = _building_started_at
        student_topics = sorted(
            ({'topic': t, 'payload': v['payload']} for t, v in _student_topics.items() if v['at'] >= since),
            key=lambda e: e['topic'])
        clients = _clients
        connected = bool(_connected)
    emergency = bool(process and (process.get('emergency_flag') or process.get('emergency')))
    import direct_run
    storage = {run: _storage_info(run) for run in RUNS}
    storage['direct'] = _storage_info('direct')
    return jsonify({
        'broker': {'connected': connected, 'host': BROKER_HOST, 'port': BROKER_PORT, 'clients': clients},
        'services': services,
        'building': {'process': process, 'status': status, 'emergency': emergency},
        'trace': trace,
        'student_topics': student_topics,
        'storage': storage,
        'direct': direct_run.snapshot(),
        'period': _period_info(),
    }), 200


@bms_bp.route('/services/<path:name>/<action>', methods=['POST'])
def service_action(name, action):
    if action not in ACTIONS:
        return jsonify({'error': 'action must be start, stop or restart'}), 400
    if not SERVICE_RE.match(name):
        return jsonify({'error': 'service must be <devices|iot|ai>/<file>.py'}), 400
    if not _publish('{}{}/control'.format(SERVICES_PREFIX, name), {'cmd': action}):
        return jsonify({'error': 'MQTT broker not reachable'}), 503
    return jsonify({'success': True}), 200


def _field_dir():
    return os.path.join(current_app.root_path, 'field')


def _period_info():
    """The shared period (Field/parameters.py) and whether the exported FMU still matches it."""
    import idf_session
    import run_period
    field = _field_dir()
    period = run_period.read(field, run_period.model_timestep(idf_session.working_path()))
    exported = run_period.exported_timestep(field)
    period['exportedTimestep'] = exported
    # The timestep is baked into the FMU's EnergyPlus model: a different one needs a new export.
    period['needsExport'] = bool(period['exists'] and exported and exported != period['timestep'])
    # Which weather file the run uses, and which year the stored dates carry (the two are not the same thing).
    import direct_run
    import weather_info
    period['weather'] = weather_info.info(idf_session.UPLOAD_FOLDER)
    period['stampYear'], period['stampFrom'] = direct_run.stamp_year(field, idf_session.UPLOAD_FOLDER)
    return period


def _building_running():
    with _lock:
        process = _building['process']
    return bool(isinstance(process, dict) and process.get('state') == 'running')


@bms_bp.route('/period', methods=['GET'])
def period_get():
    return jsonify(_period_info()), 200


@bms_bp.route('/period', methods=['PUT'])
def period_put():
    """Overwrite the period lines of Field/parameters.py (the FMU export writes the file)."""
    import run_period
    if _building_running():
        return jsonify({'error': 'The building is running: stop it before changing the period.'}), 409
    try:
        run_period.write(_field_dir(), request.get_json(silent=True) or {})
    except FileNotFoundError:
        return jsonify({'error': 'Nothing exported yet: Field/parameters.py is written by the FMU export.'}), 409
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400
    return jsonify(_period_info()), 200


@bms_bp.route('/direct', methods=['GET'])
def direct_get():
    import direct_run
    return jsonify(direct_run.snapshot()), 200


@bms_bp.route('/direct/start', methods=['POST'])
def direct_start():
    """Run the model in EnergyPlus alone and store the FMU points in InfluxDB."""
    import direct_run
    import run_period
    data = request.get_json(silent=True) or {}
    if _building_running():
        return jsonify({'error': 'The building is running through the FMU: stop it first.'}), 409
    try:
        period = run_period.validate(data)
        files = None
        sources = data.get('weathers')
        if sources:
            import weather_editor
            import weather_info
            if not isinstance(sources, list) or len(sources) > 12:
                raise ValueError('weathers is a list of at most 12 files.')
            files = []
            for source in sources:
                path = weather_editor.resolve(source)
                info = weather_info.describe(path)
                files.append((path, os.path.basename(path), info['years'][0] if info['kind'] == 'real' else None))
            # Oldest year first: the stored data then grows in the order of time.
            files.sort(key=lambda f: (f[2] is None, f[2] or 0, f[1]))
        direct_run.start(period, _field_dir(), keep=bool(data.get('keep')), files=files)
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400
    except RuntimeError as exc:
        return jsonify({'error': str(exc)}), 409
    except Exception as exc:    # a weather file that does not exist
        if exc.__class__.__name__ == 'SourceError':
            return jsonify({'error': str(exc)}), getattr(exc, 'status', 400)
        raise
    return jsonify({'success': True}), 200


@bms_bp.route('/direct/stop', methods=['POST'])
def direct_stop():
    import direct_run
    direct_run.stop()
    return jsonify({'success': True}), 200


@bms_bp.route('/building/start', methods=['POST'])
def building_start():
    global _building_started_at
    import direct_run
    data = request.get_json(silent=True) or {}
    if direct_run.is_active():
        return jsonify({'error': 'A direct EnergyPlus run is in progress: wait for it or stop it.'}), 409
    if _period_info()['needsExport']:
        return jsonify({'error': 'The timestep was changed after the export: export the FMU again.'}), 409
    run = data.get('run')
    mode = data.get('mode')
    if run not in RUNS:
        return jsonify({'error': 'run must be baseline or controlled'}), 400
    if mode not in MODES:
        return jsonify({'error': 'mode must be fast, scaled or sync'}), 400
    if mode == 'sync' and run != 'controlled':
        return jsonify({'error': 'sync mode is only available for the controlled run'}), 400
    try:
        step_seconds = float(data.get('step_seconds', 0))
        if step_seconds < 0 or step_seconds != step_seconds or step_seconds == float('inf'):
            raise ValueError
    except (TypeError, ValueError):
        return jsonify({'error': 'step_seconds must be a non-negative number'}), 400
    with _lock:
        # Student topics are shown "since the last building start": stale ones would look live.
        _building_started_at = time.time()
    ok = _publish('platform/building/control',
                  {'cmd': 'start', 'run': run, 'mode': mode, 'step_seconds': step_seconds})
    if not ok:
        return jsonify({'error': 'MQTT broker not reachable'}), 503
    return jsonify({'success': True}), 200


@bms_bp.route('/building/stop', methods=['POST'])
def building_stop():
    if not _publish('platform/building/control', {'cmd': 'stop'}):
        return jsonify({'error': 'MQTT broker not reachable'}), 503
    return jsonify({'success': True}), 200
