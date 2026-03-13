"""
mqtt_worker.py — AgroMind AI Background MQTT Subscriber
Replaces n8n completely. Runs in a background thread when Render starts.
Subscribes to agromind/sensors, makes Groq AI decisions, logs to DB, and
broadcasts real-time data to the React dashboard via WebSocket.
"""
import os, json, asyncio, threading, ssl, logging, datetime
import paho.mqtt.client as mqtt
import httpx
from groq import Groq

log = logging.getLogger("mqtt_worker")
logging.basicConfig(level=logging.INFO)

# ── Config ────────────────────────────────────────────────────────────────────
BROKER   = os.getenv("MQTT_BROKER", "")
PORT     = int(os.getenv("MQTT_PORT", "8883"))
MQUSER   = os.getenv("MQTT_USER", "")
MQPASS   = os.getenv("MQTT_PASS", "")
GROQ_KEY = os.getenv("GROQ_API_KEY", "")
DB_PATH  = os.getenv("DB_PATH", "agromind.db")
LAT      = os.getenv("LATITUDE",  "22.5726")
LON      = os.getenv("LONGITUDE", "88.3639")
SENSOR_TOPIC = "agromind/sensors"
PUMP_TOPIC   = "agromind/pump"

# ── Shared state (set by main.py after app starts) ───────────────────────────
_loop: asyncio.AbstractEventLoop | None = None
_ws_clients: list | None = None
_db_path: str = DB_PATH

def init(loop: asyncio.AbstractEventLoop, ws_clients: list, db_path: str):
    """Called from main.py startup to wire up shared state."""
    global _loop, _ws_clients, _db_path
    _loop = loop
    _ws_clients = ws_clients
    _db_path = db_path

# ── Groq client ───────────────────────────────────────────────────────────────
_groq = Groq(api_key=GROQ_KEY) if GROQ_KEY else None
log.info(f"Groq client: {'READY (key set)' if _groq else 'DISABLED (GROQ_API_KEY not set)'}")

# ── Weather helper ────────────────────────────────────────────────────────────
async def _fetch_weather() -> dict:
    params = {
        "latitude": LAT, "longitude": LON,
        "hourly": "precipitation_probability,rain",
        "daily": "precipitation_probability_max,temperature_2m_max",
        "forecast_days": 1, "timezone": "auto"
    }
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            r = await client.get("https://api.open-meteo.com/v1/forecast", params=params)
        d = r.json()
        prob = (d.get("hourly", {}).get("precipitation_probability") or [0])[0]
        return {"rain_expected": prob > 50, "rain_probability_next_hour": prob}
    except Exception as e:
        log.warning(f"Weather fetch failed: {e}")
        return {"rain_expected": False, "rain_probability_next_hour": 0}

# ── Groq decision ─────────────────────────────────────────────────────────────
def _ask_groq(sensor: dict, weather: dict) -> dict:
    if not _groq:
        log.error("Groq client is None — GROQ_API_KEY was empty at startup!")
        return {"decision": "SKIP", "health_score": 50, "reason": "Groq not configured",
                "next_check_minutes": 15, "confidence": 0, "risk_level": "unknown", "pump_duration_sec": 0}
    prompt = (
        f"You are an agricultural AI. Analyse the following data and respond in strict JSON only.\n"
        f"Sensor: soil_moisture={sensor.get('soil')}%, temperature={sensor.get('temp')}°C, "
        f"humidity={sensor.get('hum')}%, light={sensor.get('light')}, rain_detected={sensor.get('rain')}\n"
        f"Weather: rain_expected={weather.get('rain_expected')}, rain_probability={weather.get('rain_probability_next_hour')}%\n\n"
        f"Reply with valid JSON only, no extra text:\n"
        f'{{"decision":"IRRIGATE|SKIP|DELAY","health_score":0-100,"confidence":0.0-1.0,'
        f'"risk_level":"low|caution|high","pump_duration_sec":0-180,'
        f'"next_check_minutes":5-60,"reason":"short explanation"}}'
    )
    try:
        resp = _groq.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2, max_tokens=200
        )
        raw = resp.choices[0].message.content.strip()
        # Extract JSON if wrapped in markdown
        if "```" in raw:
            raw = raw.split("```")[1].lstrip("json").strip()
        return json.loads(raw)
    except Exception as e:
        log.error(f"Groq FAILED [{type(e).__name__}]: {e}")
        soil = sensor.get("soil", 50)
        rain = sensor.get("rain", False)
        irrigate = soil < 30 and not rain
        return {
            "decision": "IRRIGATE" if irrigate else "SKIP",
            "health_score": 50, "confidence": 0.5, "risk_level": "caution",
            "pump_duration_sec": 90 if irrigate else 0,
            "next_check_minutes": 10,
            "reason": f"Fallback rule-based (Groq error: {type(e).__name__})"
        }


