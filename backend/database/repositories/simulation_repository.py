from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.simulation_state import SimulationState
from database.repositories.base import BaseRepository


class SimulationRepository(BaseRepository):
    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def get_by_farm(self, farm_id: str) -> SimulationState | None:
        result = await self.session.execute(select(SimulationState).where(SimulationState.farm_id == farm_id))
        return result.scalar_one_or_none()

    async def upsert(self, farm_id: str, **kwargs) -> SimulationState:
        existing = await self.get_by_farm(farm_id)
        if existing:
            for key, value in kwargs.items():
                setattr(existing, key, value)
            self.session.add(existing)
            await self.session.commit()
            await self.session.refresh(existing)
            return existing
        row = SimulationState(farm_id=farm_id, **kwargs)
        self.session.add(row)
        await self.session.commit()
        await self.session.refresh(row)
        return row
