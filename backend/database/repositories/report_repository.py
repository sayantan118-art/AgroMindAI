from __future__ import annotations

from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.report import Report
from database.repositories.base import BaseRepository


class ReportRepository(BaseRepository):
    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def create(self, **kwargs) -> Report:
        report = Report(**kwargs)
        self.session.add(report)
        await self.session.commit()
        await self.session.refresh(report)
        return report

    async def list_recent(self, limit: int = 20) -> List[Report]:
        result = await self.session.execute(select(Report).order_by(Report.generated_at.desc()).limit(limit))
        return list(result.scalars().all())