# ── Database write ────────────────────────────────────────────────────────────
async def _save_reading(sensor: dict, weather: dict, ai: dict):
    import aiosqlite
    async with aiosqlite.connect(_db_path) as db:
        await db.execute(
            """INSERT INTO sensor_logs
               (soil_moisture, temperature, humidity, light,
                rain_detected, rain_expected, decision, reason,
                health_score, next_check_minutes, pump_duration_sec,
                confidence, risk_level)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (sensor.get("soil"), sensor.get("temp"), sensor.get("hum"),
             sensor.get("light"), int(sensor.get("rain", False)),
             int(weather.get("rain_expected", False)),
             ai.get("decision", "SKIP"), ai.get("reason", ""),
             ai.get("health_score", 0), ai.get("next_check_minutes", 15),
             ai.get("pump_duration_sec", 0), ai.get("confidence", 0),
             ai.get("risk_level", "unknown"))
        )
        await db.commit()

# ── WebSocket broadcast ───────────────────────────────────────────────────────
async def _broadcast(payload: dict):
    if not _ws_clients:
        return
    dead = []
    for ws in list(_ws_clients):
        try:
            await ws.send_json(payload)
        except Exception:
            dead.append(ws)
    for ws in dead:
        try:
            _ws_clients.remove(ws)
        except ValueError:
            pass

# ── Main processing coroutine (runs on the event loop) ───────────────────────
async def _process(mqclient: mqtt.Client, raw: str):
    try:
        sensor = json.loads(raw)
    except Exception:
        log.warning(f"Invalid JSON from MQTT: {raw}")
        return

    weather = await _fetch_weather()
    ai      = _ask_groq(sensor, weather)

    payload = {
        "soil_moisture":       sensor.get("soil"),
        "temperature":         sensor.get("temp"),
        "humidity":            sensor.get("hum"),
        "light":               sensor.get("light"),
        "rain_detected":       sensor.get("rain", False),
        "rain_expected":       weather.get("rain_expected", False),
        "decision":            ai.get("decision", "SKIP"),
        "reason":              ai.get("reason", ""),
        "health_score":        ai.get("health_score", 0),
        "next_check_minutes":  ai.get("next_check_minutes", 15),
        "pump_duration_sec":   ai.get("pump_duration_sec", 0),
        "confidence":          ai.get("confidence", 0),
        "risk_level":          ai.get("risk_level", "unknown"),
        "pump":                sensor.get("pump", False),
        "ts":                  datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
    }

    await _save_reading(sensor, weather, ai)
    await _broadcast(payload)

    # Trigger pump via MQTT if decision is IRRIGATE
    if ai.get("decision") == "IRRIGATE" and ai.get("pump_duration_sec", 0) > 0:
        pump_msg = json.dumps({"action": "ON", "duration_sec": ai["pump_duration_sec"]})
        mqclient.publish(PUMP_TOPIC, pump_msg, qos=1)
        log.info(f"Pump ON published for {ai['pump_duration_sec']}s")

    log.info(f"Processed: soil={sensor.get('soil')}% decision={ai.get('decision')} score={ai.get('health_score')}")

# ── MQTT callbacks ────────────────────────────────────────────────────────────
def _on_connect(client, userdata, flags, rc):
    if rc == 0:
        client.subscribe(SENSOR_TOPIC, qos=1)
        log.info(f"MQTT connected. Subscribed to '{SENSOR_TOPIC}'")
    else:
        log.error(f"MQTT connect failed: rc={rc}")

def _on_message(client, userdata, msg):
    raw = msg.payload.decode("utf-8", errors="ignore")
    if _loop:
        asyncio.run_coroutine_threadsafe(_process(client, raw), _loop)

def _on_disconnect(client, userdata, rc):
    log.warning(f"MQTT disconnected (rc={rc}). Will auto-reconnect.")

# ── Entry point called from main.py startup ───────────────────────────────────
def start():
    """Start MQTT subscriber in a daemon background thread with auto-restart watchdog."""
    if not BROKER:
        log.warning("MQTT_BROKER not set — mqtt_worker disabled.")
        return

    def _run():
        while True:  # outer loop = auto-restart on unexpected exit
            try:
                client = mqtt.Client(
                    client_id="agromind-backend",
                    clean_session=False  # keep subscriptions across brief disconnects
                )
                client.username_pw_set(MQUSER, MQPASS)
                client.tls_set(cert_reqs=ssl.CERT_NONE)
                client.tls_insecure_set(True)
                client.reconnect_delay_set(min_delay=2, max_delay=60)
                client.on_connect    = _on_connect
                client.on_message    = _on_message
                client.on_disconnect = _on_disconnect
                log.info(f"Connecting to MQTT broker {BROKER}:{PORT}")
                client.connect(BROKER, PORT, keepalive=60)
                client.loop_forever()  # blocks; auto-reconnects on drop
            except Exception as e:
                log.error(f"MQTT worker crashed: {e}. Restarting in 10s...")
                import time; time.sleep(10)

    t = threading.Thread(target=_run, daemon=True, name="mqtt-worker")
    t.start()
    log.info("MQTT worker thread started.")

