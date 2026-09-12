"""R7: MQTT replay of bundled scenarios. No real measurements are synthesized silently."""
import argparse
import json
from pathlib import Path
import time
from paho.mqtt import client as mqtt


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--broker', default='localhost')
    parser.add_argument('--port', type=int, default=1883)
    parser.add_argument('--scenario', default='sim-gearbox-drift')
    parser.add_argument('--speed', type=float, default=1200, help='Historical seconds per wall second')
    parser.add_argument('--start-step', type=int, default=170)
    args = parser.parse_args()
    if args.speed <= 0: parser.error('Speed must be positive')
    root = Path(__file__).resolve().parents[2]
    scenarios = json.loads((root / 'artifacts/demo_bundle/scenarios.json').read_text())
    scenario = next((s for s in scenarios if s['id'] == args.scenario), None)
    if scenario is None: parser.error('Unknown scenario')
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.connect(args.broker, args.port); client.loop_start()
    try:
        for point in scenario['data'][args.start_step:]:
            payload = {'scenario_id': scenario['id'], 'asset_id': scenario['asset_id'], 'step': point['step'], 'provenance': scenario['provenance'], 'point': point}
            result = client.publish(f"site/kutch-demo/asset/{scenario['asset_id']}/telemetry", json.dumps(payload), qos=1)
            result.wait_for_publish(timeout=5)
            if point['step'] % 24 == 0: print(json.dumps({'published_step': point['step'], 'provenance': scenario['provenance']}), flush=True)
            time.sleep(600 / args.speed)
    finally: client.loop_stop(); client.disconnect()


if __name__ == '__main__': main()

