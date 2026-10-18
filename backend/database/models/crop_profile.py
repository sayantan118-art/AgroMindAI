from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from database.connection import Base


class CropProfile(Base):
    __tablename__ = "crop_profiles"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    growth_stage: Mapped[str | None] = mapped_column(String(100), nullable=True)
    ideal_moisture: Mapped[float | None] = mapped_column(Float, nullable=True)
    ideal_temperature: Mapped[float | None] = mapped_column(Float, nullable=True)
    ideal_humidity: Mapped[float | None] = mapped_column(Float, nullable=True)
    water_demand: Mapped[float | None] = mapped_column(Float, nullable=True)
    stress_threshold: Mapped[float | None] = mapped_column(Float, nullable=True)
    yield_target: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
