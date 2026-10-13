"""Process supervisor of the bms_services container, driven from MQTT.

Nothing starts by itself: the platform's Control room publishes control
messages and this supervisor starts, stops and restarts the students' processes.

Services: every *.py directly in devices/, iot/ and ai/ of the Workspace
(BMS_WORK_DIR), except devices/gateway.py, which is the building. The service
name is <folder>/<file>, e.g. iot/subscriber.py. The folders are rescanned
every second.
  control  platform/services/<folder>/<file>/control   {"cmd": "start|stop|restart"}
  status   platform/services/<folder>/<file>/status    retained, qos 1:
           {state: stopped|running|crashed|finished, pid, started, exit_code,
            restarts, log_tail: [last 20 log lines]}
A started service stays wanted: exit code != 0 -> crashed and restarted with
backoff (1, 2, 4 ... 60 s, reset after a run of 60 s or more); exit code 0 ->
finished, not restarted. Saving the file while it runs restarts it at once.
Output goes to work/logs/<folder>_<file>.log (e.g. logs/iot_subscriber.py.log),
truncated above 5 MB.

Building (devices/gateway.py, or emergency_gateway.py when the file
work/.emergency exists at start time), run once, never restarted:
  control  platform/building/control   {"cmd": "start", "run": "baseline|controlled",
                                        "mode": "fast|scaled|sync", "step_seconds": 0.2}
                                       or {"cmd": "stop"}
  status   platform/building/process   retained: the service status fields plus
           emergency, run, mode, emergency_flag (the .emergency file exists now).
Logs: logs/devices_gateway.py.log or logs/emergency_gateway.log.
"""

import datetime as dt
import json
import os
import queue
import signal
import subprocess
import sys
import time

import paho.mqtt.client as mqtt

WORK = os.environ.get('BMS_WORK_DIR', '/home/jovyan/work')
LOGS = os.path.join(WORK, 'logs')
FOLDERS = ('devices', 'iot', 'ai')
BUILDING_FILE = 'gateway.py'
EMERGENCY_FLAG = os.path.join(WORK, '.emergency')
EMERGENCY_SCRIPT = '/opt/gateway/emergency_gateway.py'
BROKER = os.environ.get('MQTT_BROKER_URL', 'mosquitto')
PORT = int(os.environ.get('MQTT_BROKER_PORT', '1883'))
SERVICES_TOPIC = 'platform/services/'
BUILDING_CONTROL = 'platform/building/control'
BUILDING_STATUS = 'platform/building/process'
MAX_LOG = 5 * 1024 * 1024
MAX_BACKOFF = 60
REFRESH = 2.0
RUNS = ('baseline', 'controlled')
MODES = ('fast', 'scaled', 'sync')


def iso(ts):
    return dt.datetime.fromtimestamp(ts).isoformat(timespec='seconds') if ts else None


