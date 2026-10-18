from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from database.connection import Base


class IrrigationAudit(Base):
    """Append-only safety audit trail for every pump-command decision.

    A row is written BEFORE publishing to MQTT; if that write fails the pump is
    NOT actuated. ``published``/``published_at`` record the outcome afterwards.
    The durable daily-count and minimum-interval checks read from this table so
    a restart cannot reset the limits.
    """

    __tablename__ = "irrigation_audit"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    farm_id: Mapped[str] = mapped_column(ForeignKey("farms.id", ondelete="CASCADE"), index=True)
    action: Mapped[str] = mapped_column(String(10))
    requested_duration_sec: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    allowed_duration_sec: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    clamped: Mapped[bool] = mapped_column(Boolean, default=False)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    actor: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    published: Mapped[bool] = mapped_column(Boolean, default=False)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, default=datetime.utcnow)
