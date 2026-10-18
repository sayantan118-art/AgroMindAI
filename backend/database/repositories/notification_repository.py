from __future__ import annotations

from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.notification import Notification
from database.repositories.base import BaseRepository


class NotificationRepository(BaseRepository):
    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def create(self, **kwargs) -> Notification:
        notification = Notification(**kwargs)
        self.session.add(notification)
        await self.session.commit()
        await self.session.refresh(notification)
        return notification

    async def list_by_farm(self, farm_id: str, limit: int = 20) -> List[Notification]:
        result = await self.session.execute(
            select(Notification)
            .where(Notification.farm_id == farm_id)
            .order_by(Notification.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
