import os
import json
import asyncio
import datetime
import logging
from typing import Any, Optional

import httpx
import mqtt_worker
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.requests import Request
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession

from irrigation_service import IrrigationService
from farm_simulation import VirtualFarmEngine
from database.connection import SessionFactory, init_db
from database.repositories import (
    ActivityRepository,
    FarmRepository,
    NotificationRepository,
    RecommendationRepository,
    ReportRepository,
    SensorReadingRepository,
    SimulationRepository,
    WeatherRepository,
)
from database.seed import seed_if_needed
from database import connection as db_connection
from database.migrations_runner import run_pending_migrations
from analysis.service import AnalyzeService, AnalysisTooFrequent
from analysis.quota_manager import QuotaManager
from analysis.safety_gate import SafetyGate

load_dotenv()

# ── Config ────────────────────────────────────────────────────
DB_PATH = os.getenv("DB_PATH", "agromind.db")
OPEN_METEO_URL = os.getenv("OPEN_METEO_URL", "https://api.open-meteo.com/v1/forecast")
LAT = os.getenv("LATITUDE", "22.5726")
LON = os.getenv("LONGITUDE", "88.3639")
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("agromind.main")

# ── App setup ─────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="AgroMind AI Backend", version="3.0.0")
app.state.limiter = limiter
app.state.irrigation_service = IrrigationService()
app.state.virtual_farm_engine = VirtualFarmEngine()


def _rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return _rate_limit_exceeded_handler(request, exc)


app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)

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


async def _get_primary_farm_id(session: AsyncSession) -> str:
    farm_repo = FarmRepository(session)
    farms = await farm_repo.list_active()
    if farms:
        return farms[0].id

    farm = await farm_repo.create(
        name="Default Farm",
        description="Auto-created default farm",
        location="Kolkata",
        latitude=float(LAT),
        longitude=float(LON),
        area=100.0,
        crop="Tomato",
        soil_type="Loam",
        climate="Warm",
        mode="Virtual",
        active=True,
    )
    return farm.id


async def _persist_sensor_reading(data: "SensorLog") -> dict[str, Any]:
    async with SessionFactory() as session:
        farm_id = await _get_primary_farm_id(session)
        reading_repo = SensorReadingRepository(session)
        reading = await reading_repo.create(
            farm_id=farm_id,
            device_id=None,
            soil_moisture=data.soil_moisture,
            temperature=data.temperature,
            humidity=data.humidity,
            light=data.light,
            rain=bool(data.rain_detected),
            wind_speed=None,
            uv_index=None,
            air_pressure=None,
            timestamp=datetime.datetime.utcnow(),
        )

        recommendation_repo = RecommendationRepository(session)
        await recommendation_repo.create(
            farm_id=farm_id,
            decision=data.decision,
            confidence=data.confidence,
            reason=data.reason,
            risk_level=data.risk_level,
            generated_by="api",
            timestamp=datetime.datetime.utcnow(),
            approved=False,
        )

        activity_repo = ActivityRepository(session)
        await activity_repo.create(
            farm_id=farm_id,
            action_type="sensor_reading",
            message="Sensor reading persisted",
            metadata_json=json.dumps({"decision": data.decision}),
            created_at=datetime.datetime.utcnow(),
        )

        return {
            "id": reading.id,
            "farm_id": farm_id,
            "soil_moisture": reading.soil_moisture,
            "temperature": reading.temperature,
            "humidity": reading.humidity,
            "light": reading.light,
            "rain": reading.rain,
        }


def _log_db_location(db_path: str) -> None:
    """Log the resolved DB location (no secrets) and warn if it looks ephemeral."""
    try:
        logger.info("Resolved DB location: %s", db_path)
        url = db_connection.get_database_url()
        if url.startswith("sqlite"):
            # A relative DB_PATH or one inside the code dir is ephemeral on hosts
            # like Render's free tier; durable storage needs a persistent disk or
            # DATABASE_URL pointing at managed Postgres (see docs).
            code_dir = os.path.abspath(os.path.dirname(__file__))
            if os.path.abspath(db_path).startswith(code_dir) and not os.getenv("DATABASE_URL"):
                logger.warning(
                    "DB_PATH %s resolves inside the deployed code directory. On hosts with an "
                    "ephemeral filesystem (e.g. Render free tier) this DB — including quota cooldown "
                    "state and analysis reports — is LOST on redeploy/restart. Attach a persistent "
                    "disk and point DB_PATH at it, or set DATABASE_URL to managed Postgres.",
                    db_path,
                )
    except Exception as exc:  # pragma: no cover
        logger.debug("DB location logging failed: %s", exc)


