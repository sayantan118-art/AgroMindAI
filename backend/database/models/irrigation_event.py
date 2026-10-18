from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.connection import Base


class IrrigationEvent(Base):
    __tablename__ = "irrigation_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    farm_id: Mapped[str] = mapped_column(ForeignKey("farms.id", ondelete="CASCADE"), index=True)
    recommendation_id: Mapped[str | None] = mapped_column(ForeignKey("recommendations.id", ondelete="SET NULL"), index=True, nullable=True)
    pump_started: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    pump_stopped: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration: Mapped[float | None] = mapped_column(Float, nullable=True)
    water_used: Mapped[float | None] = mapped_column(Float, nullable=True)
    tank_before: Mapped[float | None] = mapped_column(Float, nullable=True)
    tank_after: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    farm: Mapped["Farm"] = relationship(back_populates="irrigation_events")
