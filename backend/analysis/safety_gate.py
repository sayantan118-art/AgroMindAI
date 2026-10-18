"""Standalone pump safety gate — every pump command passes through here.

Moved out of the agent pipeline so the safety limits are enforced in exactly
one place, for manual actuation only. Recommendations from the analysis report
are advisory and never actuate. A pump command only comes from an explicit,
separate user action (the dashboard's manual pump control → ``POST
/pump/control``).

Limits (must not be weakened):

* runtime cap: ``max_duration_seconds`` (default 180 s)
* daily cap: ``max_daily_events`` (default 10/day)
* minimum interval between irrigations: ``min_interval_seconds`` (default 600 s)
* sensor validity: soil moisture must be a valid 0–100 % reading; temperature
  must be in a plausible range; irrigation is rejected when soil is already
  above the crop waterlogging threshold or temperature exceeds 45 °C.

The daily count and the last-irrigation time are read from the durable
``irrigation_audit`` table (not memory), so a restart cannot reset them.
``day`` is the UTC calendar day by default (configurable via
``IRRIGATION_DAY_TIMEZONE``) — documented in README/docs.

Audit: a decision audit row is written *before* publishing to MQTT; if that
write fails, the pump is NOT actuated. The outcome is recorded afterwards.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Optional

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from analysis.crop_profiles import resolve_profile

logger = logging.getLogger(__name__)

HARD_TEMP_CEILING_C = 45.0  # never weakened; matches the previous Safety Supervisor
Clock = Callable[[], datetime]


@dataclass
class SafetyDecision:
    allowed: bool
    action: str  # "ON" | "OFF"
    duration_sec: int
    reason: str
    clamped: bool = False


class SafetyGate:
    def __init__(
        self,
        session_factory: Callable[[], Any],
        *,
        clock: Clock = lambda: datetime.now(timezone.utc),
        publish_fn: Optional[Callable[[str, int], bool]] = None,
        day_timezone: str | None = None,
    ):
        self.session_factory = session_factory
        self.clock = clock
        self.publish_fn = publish_fn
        # Default to UTC for the "day" boundary. IRRIGATION_DAY_TIMEZONE may name
        # an IANA zone; we fall back to UTC if it is unset/invalid.
        self.day_timezone = day_timezone or os.getenv("IRRIGATION_DAY_TIMEZONE", "UTC")

    def _now(self) -> datetime:
        now = self.clock()
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        return now.astimezone(timezone.utc)

    async def _limits_for(self, crop_name: str | None) -> dict[str, Any]:
        profile, _name, _ver = resolve_profile(crop_name)
        return profile.get("pump_limits", {})

    async def _thresholds_for(self, crop_name: str | None) -> dict[str, Any]:
        profile, _name, _ver = resolve_profile(crop_name)
        return profile.get("thresholds", {})

    async def evaluate(
        self,
        *,
        action: str,
        duration_sec: int,
        farm_id: str,
        crop_name: str | None = None,
        sensor_snapshot: dict[str, Any] | None = None,
    ) -> SafetyDecision:
        action = (action or "OFF").upper()
        if action not in ("ON", "OFF"):
            return SafetyDecision(False, "OFF", 0, f"Unknown action '{action}'")

        limits = await self._limits_for(crop_name)
        max_duration = int(limits.get("max_duration_seconds", 180))
        max_daily = int(limits.get("max_daily_events", 10))
        min_interval = int(limits.get("min_interval_seconds", 600))

        # OFF is always allowed (safe shutdown).
        if action == "OFF":
            return SafetyDecision(True, "OFF", 0, "Pump OFF command allowed.")

        # ── Duration cap ──────────────────────────────────────────────────
        try:
            requested = max(0, int(duration_sec))
        except (TypeError, ValueError):
            return SafetyDecision(False, "ON", 0, "Invalid duration.")
        clamped = False
        if requested > max_duration:
            requested = max_duration
            clamped = True

        # ── Sensor validity (safety, not advisory) ────────────────────────
        snap = sensor_snapshot or {}
        soil = snap.get("soil_moisture")
        temp = snap.get("temperature")
        hum = snap.get("humidity")
        if soil is None or not (isinstance(soil, (int, float)) and 0 <= soil <= 100):
            return SafetyDecision(False, "ON", 0, "Rejected: soil moisture missing or out of range.")
        if temp is not None and (not isinstance(temp, (int, float)) or temp > HARD_TEMP_CEILING_C or temp < -10):
            return SafetyDecision(False, "ON", 0, "Rejected: temperature outside safe irrigation range.")
        if hum is not None and (not isinstance(hum, (int, float)) and not (0 <= hum <= 100)):
            return SafetyDecision(False, "ON", 0, "Rejected: humidity out of range.")
        th = await self._thresholds_for(crop_name)
        waterlog = float(th.get("soil_moisture_percent", {}).get("waterlogging_high", 85.0))
        if soil > waterlog:
            return SafetyDecision(False, "ON", 0, f"Rejected: soil already wet ({soil}% > {waterlog}% waterlogging).")

        # ── Durable daily count ───────────────────────────────────────────
        now = self._now()
        count_today = await self._count_today(farm_id, now)
        if count_today >= max_daily:
            return SafetyDecision(False, "ON", 0, f"Rejected: daily limit reached ({count_today}/{max_daily}).")

        # ── Minimum interval ──────────────────────────────────────────────
        last = await self._last_allowed_on(farm_id)
        if last is not None and (now - last).total_seconds() < min_interval:
            remaining = min_interval - int((now - last).total_seconds())
            return SafetyDecision(False, "ON", 0, f"Rejected: minimum interval not elapsed ({remaining}s remaining).")

        reason = "Allowed."
        if clamped:
            reason = f"Duration clamped to {max_duration}s."
        return SafetyDecision(True, "ON", requested, reason, clamped=True)

    async def _count_today(self, farm_id: str, now: datetime) -> int:
        from database.models.irrigation_audit import IrrigationAudit
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        async with self.session_factory() as session:  # type: AsyncSession
            cur = await session.execute(
                select(IrrigationAudit).where(
                    IrrigationAudit.farm_id == farm_id,
                    IrrigationAudit.allowed.is_(True),
                    IrrigationAudit.action == "ON",
                    IrrigationAudit.created_at >= day_start,
                )
            )
            return len(cur.scalars().all())

    async def _last_allowed_on(self, farm_id: str) -> Optional[datetime]:
        from database.models.irrigation_audit import IrrigationAudit
        async with self.session_factory() as session:  # type: AsyncSession
            cur = await session.execute(
                select(IrrigationAudit).where(
                    IrrigationAudit.farm_id == farm_id,
                    IrrigationAudit.allowed.is_(True),
                    IrrigationAudit.action == "ON",
                ).order_by(IrrigationAudit.created_at.desc()).limit(1)
            )
            row = cur.scalar_one_or_none()
            return row.created_at if row else None

    async def actuate(
        self,
        *,
        action: str,
        duration_sec: int,
        farm_id: str,
        crop_name: str | None = None,
        sensor_snapshot: dict[str, Any] | None = None,
        source: str = "manual_ui",
        actor: str | None = None,
    ) -> tuple[SafetyDecision, bool, Optional[str]]:
        """Evaluate → audit-write → publish → record outcome.

        Returns (decision, published, audit_id). If the audit write fails the
        pump is NOT actuated and ``published`` is False.
        """
        decision = await self.evaluate(
            action=action, duration_sec=duration_sec, farm_id=farm_id,
            crop_name=crop_name, sensor_snapshot=sensor_snapshot,
        )
        audit_id = await self._write_audit(
            decision=decision, farm_id=farm_id, source=source, actor=actor,
            requested_duration=int(duration_sec or 0),
        )
        if audit_id is None:
            return decision, False, None

        published = False
        if decision.allowed and decision.action == "ON" and self.publish_fn is not None:
            try:
                published = bool(self.publish_fn(decision.action, decision.duration_sec))
            except Exception as exc:
                logger.error("Pump publish failed: %s", exc)
                published = False
        await self._record_outcome(audit_id, published)
        return decision, published, audit_id

    async def _write_audit(
        self, *, decision: SafetyDecision, farm_id: str, source: str,
        actor: str | None, requested_duration: int,
    ) -> Optional[str]:
        from database.models.irrigation_audit import IrrigationAudit
        now = self._now()
        row = IrrigationAudit(
            farm_id=farm_id, action=decision.action, requested_duration_sec=requested_duration,
            allowed_duration_sec=decision.duration_sec, allowed=decision.allowed,
            clamped=decision.clamped, reason=decision.reason, source=source, actor=actor,
            created_at=now, published=False, published_at=None,
        )
        try:
            async with self.session_factory() as session:  # type: AsyncSession
                session.add(row)
                await session.commit()
                await session.refresh(row)
                return row.id
        except Exception as exc:
            logger.error("Safety audit write failed — NOT actuating: %s", exc)
            return None

    async def _record_outcome(self, audit_id: str, published: bool) -> None:
        from database.models.irrigation_audit import IrrigationAudit
        now = self._now()
        try:
            async with self.session_factory() as session:  # type: AsyncSession
                row = await session.get(IrrigationAudit, audit_id)
                if row is not None:
                    row.published = published
                    row.published_at = now if published else None
                    await session.commit()
        except Exception as exc:
            logger.error("Safety audit outcome update failed: %s", exc)
