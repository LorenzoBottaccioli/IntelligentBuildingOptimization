"""
subscriber.py -- the subscriber of the demo: a finished one, to read next to the Lab's empty one.

The idea
--------
The gateway publishes the readings of the building on the MQTT broker, and a broker keeps no history: a message that nobody
receives is lost (a retained one keeps only the LAST value). This script listens to the broker and stores every reading in a
time series database, so that Grafana and the data notebooks can plot, query and analyse it later:

    gateway --MQTT--> broker --MQTT--> this script --HTTP--> InfluxDB 1.x --> Grafana, data notebooks

It has the same five sections as the Lab's subscriber: 1. what it listens to, 2. clean and check, 3. store, 4. republish,
5. the service. It is a service: BMS > Control room > Start on iot/subscriber.py, BEFORE the building, otherwise the first
values are lost. Everything it print()s appears in its log in the Control room.

How the schema was chosen
-------------------------
InfluxDB 1.x has no schema to declare: it exists from the first line written. So you choose it, and the way to choose it is to
start from the question you will ask the data later. For example "the temperature of the south zone, in the controlled run":

    SELECT value FROM points WHERE point = 'temperature_south'          on the database controlled_building

Every part of that question is one decision of the schema:

    decision         in the question            what we chose
    ---------------  -------------------------  --------------------------------------------------------------------------
    1 database       controlled_building        one per run (the baseline run: base_building), so that two runs never
                                                overwrite each other. The platform creates them; this script only writes.
    2 measurement    FROM points                one for the whole building, like one table with a row per reading
    3 tag            WHERE point = '...'        "point": the NAME of the sensor or actuator (temperature_south, heating_kw,
                                                setpoint_south, ...). Text that is indexed: what you filter and group by
    4 field          SELECT value               "value": the number itself, always a float. What you plot and aggregate
    5 timestamp      the time axis of the plot  the SIMULATED instant of the reading (the "ts" of the message, in seconds),
                                                not the clock of the computer

Rule of thumb: what you filter or group by is a TAG, what you average is a FIELD. A new sensor needs no change here: it is
just one more value of the tag "point". Writing the same measurement, tags and timestamp twice stores ONE point (the second
replaces the first), which is why heating_kw and heating_kwh have different names.

One reading is one line of the "line protocol", and the lines of a batch go in one  POST /write?db=<database>&precision=s :

    points,point=temperature_south value=20.4 1767226200
    ------ ----------------------- ---------- ----------
    2      3                       4          5            the numbers are the decisions above (1 is the ?db= of the POST)

From a message to a line, with the decision that each part comes from:

    topic    demo/controlled/temperature_south      ->  1 database controlled_building   3 tag point=temperature_south
    payload  {"value": 20.4, "ts": "2026-01-01T00:10:00"}      ->  4 field value=20.4   5 timestamp 1767226200
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
AUTH = {"u": os.getenv("INFLUX_USERNAME", ""), "p": os.getenv("INFLUX_PASSWORD", "")}     # InfluxDB 1.x: user and password as parameters
FLUSH_EVERY = 2.0                                    # s between two writes


# ===========================================================================
# 1. What it listens to
# ===========================================================================
# demo/+/# : every point of every run (+ is one level, # is everything below). The topic tells everything we need:
#     demo/<run>/<point>   or   demo/<run>/setpoint/<zone>
# the run (second level) is decision 1, the database; the rest is decision 3, the tag value (setpoint/south -> setpoint_south).
# The weather of demo/site/ is the same as the one of the run: it is not stored twice.
DATABASE = {"baseline": "base_building", "controlled": "controlled_building"}          # decision 1
pending = {"baseline": [], "controlled": []}        # run -> lines waiting for the next write
lock = threading.Lock()                              # the MQTT thread fills pending, the writer thread empties it


# ===========================================================================
# 2. Clean and check
# ===========================================================================
# A value outside the physical range of its point is a faulty sensor, not a fact: it is dropped (and said in the log).
# A name ending in "_" is a family: "temperature_" covers temperature_west, temperature_south, ... Any other name is exact:
# "heating_kw" is the power, and must not catch heating_kwh, the energy since the start, which only ever grows.
RANGE = {"temperature_": (-40, 60), "outdoor_temperature": (-40, 60), "outdoor_humidity": (0, 100), "wind_speed": (0, 80),
         "solar_direct": (0, 1500), "electricity_kw": (0, 1e4), "heating_kw": (0, 1e4), "setpoint_": (0, 40)}


def plausible(point, value):
    for name, (low, high) in RANGE.items():
        if point == name or (name.endswith("_") and point.startswith(name)):
            return low <= value <= high
    return True                                      # the cumulative energies (..._kwh) have no range


# ===========================================================================
# 3. Store: the schema
# ===========================================================================
MEASUREMENT = "points"                               # decision 2: one for the whole building
TAG_KEY = "point"                                    # decision 3: the name of the sensor or actuator is the tag value
FIELD_KEY = "value"                                  # decision 4: the number itself


def to_line(point, value, ts):
    """One reading -> one line, with the parts in the order of the line protocol:
         measurement , tag key = tag value   field key = number   timestamp (decision 5)
    point is the tag value (3), value the field (4), ts a datetime: int(ts.timestamp()) is its seconds, as precision=s says."""
    return f"{MEASUREMENT},{TAG_KEY}={point} {FIELD_KEY}={value} {int(ts.timestamp())}"


def flusher():
    "Every FLUSH_EVERY seconds: one POST per run, to ITS database (decision 1), with all its lines. One request per value would be far too slow."
    while True:
        time.sleep(FLUSH_EVERY)
        for run, database in DATABASE.items():
            with lock:
                lines, pending[run] = pending[run], []       # take the lines and leave an empty list for the MQTT thread
            if not lines:
                continue
            try:
                requests.post(f"{INFLUX}/write", params={**AUTH, "db": database, "precision": "s"},
                              data="\n".join(lines), timeout=10).raise_for_status()
            except requests.RequestException as e:           # InfluxDB did not answer: keep the batch, try again next round
                print("InfluxDB did not answer, batch kept:", e, flush=True)
                with lock:
                    pending[run] = lines + pending[run]


# ===========================================================================
# 4. Republish
# ===========================================================================
# What it is for: the devices speak their own language (raw names, odd units, now and then a wrong value). Once a value is
# renamed, converted (J -> kWh) and checked in section 2, it can go out AGAIN on a clean topic of yours, for whoever should not
# have to know the devices: an HMI, a controller, another service. The database keeps the history, this keeps the "now".
#
# The demo does not do it, and the reason is simple: its gateway already publishes clean values (names, units, one topic per
# point) and the HMIs and the controller read them from the gateway directly, so republishing would only copy messages.
# In the Lab it can make sense: if your gateway publishes raw FMU names or joules, here you would publish the clean ones.
# It would be a few lines in on_message, after the check:  client.publish("clean/<run>/<point>", payload, retain=True)


# ===========================================================================
# 5. The service
# ===========================================================================
def on_message(client, userdata, msg):
    "Called for every message, in the MQTT thread: read it, check it, and leave the line for the next write."
    if not msg.payload:                              # an empty retained message: the gateway clearing an old value
        return
    try:
        parts = msg.topic.split("/")                 # demo/<run>/<point>  or  demo/<run>/setpoint/<zone>
        run, point = parts[1], "_".join(parts[2:])   # run -> which database (1); point -> the tag value (3)
        if run not in DATABASE or point in ("clock", "ack") or parts[2] == "cmd":
            return                                   # the site copy, the tick, the answers and the commands are not measurements
        data = json.loads(msg.payload)
        value = float(data["value"])                 # the field (4)
        if not plausible(point, value):
            print("dropped (out of range):", msg.topic, value, flush=True)
            return
        ts = datetime.fromisoformat(data["ts"]).replace(tzinfo=timezone.utc)   # the timestamp (5): "ts" has no time zone, it is simulated time
        with lock:
            pending[run].append(to_line(point, value, ts))
    except (KeyError, IndexError, ValueError, TypeError):   # a message we cannot read must not stop the service
        print("not stored:", msg.topic, msg.payload[:80], flush=True)


threading.Thread(target=flusher, daemon=True).start()       # daemon: it ends with the script
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="subscriber")
client.on_connect = lambda c, u, flags, rc, props: c.subscribe([("demo/+/#", 0)])   # in on_connect: a reconnection subscribes again
client.on_message = on_message
client.connect(HOST, PORT)
client.loop_forever()                                        # listen until the Control room stops the service