class Managed:
    """One child process: its state, its log and what to publish about it."""

    def __init__(self, name, topic, log_path, restart):
        self.name = name
        self.topic = topic                  # status topic
        self.log_path = log_path
        self.restart = restart              # False for the building: runs once
        self.proc = None
        self.state = 'stopped'
        self.exit_code = None
        self.restarts = 0
        self.started = 0.0
        self.wanted = False
        self.backoff = 1
        self.retry_at = 0.0
        self.mtime = None
        self.logfile = None
        self.last_sig = None
        self.last_pub = 0.0
        self.force = True                   # publish on the next tick

    # -- helpers ----------------------------------------------------------
    def note(self, msg):
        line = f'[supervisor {dt.datetime.now():%Y-%m-%d %H:%M:%S}] {msg}\n'
        try:
            os.makedirs(LOGS, exist_ok=True)
            if self.logfile:
                self.logfile.write(line)
                self.logfile.flush()
            else:
                with open(self.log_path, 'a', encoding='utf-8') as f:
                    f.write(line)
        except OSError:
            pass
        print(f'[supervisor] {self.name}: {msg}', flush=True)

    def log_tail(self, n=20):
        try:
            with open(self.log_path, 'rb') as f:
                f.seek(0, os.SEEK_END)
                f.seek(max(0, f.tell() - 16384))
                data = f.read().decode('utf-8', 'replace')
            return data.splitlines()[-n:]
        except OSError:
            return []

    def running(self):
        return self.proc is not None and self.proc.poll() is None

    def rotate(self):
        try:
            if os.path.getsize(self.log_path) > MAX_LOG:
                os.truncate(self.log_path, 0)
                self.note('log truncated (over 5 MB)')
        except OSError:
            pass

    # -- process control --------------------------------------------------
    def spawn(self, cmd, cwd, env=None):
        os.makedirs(LOGS, exist_ok=True)
        self.close_log()
        self.logfile = open(self.log_path, 'a', buffering=1, encoding='utf-8')
        try:
            self.proc = subprocess.Popen(cmd, cwd=cwd, env=env or os.environ.copy(),
                                         stdout=self.logfile, stderr=subprocess.STDOUT)
        except OSError as e:
            self.note(f'cannot start: {e}')
            self.proc, self.state, self.exit_code = None, 'crashed', -1
            self.force = True
            return False
        self.started = time.time()
        self.state = 'running'
        self.exit_code = None
        self.note(f'started (pid {self.proc.pid})')
        self.force = True
        return True

    def terminate(self):
        """Send SIGTERM (no waiting); see reap_stopped."""
        if self.running():
            self.proc.terminate()

    def kill_and_wait(self, deadline):
        if self.proc is None:
            return
        try:
            self.proc.wait(max(0.0, deadline - time.time()))
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait()
        self.exit_code = self.proc.returncode
        self.proc = None
        self.close_log()

    def stop(self):
        """User stop: terminate, wait 5 s, kill. The process is no longer wanted."""
        self.wanted = False
        if self.proc is not None:
            self.terminate()
            self.kill_and_wait(time.time() + 5)
            self.note(f'stopped (exit code {self.exit_code})')
        self.state = 'stopped'
        self.force = True

    def close_log(self):
        if self.logfile:
            try:
                self.logfile.close()
            except OSError:
                pass
            self.logfile = None

    # -- status -----------------------------------------------------------
    def payload(self):
        return {
            'state': self.state,
            'pid': self.proc.pid if self.running() else None,
            'started': iso(self.started) if self.state == 'running' else (iso(self.started) if self.started else None),
            'exit_code': self.exit_code,
            'restarts': self.restarts,
            'log_tail': self.log_tail(),
        }

    def extra(self):
        return {}

    def publish(self, client, now, retain_empty=False):
        sig = (self.state, self.proc.pid if self.proc else None, self.started,
               self.exit_code, self.restarts, tuple(sorted(self.extra().items())))
        due = self.force or sig != self.last_sig or (self.state == 'running' and now - self.last_pub >= REFRESH)
        if not due:
            return
        body = self.payload()
        body.update(self.extra())
        client.publish(self.topic, json.dumps(body), qos=1, retain=True)
        self.last_sig, self.last_pub, self.force = sig, now, False

    def clear(self, client):
        client.publish(self.topic, b'', qos=1, retain=True)


