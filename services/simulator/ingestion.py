"""MQTT subscriber forwards scenario/step to API for validated aligned-score ingestion."""
import json
import os
import httpx
from paho.mqtt import client as mqtt


def on_message(client, userdata, message):
    try:
        payload = json.loads(message.payload)
        with httpx.Client(timeout=8) as api:
            response = api.post(os.getenv('API_URL', 'http://localhost:8000') + '/ingest/replay', json={'scenario_id': payload['scenario_id'], 'step': payload['step']})
            response.raise_for_status()
    except (ValueError, KeyError, httpx.HTTPError) as exc:
        print(json.dumps({'error': 'Replay ingestion failed', 'type': type(exc).__name__}), flush=True)


def main():
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_message = on_message
    client.on_connect = lambda c, u, f, reason, properties: c.subscribe('site/+/asset/+/telemetry', qos=1)
    client.connect(os.getenv('MQTT_HOST', 'localhost'), int(os.getenv('MQTT_PORT', '1883')))
    client.loop_forever()


if __name__ == '__main__': main()

