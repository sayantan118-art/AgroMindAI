from __future__ import annotations

from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.weather_history import WeatherHistory
from database.repositories.base import BaseRepository


class WeatherRepository(BaseRepository):
    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def create(self, **kwargs) -> WeatherHistory:
        row = WeatherHistory(**kwargs)
        self.session.add(row)
        await self.session.commit()
        await self.session.refresh(row)
        return row

    async def list_by_farm(self, farm_id: str, limit: int = 20) -> List[WeatherHistory]:
        result = await self.session.execute(
            select(WeatherHistory)
            .where(WeatherHistory.farm_id == farm_id)
            .order_by(WeatherHistory.timestamp.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
