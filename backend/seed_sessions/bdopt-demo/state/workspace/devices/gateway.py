"""Demo gateway: the devices of the building, on MQTT.

Sensors (every one publishes on  demo/<run>/<point>  a retained {"value", "unit", "ts"}; "ts" is the SIMULATED time):

    temperature_<west|south|east|north>   zone air temperature, degC
    outdoor_temperature, outdoor_humidity, wind_speed, solar_direct     the weather EnergyPlus uses
    electricity_kw, heating_kw            mean power of the last step     (the FMU meters are joules per step)
    electricity_kwh, heating_kwh          energy since the start of the run
    clock                                 the simulated instant, the last message of every step (a "tick")

The weather, the clock and the name of the run in progress are also published under  demo/site/<point>  (run, clock,
outdoor_temperature, outdoor_humidity, wind_speed, solar_direct), for the HMIs: they show the site, whichever run is live.

A sensor is published when it moved more than its deadband, and at least every HEARTBEAT steps, so that a silent
sensor can be told from a dead one.

Actuators (controlled run only): the heating setpoint of each zone.
    demo/controlled/cmd/<zone>        {"value": degC}   what somebody asks (controller, operator): checked, clamped to the range
    demo/controlled/setpoint/<zone>   {"value", "unit", "ts"}  retained: what the building really has
In "sync" mode the gateway waits after every tick for  demo/controlled/ack  {"ts": <the tick's ts>}  (5 s at most).
"""
import json
import math
import os
import sys
import threading
import time

import paho.mqtt.client as mqtt
from building import Building, BuildingStopped

RUN = os.getenv("SBEP_RUN", "baseline")
MODE = os.getenv("SBEP_MODE", "fast")
STEP_SECONDS = float(os.getenv("SBEP_STEP_SECONDS", "1.0"))
HOST = os.getenv("MQTT_BROKER_URL", "mosquitto")
PORT = int(os.getenv("MQTT_BROKER_PORT", "1883"))

ZONES = ("west", "south", "east", "north")
HEARTBEAT = 6                       # steps (one hour at 10 min): an unchanged sensor is published again
ACK_TIMEOUT = 5.0                   # s, sync mode

# point -> (FMU output, unit, deadband)
SENSORS = {f"temperature_{z}": (f"Zone_Air_Temperature_ZONE{z.upper()}", "degC", 0.1) for z in ZONES}
SENSORS.update({
    "outdoor_temperature": ("Site_Outdoor_Air_Drybulb_Temperature_Environment", "degC", 0.1),
    "outdoor_humidity": ("Site_Outdoor_Air_Relative_Humidity_Environment", "%", 1.0),
    "wind_speed": ("Site_Wind_Speed_Environment", "m/s", 0.2),
    "solar_direct": ("Site_Direct_Solar_Radiation_Rate_per_Area_Environment", "W/m2", 5.0),
})
SITE = ("outdoor_temperature", "outdoor_humidity", "wind_speed", "solar_direct")        # also under demo/site
METERS = {"electricity": "Electricity_Facility", "heating": "DistrictHeating_Facility"}   # J per step
ACTUATORS = {z: (f"ZONE{z.upper()}_Heating_Setpoint_FMU", 10.0, 30.0) for z in ZONES}     # FMU input, min, max
DEFAULT = 12.0                      # degC, until somebody commands
DEMO_DAYS = 7                       # the demo covers one week: both runs stop at the same simulated instant (the FMU is a year)


