#!/usr/bin/env python3
"""
gateway.py -- your device gateway (STUDENT FILE).

The idea
--------
Imagine you were given a real building in which you installed sensors and
actuators (you chose them in "Building & devices > Sensors & actuators"). Real
IoT devices would publish their readings on an MQTT broker and receive commands
from it. There is no physical building here: EnergyPlus, packed as an FMU,
computes what those sensors would measure. This script plays the role of ALL
your field devices:

    EnergyPlus (FMU)  --values-->  gateway.py  --MQTT publish-->   broker  --> your subscriber, HMI, controller
    EnergyPlus (FMU)  <--inputs--  gateway.py  <--MQTT subscribe--  broker  <-- your controller, operator

Everything about how the devices talk is your design: topic names, payload
format, how often a sensor publishes, how a command is accepted or refused.

How it is run
-------------
You do not run it by hand. In "BMS > Control room" you press Start on the
building: the platform runs this file once (working directory Workspace/devices)
with three environment variables:

    SBEP_RUN           "baseline"   native EnergyPlus control; the baseline FMU has NO
                                    actuator inputs: you can only publish sensors.
                       "controlled" the FMU has the actuator inputs you chose: commands
                                    you receive can change the building.
    SBEP_MODE          "fast"       step as fast as EnergyPlus can.
                       "scaled"     wait SBEP_STEP_SECONDS of real time between steps.
                       "sync"       wait for your controller at every step (a handshake
                                    you design, e.g. publish a "tick", wait for an "ack").
    SBEP_STEP_SECONDS  seconds of real time per step in "scaled" mode.

The script must end with exit code 0 when the simulation is finished and a
non-zero code if something went wrong. Everything you print() appears in the
log of the Control room: print what helps you debug.

Rules
-----
* Topics starting with "platform/" are reserved for the platform: do not use them.
* Broker: host from the environment variable MQTT_BROKER_URL (default "mosquitto"),
  port MQTT_BROKER_PORT (default 1883).
* Both runs should publish the same sensors on comparable topics, and the data of
  the two runs must be distinguishable (put the run in the topic or in the payload).

The platform library: building.py
---------------------------------
`from building import Building, BuildingStopped` gives you the building. Its API:

    b = Building(run)              run = "baseline" or "controlled"
    b.outputs                      list of FMU output names  (your sensors)
    b.inputs                       list of FMU input names   (your actuators; empty in baseline)
    b.step_size, b.steps_total     seconds per step, number of steps of the run
    b.start(initial)               start EnergyPlus; initial = {input name: value} or None
    b.read()                       values at the current time (before the first step)
    b.step()                       advance one step; returns
                                   {"step": n, "time": seconds, "ts": "2026-01-01T00:10:00",
                                    "values": {output name: value}}
    b.set(name, value)             set an input; applied at the next step()
    b.set_many({name: value})      same, for several inputs
    b.done                         True when the last step has been made
    b.close()                      stop EnergyPlus (or use "with Building(run) as b:")

    BuildingStopped                raised by step() if EnergyPlus died: stop and exit non-zero.

Use "ts" (the SIMULATED time) as the timestamp of your measurements, not the clock
of the computer: a week of simulation can run in one minute.

MQTT with paho-mqtt (already installed)
---------------------------------------
    import paho.mqtt.client as mqtt
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="...")
    client.on_connect = ...        called when connected: subscribe there
    client.on_message = ...        called for every message received: (client, userdata, msg)
                                   msg.topic is a str, msg.payload is bytes
    client.connect(host, port)
    client.loop_start()            network loop in a background thread
    client.subscribe(topic, qos)
    client.publish(topic, payload, qos=0, retain=False)
Documentation: https://eclipse.dev/paho/files/paho.mqtt.python/html/client.html
Careful: on_message runs in another thread. Do not call b.set() from there
directly: store the command, and apply it in your main loop before b.step().
"""
import os
import sys

from building import Building

RUN = os.getenv("SBEP_RUN", "baseline")
MODE = os.getenv("SBEP_MODE", "fast")
STEP_SECONDS = float(os.getenv("SBEP_STEP_SECONDS", "1.0"))
MQTT_BROKER_URL = os.getenv("MQTT_BROKER_URL", "mosquitto")
MQTT_BROKER_PORT = int(os.getenv("MQTT_BROKER_PORT", "1883"))


# ===========================================================================
# 1. Your devices
# ===========================================================================
# Describe your sensors and actuators: which FMU variable each one reads or
# drives, its name in your installation, its unit, and the parameters it needs
# (for a sensor: when it publishes; for an actuator: the range it accepts and
# the value it holds until somebody commands it).
# Start by running the building once: show_building() below prints the exact
# names of the FMU outputs and inputs.
#
# TODO


# ===========================================================================
# 2. Topics and payloads
# ===========================================================================
# Design the MQTT side of each device:
#   - the topic a sensor publishes on, and the one an actuator listens on;
#   - the payload: which fields (value, unit, timestamp, run, quality, ...)
#     and in which format (JSON is the usual choice);
#   - when a sensor publishes: every step, only when the value changed by more
#     than a threshold (deadband), plus a periodic "I am alive" message
#     (heartbeat) so that a silent sensor can be told apart from a dead one;
#   - how a command is read and checked: a value outside the range or a
#     malformed message must not reach the building.
#
# TODO


# ===========================================================================
# 3. The gateway
# ===========================================================================
# The loop of a field gateway, in order:
#   a. connect to the broker; in the controlled run, subscribe to the command
#      topics of your actuators;
#   b. open the building for RUN and start it (actuators at their default values);
#   c. until the building is done:
#        - apply the commands received since the last step,
#        - advance one step,
#        - publish the sensors that must be published,
#        - wait according to MODE ("scaled": STEP_SECONDS; "sync": your handshake);
#   d. close the building and the MQTT connection, exit with code 0;
#      if EnergyPlus stops (BuildingStopped) exit with a non-zero code.
#
# TODO


# ===========================================================================
# Given: list what your building exposes
# ===========================================================================
def show_building():
    """Print the FMU outputs (sensors) and inputs (actuators) of this run."""
    with Building(RUN, publish_status=False) as b:
        print(f"Run {RUN}: {b.steps_total} steps of {b.step_size:g} s", flush=True)
        print("FMU outputs (sensors):  ", b.outputs, flush=True)
        print("FMU inputs (actuators): ", b.inputs, flush=True)


def main():
    show_building()
    # TODO: replace these two lines with your gateway (section 3).
    print("TODO: the gateway is not written yet (devices/gateway.py).", flush=True)
    sys.exit(2)


if __name__ == "__main__":
    main()
