"""End-to-end test of gateway/supervisor.py inside ONE container with no network.

The container has no route to the platform, so the test brings its own broker: a tiny MQTT 3.1.1 broker (thread, 127.0.0.1:1883,
QoS 0/1, wildcards, retained messages). Then it runs the real supervisor as a child process, drives it with the same control
messages the Control room publishes, and checks the answers:

  1. the supervisor connects and publishes a retained status for every *.py of Workspace/{devices,iot,ai} (devices/gateway.py excepted)
  2. 'start' of ai/controller.py (the template exits 0) -> state finished, exit_code 0
  3. with Workspace/.emergency present, platform/building/control {"cmd":"start","run":"baseline","mode":"fast"} runs
     emergency_gateway.py --once on Field/lab_optimal_baseline.fmu (pyfmi + EnergyPlus child process + paho) until the week
     is over -> platform/building/process state finished; the sensor messages that arrived at the broker are counted
  4. 'stop' of a service and SIGTERM of the supervisor (exit code)

    docker run --rm --network none --memory=1g --entrypoint /opt/conda/envs/conda_environment/bin/python \
      -e LD_LIBRARY_PATH=/opt/conda/envs/conda_environment/lib -e PYTHONPATH=/opt/gateway \
      -v <repo>/gateway:/opt/gateway:ro -v <repo>/Field:/home/jovyan/field:ro \
      -v <repo>/conda-environment/fmi_mlc:/opt/conda/envs/conda_environment/lib/python3.9/site-packages/fmi_mlc:ro \
      -v <COPY of Workspace>:/home/jovyan/work -v <repo>/tests/runtime/supervisor_e2e.py:/e2e.py:ro  <image> /e2e.py

Prints a JSON summary as the last line.
"""
import json
import os
import signal
import socket
import socketserver
import subprocess
import sys
import threading
import time

import paho.mqtt.client as mqtt

HOST, PORT = "127.0.0.1", 1883
WORK = "/home/jovyan/work"


# ---------------------------------------------------------------- mini broker
def topic_matches(filt, topic):
    f, t = filt.split("/"), topic.split("/")
    for i, p in enumerate(f):
        if p == "#":
            return True
        if i >= len(t) or (p != "+" and p != t[i]):
            return False
    return len(f) == len(t)


class Broker(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self):
        super().__init__((HOST, PORT), Handler)
        self.lock = threading.Lock()
        self.subs = []          # (handler, filter)
        self.retained = {}
        self.count = 0


def varint(n):
    out = bytearray()
    while True:
        b, n = n % 128, n // 128
        out.append(b | (128 if n else 0))
        if not n:
            return bytes(out)


class Handler(socketserver.BaseRequestHandler):
    def send(self, data):
        with self.wlock:
            try:
                self.request.sendall(data)
            except OSError:
                pass

    def deliver(self, topic, payload, retain):
        tb = topic.encode()
        body = len(tb).to_bytes(2, "big") + tb + payload
        self.send(bytes([0x30 | (1 if retain else 0)]) + varint(len(body)) + body)

    def recv(self, n):
        buf = b""
        while len(buf) < n:
            c = self.request.recv(n - len(buf))
            if not c:
                raise EOFError
            buf += c
        return buf

    def handle(self):
        self.wlock = threading.Lock()
        srv = self.server
        try:
            while True:
                b0 = self.recv(1)[0]
                mult, length = 1, 0
                while True:
                    d = self.recv(1)[0]
                    length += (d & 127) * mult
                    mult *= 128
                    if not d & 128:
                        break
                body = self.recv(length) if length else b""
                ptype = b0 >> 4
                if ptype == 1:
                    self.send(b"\x20\x02\x00\x00")
                elif ptype == 3:
                    qos, retain = (b0 >> 1) & 3, bool(b0 & 1)
                    tl = int.from_bytes(body[:2], "big")
                    topic = body[2:2 + tl].decode()
                    pos = 2 + tl
                    if qos:
                        self.send(b"\x40\x02" + body[pos:pos + 2])
                        pos += 2
                    payload = body[pos:]
                    with srv.lock:
                        srv.count += 1
                        if retain:
                            if payload:
                                srv.retained[topic] = payload
                            else:
                                srv.retained.pop(topic, None)
                        targets = [h for h, f in srv.subs if topic_matches(f, topic)]
                    for h in set(targets):
                        h.deliver(topic, payload, False)
                elif ptype == 8:
                    pid = body[:2]
                    pos, granted = 2, b""
                    while pos < len(body):
                        fl = int.from_bytes(body[pos:pos + 2], "big")
                        filt = body[pos + 2:pos + 2 + fl].decode()
                        pos += 2 + fl + 1
                        granted += b"\x00"
                        with srv.lock:
                            srv.subs.append((self, filt))
                            ret = [(t, p) for t, p in srv.retained.items() if topic_matches(filt, t)]
                        for t, p in ret:
                            self.deliver(t, p, True)
                    self.send(b"\x90" + varint(2 + len(granted)) + pid + granted)
                elif ptype == 10:
                    self.send(b"\xb0\x02" + body[:2])
                elif ptype == 12:
                    self.send(b"\xd0\x00")
                elif ptype == 14:
                    return
        except (EOFError, OSError):
            pass
        finally:
            with srv.lock:
                srv.subs = [(h, f) for h, f in srv.subs if h is not self]