@app.on_event("startup")
async def startup():
    try:
        await init_db()
        await seed_if_needed()
        # Forward-only, idempotent migrations (ALTER existing tables + create new
        # ones + backfill crop-profile versions). A backup is taken before any
        # pending migration touches an existing populated DB.
        engine = db_connection.engine
        db_path = os.path.abspath(DB_PATH)
        applied = await run_pending_migrations(engine, db_path if str(engine.url).startswith("sqlite") else None)
        if applied:
            logger.info("Applied migrations: %s", applied)
        _log_db_location(db_path)
    except Exception as exc:
        logger.warning("Database initialization failed: %s", exc)

    # Resolve Groq model + lease/backoff from env (kept on the backend only).
    groq_model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    lease_seconds = int(os.getenv("QUOTA_LEASE_SECONDS", "60"))
    backoff_seconds = int(os.getenv("QUOTA_BACKOFF_SECONDS", "300"))

    # Single quota gate over the same DB (SQLite or Postgres via DATABASE_URL).
    # The atomic claim is a conditional UPDATE inside a transaction, safe across
    # processes (SQLite busy_timeout / Postgres row locks), not just one process.
    quota_manager = QuotaManager.for_session_factory(
        SessionFactory, model=groq_model,
        lease_seconds=lease_seconds, conservative_backoff_seconds=backoff_seconds,
    )

    app.state.quota_manager = quota_manager
    app.state.analyze_service = AnalyzeService(
        SessionFactory, quota_manager, groq_model=groq_model,
        cache_ttl_seconds=int(os.getenv("ANALYSIS_CACHE_TTL_SECONDS", "1800")),
        min_interval_seconds=int(os.getenv("MIN_ANALYZE_INTERVAL_SECONDS", "15")),
    )
    app.state.safety_gate = SafetyGate(
        SessionFactory, publish_fn=mqtt_worker.publish_pump,
    )

    loop = asyncio.get_running_loop()
    mqtt_worker.init(loop, ws_clients, DB_PATH)
    mqtt_worker.start()
    print("AgroMind Backend v3.1 started. DB initialized + migrations applied. MQTT worker launched.")

# ── Models ────────────────────────────────────────────────────
class SensorLog(BaseModel):
    model_config = ConfigDict(extra="ignore")

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
    model_config = ConfigDict(extra="ignore")

    action: str
    duration_sec: int = 0


class IrrigationRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    sensor_data: dict[str, Any]
    weather_data: Optional[dict[str, Any]] = None


class ReportData(BaseModel):
    model_config = ConfigDict(extra="ignore")

    date: str
    summary: str
    stats: dict[str, Any] = {}

# ── Endpoints ─────────────────────────────────────────────────

@app.post("/sensor/log")
async def log_sensor(data: SensorLog):
    await _persist_sensor_reading(data)
    payload = data.model_dump()
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
    async with SessionFactory() as session:
        repo = SensorReadingRepository(session)
        row = await repo.get_latest_by_farm((await _get_primary_farm_id(session)))
    if not row:
        return {"message": "No data yet"}
    return {
        "id": row.id,
        "farm_id": row.farm_id,
        "soil_moisture": row.soil_moisture,
        "temperature": row.temperature,
        "humidity": row.humidity,
        "light": row.light,
        "rain_detected": bool(row.rain),
        "timestamp": row.timestamp.isoformat() if row.timestamp else None,
        "created_at": row.created_at.isoformat(),
    }


@app.get("/sensor/history")
async def sensor_history(limit: int = 100):
    async with SessionFactory() as session:
        farm_id = await _get_primary_farm_id(session)
        repo = SensorReadingRepository(session)
        rows = await repo.list_by_farm(farm_id, limit=limit)
    return [
        {
            "id": row.id,
            "farm_id": row.farm_id,
            "soil_moisture": row.soil_moisture,
            "temperature": row.temperature,
            "humidity": row.humidity,
            "light": row.light,
            "rain_detected": bool(row.rain),
            "timestamp": row.timestamp.isoformat() if row.timestamp else None,
            "created_at": row.created_at.isoformat(),
        }
        for row in rows
    ]


