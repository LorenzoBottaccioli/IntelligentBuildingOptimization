"""Emergency gateway: the platform's own gateway, for a group that is stuck.

Platform code, mounted read-only. Normally the students write their gateway
(devices/gateway.py) on top of building.py. When the teacher enables the
emergency gateway for a group (flag file Workspace/.emergency) the supervisor
runs this one instead: it reads Field/points.yaml and publishes the building on
MQTT with the topic contract described in README.md.

Run once (what the supervisor does):
    python emergency_gateway.py --once --run baseline|controlled --mode fast|scaled|sync --step-seconds 0.2
Run as a service (idle, waits for a start command on building/<run>/sim/control):
    python emergency_gateway.py --run baseline|controlled
From a notebook:
    from emergency_gateway import run; run('controlled', mode='sync')

The pure logic (validation, priority array, deadband) has no dependency on pyfmi
or paho, so it can be tested on its own. The FMU is driven through building.py.
"""

import argparse
import datetime as dt
import json
import math
import os
import queue
import re
import sys
import threading
import time

try:
    import yaml
except ImportError:                      # only the pure logic is usable then
    yaml = None
try:
    import paho.mqtt.client as mqtt
except ImportError:
    mqtt = None

from building import Building, DEFAULT_FIELD_DIR, RUNS, sim_timestamp

ID_RE = re.compile(r'^[A-Za-z0-9_\-]+$')
GATEWAY_DEFAULTS = {'sync_timeout_s': 5, 'command_timeout_steps': 3, 'heartbeat_steps': 6}


# ---------------------------------------------------------------------------
# Pure logic
# ---------------------------------------------------------------------------

