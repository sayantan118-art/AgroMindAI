import os, json, asyncio, datetime
import mqtt_worker
import analytics as ana
import crop_config as cc
from typing import Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from starlette.requests import Request
import aiosqlite, httpx
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

# ── Config ────────────────────────────────────────────────────
DB_PATH = os.getenv("DB_PATH", "agromind.db")
OPEN_METEO_URL = os.getenv("OPEN_METEO_URL", "https://api.open-meteo.com/v1/forecast")
LAT = os.getenv("LATITUDE", "22.5726")
LON = os.getenv("LONGITUDE", "88.3639")
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")

# ── App setup ─────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="AgroMind AI Backend", version="3.0.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include multi-agent system router
try:
    from agents_endpoint import router as agents_router
    app.include_router(agents_router)
    print("Multi-agent system loaded.")
except ImportError:
    print("Warning: Multi-agent system not available")

# Active WebSocket connections
ws_clients: list[WebSocket] = []

# ── DB init ──────────────────────────────────────────────────
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        # Core sensor log table (v3 schema)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS sensor_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT DEFAULT (datetime('now','localtime')),
                soil_moisture REAL,
                temperature REAL,
                humidity REAL,
                light REAL,
                rain_detected INTEGER,
                rain_expected INTEGER,
                decision TEXT,
                reason TEXT,
                health_score REAL,
                next_check_minutes INTEGER,
                pump_duration_sec INTEGER DEFAULT 0,
                confidence REAL DEFAULT 0,
                risk_level TEXT DEFAULT 'unknown'
            )
        """)
        # Pump activity log
        await db.execute("""
            CREATE TABLE IF NOT EXISTS pump_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT DEFAULT (datetime('now','localtime')),
                action TEXT,
                duration_sec INTEGER
            )
        """)
        # Daily AI-generated farm reports
        await db.execute("""
            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT UNIQUE,
                summary TEXT,
                stats_json TEXT,
                created_at TEXT DEFAULT (datetime('now','localtime'))
            )
        """)
        await db.commit()

        # Migration: add new columns to existing sensor_logs tables if they don't exist
        existing = await db.execute("PRAGMA table_info(sensor_logs)")
        cols = {row[1] for row in await existing.fetchall()}
        migrations = [
            ("light", "REAL"),
            ("rain_detected", "INTEGER"),
            ("pump_duration_sec", "INTEGER DEFAULT 0"),
            ("confidence", "REAL DEFAULT 0"),
            ("risk_level", "TEXT DEFAULT 'unknown'"),
        ]
        for col, col_type in migrations:
            if col not in cols:
                await db.execute(f"ALTER TABLE sensor_logs ADD COLUMN {col} {col_type}")
        await db.commit()

@app.on_event("startup")
async def startup():
    await init_db()
    await cc.init_crop_table()
    # Launch the MQTT background subscriber (replaces n8n)
    loop = asyncio.get_running_loop()
    mqtt_worker.init(loop, ws_clients, DB_PATH)
    mqtt_worker.start()
    print("AgroMind Backend v3.0 started. DB initialized. MQTT worker launched.")

# ── Models ────────────────────────────────────────────────────
class SensorLog(BaseModel):
    soil_moisture: Optional[float] = 50.0
    temperature: Optional[float] = 25.0
    humidity: Optional[float] = 60.0
    light: Optional[float] = None
    rain_detected: Optional[bool] = False
    rain_expected: Optional[bool] = False
    health_score: Optional[float] = 0.0
    urgency: Optional[str] = "low"
    decision: Optional[str] = "skip"
    reason: Optional[str] = "no data"
    next_check_minutes: Optional[int] = 15
    pump_duration_sec: Optional[int] = 0
    confidence: Optional[float] = 0.0
    risk_level: Optional[str] = "unknown"

class PumpAction(BaseModel):
    action: str
    duration_sec: int = 0

class ReportData(BaseModel):
    date: str
    summary: str
    stats: dict = {}

# ── Endpoints ─────────────────────────────────────────────────

@app.post("/sensor/log")
async def log_sensor(data: SensorLog):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO sensor_logs
               (soil_moisture, temperature, humidity, light,
                rain_detected, rain_expected, decision, reason,
                health_score, next_check_minutes, pump_duration_sec,
                confidence, risk_level)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (data.soil_moisture, data.temperature, data.humidity,
             data.light, int(data.rain_detected), int(data.rain_expected),
             data.decision, data.reason, data.health_score,
             data.next_check_minutes, data.pump_duration_sec,
             data.confidence, data.risk_level)
        )
        await db.commit()
    payload = data.model_dump()
    # Broadcast to all connected WebSocket dashboard clients
    dead = []
    for ws in ws_clients:
        try:
            await ws.send_json(payload)
        except Exception:
            dead.append(ws)
    for ws in dead:
        ws_clients.remove(ws)
    return {"status": "logged"}

@app.get("/sensor/latest")
async def sensor_latest():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM sensor_logs ORDER BY id DESC LIMIT 1"
        )
        row = await cur.fetchone()
    return dict(row) if row else {"message": "No data yet"}

@app.get("/sensor/history")
async def sensor_history(limit: int = 100, hours: Optional[int] = None):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if hours:
            since = (datetime.datetime.now() - datetime.timedelta(hours=hours)).isoformat(sep=' ')
            cur = await db.execute(
                "SELECT * FROM sensor_logs WHERE ts >= ? ORDER BY id DESC LIMIT ?",
                (since, limit)
            )
        else:
            cur = await db.execute(
                "SELECT * FROM sensor_logs ORDER BY id DESC LIMIT ?", (limit,)
            )
        rows = await cur.fetchall()
    return [dict(r) for r in rows]

@app.get("/weather/forecast")
async def weather_forecast():
    params = {
        "latitude": LAT,
        "longitude": LON,
        "hourly": "precipitation_probability,rain",
        "daily": "precipitation_probability_max,temperature_2m_max",
        "forecast_days": 1,
        "timezone": "auto"
    }
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(OPEN_METEO_URL, params=params, timeout=10)
        data = r.json()
        hourly = data.get("hourly", {})
        daily = data.get("daily", {})
        rain_prob = hourly.get("precipitation_probability", [0])[0]
        return {
            "rain_probability_next_hour": rain_prob,
            "rain_expected": rain_prob > 50,
            "precipitation_probability_max": (daily.get("precipitation_probability_max") or [0])[0],
            "temperature_2m_max": (daily.get("temperature_2m_max") or [None])[0],
        }
    except Exception as e:
        return {"rain_probability_next_hour": 0, "rain_expected": False, "error": str(e)}

@app.post("/pump/log")
async def log_pump(action: PumpAction):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO pump_log (action, duration_sec) VALUES (?,?)",
            (action.action, action.duration_sec)
        )
        await db.commit()
    return {"status": "logged"}

@app.get("/pump/usage/today")
async def pump_usage_today():
    today = datetime.date.today().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM pump_log WHERE ts LIKE ? ORDER BY id DESC",
            (f"{today}%",)
        )
        rows = await cur.fetchall()
    rows = [dict(r) for r in rows]
    total_on_sec = sum(r["duration_sec"] for r in rows if r["action"] == "ON")
    return {"date": today, "total_on_seconds": total_on_sec, "events": rows}

# ── Analytics endpoints ───────────────────────────────────────────────────────

@app.get("/analytics/et0")
async def get_et0():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT temperature, humidity, light FROM sensor_logs ORDER BY id DESC LIMIT 1")
        row = await cur.fetchone()
    if not row:
        return {"error": "No sensor data yet"}
    r = dict(row)
    return ana.compute_et0(r["temperature"] or 25, r["humidity"] or 60, r["light"] or 1000)

@app.get("/analytics/stress")
async def get_stress():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM sensor_logs ORDER BY id DESC LIMIT 1")
        row = await cur.fetchone()
    if not row:
        return {"error": "No sensor data yet"}
    r = dict(row)
    cfg = await cc.get_crop_config()
    return ana.compute_stress_index(
        r["soil_moisture"] or 50, r["temperature"] or 25, r["humidity"] or 60,
        r["light"] or 1000, bool(r["rain_detected"]),
        cfg["soil_min_pct"], cfg["soil_max_pct"]
    )

@app.get("/analytics/pest-risk")
async def get_pest_risk():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT temperature, humidity FROM sensor_logs ORDER BY id DESC LIMIT 1")
        row = await cur.fetchone()
    if not row:
        return {"error": "No sensor data yet"}
    r = dict(row)
    return ana.compute_pest_risk(r["temperature"] or 25, r["humidity"] or 60)

@app.get("/analytics/irrigation-eta")
async def get_irrigation_eta():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT soil_moisture, ts FROM sensor_logs ORDER BY id DESC LIMIT 48")
        rows = await cur.fetchall()
    cfg = await cc.get_crop_config()
    return ana.compute_irrigation_eta([dict(r) for r in rows], cfg["soil_min_pct"])

@app.get("/analytics/water-usage")
async def get_water_usage():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        since = (datetime.datetime.now() - datetime.timedelta(days=7)).isoformat(sep=' ')
        cur = await db.execute(
            "SELECT action, duration_sec, ts FROM pump_log WHERE ts >= ? ORDER BY id DESC", (since,)
        )
        rows = await cur.fetchall()
    return ana.compute_water_usage([dict(r) for r in rows])

@app.get("/analytics/all")
async def get_all_analytics():
    """Single endpoint — dashboard fetches all analytics in one call."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM sensor_logs ORDER BY id DESC LIMIT 1")
        row = await cur.fetchone()
        latest = dict(row) if row else {}
        cur2 = await db.execute("SELECT soil_moisture, ts FROM sensor_logs ORDER BY id DESC LIMIT 48")
        history = [dict(r) for r in await cur2.fetchall()]
        since7d = (datetime.datetime.now() - datetime.timedelta(days=7)).isoformat(sep=' ')
        cur3 = await db.execute("SELECT action, duration_sec, ts FROM pump_log WHERE ts >= ?", (since7d,))
        pump_rows = [dict(r) for r in await cur3.fetchall()]
    if not latest:
        return {"error": "No data yet"}
    cfg = await cc.get_crop_config()
    t = latest.get("temperature") or 25.0
    h = latest.get("humidity") or 60.0
    l = latest.get("light") or 1000.0
    s = latest.get("soil_moisture") or 50.0
    rain = bool(latest.get("rain_detected"))
    return {
        "et0":            ana.compute_et0(t, h, l),
        "stress":         ana.compute_stress_index(s, t, h, l, rain, cfg["soil_min_pct"], cfg["soil_max_pct"]),
        "pest_risk":      ana.compute_pest_risk(t, h),
        "irrigation_eta": ana.compute_irrigation_eta(history, cfg["soil_min_pct"]),
        "water_usage":    ana.compute_water_usage(pump_rows),
        "crop_config":    cfg,
    }


