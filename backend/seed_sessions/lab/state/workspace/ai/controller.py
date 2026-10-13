#!/usr/bin/env python3
"""
controller.py -- your building controller (STUDENT FILE, optional).

The idea
--------
In the baseline run the building is controlled by EnergyPlus itself (its own
thermostats and schedules). In the controlled run the actuators you installed
obey the commands that arrive on their MQTT command topics. This script is the
controller: it listens to the sensors, decides, and sends commands.

    devices --MQTT--> broker --MQTT--> controller.py
                         ^                  |
                         +-------MQTT-------+   commands on the command topics of your actuators

The decision can be anything, from a rule ("if the kitchen is below 20 degC,
set the heating setpoint to 21") to a reinforcement-learning agent trained in
"AI > Agent training". What counts is that it does better than the baseline:
less energy for the same comfort, or more comfort for the same energy. Compare
the two runs with your data.

How it is run
-------------
It is a service: in "BMS > Control room" you press Start on ai/controller.py and
it keeps running until you press Stop. Start it before the controlled run of
the building. If it crashes the platform restarts it; if you save the file
while it runs, it restarts with the new code. Everything you print() appears in
its log in the Control room.

Things to decide
----------------
* What you listen to: the topics of your devices, or the clean topics your
  subscriber republishes.
* When you decide: at every new value, at a fixed interval of SIMULATED time
  (the timestamps in the payloads), or at every step of the building if you use
  the synchronous mode.
* Synchronous mode ("sync" in the Control room): your gateway waits for the
  controller at every step, with the handshake you designed in gateway.py
  (e.g. it publishes a "tick" and waits for an "ack"). The controller must take
  part in it: decide, publish the commands, then answer.
* What you send: the command topic and payload format that your gateway.py
  accepts, within the range of each actuator.
* What happens when information is missing: no value yet, a sensor that went
  silent, a message you cannot read.

Using a trained agent
---------------------
"AI > Agent training" saves the model in ai/models/ (next to this file):
    from stable_baselines3 import PPO
    model = PPO.load(os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", "<name>.zip"))
    action, _ = model.predict(observation, deterministic=True)
The observation must have the same variables, in the same order and units, as
in training; the action must be mapped back to your actuators and their range.

MQTT with paho-mqtt (already installed)
---------------------------------------
    import paho.mqtt.client as mqtt
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="...")
    client.on_connect = ...        subscribe here
    client.on_message = ...        (client, userdata, msg): msg.topic str, msg.payload bytes
    client.connect(host, port)     host MQTT_BROKER_URL ("mosquitto"), port MQTT_BROKER_PORT (1883)
    client.loop_forever()          keeps listening (blocks)
    client.publish(topic, payload, qos=0, retain=False)
Documentation: https://eclipse.dev/paho/files/paho.mqtt.python/html/client.html

Topics starting with "platform/" are reserved for the platform: do not publish there.
"""
import os
import sys

MQTT_BROKER_URL = os.getenv("MQTT_BROKER_URL", "mosquitto")
MQTT_BROKER_PORT = int(os.getenv("MQTT_BROKER_PORT", "1883"))


# ===========================================================================
# 1. Inputs
# ===========================================================================
# The topics you listen to, and how you keep the latest known value of each
# quantity you need (with its simulated time).
#
# TODO


# ===========================================================================
# 2. The control law
# ===========================================================================
# From the latest values to the commands: {actuator: value}. Start simple (a
# rule), measure, then improve. Keep the commands inside the range of each
# actuator.
#
# TODO


# ===========================================================================
# 3. Outputs
# ===========================================================================
# Publish the commands on the command topics of your actuators, in the format
# your gateway.py accepts; in synchronous mode, answer the handshake after the
# commands.
#
# TODO


# ===========================================================================
# 4. The service
# ===========================================================================
# Connect, subscribe, decide when a new value (or a tick) arrives, publish, and
# keep running until the Control room stops you. A message you cannot read must
# not stop the service.
#
# TODO


def main():
    # TODO: replace these two lines with your controller (section 4).
    print("TODO: the controller is not written yet (ai/controller.py).", flush=True)
    sys.exit(0)


if __name__ == "__main__":
    main()