class Service(Managed):
    def __init__(self, folder, file):
        name = f'{folder}/{file}'
        super().__init__(name, f'{SERVICES_TOPIC}{name}/status',
                         os.path.join(LOGS, f'{folder}_{file}.log'), True)
        self.folder, self.file = folder, file
        self.path = os.path.join(WORK, folder, file)

    def start(self, restart=False):
        if self.running():
            return
        try:
            self.mtime = os.path.getmtime(self.path)
        except OSError:
            self.note('file missing, cannot start')
            return
        self.wanted = True
        if restart:
            self.restarts += 1
        self.spawn([sys.executable, '-u', self.path], os.path.join(WORK, self.folder))

    def tick(self):
        exists = os.path.isfile(self.path)
        if self.running():
            self.rotate()
            if exists and os.path.getmtime(self.path) != self.mtime:
                self.note('file changed, restarting')
                self.stop()
                self.backoff, self.retry_at = 1, 0.0
                self.start(restart=True)
            return
        if self.proc is not None:                         # it exited by itself
            code = self.proc.wait()
            ran = time.time() - self.started
            self.proc = None
            self.close_log()
            self.exit_code = code
            self.force = True
            if code == 0:
                self.state, self.wanted = 'finished', False
                self.note('finished (exit code 0)')
                return
            self.state = 'crashed'
            if ran >= MAX_BACKOFF:
                self.backoff = 1
            delay = self.backoff                          # 1, 2, 4 ... 60 s
            self.backoff = min(self.backoff * 2, MAX_BACKOFF)
            self.retry_at = time.time() + delay
            self.note(f'exited with code {code} after {ran:.0f} s, restart in {delay} s')
            return
        if self.wanted and self.state == 'crashed' and exists and time.time() >= self.retry_at:
            self.start(restart=True)
        elif self.wanted and self.state == 'crashed' and exists and os.path.getmtime(self.path) != self.mtime:
            self.backoff, self.retry_at = 1, 0.0          # edited while waiting: no more waiting
            self.start(restart=True)

    def handle(self, cmd):
        if cmd == 'start':
            if self.running():
                self.note('start ignored: already running')
            else:
                self.backoff, self.retry_at = 1, 0.0
                self.start()
        elif cmd == 'stop':
            self.stop()
        elif cmd == 'restart':
            self.stop()
            self.backoff, self.retry_at = 1, 0.0
            self.start(restart=True)
        else:
            self.note(f'unknown command {cmd!r}')


class Building(Managed):
    def __init__(self):
        super().__init__('building', BUILDING_STATUS, os.path.join(LOGS, 'devices_gateway.py.log'), False)
        self.emergency = False
        self.run = None
        self.mode = None
        self.flag = os.path.exists(EMERGENCY_FLAG)

    def extra(self):
        return {'emergency': self.emergency, 'run': self.run, 'mode': self.mode,
                'emergency_flag': self.flag}

    def start(self, run, mode, step):
        if self.running():
            self.note('start ignored: the building is already running')
            return
        emergency = os.path.exists(EMERGENCY_FLAG)
        self.log_path = os.path.join(LOGS, 'emergency_gateway.log' if emergency
                                     else 'devices_gateway.py.log')
        if run not in RUNS or mode not in MODES:
            self.note(f'start ignored: bad run/mode ({run!r}, {mode!r})')
            return
        try:
            step = float(step)
            # Only the scaled mode waits between steps; fast and sync ignore the value.
            if step < 0 or (mode == 'scaled' and step == 0):
                raise ValueError
        except (TypeError, ValueError):
            self.note(f'start ignored: bad step_seconds ({step!r})')
            return
        env = os.environ.copy()
        env.update(SBEP_RUN=run, SBEP_MODE=mode, SBEP_STEP_SECONDS=str(step))
        if emergency:
            cmd = [sys.executable, '-u', EMERGENCY_SCRIPT, '--once', '--run', run, '--mode', mode,
                   '--step-seconds', str(step)]
            cwd = os.path.dirname(EMERGENCY_SCRIPT)
        else:
            cmd = [sys.executable, '-u', os.path.join(WORK, 'devices', BUILDING_FILE)]
            cwd = os.path.join(WORK, 'devices')
        self.emergency, self.run, self.mode = emergency, run, mode
        self.restarts = 0
        self.wanted = True
        self.note(f'starting {" ".join(cmd[2:])} (emergency={emergency})')
        self.spawn(cmd, cwd, env)

    def tick(self):
        flag = os.path.exists(EMERGENCY_FLAG)
        if flag != self.flag:
            self.flag, self.force = flag, True
        if self.running():
            self.rotate()
        elif self.proc is not None:
            code = self.proc.wait()
            self.proc = None
            self.close_log()
            self.exit_code, self.wanted, self.force = code, False, True
            self.state = 'finished' if code == 0 else 'crashed'
            self.note(f'exited with code {code}')

    def handle(self, msg):
        cmd = msg.get('cmd')
        if cmd == 'start':
            self.start(msg.get('run', 'baseline'), msg.get('mode', 'fast'), msg.get('step_seconds', 0.2))
        elif cmd == 'stop':
            self.stop()
        else:
            self.note(f'unknown command {cmd!r}')


