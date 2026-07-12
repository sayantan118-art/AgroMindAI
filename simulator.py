"""
AgroMind AI — Sensor Simulator
Replaces the ESP32 hardware during software-only testing.
Publishes realistic sensor data to HiveMQ Cloud every 30 seconds.

Setup:
    Copy backend/.env and fill in MQTT credentials (already done if you
    followed the secrets setup). The simulator reads the same .env file.

Run:
    cd "C:\\My files\\projectss\\AgroMindAI"
    python simulator.py
"""

import json
import math
import os
import random
import ssl
import time

import paho.mqtt.client as mqtt
from dotenv import load_dotenv

# ── Load credentials from backend/.env ───────────────────────────────────────
_env_path = os.path.join(os.path.dirname(__file__), "backend", ".env")
load_dotenv(_env_path)

BROKER   = os.getenv("MQTT_BROKER", "")
PORT     = int(os.getenv("MQTT_PORT", "8883"))
MQUSER   = os.getenv("MQTT_USER", "")
MQPASS   = os.getenv("MQTT_PASS", "")
TOPIC    = "agromind/data"   # unified channel
INTERVAL = 30  # seconds between publishes

if not BROKER:
    raise SystemExit(
        "[Simulator] ERROR: MQTT_BROKER not set.\n"
        "  Fill in backend/.env with your HiveMQ credentials."
    )

# ── Realistic sensor state ────────────────────────────────────────────────────
moisture  = 60.0   # starts healthy, dries out slowly
temp_base = 27.0
humidity  = 65.0
tick      = 0

def next_reading():
    global moisture, humidity, tick
    tick += 1

    # Soil dries ~0.5% per interval unless just irrigated
    moisture -= random.uniform(0.3, 0.8)
    moisture  = max(10.0, min(100.0, moisture))

    # Randomly simulate irrigation bumping moisture back up
    if moisture < 25 and random.random() < 0.3:
        moisture += random.uniform(20, 35)
        moisture  = min(100.0, moisture)

    # Temperature follows a smooth daily curve + noise
    hour = (tick * INTERVAL / 3600) % 24
    temp = temp_base + 4 * math.sin((hour - 6) * math.pi / 12) + random.uniform(-0.5, 0.5)

    # Humidity inverse of temp curve
    hum = 65 - 10 * math.sin((hour - 6) * math.pi / 12) + random.uniform(-2, 2)
    hum = max(30.0, min(95.0, hum))

    light = int(1000 + 3000 * max(0, math.sin((hour - 6) * math.pi / 12)) + random.randint(-100, 100))
    rain  = random.random() < 0.1  # 10% chance of rain event

    return {
        "type":  "sensor",       # unified channel message type
        "soil":  round(moisture, 1),
        "temp":  round(temp, 1),
        "hum":   round(hum, 1),
        "light": max(0, light),
        "rain":  rain,
    }

# ── MQTT callbacks ────────────────────────────────────────────────────────────
def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        print(f"[Simulator] Connected to HiveMQ at {BROKER}:{PORT}")
    else:
        print(f"[Simulator] Connection failed (rc={rc})")

def on_publish(client, userdata, mid, rc=None, properties=None):
    pass

def on_disconnect(client, userdata, disconnect_flags, rc, properties=None):
    print(f"[Simulator] Disconnected (rc={rc}). Will reconnect on next loop.")

# ── Main loop ─────────────────────────────────────────────────────────────────
def main():
    client = mqtt.Client(
        client_id=f"agromind-simulator-{random.randint(1000, 9999)}",
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2
    )
    client.username_pw_set(MQUSER, MQPASS)

    # TLS — same as ESP32 firmware (insecure skip verify for dev)
    client.tls_set(cert_reqs=ssl.CERT_NONE)
    client.tls_insecure_set(True)

    client.on_connect    = on_connect
    client.on_publish    = on_publish
    client.on_disconnect = on_disconnect

    print(f"[Simulator] Connecting to {BROKER}:{PORT} as '{MQUSER}'...")
    try:
        client.connect(BROKER, PORT, keepalive=60)
    except Exception as e:
        raise SystemExit(f"[Simulator] Cannot connect: {e}")

    client.loop_start()
    print(f"[Simulator] Publishing to '{TOPIC}' every {INTERVAL}s. Press Ctrl+C to stop.\n")

    try:
        while True:
            payload = next_reading()
            result  = client.publish(TOPIC, json.dumps(payload), qos=1)
            result.wait_for_publish()
            print(f"[Simulator] Published: {payload}")
            time.sleep(INTERVAL)
    except KeyboardInterrupt:
        print("\n[Simulator] Stopped.")
    finally:
        client.loop_stop()
        client.disconnect()

if __name__ == "__main__":
    main()
