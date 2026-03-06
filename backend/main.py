import os, json, asyncio, datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import aiosqlite, httpx
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="AgroMind AI Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

DB_PATH = os.getenv("DB_PATH", "agromind.db")
OPEN_METEO_URL = os.getenv("OPEN_METEO_URL", "https://api.open-meteo.com/v1/forecast")
LAT = os.getenv("LATITUDE", "22.5726")
LON = os.getenv("LONGITUDE", "88.3639")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:14b")

# Active WebSocket connections
ws_clients: list[WebSocket] = []

# Global location cache
detected_location = {"lat": 20.2961, "lon": 85.8245, "city": "Bhubaneswar"}

# ── DB init ──────────────────────────────────────────────────
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS sensor_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT DEFAULT (datetime('now','localtime')),
                soil_moisture REAL,
                temperature REAL,
                humidity REAL,
                rain_expected INTEGER,
                decision TEXT,
                reason TEXT,
                health_score REAL,
                next_check_minutes INTEGER
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS pump_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT DEFAULT (datetime('now','localtime')),
                action TEXT,
                duration_sec INTEGER
            )
        """)
        await db.commit()

async def detect_location():
    """Auto-detect location from IP using ip-api.com"""
    print("🔍 Detecting location from IP...")
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get("http://ip-api.com/json/")
        data = r.json()
        if data.get("status") == "success":
            lat = data["lat"]
            lon = data["lon"]
            city = data["city"]
            country = data["countryCode"]
            print(f"📍 Location detected: {city}, {country} ({lat}, {lon})")
            return lat, lon, city
    except Exception as e:
        print(f"⚠️ Location detection failed: {e}. Using .env fallback.")
    # Fallback to .env values
    return float(os.getenv("LATITUDE", "20.2961")), \
           float(os.getenv("LONGITUDE", "85.8245")), \
           "Bhubaneswar"

@app.on_event("startup")
async def startup():
    global detected_location
    print(f"📍 Location: {detected_location}")
    await init_db()
    try:
        lat, lon, city = await detect_location()
        detected_location = {"lat": lat, "lon": lon, "city": city}
    except Exception as e:
        print(f"⚠️ Location detection error: {e}")
    print(f"📍 Using location: {detected_location['city']} ({detected_location['lat']}, {detected_location['lon']})")
    print("✅ AgroMind Backend started. DB initialized.")

# ── Models ────────────────────────────────────────────────────
class SensorLog(BaseModel):
    soil_moisture: float
    temperature: float
    humidity: float
    rain_expected: bool
    decision: str
    reason: str
    health_score: float
    next_check_minutes: int

class PumpAction(BaseModel):
    action: str
    duration_sec: int = 0

# ── Endpoints ─────────────────────────────────────────────────

@app.post("/sensor/log")
async def log_sensor(data: SensorLog):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO sensor_logs
               (soil_moisture, temperature, humidity, rain_expected,
                decision, reason, health_score, next_check_minutes)
               VALUES (?,?,?,?,?,?,?,?)""",
            (data.soil_moisture, data.temperature, data.humidity,
             int(data.rain_expected), data.decision, data.reason,
             data.health_score, data.next_check_minutes)
        )
        await db.commit()
    payload = data.model_dump()
    # Notify all connected WebSocket dashboard clients
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
        "latitude": detected_location["lat"],
        "longitude": detected_location["lon"],
        "hourly": "precipitation_probability,rain",
        "forecast_days": 1,
        "timezone": "auto"
    }
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(OPEN_METEO_URL, params=params, timeout=10)
        data = r.json()
        hourly = data.get("hourly", {})
        rain_prob = hourly.get("precipitation_probability", [0])[0]
        return {
            "rain_probability_next_hour": rain_prob,
            "rain_expected": rain_prob > 50,
            "city": detected_location["city"]
        }
    except Exception as e:
        return {
            "rain_probability_next_hour": 0,
            "rain_expected": False,
            "city": detected_location["city"],
            "error": str(e)
        }

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

@app.post("/pump/log")
async def log_pump(action: PumpAction):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO pump_log (action, duration_sec) VALUES (?,?)",
            (action.action, action.duration_sec)
        )
        await db.commit()
    return {"status": "logged"}

# ── WebSocket endpoint for dashboard live updates ─────────────
@app.websocket("/ws/dashboard")
async def ws_dashboard(websocket: WebSocket):
    await websocket.accept()
    ws_clients.append(websocket)
    print(f"🔌 Dashboard connected. Total clients: {len(ws_clients)}")
    try:
        while True:
            await websocket.receive_text()  # keep alive
    except WebSocketDisconnect:
        ws_clients.remove(websocket)
        print(f"🔌 Dashboard disconnected. Total clients: {len(ws_clients)}")

# ── Health check ──────────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "ok", "service": "AgroMind Backend", "time": datetime.datetime.now().isoformat()}