class Gateway:
    def __init__(self):
        self.lock = threading.Lock()
        self.commands = {}                       # zone -> setpoint asked since the last step
        self.acked = ""                          # ts of the last ack received
        self.ack_event = threading.Event()
        self.published = {}                      # point -> (value, step) last published
        self.energy = {k: 0.0 for k in METERS}   # kWh since the start
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"gateway-{RUN}")
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message

    # ---- MQTT side -----------------------------------------------------------------
    def on_connect(self, client, userdata, flags, rc, props=None):
        if RUN == "controlled":
            client.subscribe([(f"demo/{RUN}/cmd/+", 0), (f"demo/{RUN}/ack", 0)])

    def on_message(self, client, userdata, msg):
        try:
            data = json.loads(msg.payload)
            if msg.topic.endswith("/ack"):
                self.acked = str(data["ts"])
                self.ack_event.set()
                return
            zone = msg.topic.rsplit("/", 1)[-1]
            value = data["value"]
            if zone not in ACTUATORS or isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError("not a setpoint")
            _, low, high = ACTUATORS[zone]
            with self.lock:
                self.commands[zone] = min(max(float(value), low), high)
        except (ValueError, KeyError, TypeError):
            print("ignored:", msg.topic, msg.payload[:80], flush=True)

    def publish(self, point, value, unit, ts, step, deadband=0.0, run=RUN):
        last = self.published.get((run, point))
        if last and abs(value - last[0]) <= deadband and step - last[1] < HEARTBEAT:
            return
        self.published[(run, point)] = (value, step)
        self.client.publish(f"demo/{run}/{point}", json.dumps({"value": round(value, 3), "unit": unit, "ts": ts}), retain=True)

    # ---- one step ------------------------------------------------------------------
    def publish_step(self, r, step_seconds):
        ts, values, step = r["ts"], r["values"], r["step"]
        for point, (fmu, unit, deadband) in SENSORS.items():
            self.publish(point, values[fmu], unit, ts, step, deadband)
            if point in SITE:
                self.publish(point, values[fmu], unit, ts, step, deadband, run="site")
        for name, fmu in METERS.items():
            joules = values[fmu]
            self.energy[name] += joules / 3.6e6
            self.publish(f"{name}_kw", joules / step_seconds / 1000.0, "kW", ts, step, 0.05)
            self.publish(f"{name}_kwh", self.energy[name], "kWh", ts, step, 0.5)
        self.client.publish(f"demo/{RUN}/clock", json.dumps({"value": ts, "ts": ts}), retain=True)
        self.client.publish("demo/site/clock", json.dumps({"value": ts, "ts": ts}), retain=True)

    def apply_commands(self, b):
        """The commands received since the last step reach the building; what it really has is published."""
        with self.lock:
            asked, self.commands = self.commands, {}
        if asked:
            b.set_many({ACTUATORS[z][0]: v for z, v in asked.items()})
            for zone, value in asked.items():
                self.publish_setpoint(zone, value, b.timestamp)

    def clear_retained(self):
        """A new run starts from nothing: what the last run left retained would look alive in an HMI."""
        topics = [f"demo/{RUN}/{p}" for p in SENSORS] + [f"demo/{RUN}/{k}_{u}" for k in METERS for u in ("kw", "kwh")]
        topics += [f"demo/{RUN}/clock"] + [f"demo/{RUN}/setpoint/{z}" for z in ZONES]
        topics += [f"demo/site/{p}" for p in SITE] + ["demo/site/clock"]
        for topic in topics:
            self.client.publish(topic, b"", retain=True)
        self.client.publish("demo/site/run", json.dumps({"value": RUN}), retain=True)

    def publish_setpoint(self, zone, value, ts):
        self.client.publish(f"demo/{RUN}/setpoint/{zone}", json.dumps({"value": value, "unit": "degC", "ts": ts}), retain=True)

    def wait_for_ack(self, ts):
        deadline = time.time() + ACK_TIMEOUT
        while self.acked != ts:
            left = deadline - time.time()
            if left <= 0 or not self.ack_event.wait(left):
                print(f"no ack for {ts}", flush=True)
                return
            self.ack_event.clear()

    def run(self):
        self.client.connect(HOST, PORT)
        self.client.loop_start()
        self.clear_retained()
        try:
            with Building(RUN) as b:
                controlled = bool(b.inputs)
                initial = {fmu: DEFAULT for fmu, _, _ in ACTUATORS.values()} if controlled else None
                b.start(initial)
                if controlled:
                    # start(initial) alone does not hold the setpoints (the zone drifts to 6 degC with no heating): set them
                    b.set_many(initial)
                    for zone in ACTUATORS:
                        self.publish_setpoint(zone, DEFAULT, b.timestamp)
                last_step = min(b.steps_total, round(DEMO_DAYS * 86400 / b.step_size))
                while b.step_no < last_step:
                    if controlled:
                        self.apply_commands(b)
                    r = b.step()
                    self.publish_step(r, b.step_size)
                    if MODE == "scaled":
                        time.sleep(STEP_SECONDS)
                    elif MODE == "sync" and controlled:
                        self.wait_for_ack(r["ts"])
                if not b.done:
                    b.report("finished", f"{last_step} steps completed ({DEMO_DAYS} days)")
                print(f"done: {last_step} steps", flush=True)
        except BuildingStopped:
            print("EnergyPlus stopped", flush=True)
            sys.exit(1)
        finally:
            time.sleep(0.5)                      # let the last messages leave
            self.client.loop_stop()
            self.client.disconnect()


if __name__ == "__main__":
    Gateway().run()
