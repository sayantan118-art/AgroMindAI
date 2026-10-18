from __future__ import annotations

from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.sensor_reading import SensorReading
from database.repositories.base import BaseRepository


class SensorReadingRepository(BaseRepository):
    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def create(self, **kwargs) -> SensorReading:
        reading = SensorReading(**kwargs)
        self.session.add(reading)
        await self.session.commit()
        await self.session.refresh(reading)
        return reading

    async def get_latest_by_farm(self, farm_id: str) -> SensorReading | None:
        result = await self.session.execute(
            select(SensorReading)
            .where(SensorReading.farm_id == farm_id)
            .order_by(SensorReading.created_at.desc())
        )
        return result.scalar_one_or_none()

    async def list_by_farm(self, farm_id: str, limit: int = 100) -> List[SensorReading]:
        result = await self.session.execute(
            select(SensorReading)
            .where(SensorReading.farm_id == farm_id)
            .order_by(SensorReading.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
