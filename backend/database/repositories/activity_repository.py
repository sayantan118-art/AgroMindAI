from __future__ import annotations

from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.activity_timeline import ActivityTimeline
from database.repositories.base import BaseRepository


class ActivityRepository(BaseRepository):
    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def create(self, **kwargs) -> ActivityTimeline:
        activity = ActivityTimeline(**kwargs)
        self.session.add(activity)
        await self.session.commit()
        await self.session.refresh(activity)
        return activity

    async def list_by_farm(self, farm_id: str, limit: int = 20) -> List[ActivityTimeline]:
        result = await self.session.execute(
            select(ActivityTimeline)
            .where(ActivityTimeline.farm_id == farm_id)
            .order_by(ActivityTimeline.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
