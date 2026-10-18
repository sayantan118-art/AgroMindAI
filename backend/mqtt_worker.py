"""
mqtt_worker.py — AgroMind AI background MQTT subscriber.

Responsibilities (analysis is NOT among them):

* subscribe to ``agromind/data`` and ingest sensor messages only,
* validate + quality-flag each reading (persist invalid ones with a flag, never
  crash on a malformed message),
* deduplicate MQTT redelivery / simulator restarts,
* persist the reading to SQLite and broadcast it over WebSocket,
* periodically refresh and persist the Open-Meteo weather snapshot (throttled),
* expose :func:`publish_pump` so the *manual* pump-control endpoint can publish a
  pump command through the safety gate.

Per-message AI analysis and autonomous pump actuation were removed: analysis
now happens only on explicit request via the ``/analysis/analyze`` endpoint, and
pump commands come only from an explicit user action through ``/pump/control``
(both gated by the standalone safety gate). Sensor ingestion, persistence,
weather updates and live dashboard updates continue independently.
"""
import os, json, time, asyncio, threading, ssl, logging, datetime, hashlib
import paho.mqtt.client as mqtt
import httpx

log = logging.getLogger("mqtt_worker")
logging.basicConfig(level=logging.INFO)

# ── Config ────────────────────────────────────────────────────────────────────
BROKER   = os.getenv("MQTT_BROKER", "")
PORT     = int(os.getenv("MQTT_PORT", "8883"))
MQUSER   = os.getenv("MQTT_USER", "")
MQPASS   = os.getenv("MQTT_PASS", "")
DB_PATH  = os.getenv("DB_PATH", "agromind.db")
LAT      = os.getenv("LATITUDE",  "22.5726")
LON      = os.getenv("LONGITUDE", "88.3639")
DATA_TOPIC = "agromind/data"
WEATHER_REFRESH_SECONDS = int(os.getenv("WEATHER_REFRESH_SECONDS", "600"))
DEDUP_WINDOW_SECONDS = int(os.getenv("SENSOR_DEDUP_WINDOW_SECONDS", "60"))

# ── Shared state (set by main.py after app starts) ───────────────────────────
_loop: asyncio.AbstractEventLoop | None = None
_ws_clients: list | None = None
_db_path: str = DB_PATH

# Module-level MQTT client ref so the manual pump-control endpoint can publish.
_client: mqtt.Client | None = None

# In-process weather cache + dedup cache (lost on restart; that is fine — the DB
# is the durable record, and these are only optimization caches).
_weather_cache: dict | None = None
_weather_cache_at: float = 0.0
_recent_dedup: dict[str, float] = {}

def init(loop: asyncio.AbstractEventLoop, ws_clients: list, db_path: str):
    global _loop, _ws_clients, _db_path
    _loop = loop
    _ws_clients = ws_clients
    _db_path = db_path


# ── Weather helper (throttled) ────────────────────────────────────────────────
async def _fetch_weather() -> dict:
    """Return a cached weather snapshot, refreshing at most every
    ``WEATHER_REFRESH_SECONDS`` to avoid hammering Open-Meteo on every message."""
    global _weather_cache, _weather_cache_at
    now = time.time()
    if _weather_cache is not None and (now - _weather_cache_at) < WEATHER_REFRESH_SECONDS:
        return _weather_cache
    params = {
        "latitude": LAT, "longitude": LON,
        "hourly": "precipitation_probability,rain",
        "daily": "precipitation_probability_max,temperature_2m_max",
        "forecast_days": 1, "timezone": "auto",
    }
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            r = await client.get("https://api.open-meteo.com/v1/forecast", params=params)
        d = r.json()
        prob = (d.get("hourly", {}).get("precipitation_probability") or [0])[0]
        max_temp = (d.get("daily", {}).get("temperature_2m_max") or [None])[0]
        result = {
            "rain_expected": prob > 60,
            "rain_probability_next_hour": prob,
            "temperature_2m_max": max_temp,
            "precipitation_probability_max": (d.get("daily", {}).get("precipitation_probability_max") or [0])[0],
            "source": "open-meteo-live",
        }
        _weather_cache = result
        _weather_cache_at = now
        return result
    except Exception as e:
        log.warning(f"Weather fetch failed: {e}")
        return {"rain_expected": False, "rain_probability_next_hour": 0, "source": "unavailable"}


