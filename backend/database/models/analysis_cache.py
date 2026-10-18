from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.connection import Base


class AnalysisCacheIndex(Base):
    """Cache *index* over immutable reports — never a duplicate store of content.

    Lookup key: (input_hash, method, analysis_version, profile_version). A row
    is reusable only while ``expires_at`` is in the future and the
    analysis/profile versions still match. Expired or version-mismatched rows
    are never reused. Stored per ``method`` so a cached rule-engine report does
    not block an eligible Groq attempt after a cooldown ends.
    """

    __tablename__ = "analysis_cache_index"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    input_hash: Mapped[str] = mapped_column(String(64), index=True)
    analysis_method: Mapped[str] = mapped_column(String(32), index=True)
    analysis_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    profile_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    report_id: Mapped[str] = mapped_column(ForeignKey("analysis_reports.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

    report: Mapped["AnalysisReport"] = relationship(back_populates="cache_index")
