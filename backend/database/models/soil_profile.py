from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from database.connection import Base


class SoilProfile(Base):
    __tablename__ = "soil_profiles"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    soil_name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    water_retention: Mapped[float | None] = mapped_column(Float, nullable=True)
    drainage_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    evaporation_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    moisture_recovery: Mapped[float | None] = mapped_column(Float, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
