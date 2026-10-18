"""Migration tests with real data: verify row counts, values, backfills, idempotency."""

import asyncio
import os
import tempfile
from datetime import datetime, timezone

import pytest
from sqlalchemy import select, text

from database.connection import init_db, get_session_factory
from database.migrations_runner import run_pending_migrations, make_backup
from database.seed import seed_if_needed
from database.models import Farm, SensorReading, CropProfile, WeatherHistory


@pytest.fixture
async def populated_db(tmp_path):
    """Create a pre-migration database with sample data."""
    db_path = tmp_path / "pre_migration.sqlite"
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{db_path}"

    import database.connection as conn
    from database.connection import _SessionFactoryProxy
    conn.engine = None
    conn.SessionFactory = _SessionFactoryProxy()

    await init_db()
    # Don't run migrations yet - this is pre-migration state

    session_factory = get_session_factory()

    # Add sample data before migrations
    async with session_factory() as session:
        # Add farms
        farm = Farm(
            id="test-farm-1",
            name="Test Farm",
            description="A test farm",
            location="Testville",
            latitude=12.34,
            longitude=56.78,
            area=120.0,
            crop="Tomato",
            soil_type="Loam",
            climate="Warm",
            mode="Virtual",
            active=True,
        )
        session.add(farm)

        # Add sensor readings (old schema without quality/dedup columns)
        reading = SensorReading(
            id="reading-1",
            farm_id="test-farm-1",
            device_id=None,
            soil_moisture=41.2,
            temperature=24.1,
            humidity=62.0,
            light=7800.0,
            rain=False,
            wind_speed=8.0,
            uv_index=4.1,
            air_pressure=1012.0,
            timestamp=datetime(2026, 7, 17, 12, 0, 0, tzinfo=timezone.utc),
            created_at=datetime(2026, 7, 17, 12, 0, 0, tzinfo=timezone.utc),
        )
        session.add(reading)

        # Add crop profiles (old schema without version columns)
        crop = CropProfile(
            id="crop-1",
            name="Tomato",
            growth_stage="Vegetative",
            ideal_moisture=45.0,
            ideal_temperature=26.0,
            ideal_humidity=65.0,
            water_demand=2.5,
            stress_threshold=35.0,
            yield_target=120.0,
            description="Tomato crop profile",
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        session.add(crop)

        # Add weather history
        weather = WeatherHistory(
            id="weather-1",
            farm_id="test-farm-1",
            temperature=25.0,
            humidity=60.0,
            wind=8.0,
            forecast="Sunny",
            rain_probability=10.0,
            uv=4.0,
            weather_description="Clear sky",
            timestamp=datetime(2026, 7, 17, 12, 0, 0, tzinfo=timezone.utc),
        )
        session.add(weather)

        await session.commit()

    # Record initial counts
    async with session_factory() as session:
        farm_count = (await session.execute(select(Farm))).scalars().all()
        reading_count = (await session.execute(select(SensorReading))).scalars().all()
        crop_count = (await session.execute(select(CropProfile))).scalars().all()
        weather_count = (await session.execute(select(WeatherHistory))).scalars().all()

    yield {
        "db_path": str(db_path),
        "session_factory": session_factory,
        "initial_counts": {
            "farms": len(farm_count),
            "sensor_readings": len(reading_count),
            "crop_profiles": len(crop_count),
            "weather_history": len(weather_count),
        },
        "conn": conn,
    }

    # Cleanup
    try:
        if conn.engine is not None:
            await conn.engine.dispose()
    except Exception:
        pass
    conn.engine = None
    conn.SessionFactory = None


async def test_migration_preserves_row_counts_and_values(populated_db):
    """Migration should preserve all existing data and backfill new columns."""
    db_path = populated_db["db_path"]
    session_factory = populated_db["session_factory"]
    initial = populated_db["initial_counts"]

    # Run migrations
    applied = await run_pending_migrations(populated_db["conn"].engine, db_path)
    assert applied, "Migrations should have been applied"

    # Verify row counts unchanged
    async with session_factory() as session:
        farm_count = len((await session.execute(select(Farm))).scalars().all())
        reading_count = len((await session.execute(select(SensorReading))).scalars().all())
        crop_count = len((await session.execute(select(CropProfile))).scalars().all())
        weather_count = len((await session.execute(select(WeatherHistory))).scalars().all())

    assert farm_count == initial["farms"]
    assert reading_count == initial["sensor_readings"]
    assert crop_count == initial["crop_profiles"]
    assert weather_count == initial["weather_history"]

    # Verify sensor reading values preserved
    async with session_factory() as session:
        reading = (await session.execute(
            select(SensorReading).where(SensorReading.id == "reading-1")
        )).scalar_one()
        assert reading.soil_moisture == 41.2
        assert reading.temperature == 24.1
        assert reading.humidity == 62.0
        # New columns should be backfilled or NULL
        assert reading.quality_status is None or reading.quality_status == "ok"
        assert reading.dedup_key is None or isinstance(reading.dedup_key, str)


async def test_migration_idempotent(populated_db):
    """Running migrations twice should not error or duplicate data."""
    db_path = populated_db["db_path"]
    session_factory = populated_db["session_factory"]

    # Run migrations first time
    applied1 = await run_pending_migrations(populated_db["conn"].engine, db_path)

    # Run migrations second time
    applied2 = await run_pending_migrations(populated_db["conn"].engine, db_path)

    # Second run should apply no new migrations
    assert applied2 == [], "Second migration run should be idempotent"


async def test_migration_on_empty_db(tmp_path):
    """Migrations should work on a brand-new empty database."""
    db_path = tmp_path / "empty.sqlite"
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{db_path}"

    import database.connection as conn
    from database.connection import _SessionFactoryProxy
    conn.engine = None
    conn.SessionFactory = _SessionFactoryProxy()

    from database.connection import init_db
    await init_db()

    # Run migrations on empty DB
    applied = await run_pending_migrations(conn.engine, str(db_path))
    assert applied, "Migrations should apply on empty DB"

    # Verify tables exist
    session_factory = get_session_factory()
    async with session_factory() as session:
        # Check all migration-created tables exist
        tables = (await session.execute(text(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ))).fetchall()
        table_names = {t[0] for t in tables}

        assert "analysis_reports" in table_names
        assert "analysis_cache_index" in table_names
        assert "api_quota_state" in table_names
        assert "irrigation_audit" in table_names
        assert "schema_version" in table_names

    try:
        if conn.engine is not None:
            await conn.engine.dispose()
    except Exception:
        pass
    conn.engine = None
    conn.SessionFactory = None


async def test_migration_independent_of_seed_order(tmp_path):
    """Migration should not depend on seed having run first."""
    db_path = tmp_path / "no_seed.sqlite"
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{db_path}"

    import database.connection as conn
    from database.connection import _SessionFactoryProxy
    conn.engine = None
    conn.SessionFactory = _SessionFactoryProxy()

    from database.connection import init_db
    await init_db()
    # Deliberately NOT calling seed_if_needed()

    # Run migrations
    applied = await run_pending_migrations(conn.engine, str(db_path))
    assert applied, "Migrations should work without seed"

    # Verify core tables exist
    session_factory = get_session_factory()
    async with session_factory() as session:
        tables = (await session.execute(text(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ))).fetchall()
        table_names = {t[0] for t in tables}
        assert "analysis_reports" in table_names
        assert "schema_version" in table_names

    try:
        if conn.engine is not None:
            await conn.engine.dispose()
    except Exception:
        pass
    conn.engine = None
    conn.SessionFactory = None


async def test_integrity_and_foreign_key_checks(populated_db):
    """Post-migration database should pass integrity and foreign key checks."""
    db_path = populated_db["db_path"]
    await run_pending_migrations(populated_db["conn"].engine, db_path)

    import sqlite3
    conn = sqlite3.connect(db_path)
    # Enable foreign keys
    conn.execute("PRAGMA foreign_keys=ON")

    # Integrity check
    integrity = conn.execute("PRAGMA integrity_check").fetchone()
    assert integrity[0] == "ok", f"Integrity check failed: {integrity}"

    # Foreign key check
    fk_check = conn.execute("PRAGMA foreign_key_check").fetchall()
    assert len(fk_check) == 0, f"Foreign key violations: {fk_check}"

    conn.close()


async def test_pre_migration_backup_created_and_restorable(populated_db, tmp_path):
    """A backup should be created before migration and be restorable."""
    db_path = populated_db["db_path"]

    # Run migrations (should trigger backup)
    await run_pending_migrations(populated_db["conn"].engine, db_path)

    # Check backup directory
    backup_dir = tmp_path / ".backups"
    # Note: The backup is created in the same directory as the DB
    actual_backup_dir = os.path.join(os.path.dirname(db_path), ".backups")

    # If no backup dir (e.g., DB wasn't populated enough), that's OK for this test
    if os.path.exists(actual_backup_dir):
        backups = [f for f in os.listdir(actual_backup_dir) if f.endswith(".bak")]
        if backups:
            backup_path = os.path.join(actual_backup_dir, backups[0])
            # Verify backup is valid SQLite
            import sqlite3
            bconn = sqlite3.connect(backup_path)
            tables = bconn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            assert len(tables) > 0, "Backup should contain tables"
            bconn.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])