
"""
AgroMind AI — Sensor Simulator
Replaces the ESP32 hardware during software-only testing.
Publishes realistic sensor data to MQTT every 30 seconds.

Run:
    cd C:\MyFiles\AgroMindAI\backend
    venv\Scripts\activate
    python ..\simulator.py
"""

import json
import time
import math
import random
import paho.mqtt.client as mqtt

# ── Config ────────────────────────────────────────────────────────────────────
BROKER   = "localhost"
PORT     = 1883
TOPIC    = "agromind/sensors"
INTERVAL = 30  # seconds between publishes

# ── Realistic sensor state ────────────────────────────────────────────────────
moisture  = 60.0   # starts healthy, dries out slowly
temp_base = 27.0   # base temperature
humidity  = 65.0
tick      = 0

def next_reading():
    global moisture, humidity, tick
    tick += 1

    # Soil dries out ~0.5% per interval unless it was just irrigated
    moisture -= random.uniform(0.3, 0.8)
    moisture  = max(10.0, min(100.0, moisture))

    # Randomly simulate irrigation bumping moisture back up
    if moisture < 25 and random.random() < 0.3:
        moisture += random.uniform(20, 35)
        moisture  = min(100.0, moisture)

    # Temperature follows a smooth daily curve + noise
    hour    = (tick * INTERVAL / 3600) % 24
    temp    = temp_base + 4 * math.sin((hour - 6) * math.pi / 12) + random.uniform(-0.5, 0.5)

    # Humidity inverse of temp curve
    humidity = 65 - 10 * math.sin((hour - 6) * math.pi / 12) + random.uniform(-2, 2)
    humidity = max(30.0, min(95.0, humidity))

    light = int(1000 + 3000 * max(0, math.sin((hour - 6) * math.pi / 12)) + random.randint(-100, 100))
    rain  = random.random() < 0.1  # 10% chance of rain event

    return {
        "soil_moisture": round(moisture, 1),
        "temperature":   round(temp, 1),
        "humidity":      round(humidity, 1),
        "light":         max(0, light),
        "rain_detected": rain,
    }

# ── MQTT callbacks ────────────────────────────────────────────────────────────
def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        print(f"[Simulator] Connected to MQTT broker at {BROKER}:{PORT}")
    else:
        print(f"[Simulator] Connection failed (rc={rc})")

def on_publish(client, userdata, mid, rc=None, properties=None):
    pass

# ── Main loop ─────────────────────────────────────────────────────────────────
def main():
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    client.on_publish = on_publish

    try:
        client.connect(BROKER, PORT, keepalive=60)
    except Exception as e:
        print(f"[Simulator] Cannot connect to MQTT broker: {e}")
        print("  Make sure Mosquitto is running:  net start mosquitto")
        return

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