@app.post("/irrigation/recommend")
async def irrigation_recommend(data: IrrigationRequest):
    service = app.state.irrigation_service
    result = service.build_recommendation(data.sensor_data, data.weather_data)
    return {
        "decision": result.decision,
        "recommended_duration_minutes": result.recommended_duration_minutes,
        "priority": result.priority,
        "reasons": result.reasons,
        "confidence": result.confidence,
        "validation_status": result.validation_status,
        "alerts": result.alerts,
    }


@app.get("/farms")
async def list_virtual_farms():
    async with SessionFactory() as session:
        repo = FarmRepository(session)
        farms = await repo.list_active()
    return [
        {
            "id": farm.id,
            "name": farm.name,
            "location": farm.location,
            "lat": farm.latitude,
            "lon": farm.longitude,
            "crop": farm.crop,
            "soil": farm.soil_type,
            "climate": farm.climate,
            "area_acres": farm.area,
            "description": farm.description,
            "health_score": 80.0,
            "recommendation": "STABLE",
            "pump_status": "OFF",
        }
        for farm in farms
    ]


@app.get("/farms/{farm_id}")
async def get_virtual_farm(farm_id: str):
    async with SessionFactory() as session:
        farm_repo = FarmRepository(session)
        farm = await farm_repo.get_by_id(farm_id)
        if not farm:
            return {"error": "Farm not found"}

        sensor_repo = SensorReadingRepository(session)
        weather_repo = WeatherRepository(session)
        activity_repo = ActivityRepository(session)
        simulation_repo = SimulationRepository(session)
        readings = await sensor_repo.list_by_farm(farm_id, limit=24)
        weather_rows = await weather_repo.list_by_farm(farm_id, limit=12)
        activities = await activity_repo.list_by_farm(farm_id, limit=12)
        simulation_state = await simulation_repo.get_by_farm(farm_id)

    latest = readings[0] if readings else None
    history = [
        {
            "ts": reading.timestamp.isoformat() if reading.timestamp else reading.created_at.isoformat(),
            "temperature": reading.temperature,
            "humidity": reading.humidity,
            "soil_moisture": reading.soil_moisture,
            "rain_probability": 0.0,
            "wind_speed": None,
            "light_level": reading.light,
            "uv_index": None,
            "tank_level": 80.0,
            "health_score": 80.0,
            "recommendation": "STABLE",
            "alerts": [],
        }
        for reading in reversed(readings)
    ]
    timeline = [
        {
            "ts": activity.created_at.isoformat(),
            "event": activity.action_type,
            "message": activity.message,
        }
        for activity in activities
    ]
    return {
        "farm": {
            "id": farm.id,
            "name": farm.name,
            "crop": farm.crop,
            "soil": farm.soil_type,
            "climate": farm.climate,
            "area_acres": farm.area,
            "description": farm.description,
        },
        "status": {
            "temperature": latest.temperature if latest else None,
            "humidity": latest.humidity if latest else None,
            "soil_moisture": latest.soil_moisture if latest else None,
            "rain_probability": weather_rows[0].rain_probability if weather_rows else 0.0,
            "wind_speed": weather_rows[0].wind if weather_rows else None,
            "light_level": latest.light if latest else None,
            "uv_index": weather_rows[0].uv if weather_rows else None,
            "tank_level": simulation_state.current_tank_level if simulation_state else 80.0,
            "health_score": simulation_state.crop_health if simulation_state else 80.0,
            "pump_status": simulation_state.pump_status if simulation_state else "OFF",
            "recommendation": "STABLE",
            "recommendation_reason": "Database-driven status",
            "alerts": [],
        },
        "history": history,
        "timeline": timeline,
        "metrics": {
            "avg_soil_moisture": round(sum(item["soil_moisture"] or 0 for item in history) / max(1, len(history)), 1),
            "avg_temperature": round(sum(item["temperature"] or 0 for item in history) / max(1, len(history)), 1),
            "avg_humidity": round(sum(item["humidity"] or 0 for item in history) / max(1, len(history)), 1),
            "latest_recommendation": "STABLE",
        },
    }


