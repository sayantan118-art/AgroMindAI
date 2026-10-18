from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from database.connection import Base


class ApiQuotaState(Base):
    """Persistent API quota/cooldown state, scoped to provider + model + key
    fingerprint (a one-way hash — the key itself is never stored or logged).

    Columns are accessed both via the ORM (creation) and via raw SQL in
    ``quota_manager.SqliteQuotaStore`` (atomic claims). Keep column names in
    sync with that module.
    """

    __tablename__ = "api_quota_state"

    provider: Mapped[str] = mapped_column(String(50), primary_key=True)
    model: Mapped[str] = mapped_column(String(100), primary_key=True)
    key_fingerprint: Mapped[str] = mapped_column(String(64), primary_key=True)
    state: Mapped[str] = mapped_column(String(32), default="AVAILABLE")
    reset_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_attempt_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    in_flight_claim_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_failure_classification: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    header_meta: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
