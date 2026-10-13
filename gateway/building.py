"""Building: the platform library that puts the building FMU in your hands.

Platform code, mounted read-only. Students use it in their own devices/gateway.py:
it loads the controlled or baseline FMU, steps it, checks that EnergyPlus is
still alive and reports the state of the run on the broker. What goes on the
broker as measurements and commands is your decision.

    from building import Building

    with Building('controlled') as b:
        b.start({'KITCHEN_Heating_Setpoint_FMU': 20.0})
        values = b.read()['values']                  # step 0
        while not b.done:
            b.set('KITCHEN_Heating_Setpoint_FMU', 18.0)
            out = b.step()                           # out['values'][name]

The pure helpers (read_parameters, pick_fmu, parse_model_description,
sim_timestamp) do not need pyfmi or paho, so they can be tested on their own.
"""

import datetime as dt
import json
import math
import os
import shutil
import tempfile
import zipfile
import xml.etree.ElementTree as ET

try:
    import paho.mqtt.client as mqtt
except ImportError:                      # the status is best effort anyway
    mqtt = None

RUNS = ('baseline', 'controlled')
HEALTH_EVERY = 12            # steps between EnergyPlus log checks
FROZEN_WINDOW = 12           # steps of constant outputs that count as a dead model
DEFAULT_FIELD_DIR = os.environ.get('GATEWAY_FIELD_DIR', '/home/jovyan/field')
STATUS_TOPIC = 'platform/building/status'


class BuildingStopped(RuntimeError):
    """EnergyPlus died, froze or failed inside the FMU: the run cannot go on."""


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------

def sim_timestamp(year, t):
    """ISO 8601 (timezone-naive) of the simulated instant: t seconds since Jan 1 00:00 of `year`."""
    return (dt.datetime(int(year), 1, 1) + dt.timedelta(seconds=float(t))).isoformat()


def parse_model_description(fmu_path):
    """Names of the FMU variables by causality, read from modelDescription.xml in the zip."""
    with zipfile.ZipFile(fmu_path) as z:
        root = ET.fromstring(z.read('modelDescription.xml'))
    inputs, outputs, everything = [], [], []
    for sv in root.iter('ScalarVariable'):
        name, causality = sv.get('name'), (sv.get('causality') or '').lower()
        everything.append(name)
        if causality == 'input':
            inputs.append(name)
        elif causality == 'output':
            outputs.append(name)
    return {'inputs': inputs, 'outputs': outputs, 'all': everything}


def read_parameters(path):
    ns = {}
    with open(path, encoding='utf-8') as f:
        exec(compile(f.read(), path, 'exec'), ns)
    par = ns.get('parameter')
    if not isinstance(par, dict):
        raise ValueError('parameters.py does not define a dict named parameter')
    missing = [k for k in ('fmu_step_size', 'fmu_start_time', 'fmu_final_time') if k not in par]
    if missing:
        raise ValueError('parameters.py lacks: ' + ', '.join(missing))
    step, start, stop = (float(par[k]) for k in ('fmu_step_size', 'fmu_start_time', 'fmu_final_time'))
    if step <= 0 or stop <= start:
        raise ValueError(f'invalid times: step {step}, start {start}, stop {stop}')
    return par, step, start, stop


def pick_fmu(field_dir, run, par):
    names = sorted(f for f in os.listdir(field_dir) if f.lower().endswith('.fmu'))
    base = [n for n in names if n[:-4].endswith('_baseline')]
    ctrl = [n for n in names if n not in base]
    hint = os.path.basename(str(par.get('fmu_path', ''))) if par else ''
    if run == 'baseline':
        want = hint[:-4] + '_baseline.fmu' if hint.endswith('.fmu') else ''
        cands = [want] if want in base else base
    else:
        cands = [hint] if hint in ctrl else ctrl
    if len(cands) != 1:
        raise ValueError(f'expected exactly one {run} FMU in {field_dir}, found {cands or "none"}'
                         + (' (export the model first)' if not cands else ''))
    return os.path.join(field_dir, cands[0])


# ---------------------------------------------------------------------------
# Building
# ---------------------------------------------------------------------------

