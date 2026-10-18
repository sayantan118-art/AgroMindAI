from __future__ import annotations

from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.farm import Farm
from database.repositories.base import BaseRepository


class FarmRepository(BaseRepository):
    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def create(self, **kwargs) -> Farm:
        farm = Farm(**kwargs)
        self.session.add(farm)
        await self.session.commit()
        await self.session.refresh(farm)
        return farm

    async def list_active(self) -> List[Farm]:
        result = await self.session.execute(select(Farm).where(Farm.active.is_(True)).order_by(Farm.created_at.desc()))
        return list(result.scalars().all())

    async def get_by_id(self, farm_id: str) -> Farm | None:
        result = await self.session.execute(select(Farm).where(Farm.id == farm_id))
        return result.scalar_one_or_none()
