from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.connection import Base


class SimulationState(Base):
    __tablename__ = "simulation_state"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    farm_id: Mapped[str] = mapped_column(ForeignKey("farms.id", ondelete="CASCADE"), index=True, unique=True)
    current_weather: Mapped[str | None] = mapped_column(Text, nullable=True)
    current_soil_moisture: Mapped[float | None] = mapped_column(Float, nullable=True)
    current_tank_level: Mapped[float | None] = mapped_column(Float, nullable=True)
    crop_health: Mapped[float | None] = mapped_column(Float, nullable=True)
    growth_stage: Mapped[str | None] = mapped_column(String(100), nullable=True)
    pump_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    simulation_time: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_updated: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    farm: Mapped["Farm"] = relationship(back_populates="simulation_state")