class Building:
    def __init__(self, run='controlled', field_dir=DEFAULT_FIELD_DIR, publish_status=True, year=None):
        if run not in RUNS:
            raise ValueError(f'run must be one of {RUNS}')
        self.run = run
        self.field_dir = field_dir
        self.publish_status = publish_status
        self.year = int(year) if year is not None else dt.datetime.now().year
        try:
            self.parameters, self.step_size, self.start_time, self.stop_time = read_parameters(
                os.path.join(field_dir, 'parameters.py'))
        except (OSError, ValueError) as e:
            raise ValueError(f'parameters.py: {e}')
        self.fmu_path = pick_fmu(field_dir, run, self.parameters)
        self.md = parse_model_description(self.fmu_path)
        self.inputs = list(self.md['inputs'])
        self.outputs = list(self.md['outputs'])
        self.steps_total = int(math.ceil((self.stop_time - self.start_time) / self.step_size - 1e-9))
        self.step_no = 0
        self.t = self.start_time
        self.fmu = None
        self.work = None
        self._cwd = None
        self._pending = {}
        self._series = {}
        self._client = None
        self._last_pub = None
        self._finished = False

    @property
    def done(self):
        return self.step_no == self.steps_total

    @property
    def timestamp(self):
        return sim_timestamp(self.year, self.t)

    # -- life cycle ----------------------------------------------------------
    def start(self, initial=None):
        """Load the FMU in a fresh working dir and initialise it. `initial`: {input: value}."""
        from pyfmi import load_fmu
        initial = dict(initial or {})
        for name in initial:
            self._check_input(name)
        self._cwd = os.getcwd()
        # The FMU starts EnergyPlus in the cwd and writes Output_EPExport_Slave/ there
        self.work = tempfile.mkdtemp(prefix=f'building_{self.run}_')
        local = os.path.join(self.work, os.path.basename(self.fmu_path))
        shutil.copy(self.fmu_path, local)
        os.chdir(self.work)
        self.step_no, self.t, self._finished = 0, self.start_time, False
        self._series = {n: [] for n in self.outputs}
        self._open_client()
        try:
            self.fmu = load_fmu(local)
            if initial:
                self.fmu.set(list(initial), [float(v) for v in initial.values()])
            self.fmu.initialize(start_time=self.start_time, stop_time=self.stop_time)
        except Exception as e:
            self._report('fault', f'{type(e).__name__}: {e}')
            self.close()
            raise
        self._report('running')

    def read(self):
        """Outputs at the current time, in the same shape as step() returns."""
        raw = self.fmu.get(self.outputs) if self.outputs else []
        return {'step': self.step_no, 'time': self.t, 'ts': self.timestamp,
                'values': {n: float(v) for n, v in zip(self.outputs, raw)}}

    def set(self, name, value):
        """Queue an input value (FMU units); it is applied at the next step()."""
        self._check_input(name)
        self._pending[name] = float(value)

    def set_many(self, values):
        for name in values:
            self._check_input(name)
        for name, value in values.items():
            self._pending[name] = float(value)

    def step(self):
        """Apply the pending inputs, advance one step and return {step, time, ts, values}."""
        if self.fmu is None:
            raise RuntimeError('call start() first')
        if self.done:
            raise RuntimeError('the run is finished')
        try:
            if self._pending:
                self.fmu.set(list(self._pending), list(self._pending.values()))
                self._pending = {}
            self.fmu.do_step(current_t=self.t, step_size=self.step_size)
            self.t += self.step_size
            self.step_no += 1
            out = self.read()
            self._health(out['values'])
        except BuildingStopped as e:
            self._report('fault', str(e))
            raise
        except Exception as e:
            self._report('fault', f'{type(e).__name__}: {e}')
            raise BuildingStopped(f'{type(e).__name__}: {e}') from e
        if self.done:
            self._finished = True
            self._report('finished', f'{self.steps_total} steps completed')
        else:
            self._report('running')
        return out

    def report(self, state, message=''):
        """Publish the state of the run now (for gateways that stop it themselves)."""
        self._report(state, message)

    def close(self):
        """Terminate the FMU, restore the cwd, remove the work dir, flush the status."""
        if self.fmu is not None:
            for call in (self.fmu.terminate, self.fmu.free_instance):
                try:
                    call()
                except Exception:
                    pass
            self.fmu = None
        self._close_client()
        if self._cwd is not None:
            try:
                os.chdir(self._cwd)
            except OSError:
                pass
            self._cwd = None
        if self.work is not None:
            shutil.rmtree(self.work, ignore_errors=True)
            self.work = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    # -- internals -----------------------------------------------------------
    def _check_input(self, name):
        if name not in self.inputs:
            raise KeyError(f'{name!r} is not an input of the {self.run} FMU')

    def _health(self, values):
        from fmi_mlc.eplus_health import check_slave, watch_frozen
        for n, v in values.items():
            s = self._series[n]
            s.append(v)
            del s[:-FROZEN_WINDOW]
        # Constant outputs are normal at night or at a setpoint (a baseline can hold exactly
        # 20.0 and a constant base load for days), so a flat window is only a reason to look
        # at the EnergyPlus log now; the run stops only if the log says EnergyPlus ended.
        flat = bool(self._series) and watch_frozen(self._series, FROZEN_WINDOW)
        if self.step_no % HEALTH_EVERY == 0 or self.done or flat:
            rep = check_slave(self.work, raise_on_error=False)
            if rep.get('fatal'):
                detail = rep['severe'][-1] if rep['severe'] else rep['fatal_line']
                raise BuildingStopped(f'EnergyPlus terminated at step {self.step_no}: {detail}')

    def _open_client(self):
        if not self.publish_status or mqtt is None:
            return
        try:
            self._client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                                       client_id=f'building_{self.run}_{os.getpid()}')
            self._client.connect_async(os.environ.get('MQTT_BROKER_URL', 'mosquitto'),
                                       int(os.environ.get('MQTT_BROKER_PORT', 1883)), keepalive=30)
            self._client.loop_start()
        except Exception:
            self._client = None

    def _close_client(self):
        c, self._client = self._client, None
        if c is None:
            return
        try:
            if self._last_pub is not None:
                self._last_pub.wait_for_publish(timeout=1.5)
        except Exception:
            pass
        try:
            c.loop_stop()
            c.disconnect()
        except Exception:
            pass
        self._last_pub = None

    def _report(self, state, message=''):
        if self._client is None:
            return
        payload = {'state': state, 'run': self.run, 'step': self.step_no,
                   'steps_total': self.steps_total, 'sim_time': self.timestamp, 'message': message}
        try:
            self._last_pub = self._client.publish(STATUS_TOPIC, json.dumps(payload), qos=1, retain=True)
        except Exception:
            pass