# ── Crop Stage endpoints ───────────────────────────────────────────────────────

@app.get("/crop/stage")
async def get_crop_stage():
    return await cc.get_crop_config()

class CropStageUpdate(BaseModel):
    crop: str
    stage: str

@app.post("/crop/stage")
async def set_crop_stage(data: CropStageUpdate):
    try:
        return await cc.set_crop_config(data.crop, data.stage)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Report endpoints ──────────────────────────────────────────

@app.post("/report/save")
async def save_report(data: ReportData):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO reports (date, summary, stats_json) VALUES (?,?,?)",
            (data.date, data.summary, json.dumps(data.stats))
        )
        await db.commit()
    return {"status": "saved", "date": data.date}

@app.get("/report/list")
async def list_reports(limit: int = 30):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT date, summary, created_at FROM reports ORDER BY date DESC LIMIT ?",
            (limit,)
        )
        rows = await cur.fetchall()
    return [dict(r) for r in rows]

@app.get("/report/{date}")
async def get_report(date: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM reports WHERE date = ?", (date,)
        )
        row = await cur.fetchone()
    if not row:
        return {"error": "Report not found"}
    r = dict(row)
    r["stats"] = json.loads(r.get("stats_json") or "{}")
    return r

# ── WebSocket endpoint for dashboard live updates ─────────────
@app.websocket("/ws/dashboard")
async def ws_dashboard(websocket: WebSocket):
    await websocket.accept()
    ws_clients.append(websocket)
    print(f"Dashboard connected. Total clients: {len(ws_clients)}")
    try:
        while True:
            await websocket.receive_text()  # keep-alive ping
    except WebSocketDisconnect:
        ws_clients.remove(websocket)
        print(f"Dashboard disconnected. Total clients: {len(ws_clients)}")

# ── Health check ──────────────────────────────────────────────
@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "AgroMind AI Backend",
        "version": "3.0.0",
        "time": datetime.datetime.now().isoformat()
    }
