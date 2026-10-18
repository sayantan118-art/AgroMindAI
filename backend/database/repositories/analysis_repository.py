"""Repository helpers for analysis reports + cache index.

The cache is an index over immutable reports (see ``AnalysisCacheIndex``).
``persist_report`` writes the report and its cache-index row in one
transaction. ``find_cached_report`` returns the report JSON for a non-expired
matching entry. Report history is read-only.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.analysis_cache import AnalysisCacheIndex
from database.models.analysis_report import AnalysisReport


async def persist_report(session_factory, *, farm_id: str, report: Any, ttl_seconds: int) -> AnalysisReport:
    """Persist an immutable report + its cache index entry in one transaction."""
    report_json = report.model_dump_json() if hasattr(report, "model_dump_json") else json.dumps(report)
    created_at = report.generated_at
    try:
        created_dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        created_dt = datetime.now(timezone.utc)
    expires_at = created_dt + timedelta(seconds=ttl_seconds)
    sensor_ts = None
    if report.sensor_data_timestamp:
        try:
            sensor_ts = datetime.fromisoformat(report.sensor_data_timestamp.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            sensor_ts = None

    row = AnalysisReport(
        farm_id=farm_id,
        input_hash=report.input_hash,
        analysis_method=report.analysis_method,
        engine_id=report.engine_id,
        analysis_version=report.analysis_version,
        profile_name=report.crop_profile.name,
        profile_version=report.crop_profile.version,
        overall_status=report.overall_status,
        health_score=report.health_score,
        irrigation_recommendation=report.irrigation_recommendation,
        dashboard_summary=report.dashboard_summary,
        sensor_data_timestamp=sensor_ts,
        report_json=report_json,
        created_at=created_dt,
    )
    cache = AnalysisCacheIndex(
        input_hash=report.input_hash,
        analysis_method=report.analysis_method,
        analysis_version=report.analysis_version,
        profile_version=report.crop_profile.version,
        created_at=created_dt,
        expires_at=expires_at,
    )
    async with session_factory() as session:  # type: AsyncSession
        session.add(row)
        await session.flush()
        cache.report_id = row.id
        session.add(cache)
        await session.commit()
        await session.refresh(row)
    return row


async def find_cached_report(session_factory, input_hash: str, method: str, ttl_seconds: int, now: datetime) -> Optional[str]:
    """Return cached ``report_json`` if a non-expired matching entry exists, else None."""
    async with session_factory() as session:  # type: AsyncSession
        cur = await session.execute(
            select(AnalysisReport.report_json)
            .join(AnalysisCacheIndex, AnalysisCacheIndex.report_id == AnalysisReport.id)
            .where(
                AnalysisCacheIndex.input_hash == input_hash,
                AnalysisCacheIndex.analysis_method == method,
                AnalysisCacheIndex.expires_at > now,
            )
            .order_by(desc(AnalysisCacheIndex.created_at))
            .limit(1)
        )
        row = cur.scalar_one_or_none()
        return row


async def list_reports(session_factory, *, farm_id: str | None = None, limit: int = 20, offset: int = 0) -> list[dict[str, Any]]:
    """Newest-first summary list (no report bodies)."""
    async with session_factory() as session:  # type: AsyncSession
        stmt = select(AnalysisReport).order_by(desc(AnalysisReport.created_at)).limit(limit).offset(offset)
        if farm_id is not None:
            stmt = stmt.where(AnalysisReport.farm_id == farm_id)
        cur = await session.execute(stmt)
        rows = cur.scalars().all()
    return [
        {
            "id": r.id,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "analysis_method": r.analysis_method,
            "engine_id": r.engine_id,
            "analysis_version": r.analysis_version,
            "profile_name": r.profile_name,
            "overall_status": r.overall_status,
            "health_score": r.health_score,
            "irrigation_recommendation": r.irrigation_recommendation,
            "dashboard_summary": r.dashboard_summary,
            "sensor_data_timestamp": r.sensor_data_timestamp.isoformat() if r.sensor_data_timestamp else None,
            "farm_id": r.farm_id,
        }
        for r in rows
    ]


async def get_report(session_factory, report_id: str) -> Optional[dict[str, Any]]:
    async with session_factory() as session:  # type: AsyncSession
        row = await session.get(AnalysisReport, report_id)
        if row is None:
            return None
        return {
            "id": row.id,
            "farm_id": row.farm_id,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "report": json.loads(row.report_json or "{}"),
        }
