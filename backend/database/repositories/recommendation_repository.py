from __future__ import annotations

from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.recommendation import Recommendation
from database.repositories.base import BaseRepository


class RecommendationRepository(BaseRepository):
    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def create(self, **kwargs) -> Recommendation:
        recommendation = Recommendation(**kwargs)
        self.session.add(recommendation)
        await self.session.commit()
        await self.session.refresh(recommendation)
        return recommendation

    async def list_by_farm(self, farm_id: str, limit: int = 20) -> List[Recommendation]:
        result = await self.session.execute(
            select(Recommendation)
            .where(Recommendation.farm_id == farm_id)
            .order_by(Recommendation.timestamp.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