class Supervisor:
    def __init__(self):
        self.services = {}
        self.building = Building()
        self.commands = queue.Queue()
        self.connected = False
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id='bms_supervisor')
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.on_message = self.on_message
        self.client.reconnect_delay_set(1, 10)

    # -- MQTT callbacks only enqueue --------------------------------------
    def on_connect(self, client, userdata, flags, reason_code, properties=None):
        print(f'[supervisor] connected to {BROKER}:{PORT} ({reason_code})', flush=True)
        client.subscribe([(SERVICES_TOPIC + '#', 1), (BUILDING_CONTROL, 1)])
        self.connected = True
        self.commands.put(('republish', None))

    def on_disconnect(self, client, userdata, *args):
        self.connected = False
        print('[supervisor] disconnected from the broker', flush=True)

    def on_message(self, client, userdata, msg):
        if msg.retain or not msg.payload:       # stale retained controls must not start anything
            return
        self.commands.put((msg.topic, msg.payload))

    # -- command execution (main thread) ----------------------------------
    def execute(self, topic, payload):
        if topic == 'republish':
            for m in [self.building, *self.services.values()]:
                m.force = True
            return
        try:
            msg = json.loads(payload)
            if not isinstance(msg, dict):
                raise ValueError('not an object')
        except ValueError as e:
            print(f'[supervisor] bad message on {topic}: {e}', flush=True)
            return
        if topic == BUILDING_CONTROL:
            self.building.handle(msg)
        elif topic.startswith(SERVICES_TOPIC) and topic.endswith('/control'):
            name = topic[len(SERVICES_TOPIC):-len('/control')]
            svc = self.services.get(name)
            if svc is None:
                print(f'[supervisor] control for unknown service {name}', flush=True)
            else:
                svc.handle(msg.get('cmd'))

    def scan(self):
        found = set()
        for folder in FOLDERS:
            try:
                files = os.listdir(os.path.join(WORK, folder))
            except OSError:
                continue
            for f in files:
                name = f'{folder}/{f}'
                if not f.endswith('.py') or name == f'devices/{BUILDING_FILE}':
                    continue
                if os.path.isfile(os.path.join(WORK, folder, f)):
                    found.add(name)
        for name in sorted(found - self.services.keys()):
            folder, file = name.split('/')
            self.services[name] = Service(folder, file)
            print(f'[supervisor] service found: {name}', flush=True)
        for name in sorted(self.services.keys() - found):
            svc = self.services.pop(name)
            svc.note('file removed, stopping')
            svc.stop()
            svc.publish(self.client, time.time())
            svc.clear(self.client)

    def stop_all(self):
        everything = [self.building, *self.services.values()]
        for m in everything:
            m.wanted = False
            m.terminate()
        deadline = time.time() + 5
        for m in everything:
            m.kill_and_wait(deadline)
            if m.state == 'running':
                m.state = 'stopped'
            m.force = True
            m.publish(self.client, time.time())
        time.sleep(0.3)                          # let qos 1 publishes leave

    def run(self):
        done = []
        signal.signal(signal.SIGTERM, lambda *a: done.append(1))
        self.client.connect_async(BROKER, PORT, keepalive=30)
        self.client.loop_start()
        print(f'[supervisor] workspace {WORK}', flush=True)
        os.makedirs(LOGS, exist_ok=True)
        last_scan = 0.0
        try:
            while not done:
                try:
                    topic, payload = self.commands.get(timeout=1)
                    self.execute(topic, payload)
                    while True:
                        topic, payload = self.commands.get_nowait()
                        self.execute(topic, payload)
                except queue.Empty:
                    pass
                except Exception as e:
                    print(f'[supervisor] command error: {e}', flush=True)
                now = time.time()
                if now - last_scan >= 1:
                    last_scan = now
                    try:
                        self.scan()
                    except Exception as e:
                        print(f'[supervisor] scan error: {e}', flush=True)
                for m in [self.building, *list(self.services.values())]:
                    try:
                        m.tick()
                        m.publish(self.client, now)
                    except Exception as e:
                        print(f'[supervisor] {m.name}: {e}', flush=True)
        except KeyboardInterrupt:
            pass
        self.stop_all()
        self.client.loop_stop()
        self.client.disconnect()


if __name__ == '__main__':
    Supervisor().run()
