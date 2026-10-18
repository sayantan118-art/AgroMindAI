from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.connection import Base


class RuleTrigger(Base):
    __tablename__ = "rule_triggers"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    farm_id: Mapped[str] = mapped_column(ForeignKey("farms.id", ondelete="CASCADE"), index=True)
    rule_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sensor_values: Mapped[str | None] = mapped_column(Text, nullable=True)
    trigger_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, default=datetime.utcnow)

    farm: Mapped["Farm"] = relationship(back_populates="rule_triggers")
