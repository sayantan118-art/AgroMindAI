"""
AgroMind AI — Sensor Simulator
Replaces the ESP32 hardware during software-only testing.
Publishes realistic sensor data to HiveMQ Cloud every 30 seconds.
Listens for pump commands on the same channel and increases soil
moisture accordingly — mirrors real ESP32 behaviour.

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
import threading

import paho.mqtt.client as mqtt
from dotenv import load_dotenv

# ── Load credentials from backend/.env ───────────────────────────────────────
_env_path = os.path.join(os.path.dirname(__file__), "backend", ".env")
load_dotenv(_env_path)

BROKER   = os.getenv("MQTT_BROKER", "")
PORT     = int(os.getenv("MQTT_PORT", "8883"))
MQUSER   = os.getenv("MQTT_USER", "")
MQPASS   = os.getenv("MQTT_PASS", "")
TOPIC    = "agromind/data"
INTERVAL = 30  # seconds between sensor publishes

if not BROKER:
    raise SystemExit(
        "[Simulator] ERROR: MQTT_BROKER not set.\n"
        "  Fill in backend/.env with your HiveMQ credentials."
    )

# ── Sensor state ──────────────────────────────────────────────────────────────
moisture      = 60.0   # %  — dries out gradually
temp_base     = 27.0   # °C base temperature
humidity      = 65.0   # %
tick          = 0

# ── Pump state ────────────────────────────────────────────────────────────────
# When the backend sends a pump ON command the simulator applies irrigation:
# moisture rises ~0.15 % per second of pump runtime (90 s → +13.5 %)
pump_active        = False
pump_duration_sec  = 0
pump_timer         = None          # threading.Timer handle
pump_lock          = threading.Lock()

MOISTURE_RATE_PER_SEC = 0.15       # % moisture gained per second of irrigation


def _pump_off():
    """Called when pump duration expires."""
    global pump_active, pump_duration_sec
    with pump_lock:
        pump_active       = False
        pump_duration_sec = 0
    print("[Simulator] Pump OFF (duration expired)")


def apply_pump(duration: int):
    """Turn pump on for `duration` seconds, raise moisture, schedule OFF."""
    global moisture, pump_active, pump_duration_sec, pump_timer

    with pump_lock:
        # Cancel any existing timer
        if pump_timer and pump_timer.is_alive():
            pump_timer.cancel()

        pump_active       = True
        pump_duration_sec = duration

        # Raise moisture immediately by the full amount the pump would deliver
        gain     = duration * MOISTURE_RATE_PER_SEC
        moisture = min(100.0, moisture + gain)
        print(f"[Simulator] Pump ON for {duration}s  →  moisture now {moisture:.1f}%")

        pump_timer = threading.Timer(duration, _pump_off)
        pump_timer.daemon = True
        pump_timer.start()


# ── Crop health score (computed locally, mirrors agent logic) ─────────────────
def compute_health_score(soil: float, temp: float, hum: float, rain: bool) -> int:
    """
    Rule-based health score 0–100.
    Matches the CropDoctorAgent fallback so the simulator value is consistent
    with what the backend would compute when Groq is unavailable.
    """
    score = 100

    # Soil moisture
    if soil < 20:
        score -= 40
    elif soil < 30:
        score -= 25
    elif soil > 85:
        score -= 15   # overwatering

    # Temperature
    if temp > 38:
        score -= 30
    elif temp > 34:
        score -= 20
    elif temp < 15:
        score -= 15

    # Humidity
    if hum < 30:
        score -= 15
    elif hum > 90:
        score -= 10

    # Rain bonus — slight positive if rain detected
    if rain:
        score = min(100, score + 5)

    return max(0, min(100, score))


# ── Sensor reading ─────────────────────────────────────────────────────────────
def next_reading():
    global moisture, humidity, tick
    tick += 1

    with pump_lock:
        currently_pumping = pump_active

    # Soil dries ~0.4–0.7 % per interval when pump is not running
    if not currently_pumping:
        moisture -= random.uniform(0.4, 0.7)
        moisture  = max(10.0, min(100.0, moisture))

    # Temperature: smooth daily sine curve + small noise
    hour = (tick * INTERVAL / 3600) % 24
    temp = temp_base + 4 * math.sin((hour - 6) * math.pi / 12) + random.uniform(-0.5, 0.5)

    # Humidity: inverse of temperature curve
    hum = 65 - 10 * math.sin((hour - 6) * math.pi / 12) + random.uniform(-2, 2)
    hum = max(30.0, min(95.0, hum))

    # Light: zero at night, peaks midday
    light = int(1000 + 3000 * max(0, math.sin((hour - 6) * math.pi / 12)) + random.randint(-100, 100))
    light = max(0, light)

    # Rain: 10 % chance per interval
    rain = random.random() < 0.1
    if rain:
        # Rain also slightly raises soil moisture
        moisture = min(100.0, moisture + random.uniform(1.0, 4.0))

    health = compute_health_score(moisture, temp, hum, rain)

    return {
        "type":         "sensor",
        "soil":         round(moisture, 1),
        "temp":         round(temp, 1),
        "hum":          round(hum, 1),
        "light":        light,
        "rain":         rain,
        "pump":         currently_pumping,
        "health_score": health,
    }


# ── MQTT callbacks ────────────────────────────────────────────────────────────
def on_connect(client, userdata, flags, reason_code, properties=None):
    if reason_code == 0:
        client.subscribe(TOPIC, qos=1)
        print(f"[Simulator] Connected to HiveMQ at {BROKER}:{PORT}")
        print(f"[Simulator] Subscribed to '{TOPIC}' for pump commands")
    else:
        print(f"[Simulator] Connection failed (reason_code={reason_code})")


def on_message(client, userdata, msg):
    """Handle incoming pump commands from the backend."""
    try:
        data = json.loads(msg.payload.decode())
        if data.get("type") == "pump":
            action   = data.get("action", "OFF")
            duration = int(data.get("duration_sec", 0))
            if action == "ON" and duration > 0:
                apply_pump(duration)
            elif action == "OFF":
                with pump_lock:
                    global pump_active
                    pump_active = False
                if pump_timer and pump_timer.is_alive():
                    pump_timer.cancel()
                print("[Simulator] Pump OFF (manual command)")
    except Exception as e:
        print(f"[Simulator] Bad incoming message: {e}")


def on_publish(client, userdata, mid, reason_code=None, properties=None):
    pass


def on_disconnect(client, userdata, disconnect_flags, reason_code=None, properties=None):
    print(f"[Simulator] Disconnected (reason_code={reason_code}). Reconnecting...")


# ── Main loop ─────────────────────────────────────────────────────────────────
def main():
    client = mqtt.Client(
        client_id=f"agromind-simulator-{random.randint(1000, 9999)}",
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2
    )
    client.username_pw_set(MQUSER, MQPASS)
    client.tls_set(cert_reqs=ssl.CERT_NONE)
    client.tls_insecure_set(True)

    client.on_connect    = on_connect
    client.on_message    = on_message
    client.on_publish    = on_publish
    client.on_disconnect = on_disconnect

    print(f"[Simulator] Connecting to {BROKER}:{PORT} as '{MQUSER}'...")
    try:
        client.connect(BROKER, PORT, keepalive=60)
    except Exception as e:
        raise SystemExit(f"[Simulator] Cannot connect: {e}")

    client.loop_start()
    print(f"[Simulator] Publishing sensor data every {INTERVAL}s. Press Ctrl+C to stop.\n")

    try:
        while True:
            payload = next_reading()
            result  = client.publish(TOPIC, json.dumps(payload), qos=1)
            result.wait_for_publish()
            print(
                f"[Simulator] soil={payload['soil']}%  "
                f"temp={payload['temp']}°C  "
                f"hum={payload['hum']}%  "
                f"health={payload['health_score']}  "
                f"pump={'ON' if payload['pump'] else 'OFF'}"
            )
            time.sleep(INTERVAL)
    except KeyboardInterrupt:
        print("\n[Simulator] Stopped.")
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
