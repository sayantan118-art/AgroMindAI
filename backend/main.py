import os, json, asyncio, datetime
from typing import Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
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
ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:5173,http://localhost:3000"
).split(",")

# ── App setup ─────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="AgroMind AI Backend", version="3.0.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
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
    print("AgroMind Backend v3.0 started. DB initialized.")

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
async def sensor_history(limit: int = 100):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
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