# ---------------------------------------------------------------- the test
log = []                      # (time, topic, parsed payload)
status = {}                   # latest status per topic
results = {}


def on_message(c, u, m):
    try:
        p = json.loads(m.payload)
    except ValueError:
        p = m.payload
    log.append((time.time(), m.topic, p))
    if m.topic.startswith("platform/"):
        status[m.topic] = p


def wait_for(cond, timeout, what):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if cond():
            return True
        time.sleep(0.2)
    results.setdefault("timeouts", []).append(what)
    return False


def main():
    broker = Broker()
    threading.Thread(target=broker.serve_forever, daemon=True).start()

    env = dict(os.environ, BMS_WORK_DIR=WORK, MQTT_BROKER_URL=HOST, MQTT_BROKER_PORT=str(PORT))
    sup = subprocess.Popen([sys.executable, "-u", "/opt/gateway/supervisor.py"], env=env,
                           stdout=open("/tmp/supervisor.out", "w"), stderr=subprocess.STDOUT)

    cl = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="e2e")
    cl.on_message = on_message
    cl.connect(HOST, PORT)
    cl.subscribe([("platform/#", 0), ("building/#", 0), ("#", 0)])
    cl.loop_start()

    # 1. every service of the Workspace has a retained status
    names = ["iot/subscriber.py", "ai/controller.py"]
    results["1_status_published"] = wait_for(
        lambda: all(f"platform/services/{n}/status" in status for n in names) and "platform/building/process" in status,
        30, "status of the services")
    results["1_services_seen"] = sorted(t.split("platform/services/")[1].rsplit("/", 1)[0]
                                        for t in status if t.startswith("platform/services/"))
    results["1_building_status"] = {k: status.get("platform/building/process", {}).get(k)
                                    for k in ("state", "emergency", "emergency_flag")}

    # 2. start a service that exits 0 (the template of ai/controller.py)
    cl.publish("platform/services/ai/controller.py/control", json.dumps({"cmd": "start"}), qos=1)
    ok = wait_for(lambda: status.get("platform/services/ai/controller.py/status", {}).get("state") == "finished", 20,
                  "controller.py finished")
    s = status.get("platform/services/ai/controller.py/status", {})
    results["2_controller_template"] = {"finished": ok, "state": s.get("state"), "exit_code": s.get("exit_code"),
                                        "log_tail": s.get("log_tail", [])[-2:]}

    # 3. the building through the emergency gateway
    open(os.path.join(WORK, ".emergency"), "w").close()
    wait_for(lambda: status.get("platform/building/process", {}).get("emergency_flag") is True, 10, "flag seen")
    n0, t0 = len(log), time.time()
    cl.publish("platform/building/control", json.dumps({"cmd": "start", "run": "baseline", "mode": "fast",
                                                         "step_seconds": 0}), qos=1)
    wait_for(lambda: status.get("platform/building/process", {}).get("state") == "running", 30, "building running")
    ok = wait_for(lambda: status.get("platform/building/process", {}).get("state") in ("finished", "crashed"), 600,
                  "building finished")
    b = status.get("platform/building/process", {})
    non_platform = [(t, p) for _, t, p in log[n0:] if not t.startswith("platform/")]
    topics = sorted({t for t, _ in non_platform})
    results["3_building"] = {"ok": ok, "state": b.get("state"), "exit_code": b.get("exit_code"), "emergency": b.get("emergency"),
                             "wall_s": round(time.time() - t0, 1), "messages_from_building": len(non_platform),
                             "distinct_topics": len(topics), "example_topics": topics[:6],
                             "log_tail": b.get("log_tail", [])[-3:]}

    # 4. stop and shut down
    cl.publish("platform/services/iot/subscriber.py/control", json.dumps({"cmd": "start"}), qos=1)
    time.sleep(3)
    cl.publish("platform/services/iot/subscriber.py/control", json.dumps({"cmd": "stop"}), qos=1)
    time.sleep(2)
    results["4_subscriber_after_stop"] = status.get("platform/services/iot/subscriber.py/status", {}).get("state")
    sup.send_signal(signal.SIGTERM)
    try:
        results["4_supervisor_exit_code_on_SIGTERM"] = sup.wait(30)
    except subprocess.TimeoutExpired:
        sup.kill()
        results["4_supervisor_exit_code_on_SIGTERM"] = "did not stop in 30 s"
    results["supervisor_stdout_tail"] = open("/tmp/supervisor.out").read().splitlines()[-8:]
    results["logs_dir"] = sorted(os.listdir(os.path.join(WORK, "logs"))) if os.path.isdir(os.path.join(WORK, "logs")) else None
    cl.loop_stop()
    print(json.dumps(results, indent=1, default=str))


if __name__ == "__main__":
    main()