@app.get("/weather/forecast")
async def weather_forecast():
    params: dict[str, Any] = {
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
        rain_prob = (hourly.get("precipitation_probability") or [0])[0]
        payload = {
            "rain_probability_next_hour": rain_prob,
            "rain_expected": rain_prob > 50,
            "precipitation_probability_max": (daily.get("precipitation_probability_max") or [0])[0],
            "temperature_2m_max": (daily.get("temperature_2m_max") or [None])[0],
        }

        async with SessionFactory() as session:
            farm_id = await _get_primary_farm_id(session)
            weather_repo = WeatherRepository(session)
            await weather_repo.create(
                farm_id=farm_id,
                temperature=float(payload.get("temperature_2m_max") or 25.0),
                humidity=60.0,
                wind=8.0,
                forecast="Forecast persisted",
                rain_probability=float(rain_prob or 0),
                uv=4.0,
                weather_description="Persisted from forecast endpoint",
                timestamp=datetime.datetime.utcnow(),
            )
        return payload
    except Exception as e:
        return {"rain_probability_next_hour": 0, "rain_expected": False, "error": str(e)}


@app.post("/pump/log")
async def log_pump(action: PumpAction):
    async with SessionFactory() as session:
        farm_id = await _get_primary_farm_id(session)
        recommendation_repo = RecommendationRepository(session)
        recommendations = await recommendation_repo.list_by_farm(farm_id, limit=1)
        recommendation_id = recommendations[0].id if recommendations else None
        event_repo = ActivityRepository(session)
        await event_repo.create(
            farm_id=farm_id,
            action_type="pump_event",
            message=f"Pump {action.action}",
            metadata_json=json.dumps({"duration_sec": action.duration_sec}),
            created_at=datetime.datetime.utcnow(),
        )
        if recommendation_id:
            from database.models.irrigation_event import IrrigationEvent
            session.add(IrrigationEvent(
                farm_id=farm_id,
                recommendation_id=recommendation_id,
                pump_started=datetime.datetime.utcnow(),
                pump_stopped=datetime.datetime.utcnow(),
                duration=float(action.duration_sec),
                water_used=float(action.duration_sec) * 0.2,
                tank_before=80.0,
                tank_after=78.0,
                status=action.action,
            ))
        await session.commit()
    return {"status": "logged"}


@app.get("/pump/usage/today")
async def pump_usage_today():
    today = datetime.date.today().isoformat()
    async with SessionFactory() as session:
        from database.models.irrigation_event import IrrigationEvent
        from sqlalchemy import select
        result = await session.execute(
            select(IrrigationEvent).where(IrrigationEvent.created_at >= datetime.datetime.combine(datetime.date.today(), datetime.time.min))
        )
        rows = result.scalars().all()
    return {
        "date": today,
        "total_on_seconds": sum(int(event.duration or 0) for event in rows),
        "events": [
            {
                "action": event.status,
                "duration_sec": int(event.duration or 0),
                "ts": event.created_at.isoformat() if event.created_at else None,
            }
            for event in rows
        ],
    }

# ── Report endpoints ──────────────────────────────────────────

@app.post("/report/save")
async def save_report(data: ReportData):
    async with SessionFactory() as session:
        farm_id = await _get_primary_farm_id(session)
        report_repo = ReportRepository(session)
        await report_repo.create(
            farm_id=farm_id,
            report_type="daily",
            title=data.summary,
            summary=data.summary,
            metadata_json=json.dumps(data.stats),
            generated_at=datetime.datetime.fromisoformat(data.date) if data.date else datetime.datetime.utcnow(),
        )
    return {"status": "saved", "date": data.date}


@app.get("/report/list")
async def list_reports(limit: int = 30):
    async with SessionFactory() as session:
        repo = ReportRepository(session)
        rows = await repo.list_recent(limit=limit)
    return [
        {
            "date": row.generated_at.date().isoformat(),
            "summary": row.summary or row.title,
            "created_at": row.created_at.isoformat(),
        }
        for row in rows
    ]


@app.get("/report/{date}")
async def get_report(date: str):
    async with SessionFactory() as session:
        from database.models.report import Report
        from sqlalchemy import select
        result = await session.execute(select(Report).where(Report.generated_at >= datetime.datetime.fromisoformat(date)))
        row = result.scalar_one_or_none()
    if not row:
        return {"error": "Report not found"}
    return {
        "id": row.id,
        "date": row.generated_at.date().isoformat(),
        "summary": row.summary or row.title,
        "stats": json.loads(row.metadata_json or "{}"),
        "created_at": row.created_at.isoformat(),
    }

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
        "version": "3.1.0",
        "time": datetime.datetime.now().isoformat()
    }


