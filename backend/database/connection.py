from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

load_dotenv()


class Base(DeclarativeBase):
    pass


def get_database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if url:
        return url

    db_path = os.getenv("DB_PATH")
    if db_path:
        return f"sqlite+aiosqlite:///{os.path.abspath(db_path)}"

    user = os.getenv("POSTGRES_USER", "agromind")
    password = os.getenv("POSTGRES_PASSWORD", "agromind")
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    db = os.getenv("POSTGRES_DB", "agromind")
    return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{db}"


engine: AsyncEngine | None = None
SessionFactory = None


class _SessionFactoryProxy:
    def __call__(self):
        return get_session_factory()()


def get_session_factory():
    global engine, SessionFactory
    if SessionFactory is None or engine is None:
        engine = create_async_engine(get_database_url(), echo=False, future=True)
        SessionFactory = async_sessionmaker(engine, expire_on_commit=False)
    return SessionFactory


SessionFactory = _SessionFactoryProxy()


async def init_db(force: bool = False) -> None:
    from database.models import (
        ActivityTimeline,
        CropProfile,
        Device,
        Farm,
        IrrigationEvent,
        Notification,
        Recommendation,
        Report,
        RuleTrigger,
        SensorReading,
        SimulationState,
        SoilProfile,
        WeatherHistory,
    )

    if engine is None:
        get_session_factory()

    assert engine is not None
    async with engine.begin() as conn:
        if force:
            await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)


@asynccontextmanager
async def get_async_session() -> AsyncIterator[AsyncSession]:
    factory = get_session_factory()
    async with factory() as session:
        yield session
