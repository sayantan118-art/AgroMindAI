import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

from database.connection import init_db, get_async_session
from database.repositories import FarmRepository, SensorReadingRepository


@pytest.mark.asyncio
async def test_farm_and_sensor_repository_round_trip(tmp_path):
    db_path = tmp_path / "agromind_test.sqlite"
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{db_path}"

    await init_db(force=True)
    async with get_async_session() as session:
        farm_repo = FarmRepository(session)
        farm = await farm_repo.create(
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

        assert farm.id is not None

        sensor_repo = SensorReadingRepository(session)
        reading = await sensor_repo.create(
            farm_id=farm.id,
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
        )

        assert reading.id is not None
        latest = await sensor_repo.get_latest_by_farm(farm.id)
        assert latest is not None
        assert latest.soil_moisture == 41.2