# ── On-demand analysis endpoints (Groq behind the quota gate + rule engine) ──
class AnalyzeRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    force: bool = False


async def _primary_farm_id() -> str:
    async with SessionFactory() as session:
        return await _get_primary_farm_id(session)


@app.post("/analysis/analyze")
async def analyze_crop_health(request: AnalyzeRequest, fastapi_request: Request):
    """User-triggered crop-health analysis. Exactly one Groq call may happen,
    only after the persistent quota gate allows it; otherwise a deterministic
    rule-engine report is returned. Never auto-invoked by sensor data.
    """
    service: AnalyzeService = app.state.analyze_service
    farm_id = await _primary_farm_id()
    client_id = get_remote_address(fastapi_request)
    groq_key = os.getenv("GROQ_API_KEY", "") or None
    try:
        response = await service.analyze(
            farm_id=farm_id, client_id=client_id, force=request.force,
            groq_api_key=groq_key,
        )
    except AnalysisTooFrequent as exc:
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=429,
            content={"error": "too_frequent", "retry_after_seconds": exc.retry_after_seconds},
            headers={"Retry-After": str(exc.retry_after_seconds)},
        )
    return response.model_dump()


@app.get("/analysis/reports")
async def list_analysis_reports(limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0)):
    """Paginated, newest-first history of analysis reports (read-only)."""
    from database.repositories.analysis_repository import list_reports
    farm_id = await _primary_farm_id()
    return {"reports": await list_reports(SessionFactory, farm_id=farm_id, limit=limit, offset=offset)}


@app.get("/analysis/reports/{report_id}")
async def get_analysis_report(report_id: str):
    from database.repositories.analysis_repository import get_report
    row = await get_report(SessionFactory, report_id)
    if row is None:
        return {"error": "Report not found"}
    return row


@app.get("/analysis/quota/status")
async def analysis_quota_status():
    """Human-readable quota/cooldown state (no secrets, no key)."""
    manager: QuotaManager = app.state.quota_manager
    view = await manager.get_view(os.getenv("GROQ_API_KEY", "") or None)
    return view.to_dict()


# ── Manual pump control (actuation only through the safety gate) ─────────────
class PumpControlRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    action: str
    duration_sec: int = 0


@app.post("/pump/control")
async def pump_control(request: PumpControlRequest, fastapi_request: Request):
    """Manual, user-triggered pump command. Passes through the standalone
    safety gate (180s cap, 10/day, sensor validity, min interval) and writes an
    audit record before publishing. Analysis reports never reach this path.
    """
    gate: SafetyGate = app.state.safety_gate
    farm_id = await _primary_farm_id()
    sensor_snapshot = None
    crop_name = None
    async with SessionFactory() as session:
        farm = await FarmRepository(session).get_by_id(farm_id)
        crop_name = farm.crop if farm else None
        latest = await SensorReadingRepository(session).get_latest_by_farm(farm_id)
        if latest:
            sensor_snapshot = {
                "soil_moisture": latest.soil_moisture,
                "temperature": latest.temperature,
                "humidity": latest.humidity,
                "rain": bool(latest.rain) if latest.rain is not None else None,
            }
    decision, published, audit_id = await gate.actuate(
        action=request.action, duration_sec=request.duration_sec, farm_id=farm_id,
        crop_name=crop_name, sensor_snapshot=sensor_snapshot,
        source="manual_ui", actor=get_remote_address(fastapi_request),
    )
    return {
        "allowed": decision.allowed,
        "action": decision.action,
        "duration_sec": decision.duration_sec,
        "clamped": decision.clamped,
        "reason": decision.reason,
        "published": published,
        "audit_id": audit_id,
    }