# ── Sensor validation + quality ──────────────────────────────────────────────
def _classify_quality(sensor: dict) -> tuple[str, str]:
    """Return (quality_status, quality_reason). 'ok' / 'out_of_range' / 'malformed'."""
    try:
        soil = sensor.get("soil")
        temp = sensor.get("temp")
        hum = sensor.get("hum")
        problems = []
        if soil is not None and not (isinstance(soil, (int, float)) and 0 <= soil <= 100):
            problems.append(f"soil {soil} out of 0–100")
        if temp is not None and not (isinstance(temp, (int, float)) and -10 <= temp <= 60):
            problems.append(f"temp {temp} out of range")
        if hum is not None and not (isinstance(hum, (int, float)) and 0 <= hum <= 100):
            problems.append(f"hum {hum} out of 0–100")
        if problems:
            return "out_of_range", "; ".join(problems)
        return "ok", ""
    except Exception as e:
        return "malformed", f"validation error: {e}"


def _dedup_key(sensor: dict) -> str:
    """Stable hash of the sensor values for deduplication.

    The firmware/simulator send no device id and no device timestamp, so dedup
    is based on the sensor values themselves. Identical readings received
    within ``SENSOR_DEDUP_WINDOW_SECONDS`` are suppressed (handles MQTT
    redelivery and simulator restarts). Documented limitation: two *distinct*
    readings with identical values within that window are also suppressed.
    """
    stable = json.dumps({
        "soil": sensor.get("soil"),
        "temp": sensor.get("temp"),
        "hum": sensor.get("hum"),
        "light": sensor.get("light"),
        "rain": bool(sensor.get("rain", False)),
    }, sort_keys=True, default=str)
    return hashlib.sha256(stable.encode("utf-8")).hexdigest()[:32]


# ── Database write ────────────────────────────────────────────────────────────
async def _save_reading(sensor: dict, weather: dict, quality_status: str, quality_reason: str, dedup_key: str):
    from database.connection import SessionFactory
    from database.repositories import (
        ActivityRepository, FarmRepository, SensorReadingRepository, WeatherRepository,
    )

    now = datetime.datetime.utcnow()
    async with SessionFactory() as session:
        farm_repo = FarmRepository(session)
        farms = await farm_repo.list_active()
        if farms:
            farm_id = farms[0].id
        else:
            farm = await farm_repo.create(
                name="Default Farm", description="Auto-created default farm",
                location="Kolkata", latitude=22.5726, longitude=88.3639,
                area=100.0, crop="Tomato", soil_type="Loam", climate="Warm",
                mode="Virtual", active=True,
            )
            farm_id = farm.id

        sensor_repo = SensorReadingRepository(session)
        await sensor_repo.create(
            farm_id=farm_id,
            device_id=None,
            soil_moisture=sensor.get("soil"),
            temperature=sensor.get("temp"),
            humidity=sensor.get("hum"),
            light=sensor.get("light"),
            rain=bool(sensor.get("rain", False)),
            wind_speed=None, uv_index=None, air_pressure=None,
            quality_status=quality_status,
            quality_reason=quality_reason or None,
            dedup_key=dedup_key,
            received_at=now,
            timestamp=now,  # no device clock → server receive time (documented)
        )

        # Persist weather (throttled upstream). Keep one row per refresh.
        if weather.get("source") == "open-meteo-live":
            weather_repo = WeatherRepository(session)
            await weather_repo.create(
                farm_id=farm_id,
                temperature=float(weather.get("temperature_2m_max") or 25.0),
                humidity=60.0, wind=8.0,
                forecast="Forecast persisted",
                rain_probability=float(weather.get("rain_probability_next_hour") or 0),
                uv=4.0,
                weather_description="Persisted from MQTT weather refresh",
                timestamp=now,
            )

        activity_repo = ActivityRepository(session)
        await activity_repo.create(
            farm_id=farm_id, action_type="mqtt_sensor",
            message="MQTT sensor update persisted",
            metadata_json=json.dumps({"quality": quality_status}),
            created_at=now,
        )


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
async def _process(raw: str):
    """Ingest a single MQTT message. No analysis, no pump actuation."""
    try:
        msg = json.loads(raw)
    except Exception:
        log.warning(f"Invalid JSON from MQTT: {raw[:120]}")
        return

    # Ignore non-sensor messages on the unified channel (pump echoes, etc.).
    if msg.get("type") != "sensor":
        log.info(f"Ignored non-sensor message: type={msg.get('type')}")
        return

    sensor = msg  # keys: soil, temp, hum, light, rain
    quality_status, quality_reason = _classify_quality(sensor)
    dk = _dedup_key(sensor)

    # Deduplicate within the configured window.
    now_ts = time.time()
    seen = _recent_dedup.get(dk)
    if seen is not None and (now_ts - seen) < DEDUP_WINDOW_SECONDS:
        log.debug("Duplicate sensor message suppressed")
        return
    _recent_dedup[dk] = now_ts
    # Bound the dedup cache by dropping expired entries occasionally.
    if len(_recent_dedup) > 1000:
        cutoff = now_ts - DEDUP_WINDOW_SECONDS
        for k in [k for k, v in _recent_dedup.items() if v < cutoff]:
            del _recent_dedup[k]

    weather = await _fetch_weather()

    # Persist (never crash on a bad reading — flag and continue).
    try:
        await _save_reading(sensor, weather, quality_status, quality_reason, dk)
    except Exception as e:
        log.error(f"Sensor persistence failed (WebSocket stays alive): {e}")

    # Broadcast sensor data only (no AI decision, no health_score fabrication).
    payload = {
        "soil_moisture": sensor.get("soil"),
        "temperature": sensor.get("temp"),
        "humidity": sensor.get("hum"),
        "light": sensor.get("light"),
        "rain_detected": sensor.get("rain", False),
        "rain_expected": weather.get("rain_expected", False),
        "rain_probability": weather.get("rain_probability_next_hour", 0),
        "quality_status": quality_status,
        "received_at": datetime.datetime.utcnow().isoformat() + "Z",
    }
    await _broadcast(payload)
    log.info(f"Ingested: soil={sensor.get('soil')}% temp={sensor.get('temp')}°C quality={quality_status}")


