"""Demo subscriber: every point of the building goes to InfluxDB as  points,point=<name> value=<x>  at its simulated time
(database base_building for the baseline run, controlled_building for the controlled one).

Points are the last level of the topics  demo/<run>/<point>  and  demo/controlled/setpoint/<zone>  (stored as
setpoint_<zone>). A value outside the physical range of its point is dropped, and the lines are written in batches.
"""
import json
import os
import threading
import time
from datetime import datetime, timezone

import paho.mqtt.client as mqtt
import requests

HOST = os.getenv("MQTT_BROKER_URL", "mosquitto")
PORT = int(os.getenv("MQTT_BROKER_PORT", "1883"))
INFLUX = os.getenv("INFLUX_URL", "http://influxdb:8086")
AUTH = {"u": os.getenv("INFLUX_USERNAME", ""), "p": os.getenv("INFLUX_PASSWORD", "")}
DATABASE = {"baseline": "base_building", "controlled": "controlled_building"}
RANGE = {"temperature": (-40, 60), "outdoor_temperature": (-40, 60), "outdoor_humidity": (0, 100), "wind_speed": (0, 80),
         "solar_direct": (0, 1500), "electricity_kw": (0, 1e4), "heating_kw": (0, 1e4), "setpoint": (0, 40)}   # by prefix of the point
FLUSH_EVERY = 2.0                           # s

pending = {"baseline": [], "controlled": []}
lock = threading.Lock()


def plausible(point, value):
    for prefix, (low, high) in RANGE.items():
        if point.startswith(prefix):
            return low <= value <= high
    return True                              # the cumulative energies have no range


def on_message(client, userdata, msg):
    if not msg.payload:                                      # a retained value cleared by the gateway
        return
    try:
        parts = msg.topic.split("/")                         # demo/<run>/<point>  or  demo/<run>/setpoint/<zone>
        run, point = parts[1], "_".join(parts[2:])
        if run not in DATABASE or point in ("clock", "ack") or parts[2] == "cmd":
            return
        data = json.loads(msg.payload)
        value = float(data["value"])
        if not plausible(point, value):
            print("dropped (out of range):", msg.topic, value, flush=True)
            return
        ts = datetime.fromisoformat(data["ts"]).replace(tzinfo=timezone.utc)
        with lock:
            pending[run].append(f"points,point={point} value={value} {int(ts.timestamp())}")
    except (KeyError, IndexError, ValueError, TypeError):
        print("not stored:", msg.topic, msg.payload[:80], flush=True)


def flusher():
    while True:
        time.sleep(FLUSH_EVERY)
        for run, database in DATABASE.items():
            with lock:
                lines, pending[run] = pending[run], []
            if not lines:
                continue
            try:
                r = requests.post(f"{INFLUX}/write", params={**AUTH, "db": database, "precision": "s"},
                                  data="\n".join(lines), timeout=10)
                r.raise_for_status()
            except requests.RequestException as e:
                print("InfluxDB did not answer, batch kept:", e, flush=True)
                with lock:
                    pending[run] = lines + pending[run]


threading.Thread(target=flusher, daemon=True).start()
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="subscriber")
client.on_connect = lambda c, u, flags, rc, props: c.subscribe([("demo/+/#", 0)])
client.on_message = on_message
client.connect(HOST, PORT)
client.loop_forever()
