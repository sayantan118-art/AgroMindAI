from __future__ import annotations

import uuid
from datetime import datetime
from typing import List

from sqlalchemy import Boolean, DateTime, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.connection import Base


class Farm(Base):
    __tablename__ = "farms"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    area: Mapped[float | None] = mapped_column(Float, nullable=True)
    crop: Mapped[str | None] = mapped_column(String(255), nullable=True)
    soil_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    climate: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mode: Mapped[str] = mapped_column(String(50), default="Virtual")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    devices: Mapped[List["Device"]] = relationship(back_populates="farm", cascade="all, delete-orphan")
    sensor_readings: Mapped[List["SensorReading"]] = relationship(back_populates="farm", cascade="all, delete-orphan")
    weather_history: Mapped[List["WeatherHistory"]] = relationship(back_populates="farm", cascade="all, delete-orphan")
    recommendations: Mapped[List["Recommendation"]] = relationship(back_populates="farm", cascade="all, delete-orphan")
    irrigation_events: Mapped[List["IrrigationEvent"]] = relationship(back_populates="farm", cascade="all, delete-orphan")
    rule_triggers: Mapped[List["RuleTrigger"]] = relationship(back_populates="farm", cascade="all, delete-orphan")
    notifications: Mapped[List["Notification"]] = relationship(back_populates="farm", cascade="all, delete-orphan")
    activities: Mapped[List["ActivityTimeline"]] = relationship(back_populates="farm", cascade="all, delete-orphan")
    reports: Mapped[List["Report"]] = relationship(back_populates="farm", cascade="all, delete-orphan")
    simulation_state: Mapped["SimulationState | None"] = relationship(back_populates="farm", uselist=False, cascade="all, delete-orphan")
