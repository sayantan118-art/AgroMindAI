from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.connection import Base


class AnalysisReport(Base):
    """Immutable analysis report history with full reproducibility context.

    The structured report (per-sensor assessments, risks, evidence, recommended
    actions, data-quality warnings) is stored verbatim as validated JSON in
    ``report_json``. Indexed columns mirror the fields we filter/query by
    (created_at, input_hash, method, farm_id, profile_version, analysis_version).
    Never stores API keys, auth headers or raw provider error bodies.
    """

    __tablename__ = "analysis_reports"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    farm_id: Mapped[str] = mapped_column(ForeignKey("farms.id", ondelete="CASCADE"), index=True)
    input_hash: Mapped[str] = mapped_column(String(64), index=True)
    analysis_method: Mapped[str] = mapped_column(String(32), index=True)
    engine_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    analysis_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    profile_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    profile_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    overall_status: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    health_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    irrigation_recommendation: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    dashboard_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sensor_data_timestamp: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    report_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, default=datetime.utcnow)

    cache_index: Mapped[Optional["AnalysisCacheIndex"]] = relationship(
        back_populates="report", uselist=False, cascade="all, delete-orphan"
    )