def is_number(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def clamp(value, lo=None, hi=None):
    if lo is not None and value < lo:
        return lo
    if hi is not None and value > hi:
        return hi
    return value


def validate_points(cfg, md, run):
    """Check points.yaml against the FMU. Returns (errors, warnings, normalised config).

    The normalised config has defaults filled in and, for the baseline, only the
    points the baseline FMU can serve.
    """
    errors, warnings = [], []
    if not isinstance(cfg, dict):
        return ['points.yaml is empty or is not a mapping'], warnings, None

    site = cfg.get('site') or {}
    year = site.get('year')
    if year is None:
        year = dt.datetime.now().year
        warnings.append(f'site.year missing, using {year}')
    elif not isinstance(year, int) or isinstance(year, bool):
        errors.append(f'site.year must be an integer, got {year!r}')
        year = dt.datetime.now().year

    gw = dict(GATEWAY_DEFAULTS)
    gw.update(cfg.get('gateway') or {})
    for key in GATEWAY_DEFAULTS:
        if not is_number(gw[key]) or gw[key] <= 0:
            errors.append(f'gateway.{key} must be a positive number, got {gw[key]!r}')

    raw_points = cfg.get('points')
    if not isinstance(raw_points, list) or not raw_points:
        errors.append('points: list is missing or empty')
        raw_points = []

    inputs, outputs, allv = set(md['inputs']), set(md['outputs']), set(md['all'])
    ids, points = set(), []
    for i, p in enumerate(raw_points):
        label = f'points[{i}]'
        if not isinstance(p, dict):
            errors.append(f'{label}: must be a mapping')
            continue
        fmu_name = p.get('fmu')
        ptype = p.get('type')
        if fmu_name:
            label = f'point fmu={fmu_name}'
        # Commands of the controlled FMU do not exist in the baseline: nothing to check there.
        if run == 'baseline' and ptype == 'command' and fmu_name and fmu_name not in allv:
            continue
        ok = True
        pid = p.get('id')
        if not isinstance(pid, str) or not ID_RE.match(pid):
            errors.append(f'{label}: id {pid!r} is missing or has characters other than letters, digits, _ and -')
            ok = False
        else:
            label = f'point "{pid}"'
            if pid in ids:
                errors.append(f'{label}: duplicate id')
                continue
            ids.add(pid)
        q = dict(p)
        if not fmu_name:
            errors.append(f'{label}: fmu is missing')
            ok = False
        if ptype not in ('measurement', 'command'):
            errors.append(f'{label}: type must be measurement or command, got {ptype!r}')
            continue
        if not p.get('unit') or not isinstance(p.get('unit'), str):
            errors.append(f'{label}: unit is missing')
            ok = False
        if ptype == 'measurement':
            q.setdefault('scale', 1)
            q.setdefault('offset', 0)
            # The deadband is a commissioning decision (how much change is worth a message).
            if q.get('deadband') is None:
                errors.append(f'{label}: deadband is missing')
                q['deadband'] = 0
                ok = False
            for key in ('scale', 'offset', 'deadband'):
                if not is_number(q[key]):
                    errors.append(f'{label}: {key} must be a number, got {q[key]!r}')
                    ok = False
            if ok and q['scale'] == 0:
                errors.append(f'{label}: scale cannot be 0')
                ok = False
            if ok and q['deadband'] < 0:
                errors.append(f'{label}: deadband cannot be negative')
                ok = False
            if fmu_name and fmu_name not in allv:
                if run == 'baseline':
                    warnings.append(f'{label}: {fmu_name} is not in the baseline FMU, point skipped')
                else:
                    errors.append(f'{label}: fmu name {fmu_name!r} is not in modelDescription.xml')
                ok = False
            elif fmu_name and fmu_name in inputs:
                errors.append(f'{label}: {fmu_name!r} is an FMU input, a measurement must be an output')
                ok = False
        else:
            q.setdefault('scale', 1)
            q.setdefault('offset', 0)
            for key in ('scale', 'offset'):
                if not is_number(q[key]):
                    errors.append(f'{label}: {key} must be a number, got {q[key]!r}')
                    ok = False
            if ok and q['scale'] == 0:
                errors.append(f'{label}: scale cannot be 0')
                ok = False
            lo, hi, default = q.get('min'), q.get('max'), q.get('default')
            for key, val in (('min', lo), ('max', hi)):
                if val is None:
                    errors.append(f'{label}: {key} is missing')
                    ok = False
                elif not is_number(val):
                    errors.append(f'{label}: {key} must be a number, got {val!r}')
                    ok = False
            if not is_number(default):
                errors.append(f'{label}: default is missing or not a number')
                ok = False
            elif is_number(lo) and is_number(hi):
                if lo > hi:
                    errors.append(f'{label}: min {lo} is greater than max {hi}')
                    ok = False
                elif default < lo or default > hi:
                    errors.append(f'{label}: default {default} is outside [{lo}, {hi}]')
                    ok = False
            if fmu_name and fmu_name not in allv:
                if run == 'baseline':
                    ok = False       # commands of the controlled FMU: not served by the baseline
                else:
                    errors.append(f'{label}: fmu name {fmu_name!r} is not in modelDescription.xml')
                    ok = False
            elif fmu_name and fmu_name not in inputs:
                errors.append(f'{label}: {fmu_name!r} is not an FMU input')
                ok = False
        if ok:
            points.append(q)

    cmd_fmu = {}
    for q in points:
        if q['type'] == 'command':
            if q['fmu'] in cmd_fmu:
                errors.append(f'points "{cmd_fmu[q["fmu"]]}" and "{q["id"]}" both drive {q["fmu"]}')
            cmd_fmu[q['fmu']] = q['id']
    declared = {p.get('fmu') for p in raw_points if isinstance(p, dict) and p.get('type') == 'command'}
    missing = [n for n in md['inputs'] if n not in declared]
    if missing:
        if run == 'controlled':
            for n in missing:
                errors.append(f'FMU input {n!r} has no command point in points.yaml')
        else:
            warnings.append('baseline FMU inputs left at their start value: ' + ', '.join(missing))

    return errors, warnings, {'site': {'name': site.get('name', ''), 'year': year},
                              'gateway': gw, 'points': points}


class CommandTable:
    """Priority array per command point: operator > controller > default.

    Operator commands stay until released. Controller commands are valid in the
    step they arrive and for `timeout_steps` steps after it; then they expire.
    An empty payload releases a command.
    """

    def __init__(self, points, timeout_steps):
        self.timeout = timeout_steps
        self.points = {p['id']: p for p in points if p['type'] == 'command'}
        self.slots = {pid: {'operator': None, 'controller': None} for pid in self.points}
        self.lock = threading.Lock()

    def set(self, pid, source, value, step):
        with self.lock:
            self.slots[pid][source] = (value, step)

    def release(self, pid, source):
        with self.lock:
            self.slots[pid][source] = None

    def resolve(self, pid, step):
        """Returns (value, source, clamped_from). value is within [min, max]."""
        p = self.points[pid]
        with self.lock:
            op, ctl = self.slots[pid]['operator'], self.slots[pid]['controller']
            if ctl is not None and step - ctl[1] > self.timeout:
                self.slots[pid]['controller'] = ctl = None       # expired
            if op is not None:
                raw, source = op[0], 'operator'
            elif ctl is not None:
                raw, source = ctl[0], 'controller'
            else:
                raw, source = p['default'], 'default'
        value = clamp(raw, p.get('min'), p.get('max'))
        return value, source, (raw if value != raw else None)


class DeadbandFilter:
    """Publish on change beyond the deadband, or after `heartbeat` steps."""

    def __init__(self, heartbeat):
        self.heartbeat = heartbeat
        self.last = {}

    def should_publish(self, key, value, step, deadband=0.0):
        prev = self.last.get(key)
        if prev is None:
            publish = True
        else:
            pv, pstep = prev
            changed = abs(value - pv) > deadband if deadband > 0 else value != pv
            publish = changed or step - pstep >= self.heartbeat
        if publish:
            self.last[key] = (value, step)
        return publish


# ---------------------------------------------------------------------------
# Gateway
# ---------------------------------------------------------------------------

class Gateway:
    def __init__(self, run_name, field_dir=DEFAULT_FIELD_DIR, broker=None, port=None):
        if run_name not in RUNS:
            raise ValueError(f'run must be one of {RUNS}')
        if mqtt is None:
            raise RuntimeError('paho-mqtt is not installed')
        self.run = run_name
        self.field_dir = field_dir
        self.broker = broker or os.environ.get('MQTT_BROKER_URL', 'mosquitto')
        self.port = int(port or os.environ.get('MQTT_BROKER_PORT', 1883))
        self.prefix = f'building/{run_name}'
        self.control = queue.Queue()
        self.stop_event = threading.Event()
        self.running = False
        self.table = None
        self.point_by_id = {}
        self._ack = -1
        self._ack_cv = threading.Condition()
        self._unknown_warned = set()
        self.ctl = None              # who drove the controlled run: filled in during the run
        self.status = {'state': 'idle', 'sim_time': None, 'step': 0, 'steps_total': 0,
                       'mode': None, 'message': ''}
        self._last_status = 0.0
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                                  client_id=f'gateway_{run_name}_{os.getpid()}')
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.will_set(f'{self.prefix}/sim/status', json.dumps(
            dict(self.status, state='fault', message='gateway process disconnected')),
            qos=1, retain=True)

    # -- MQTT plumbing ------------------------------------------------------
    def connect(self):
        while True:
            try:
                self.client.connect(self.broker, self.port, keepalive=30)
                break
            except OSError as e:
                print(f'[gateway] broker {self.broker}:{self.port} not reachable ({e}), retrying', flush=True)
                time.sleep(2)
        self.client.loop_start()

    def disconnect(self):
        info = self.client.disconnect()      # before loop_stop: a clean disconnect does not fire the will
        time.sleep(0.2)
        self.client.loop_stop()

    def _on_connect(self, client, userdata, flags, rc, props=None):
        client.subscribe(f'{self.prefix}/sim/control', qos=1)
        if self.run == 'controlled':
            client.subscribe(f'{self.prefix}/+/command/+', qos=1)
            client.subscribe(f'{self.prefix}/sim/ack', qos=1)

    def _on_message(self, client, userdata, msg):
        try:
            parts = msg.topic.split('/')
            if msg.topic == f'{self.prefix}/sim/control':
                self._on_control(msg.payload)
            elif msg.topic == f'{self.prefix}/sim/ack':
                step = int(json.loads(msg.payload)['step'])
                with self._ack_cv:
                    if self.ctl is not None and step > self._ack:
                        self.ctl['acks'] += 1
                    self._ack = max(self._ack, step)
                    self._ack_cv.notify_all()
            elif len(parts) == 5 and parts[3] == 'command':
                self._on_command(parts[2], parts[4], msg.payload)
        except Exception as e:
            self.log('warning', f'bad message on {msg.topic}: {e}')

    def _on_control(self, payload):
        data = json.loads(payload)
        cmd = data.get('cmd')
        if cmd == 'start':
            if self.running:
                self.log('warning', 'start ignored: a run is already in progress')
            else:
                self.control.put(data)
        elif cmd == 'stop':
            self.stop_event.set()
        else:
            self.log('warning', f'unknown control command {cmd!r}')

    def _on_command(self, pid, source, payload):
        if source not in ('operator', 'controller'):
            return
        if self.table is None or pid not in self.table.points:
            if pid not in self._unknown_warned and pid != 'sim':
                self._unknown_warned.add(pid)
                self.log('warning', f'command for "{pid}" ignored: not a command point (or no run in progress)')
            return
        if not payload or not payload.strip():
            self.table.release(pid, source)
            self.log('info', f'{source} released "{pid}"')
            return
        value = json.loads(payload).get('value')
        if not is_number(value):
            self.log('warning', f'{source} command for "{pid}" has no numeric value: {payload[:60]!r}')
            return
        self.table.set(pid, source, float(value), self.status['step'])
        if self.ctl is not None and source == 'controller':
            self.ctl['commands'] += 1
            self.ctl['last_command_step'] = self.status['step']
            if pid not in self.ctl['points']:
                self.ctl['points'] = sorted(self.ctl['points'] + [pid])

    def publish(self, topic, payload, retain=False, qos=0):
        self.client.publish(topic, json.dumps(payload), qos=qos, retain=retain)

    def log(self, level, msg):
        print(f'[gateway:{self.run}] {level}: {msg}', flush=True)
        try:
            self.publish(f'{self.prefix}/sim/log',
                         {'ts': dt.datetime.now().isoformat(timespec='seconds'), 'level': level, 'msg': msg})
        except Exception:
            pass

    def set_status(self, force=True, **fields):
        self.status.update(fields)
        now = time.time()
        if force or now - self._last_status >= 0.5:
            self._last_status = now
            self.publish(f'{self.prefix}/sim/status', self.status, retain=True, qos=1)

    # -- service loop --------------------------------------------------------
    def serve(self):
        self.set_status(state='idle', message='waiting for a start command')
        self.log('info', 'gateway ready')
        while True:
            try:
                data = self.control.get(timeout=1)
            except queue.Empty:
                continue
            self.simulate(data.get('mode', 'sync'), float(data.get('step_seconds', 1.0)))

    # -- one run -------------------------------------------------------------
    def load_config(self):
        """Returns (building, cfg) or raises ValueError with the message. The Building is not started."""
        if yaml is None:
            raise ValueError('PyYAML is not installed')
        pfile = os.path.join(self.field_dir, 'parameters.py')
        yfile = os.path.join(self.field_dir, 'points.yaml')
        if not os.path.isfile(pfile):
            raise ValueError('Field/parameters.py not found: export the model first')
        if not os.path.isfile(yfile):
            raise ValueError('Field/points.yaml not found: export the model first')
        building = Building(self.run, self.field_dir)     # ValueError: parameters.py or FMU problem
        try:
            with open(yfile, encoding='utf-8') as f:
                raw = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ValueError(f'points.yaml is not valid YAML: {e}')
        errors, warnings, cfg = validate_points(raw, building.md, self.run)
        for w in warnings:
            self.log('warning', w)
        if errors:
            for e in errors:
                self.log('error', e)
            more = f' (+{len(errors) - 3} more, see the log)' if len(errors) > 3 else ''
            raise ValueError('points.yaml: ' + '; '.join(errors[:3]) + more)
        building.year = cfg['site']['year']
        return building, cfg

    def wait_ack(self, step, timeout):
        with self._ack_cv:
            return self._ack_cv.wait_for(lambda: self._ack >= step or self.stop_event.is_set(), timeout)

    def simulate(self, mode='sync', step_seconds=1.0):
        if mode not in ('sync', 'scaled', 'fast'):
            mode = 'sync'
        if self.run == 'baseline' and mode != 'scaled':
            mode = 'fast'            # nothing to wait for in the baseline
        self.running = True
        self.stop_event.clear()
        try:
            self.set_status(state='starting', sim_time=None, step=0, steps_total=0, mode=mode, message='',
                            controller=None)
            try:
                building, cfg = self.load_config()
            except Exception as e:
                self.set_status(state='config_error', message=str(e))
                self.log('error', f'config_error: {e}')
                return
            self._simulate(building, cfg, mode, step_seconds)
        except Exception as e:
            self.set_status(state='fault', message=f'{type(e).__name__}: {e}')
            self.log('error', f'fault: {type(e).__name__}: {e}')
        finally:
            self.table = None
            self.ctl = None          # the summary stays in self.status['controller']
            self.running = False

    def _simulate(self, building, cfg, mode, step_seconds):
        run, year, gw = self.run, cfg['site']['year'], cfg['gateway']
        controlled = run == 'controlled'
        points = cfg['points']
        meas = [p for p in points if p['type'] == 'measurement']
        cmds = [p for p in points if p['type'] == 'command']
        self.point_by_id = {p['id']: p for p in points}
        h, steps_total = building.step_size, building.steps_total
        sync = controlled and mode == 'sync'

        self._ack = -1
        self.table = CommandTable(cmds, gw['command_timeout_steps']) if controlled else None
        if controlled:
            # What the controller did, published in the status: ticks it answered, commands
            # it sent, and which source drove the command points over the run.
            self.ctl = {'ticks': 0, 'acks': 0, 'timeouts': 0, 'commands': 0, 'last_command_step': None,
                        'points': [], 'sources': {'operator': 0, 'controller': 0, 'default': 0}}
            self.status['controller'] = self.ctl
        db_val = DeadbandFilter(gw['heartbeat_steps'])
        db_act = DeadbandFilter(gw['heartbeat_steps'])
        clamp_logged = {}
        timeouts = 0
        step = 0

        try:
            with building:
                # Defaults before initialize, as fmi_gym.configure_fmu sets its parameters
                building.start({p['fmu']: (p['default'] - p['offset']) / p['scale'] for p in cmds})
                # The baseline has no controller to wait for: it runs flat out ("fast") or, in
                # scaled mode, one step every step_seconds so that live consumers can follow it.
                if mode == 'scaled':
                    kind = f'scaled, {step_seconds:g} s per step'
                else:
                    kind = {'fast': 'as fast as possible',
                            'sync': 'sync, waits for the controller ack'}[mode]
                self.log('info', f'run started ({run}, {kind}), {steps_total} steps of {h:g} s, year {year}')
                self.set_status(state='running', sim_time=sim_timestamp(year, building.start_time), step=0,
                                steps_total=steps_total, mode=mode, message='')

                out = building.read()
                self._publish_values(out, meas, db_val, 'good')
                self.publish(f'{self.prefix}/sim/tick', {'step': step, 'ts': out['ts']})
                if controlled:
                    self.ctl['ticks'] += 1
                    if sync and not self._wait_sync(step, gw['sync_timeout_s']):
                        timeouts += 1
                        self.ctl['timeouts'] = timeouts
                        self._log_timeout(step, timeouts, gw['sync_timeout_s'])
                deadline = time.time()
                milestone = max(1, steps_total // 10)

                while not building.done and not self.stop_event.is_set():
                    if controlled:
                        self._apply_commands(building, cmds, db_act, out['ts'], step, clamp_logged)
                    out = building.step()
                    step = out['step']
                    self._publish_values(out, meas, db_val, 'good')
                    if step % milestone == 0:
                        self.log('info', f'step {step}/{steps_total} ({out["ts"]})')
                    self.set_status(force=step == steps_total, sim_time=out['ts'], step=step)

                    # Every run publishes the tick after the values of the step.
                    self.publish(f'{self.prefix}/sim/tick', {'step': step, 'ts': out['ts']})
                    if controlled:
                        self.ctl['ticks'] += 1
                    if step < steps_total:
                        if sync:
                            if not self._wait_sync(step, gw['sync_timeout_s']):
                                timeouts += 1
                                self.ctl['timeouts'] = timeouts
                                self._log_timeout(step, timeouts, gw['sync_timeout_s'])
                        elif mode == 'scaled':
                            # a scaled run does not wait for the ack
                            deadline += step_seconds
                            time.sleep(max(0.0, deadline - time.time()))

                if self.stop_event.is_set():
                    building.report('finished', f'stopped by the user at step {step}')
                    self.set_status(state='idle', message=f'stopped by the user at step {step}')
                    self.log('info', f'run stopped at step {step}')
                else:
                    self.set_status(state='finished', message=f'{steps_total} steps completed'
                                    + (f', {timeouts} sync timeouts' if timeouts else ''))
                    self.log('info', 'run finished')
        except Exception as e:
            # Mark every measurement so consumers see the data are not trustworthy
            try:
                self._publish_values(None, meas, None, 'fault', ts=sim_timestamp(year, building.t))
            except Exception:
                pass
            self.set_status(state='fault', message=str(e))
            self.log('error', f'fault: {e}')

    def _wait_sync(self, step, timeout):
        return self.wait_ack(step, timeout)

    def _log_timeout(self, step, n, timeout):
        if n <= 3 or n % 50 == 0:
            self.log('warning', f'no ack for step {step} after {timeout:g} s (timeout #{n}), continuing')

    def _publish_values(self, out, meas, db, quality, ts=None):
        """Publish the measurement points from a Building reading (out=None: fault, no values)."""
        values = out['values'] if out is not None else {}
        ts = out['ts'] if out is not None else ts
        step = out['step'] if out is not None else 0
        for p in meas:
            r = values.get(p['fmu'], float('nan'))
            if not math.isfinite(r):
                if quality == 'fault':
                    self.publish(f'{self.prefix}/{p["id"]}/value',
                                 {'value': None, 'unit': p['unit'], 'ts': ts, 'quality': 'fault'})
                continue
            value = r * p['scale'] + p['offset']
            if db.should_publish(p['id'], value, step, p['deadband']):
                self.publish(f'{self.prefix}/{p["id"]}/value',
                             {'value': value, 'unit': p['unit'], 'ts': ts, 'quality': quality})

    def _apply_commands(self, building, cmds, db_act, ts, step, clamp_logged):
        if not cmds:
            return
        names, vals = [], []
        for p in cmds:
            value, source, clamped_from = self.table.resolve(p['id'], step)
            if self.ctl is not None:
                self.ctl['sources'][source] += 1
            if clamped_from is not None and clamp_logged.get(p['id']) != clamped_from:
                clamp_logged[p['id']] = clamped_from
                self.log('warning', f'"{p["id"]}": {clamped_from:g} clamped to {value:g} '
                                    f'(range {p.get("min")}..{p.get("max")})')
            names.append(p['fmu'])
            vals.append((value - p['offset']) / p['scale'])
            key = (value, source)
            last = db_act.last.get(p['id'])
            if last is None or last[0] != key or step - last[1] >= db_act.heartbeat:
                db_act.last[p['id']] = (key, step)
                self.publish(f'{self.prefix}/{p["id"]}/active',
                             {'value': value, 'source': source, 'ts': ts})
        building.set_many(dict(zip(names, vals)))


def run(run_name, mode='sync', step_seconds=1.0, field_dir=DEFAULT_FIELD_DIR, broker=None, port=None):
    """Run one simulation to the end and return the final status (for notebooks and --once)."""
    gw = Gateway(run_name, field_dir, broker, port)
    gw.connect()
    try:
        gw.simulate(mode, step_seconds)
        time.sleep(0.3)                          # let the last publishes leave
        return dict(gw.status)
    finally:
        gw.disconnect()


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--run', required=True, choices=RUNS)
    ap.add_argument('--field-dir', default=DEFAULT_FIELD_DIR)
    ap.add_argument('--broker', default=None)
    ap.add_argument('--port', type=int, default=None)
    ap.add_argument('--once', action='store_true',
                    help='run now and exit (0 if finished, 1 otherwise) instead of waiting for a start command')
    ap.add_argument('--mode', default='sync', choices=('fast', 'scaled', 'sync'))
    ap.add_argument('--step-seconds', type=float, default=1.0)
    a = ap.parse_args()
    if a.once:
        status = run(a.run, a.mode, a.step_seconds, a.field_dir, a.broker, a.port)
        print(status, flush=True)
        sys.exit(0 if status.get('state') == 'finished' else 1)
    gw = Gateway(a.run, a.field_dir, a.broker, a.port)
    gw.connect()
    try:
        gw.serve()
    except KeyboardInterrupt:
        pass
    finally:
        gw.disconnect()


if __name__ == '__main__':
    main()
