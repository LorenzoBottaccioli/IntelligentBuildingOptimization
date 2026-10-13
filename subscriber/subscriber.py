#!/usr/bin/env python3
"""
MQTT -> InfluxDB v1 bridge for the simulation streams, with async batching.

One process serves every stream: the topic prefix decides which database a point
lands in, so the controlled run and the baseline run stay separate without
needing a second container.
"""
import os
import time
import json
import logging
import threading

import paho.mqtt.client as mqtt
from influxdb import InfluxDBClient
from dotenv import load_dotenv

load_dotenv()

# MQTT
MQTT_BROKER_URL = os.getenv('MQTT_BROKER_URL', 'mosquitto')
MQTT_BROKER_PORT = int(os.getenv('MQTT_BROKER_PORT', '1883'))
MQTT_USERNAME = os.getenv('MQTT_USERNAME') or None
MQTT_PASSWORD = os.getenv('MQTT_PASSWORD') or None
MQTT_CLIENT_ID = os.getenv('MQTT_CLIENT_ID', 'subscriber_bridge')

# InfluxDB v1
INFLUX_HOST = os.getenv('INFLUX_HOST', 'influxdb')
INFLUX_PORT = int(os.getenv('INFLUX_PORT', '8086'))
INFLUX_USER = os.getenv('INFLUX_USERNAME', 'admin')
INFLUX_PASS = os.getenv('INFLUX_PASSWORD', 'admin123')

# "<topic prefix>=<database>" pairs. The prefix is the first topic segment.
DEFAULT_ROUTES = 'simulationRL=controlled_building,simulationBase=base_building'


def parse_routes(raw):
    routes = {}
    for entry in raw.split(','):
        entry = entry.strip()
        if not entry:
            continue
        prefix, _, database = entry.partition('=')
        if prefix and database:
            routes[prefix.strip()] = database.strip()
    return routes


ROUTES = parse_routes(os.getenv('MQTT_ROUTES', DEFAULT_ROUTES))

BATCH_SIZE = int(os.getenv('BATCH_SIZE', '500'))
BATCH_INTERVAL = float(os.getenv('BATCH_INTERVAL', '2.0'))

MEASUREMENTS = {
    'observations': 'simulation_observations',
    'actions': 'simulation_actions',
    'rewards': 'simulation_rewards',
}

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger('mqtt_influx')

if not ROUTES:
    logger.error('No MQTT_ROUTES configured.')
    raise SystemExit(1)

try:
    influx_client = InfluxDBClient(
        host=INFLUX_HOST,
        port=INFLUX_PORT,
        username=INFLUX_USER,
        password=INFLUX_PASS,
    )
    for database in set(ROUTES.values()):
        influx_client.create_database(database)
    logger.info(
        "Connected to InfluxDB v1 at %s:%s; routes: %s",
        INFLUX_HOST, INFLUX_PORT,
        ', '.join(f'{p}/# -> {d}' for p, d in ROUTES.items()),
    )
except Exception as e:
    logger.error(f"Could not connect to InfluxDB: {e}")
    raise SystemExit(1)

# One buffer per target database.
buffers = {database: [] for database in set(ROUTES.values())}
buffer_lock = threading.Lock()
msg_counter = 0


def flush_once():
    with buffer_lock:
        pending = {db: points[:] for db, points in buffers.items() if points}
        for db in pending:
            buffers[db].clear()

    for database, batch in pending.items():
        try:
            influx_client.write_points(batch, database=database, time_precision='n')
            logger.info("Flushed %d points to %s", len(batch), database)
        except Exception as e:
            logger.error("Failed to flush to %s: %s", database, e)
            with buffer_lock:
                buffers[database][0:0] = batch


def flush_worker():
    while True:
        time.sleep(BATCH_INTERVAL)
        flush_once()


threading.Thread(target=flush_worker, daemon=True).start()


def enqueue_point(database, point):
    global msg_counter
    with buffer_lock:
        buffers[database].append(point)
        msg_counter += 1
        count = msg_counter
        buf_len = len(buffers[database])

    if count % 1000 == 0:
        logger.info("Enqueued %d points so far; %s buffer at %d", count, database, buf_len)
    if buf_len >= BATCH_SIZE:
        threading.Thread(target=flush_once, daemon=True).start()


def publish_to_influx(topic, payload):
    parts = topic.split('/')
    if len(parts) < 3:
        return

    database = ROUTES.get(parts[0])
    measurement = MEASUREMENTS.get(parts[1])
    if not database or not measurement:
        return

    name = parts[2]
    if isinstance(payload, dict):
        val, ts_val = payload.get('value'), payload.get('timestamp')
    else:
        val, ts_val = payload, None

    try:
        val = float(val)
    except (TypeError, ValueError):
        return

    try:
        timestamp = int(float(ts_val) * 1e9)
    except (TypeError, ValueError):
        timestamp = int(time.time() * 1e9)

    enqueue_point(database, {
        'measurement': measurement,
        'tags': {'name': name},
        'fields': {'value': val},
        'time': timestamp,
    })


def on_connect(client, userdata, flags, rc):
    if rc != 0:
        logger.error(f"MQTT connection failed, rc={rc}")
        return
    logger.info("Connected to MQTT broker")
    for prefix in ROUTES:
        topic = f'{prefix}/#'
        client.subscribe(topic, qos=1)
        logger.info("Subscribed to %s", topic)


def on_disconnect(client, userdata, rc):
    logger.warning(f"MQTT disconnected (rc={rc}), reconnecting...")


def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode('utf-8'))
    except Exception:
        return
    publish_to_influx(msg.topic, payload)


def main():
    client = mqtt.Client(client_id=MQTT_CLIENT_ID, clean_session=False)
    if MQTT_USERNAME and MQTT_PASSWORD:
        client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message
    client.reconnect_delay_set(min_delay=1, max_delay=30)

    while True:
        try:
            client.connect(MQTT_BROKER_URL, MQTT_BROKER_PORT, keepalive=60)
            break
        except Exception:
            time.sleep(5)
    client.loop_forever(retry_first_connection=True)


if __name__ == '__main__':
    main()
