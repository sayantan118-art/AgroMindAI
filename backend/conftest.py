"""Shared pytest fixtures.

Each test gets a fresh temp SQLite DB (init + migrations + seed), an
injectable clock, a mocked weather fetcher, and ready-to-use service instances.
Groq is always mocked in tests (we never spend real quota).
"""

from __future__ import annotations

import datetime
import os
from datetime import timedelta, timezone

import pytest


@pytest.fixture
def fixed_clock():
    """Injectable clock: starts at a fixed UTC instant; ``advance(s)`` moves it."""
    start = datetime.datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    state = {"now": start}

    def now():
        return state["now"]

    now.advance = lambda seconds=1: state.update(now=state["now"] + timedelta(seconds=seconds))  # type: ignore[attr-defined]
    now.set = lambda dt: state.update(now=dt)  # type: ignore[attr-defined]
    return now


@pytest.fixture
async def temp_db(tmp_path, monkeypatch):
    """Fresh temp SQLite DB with migrations + seed applied."""
    db_path = tmp_path / "test.sqlite"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    import database.connection as conn
    from database.connection import _SessionFactoryProxy
    conn.engine = None
    conn.SessionFactory = _SessionFactoryProxy()  # stable indirection; recreates engine from new env
    from database.connection import init_db
    from database.migrations_runner import run_pending_migrations
    from database.seed import seed_if_needed
    await init_db()
    await run_pending_migrations(conn.engine, str(db_path))
    await seed_if_needed()
    yield conn.SessionFactory
    try:
        if conn.engine is not None:
            await conn.engine.dispose()
    except Exception:
        pass
    conn.engine = None
    conn.SessionFactory = None


@pytest.fixture
def weather_stub():
    async def _f(session_factory):
        return {
            "rain_probability_next_hour": 10,
            "temperature_2m_max": 28.0,
            "rain_expected": False,
            "source": "test",
        }
    return _f


@pytest.fixture
def services(temp_db, fixed_clock, weather_stub):
    from analysis.quota_manager import QuotaManager
    from analysis.service import AnalyzeService
    from analysis.safety_gate import SafetyGate
    qm = QuotaManager.for_session_factory(temp_db, clock=fixed_clock)
    svc = AnalyzeService(
        temp_db, qm, clock=fixed_clock, weather_fetcher=weather_stub,
        cache_ttl_seconds=1800, min_interval_seconds=0,
    )
    gate = SafetyGate(temp_db, clock=fixed_clock, publish_fn=lambda a, d: True)
    return {"session_factory": temp_db, "quota": qm, "service": svc, "gate": gate, "clock": fixed_clock}


async def primary_farm_id(session_factory) -> str:
    from database.repositories import FarmRepository
    async with session_factory() as session:
        farms = await FarmRepository(session).list_active()
        return farms[0].id


async def add_reading(session_factory, *, farm_id, soil=45.0, temp=26.0, hum=65.0,
                      light=2000.0, rain=False, age_seconds=0, quality_status="ok"):
    from database.repositories import SensorReadingRepository
    now = datetime.datetime.utcnow() - timedelta(seconds=age_seconds)
    async with session_factory() as session:
        repo = SensorReadingRepository(session)
        return await repo.create(
            farm_id=farm_id, device_id=None,
            soil_moisture=soil, temperature=temp, humidity=hum, light=light,
            rain=rain, timestamp=now, received_at=now,
            quality_status=quality_status,
        )
