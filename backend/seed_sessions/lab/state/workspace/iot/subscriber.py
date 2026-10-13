#!/usr/bin/env python3
"""
subscriber.py -- your subscriber (STUDENT FILE).

The idea
--------
Your devices (devices/gateway.py) publish the readings of the building on the
MQTT broker. A broker does not keep history: a message that nobody receives is
lost. This script is the piece of a BMS that listens to the devices and keeps
what they say, so that it can be plotted, queried and analysed later:

    devices --MQTT--> broker --MQTT--> subscriber.py --> InfluxDB (time series database)
                                            |
                                            +--MQTT--> your own clean topics (HMI, other services)

Real measurements are messy: a value can be missing, out of range, stuck, or
come with a strange unit. Before storing a value you decide whether it is
plausible, how to name it and in which unit to keep it.

How it is run
-------------
It is a service: in "BMS > Control room" you press Start on iot/subscriber.py and
it must keep running (listening) until you press Stop. If it crashes, the
platform restarts it; if you save the file while it runs, it restarts with the
new code. Everything you print() appears in its log in the Control room.
Start it BEFORE the building, otherwise the first values are lost.

Where the data go: InfluxDB 1.x
-------------------------------
* Address: environment variable INFLUX_URL (http://influxdb:8086); user and password
  in INFLUX_USERNAME and INFLUX_PASSWORD (HTTP basic authentication).
* Two databases already exist, one per run, and Grafana has a data source for each:
      base_building        the baseline run
      controlled_building  the controlled run
* Writing: HTTP POST to  {INFLUX_URL}/write?db=<database>&precision=s  (or ms, ns)
  with a body of one or more lines in the "line protocol":
      <measurement>,<tag>=<value>,<tag>=<value> <field>=<value>,<field>=<value> <timestamp>
  e.g.  zone_temperature,zone=kitchen,run=baseline value=20.4 1767225600
  Tags are indexed text (what you filter and group by), fields are the values.
  Guide: https://docs.influxdata.com/influxdb/v1/write_protocols/line_protocol_tutorial/
  HTTP API: https://docs.influxdata.com/influxdb/v1/tools/api/
* `requests` is installed (requests.post(url, params=..., data=..., auth=(user, password))).
  The InfluxDB 1.x Python package `influxdb` is not.
* The timestamp is the SIMULATED time carried by your payload, not the clock of the
  computer. One HTTP request per value is slow: collect lines and write them in batches.
* The schema (measurement names, tags, fields) is your design. Write it down: your
  data notebooks and your Grafana dashboards will query it.

MQTT with paho-mqtt (already installed)
---------------------------------------
    import paho.mqtt.client as mqtt
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="...")
    client.on_connect = ...        subscribe here, so that a reconnection subscribes again
    client.on_message = ...        (client, userdata, msg): msg.topic str, msg.payload bytes
    client.connect(host, port)     host MQTT_BROKER_URL ("mosquitto"), port MQTT_BROKER_PORT (1883)
    client.loop_forever()          keeps listening (blocks)
    client.subscribe(topic, qos)   wildcards: + one level, # everything below
    client.publish(topic, payload, qos=0, retain=False)
Documentation: https://eclipse.dev/paho/files/paho.mqtt.python/html/client.html

Topics starting with "platform/" are reserved for the platform: do not publish there.
"""
import os
import sys

MQTT_BROKER_URL = os.getenv("MQTT_BROKER_URL", "mosquitto")
MQTT_BROKER_PORT = int(os.getenv("MQTT_BROKER_PORT", "1883"))
INFLUX_URL = os.getenv("INFLUX_URL", "http://influxdb:8086")
INFLUX_USERNAME = os.getenv("INFLUX_USERNAME", "")
INFLUX_PASSWORD = os.getenv("INFLUX_PASSWORD", "")


# ===========================================================================
# 1. What you listen to
# ===========================================================================
# Which topics carry the readings of your devices (the ones your gateway.py
# publishes), and how you tell from a message which device, which quantity and
# which run (baseline or controlled) it belongs to.
#
# TODO


# ===========================================================================
# 2. Clean and check
# ===========================================================================
# For every message:
#   - read the payload; a malformed message must not stop the service;
#   - names: map device names to the naming convention of your site;
#   - units: convert if you want to store something else (J -> kWh, W -> kW, ...);
#   - plausibility: physical range of each quantity, values that stop changing
#     for too long (a stuck sensor), jumps that are too fast;
#   - decide what to do with what fails: drop it, store it with a quality flag,
#     raise an alarm on a topic of yours.
#
# TODO


# ===========================================================================
# 3. Store
# ===========================================================================
# Your schema in InfluxDB: measurement(s), tags, fields, timestamp; the database
# of the right run; writing in batches (e.g. every N lines or every few
# seconds) and what happens if InfluxDB does not answer (do not lose the batch).
#
# TODO


# ===========================================================================
# 4. Republish
# ===========================================================================
# The clean values on topics of your own (for your HMI in openHAB and for other
# services): structure of the topics and of the payload.
#
# TODO


# ===========================================================================
# 5. The service
# ===========================================================================
# Connect to the broker, subscribe (in on_connect), handle every message with
# the steps above, and keep running until the Control room stops you.
#
# TODO


def main():
    # TODO: replace these two lines with your subscriber (section 5).
    print("TODO: the subscriber is not written yet (iot/subscriber.py).", flush=True)
    sys.exit(0)


if __name__ == "__main__":
    main()
