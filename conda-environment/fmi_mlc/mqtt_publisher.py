# mqtt_publisher.py
import paho.mqtt.client as mqtt
import json
from typing import Dict, Union

class MQTTPublisher:
    def __init__(self, host: str = "mosquitto", port: int = 1883, client_id: str = None):
        self.client = mqtt.Client(client_id=client_id)
        self.client.connect(host, port)
        # Inicia el loop en segundo plano
        self.client.loop_start()

    def publish_observations_rl(self, data: Dict[str, float], timestamp: float):
        """
        Publica cada observación bajo topic "simulation/observations/<key>".
        Envia payload como JSON: {"value": <float>, "timestamp": <float>}.
        """
        for key, value in data.items():
            topic = f"simulationRL/observations/{key}"
            payload = json.dumps({
                "value": float(value),
                "timestamp": float(timestamp)
            })
            # QOS=1 para entrega al menos una vez, retain=True para retener el último valor
            self.client.publish(topic, payload=payload, qos=1, retain=True)

    def publish_actions_rl(self, data: Dict[str, float], timestamp: float):
        """
        Publica cada acción bajo topic "simulation/actions/<key>".
        Mismo esquema JSON que en observations.
        """
        for key, value in data.items():
            topic = f"simulationRL/actions/{key}"
            payload = json.dumps({
                "value": float(value),
                "timestamp": float(timestamp)
            })
            self.client.publish(topic, payload=payload, qos=1, retain=True)

    def publish_rewards_rl(self, data: Dict[str, float], timestamp: float):
        for key, value in data.items():
            topic = f"simulationRL/rewards/{key}"
            payload = json.dumps({
                "value": float(value),
                "timestamp": float(timestamp)
            })
            self.client.publish(topic, payload=payload, qos=1, retain=True)

    def publish_observations_base(self, data: Dict[str, float], timestamp: float):
        for key, value in data.items():
            topic = f"simulationBase/observations/{key}"
            payload = json.dumps({
                "value": float(value),
                "timestamp": float(timestamp)
            })
            # QOS=1 para entrega al menos una vez, retain=True para retener el último valor
            self.client.publish(topic, payload=payload, qos=1, retain=True)

    def publish_actions_base(self, data: Dict[str, float], timestamp: float):
        for key, value in data.items():
            topic = f"simulationBase/actions/{key}"
            payload = json.dumps({
                "value": float(value),
                "timestamp": float(timestamp)
            })
            self.client.publish(topic, payload=payload, qos=1, retain=True)

    def publish_rewards_base(self, data: Dict[str, float], timestamp: float):
        for key, value in data.items():
            topic = f"simulationBase/rewards/{key}"
            payload = json.dumps({
                "value": float(value),
                "timestamp": float(timestamp)
            })
            self.client.publish(topic, payload=payload, qos=1, retain=True)

    def close(self):
        self.client.loop_stop()
        self.client.disconnect()
