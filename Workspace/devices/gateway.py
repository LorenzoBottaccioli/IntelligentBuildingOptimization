"""
gateway.py -- the devices of the demo building: a finished gateway, to read next to the Lab's empty one.

There is no physical building: EnergyPlus, packed as an FMU, computes what its sensors would measure. This script plays the
role of ALL the field devices: it reads the FMU and publishes the readings on the MQTT broker, and it takes the commands
from the broker and passes them to the FMU:

    EnergyPlus (FMU)  --values-->  gateway.py  --MQTT publish-->   broker  --> subscriber (database), HMIs, controller
    EnergyPlus (FMU)  <--inputs--  gateway.py  <--MQTT subscribe--  broker  <-- controller, operator

It is not run by hand: BMS > Control room > Start on the building runs it once. The variables it reads (SBEP_RUN baseline or
controlled, SBEP_MODE fast, scaled or sync, SBEP_STEP_SECONDS) are explained in the Lab's gateway. Exit code 0 when finished.

The MQTT contract (every payload is JSON; "ts" is the SIMULATED time of the step, not the clock of the computer):

    demo/<run>/<point>               {"value", "unit", "ts"}  a reading. <run> is baseline or controlled
        temperature_<west|south|east|north>                   zone air temperature, degC
        outdoor_temperature, outdoor_humidity, wind_speed, solar_direct    the weather EnergyPlus uses
        electricity_kw, heating_kw                            mean power of the last step
        electricity_kwh, heating_kwh                          energy since the start of the run
    demo/<run>/clock                 {"value": ts, "ts": ts}  the last message of every step: the "tick"
    demo/site/<point>, demo/site/clock, demo/site/run         the weather, the clock and the run in progress, for the HMIs
    demo/controlled/cmd/<zone>       {"value": degC}          a command from the controller or the operator
    demo/controlled/setpoint/<zone>  {"value", "unit", "ts"}  what the building really has after the command
    demo/controlled/ack              {"ts": <tick's ts>}      sync mode: the controller has finished this step
"""
import json
import math
import os
import queue
import sys
import time

import paho.mqtt.client as mqtt
from building import Building, BuildingStopped

RUN = os.getenv("SBEP_RUN", "baseline")
MODE = os.getenv("SBEP_MODE", "fast")
STEP_SECONDS = float(os.getenv("SBEP_STEP_SECONDS", "1.0"))
HOST = os.getenv("MQTT_BROKER_URL", "mosquitto")
PORT = int(os.getenv("MQTT_BROKER_PORT", "1883"))


# ===========================================================================
# 1. The devices
# ===========================================================================
# Each device is a row: its name in this installation -> the FMU variable it reads or drives, and its parameters.
# The exact FMU names are the ones the Control room lists for the model (b.outputs and b.inputs).
ZONES = ("west", "south", "east", "north")
HEARTBEAT = 6                       # steps (one hour at 10 min): an unchanged sensor is published again
ACK_TIMEOUT = 5.0                   # s, sync mode: how long to wait for the controller
DEFAULT = 12.0                      # degC, the setpoint the building has until somebody commands

# sensor -> (FMU output, unit, deadband): the deadband is in the unit of the sensor
SENSORS = {f"temperature_{z}": (f"Zone_Air_Temperature_ZONE{z.upper()}", "degC", 0.1) for z in ZONES}
SENSORS.update({
    "outdoor_temperature": ("Site_Outdoor_Air_Drybulb_Temperature_Environment", "degC", 0.1),
    "outdoor_humidity": ("Site_Outdoor_Air_Relative_Humidity_Environment", "%", 1.0),
    "wind_speed": ("Site_Wind_Speed_Environment", "m/s", 0.2),
    "solar_direct": ("Site_Direct_Solar_Radiation_Rate_per_Area_Environment", "W/m2", 5.0),
})
SITE = ("outdoor_temperature", "outdoor_humidity", "wind_speed", "solar_direct")        # also published under demo/site
METERS = {"electricity": "Electricity_Facility", "heating": "DistrictHeating_Facility"}   # FMU meters: J per step
ACTUATORS = {z: (f"ZONE{z.upper()}_Heating_Setpoint_FMU", 10.0, 30.0) for z in ZONES}     # zone -> (FMU input, min, max)


# ===========================================================================
# 2. Topics and payloads
# ===========================================================================
def message(run, *levels, **fields):
    'One message: the topic demo/<run>/<levels...> and a JSON object, e.g. {"value": 20.4, "unit": "degC", "ts": "..."}.'
    return "/".join(("demo", run, *levels)), json.dumps(fields)


def read_command(topic, raw):
    """A message on  demo/controlled/cmd/<zone>  with payload  {"value": degC}  ->  (zone, setpoint inside the range).
    Do not trust a command: a malformed message, a value that is not a finite number or a zone that does not exist raises
    (ValueError, KeyError or TypeError) and is ignored by the caller; a number outside the range is clamped."""
    zone, value = topic.rsplit("/", 1)[-1], json.loads(raw)["value"]
    if zone not in ACTUATORS or isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("not a setpoint")
    _, low, high = ACTUATORS[zone]
    return zone, min(max(float(value), low), high)