# ── Manual pump publish (used by the safety gate via /pump/control) ──────────
def publish_pump(action: str, duration_sec: int) -> bool:
    """Publish a manual pump command on the unified topic. Returns True on
    publish success. Called ONLY after the safety gate approves."""
    if _client is None:
        log.warning("publish_pump called but MQTT client is not connected")
        return False
    action = (action or "OFF").upper()
    pump_msg = json.dumps({"type": "pump", "action": action, "duration_sec": int(duration_sec or 0)})
    info = _client.publish(DATA_TOPIC, pump_msg, qos=1)
    ok = info.rc == mqtt.MQTT_ERR_SUCCESS
    log.info(f"Manual pump {action} published ({duration_sec}s) rc={info.rc}")
    return ok


# ── MQTT callbacks (paho-mqtt v2 signatures) ────────────────────────────────
def _on_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        client.subscribe(DATA_TOPIC, qos=1)
        log.info(f"MQTT connected. Subscribed to '{DATA_TOPIC}'")
    else:
        log.error(f"MQTT connect failed: reason_code={reason_code}")

def _on_message(client, userdata, msg):
    raw = msg.payload.decode("utf-8", errors="ignore")
    if _loop:
        asyncio.run_coroutine_threadsafe(_process(raw), _loop)

def _on_disconnect(client, userdata, disconnect_flags, reason_code, properties):
    log.warning(f"MQTT disconnected (reason_code={reason_code}). Will auto-reconnect.")

# ── Entry point called from main.py startup ───────────────────────────────────
def start():
    """Start the MQTT subscriber in a daemon background thread."""
    global _client
    if not BROKER:
        log.warning("MQTT_BROKER not set — mqtt_worker disabled.")
        return

    def _run():
        global _client
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                             client_id="agromind-backend", clean_session=True)
        client.username_pw_set(MQUSER, MQPASS)
        client.tls_set(cert_reqs=ssl.CERT_NONE)
        client.tls_insecure_set(True)
        client.on_connect    = _on_connect
        client.on_message    = _on_message
        client.on_disconnect = _on_disconnect
        _client = client
        client.connect(BROKER, PORT, keepalive=60)
        client.loop_forever()

    t = threading.Thread(target=_run, daemon=True, name="mqtt-worker")
    t.start()
    # _client is assigned inside _run; expose a publish handle once connected.
    # We can't block on connect here, so publish_pump lazily resolves the client
    # via the module ref set below once the client object exists.
    log.info("MQTT worker thread started.")
