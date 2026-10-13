"""Demo controller: a time program with the weather in it.

Every zone follows its own program (simulated time of the day):
    07:00-19:00 comfort setpoint 20 degC, otherwise setback 15 degC;
    and when the outdoor air is above 16 degC the building needs no heating: the setpoint goes to the minimum, 10 degC.
It decides once per tick of the gateway (the  demo/controlled/clock  message that closes every step), with the latest
reading of every point, publishes one command per zone on  demo/controlled/cmd/<zone>  and then answers the tick on
demo/controlled/ack  (the gateway waits for it in "sync" mode).
"""
import json
import os
from datetime import datetime

import paho.mqtt.client as mqtt

HOST = os.getenv("MQTT_BROKER_URL", "mosquitto")
PORT = int(os.getenv("MQTT_BROKER_PORT", "1883"))

ZONES = ("west", "south", "east", "north")
COMFORT, SETBACK, OFF = 20, 15, 10          # degC
DAY_FROM, DAY_TO = 7, 19                    # hours
NO_HEATING_ABOVE = 16                       # degC, outdoor

latest = {}                                 # point -> latest value


def setpoint(hour, outdoor):
    if outdoor is not None and outdoor > NO_HEATING_ABOVE:
        return OFF
    return COMFORT if DAY_FROM <= hour < DAY_TO else SETBACK


def on_message(client, userdata, msg):
    try:
        data = json.loads(msg.payload)
        point = msg.topic.rsplit("/", 1)[-1]
        if point != "clock":
            latest[point] = float(data["value"])
            return
        hour = datetime.fromisoformat(data["ts"]).hour
    except (KeyError, ValueError, TypeError):
        return                               # a message we cannot read must not stop the service
    value = setpoint(hour, latest.get("outdoor_temperature"))
    for zone in ZONES:
        client.publish(f"demo/controlled/cmd/{zone}", json.dumps({"value": value, "ts": data["ts"]}))
    client.publish("demo/controlled/ack", json.dumps({"ts": data["ts"]}))


client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="controller")
client.on_connect = lambda c, u, flags, rc, props: c.subscribe("demo/controlled/+")
client.on_message = on_message
client.connect(HOST, PORT)
client.loop_forever()