# ===========================================================================
# 3. The gateway
# ===========================================================================
class Gateway:
    def __init__(self):
        self.commands = {}                          # zone -> setpoint asked and not yet applied
        self.acks = queue.Queue()                   # the ts of every ack received (sync mode)
        self.last = {}                              # point -> (value, step) last published: for deadband and heartbeat
        self.energy = {k: 0.0 for k in METERS}      # kWh since the start of the run
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"gateway-{RUN}")
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message

    # ---- what arrives ---------------------------------------------------------------
    def on_connect(self, client, userdata, flags, rc, props=None):
        # subscribe here, not after connect(): a reconnection then subscribes again. Only the controlled run has actuators.
        if RUN == "controlled":
            client.subscribe([(f"demo/{RUN}/cmd/+", 0), (f"demo/{RUN}/ack", 0)])        # + : any zone

    def on_message(self, client, userdata, msg):
        "Runs in the MQTT thread, so it only STORES: the main loop applies the commands to the building before the next step."
        try:
            if msg.topic.endswith("/ack"):
                self.acks.put(str(json.loads(msg.payload)["ts"]))
            else:
                zone, value = read_command(msg.topic, msg.payload)
                self.commands[zone] = value                                              # a dict write is atomic
        except (ValueError, KeyError, TypeError):                                        # a bad message must not stop the gateway
            print("ignored:", msg.topic, msg.payload[:80], flush=True)

    # ---- what is sent ---------------------------------------------------------------
    def put(self, *levels, run=RUN, **fields):
        "Every message is retained: the broker keeps the last one of each topic, so an HMI opened later sees it at once."
        topic, payload = message(run, *levels, **fields)
        self.client.publish(topic, payload, retain=True)

    def publish(self, point, value, unit, ts, step, deadband=0.0):
        "A reading, unless it is the same as the last one (within the deadband) and it is not yet time for the heartbeat."
        last = self.last.get(point)
        if last and abs(value - last[0]) <= deadband and step - last[1] < HEARTBEAT:
            return                                   # publishing everything every step would flood the broker
        self.last[point] = (value, step)             # the heartbeat tells a silent sensor from a dead one
        for run in (RUN, "site") if point in SITE else (RUN,):
            self.put(point, run=run, value=round(value, 3), unit=unit, ts=ts)

    def publish_step(self, r, step_seconds):
        "Everything the building measured in this step; the clock goes last, so a listener knows the step is complete."
        ts, values, step = r["ts"], r["values"], r["step"]
        for point, (fmu, unit, deadband) in SENSORS.items():
            self.publish(point, values[fmu], unit, ts, step, deadband)
        for name, fmu in METERS.items():
            joules = values[fmu]
            self.energy[name] += joules / 3.6e6                                                # J -> kWh
            self.publish(f"{name}_kw", joules / step_seconds / 1000.0, "kW", ts, step, 0.05)   # J per step -> mean kW
            self.publish(f"{name}_kwh", self.energy[name], "kWh", ts, step, 0.5)
        for run in (RUN, "site"):
            self.put("clock", run=run, value=ts, ts=ts)

    def clear_retained(self):
        "A new run starts from nothing: what the last run left retained would look alive in an HMI."
        mine = [*SENSORS, *(f"{m}_{u}" for m in METERS for u in ("kw", "kwh")), "clock", *(f"setpoint/{z}" for z in ZONES)]
        for run, points in ((RUN, mine), ("site", (*SITE, "clock"))):
            for point in points:
                self.client.publish(f"demo/{run}/{point}", b"", retain=True)        # an empty retained message deletes it
        self.put("run", run="site", value=RUN)

    # ---- the building ---------------------------------------------------------------
    def apply_commands(self, b):
        "The commands received since the last step reach the building; what it really has is published."
        asked = {zone: self.commands.pop(zone) for zone in list(self.commands)}      # pop: a command that arrives now waits
        if asked:
            b.set_many({ACTUATORS[z][0]: v for z, v in asked.items()})              # applied by the next b.step()
            for zone, value in asked.items():
                self.put("setpoint", zone, value=value, unit="degC", ts=b.timestamp)

    def wait_for_ack(self, ts):
        "Sync mode: block until the controller answers THIS tick, at most ACK_TIMEOUT s (a dead controller must not freeze us)."
        end = time.time() + ACK_TIMEOUT
        try:
            while self.acks.get(timeout=max(end - time.time(), 0)) != ts:               # an older tick's ack is just skipped
                pass
        except queue.Empty:
            print(f"no ack for {ts}", flush=True)

    def run(self):
        self.client.connect(HOST, PORT)
        self.client.loop_start()                                  # the MQTT network loop, in a background thread
        self.clear_retained()
        try:
            with Building(RUN) as b:
                controlled = bool(b.inputs)                       # the baseline FMU has no actuator inputs
                b.start({fmu: DEFAULT for fmu, _, _ in ACTUATORS.values()} if controlled else None)
                if controlled:
                    # start(initial) alone does not hold the setpoints (the zone drifts to 6 degC with no heating): the
                    # first apply_commands below sets them, and publishes them, as if somebody had commanded the default
                    for zone in ACTUATORS:
                        self.commands.setdefault(zone, DEFAULT)
                while not b.done:                                 # the length of the run is the period of the Control room
                    if controlled:
                        self.apply_commands(b)                    # 1. commands received since the last step
                    r = b.step()                                  # 2. EnergyPlus advances one step
                    self.publish_step(r, b.step_size)             # 3. the sensors
                    if MODE == "scaled":                          # 4. the pace
                        time.sleep(STEP_SECONDS)
                    elif MODE == "sync" and controlled:
                        self.wait_for_ack(r["ts"])
                print(f"done: {b.steps_total} steps", flush=True)
        except BuildingStopped:
            print("EnergyPlus stopped", flush=True)
            sys.exit(1)
        finally:
            time.sleep(0.5)                                       # let the last messages leave
            self.client.loop_stop()
            self.client.disconnect()


if __name__ == "__main__":
    Gateway().run()
