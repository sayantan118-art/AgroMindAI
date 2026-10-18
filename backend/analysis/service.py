"""AnalyzeService — the single user-triggered entry point for crop analysis.

Order (per the task): build snapshot → compute input hash → cache lookup →
single-flight → quota gate → Groq (if eligible) → validate → else Path B →
persist → respond.

Sensor ingestion (MQTT), persistence, weather updates and live dashboard
updates continue independently and never call this service. Groq is only called
from here, only after the quota gate allows it, never on rerenders/navigation/
history refresh/report redisplay, and never with automatic retries.

Cache rules (see ``cache.py``): API and rule-engine reports are cached
separately. A cached rule-engine report does not block an eligible Groq
attempt after a cooldown ends; a cached API report may be returned during a
cooldown. ``force=true`` bypasses the cache but NEVER the quota gate.
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from pydantic import ValidationError

from analysis import cache as cache_mod
from analysis import groq_client, rule_engine
from analysis.crop_profiles import resolve_profile, analysis_version, config_version
from analysis.quota_manager import QuotaManager
from analysis.schemas import AnalysisReport, AnalysisResponse, CropProfileSnapshot
from analysis.weather import fetch_weather_snapshot

logger = logging.getLogger(__name__)

DEFAULT_CACHE_TTL = int(os.getenv("ANALYSIS_CACHE_TTL_SECONDS", "1800"))
DEFAULT_MIN_INTERVAL = int(os.getenv("MIN_ANALYZE_INTERVAL_SECONDS", "15"))


class AnalysisTooFrequent(Exception):
    def __init__(self, retry_after_seconds: int):
        self.retry_after_seconds = retry_after_seconds
        super().__init__(f"too_frequent: retry after {retry_after_seconds}s")


class AnalyzeService:
    def __init__(
        self,
        session_factory: Callable[[], Any],
        quota_manager: QuotaManager,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
        weather_fetcher: Optional[Callable] = None,
        cache_ttl_seconds: int = DEFAULT_CACHE_TTL,
        min_interval_seconds: int = DEFAULT_MIN_INTERVAL,
        groq_model: str = groq_client.DEFAULT_MODEL,
        groq_timeout_seconds: float = groq_client.DEFAULT_TIMEOUT_SECONDS,
    ):
        self.session_factory = session_factory
        self.quota = quota_manager
        self.clock = clock
        self.weather_fetcher = weather_fetcher or fetch_weather_snapshot
        self.cache_ttl = cache_ttl_seconds
        self.min_interval = min_interval_seconds
        self.groq_model = groq_model
        self.groq_timeout = groq_timeout_seconds
        self._farm_locks: dict[str, asyncio.Lock] = {}
        self._last_request: dict[str, datetime] = {}
        self._lock_guard = asyncio.Lock()

    async def _farm_lock(self, farm_id: str) -> asyncio.Lock:
        async with self._lock_guard:
            lock = self._farm_locks.get(farm_id)
            if lock is None:
                lock = asyncio.Lock()
                self._farm_locks[farm_id] = lock
            return lock

    def _enforce_min_interval(self, client_id: str | None, force: bool) -> None:
        if force or not client_id:
            return
        now = self.clock()
        last = self._last_request.get(client_id)
        if last is not None:
            elapsed = (now - last).total_seconds()
            if elapsed < self.min_interval:
                raise AnalysisTooFrequent(int(self.min_interval - elapsed))
        self._last_request[client_id] = now

    # ── Input building ──────────────────────────────────────────────────
    async def _build_inputs(self, farm_id: str) -> dict[str, Any]:
        from database.repositories import SensorReadingRepository, FarmRepository
        async with self.session_factory() as session:
            farm = await FarmRepository(session).get_by_id(farm_id)
            crop_name = farm.crop if farm else None
            readings = await SensorReadingRepository(session).list_by_farm(farm_id, limit=40)
        latest = readings[0] if readings else None
        snapshot = {
            "soil_moisture": latest.soil_moisture if latest else None,
            "temperature": latest.temperature if latest else None,
            "humidity": latest.humidity if latest else None,
            "light": latest.light if latest else None,
            "rain": bool(latest.rain) if latest and latest.rain is not None else None,
            "measured_at": (latest.timestamp or latest.created_at) if latest else None,
            "received_at": latest.created_at if latest else None,
        }
        profile, profile_name, prof_ver = resolve_profile(crop_name)
        # Prefer a DB-stored version if the active crop profile row carries one.
        db_version = await self._active_profile_version(crop_name)
        profile_version = db_version or prof_ver
        return {
            "snapshot": snapshot,
            "readings": readings,
            "profile": profile,
            "profile_name": profile_name,
            "profile_version": profile_version,
            "crop_name": crop_name,
        }

    async def _active_profile_version(self, crop_name: str | None) -> Optional[str]:
        try:
            from database.models.crop_profile import CropProfile
            from sqlalchemy import select
            async with self.session_factory() as session:
                cur = await session.execute(
                    select(CropProfile).where(CropProfile.name == (crop_name or "default"))
                )
                row = cur.scalar_one_or_none()
                if row is not None and getattr(row, "version", None):
                    return str(row.version)
        except Exception as exc:
            logger.debug("Could not read DB crop profile version: %s", exc)
        return None

    def _readings_to_history_dicts(self, readings: list[Any]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for r in readings:
            out.append({
                "ts": r.timestamp if r.timestamp is not None else r.created_at,
                "soil_moisture": r.soil_moisture,
                "temperature": r.temperature,
                "humidity": r.humidity,
                "rain": r.rain,
                "light": r.light,
            })
        return out

    # ── Cache helpers ──────────────────────────────────────────────────
    async def _find_cached(self, input_hash: str, method: str) -> Optional[AnalysisReport]:
        from database.repositories.analysis_repository import find_cached_report
        try:
            row = await find_cached_report(self.session_factory, input_hash, method, self.cache_ttl, self.clock())
        except Exception as exc:
            logger.warning("Cache lookup failed: %s", exc)
            return None
        if row is None:
            return None
        try:
            return AnalysisReport.model_validate_json(row)
        except ValidationError:
            return None

    async def _persist_report(self, report: AnalysisReport, farm_id: str) -> None:
        from database.repositories.analysis_repository import persist_report
        await persist_report(
            self.session_factory,
            farm_id=farm_id,
            report=report,
            ttl_seconds=self.cache_ttl,
        )

    # ── Quota eligibility (cheap pre-check for cache decisions) ──────────
    async def _groq_eligible(self, api_key: str | None) -> bool:
        if not api_key:
            return False
        view = await self.quota.get_view(api_key)
        if view.state == "CREDENTIAL_INVALID":
            return False
        if view.state == "COOLDOWN" and view.reset_at:
            try:
                reset_at = datetime.fromisoformat(view.reset_at.replace("Z", "+00:00"))
                return reset_at <= self.clock()
            except ValueError:
                return False
        return True

    # ── Main entry ──────────────────────────────────────────────────────
    async def analyze(
        self,
        *,
        farm_id: str,
        client_id: str | None = None,
        force: bool = False,
        groq_api_key: str | None = None,
    ) -> AnalysisResponse:
        self._enforce_min_interval(client_id, force)

        inputs = await self._build_inputs(farm_id)
        snapshot = inputs["snapshot"]
        profile = inputs["profile"]
        profile_version = inputs["profile_version"]
        a_version = analysis_version()

        weather_raw = await self.weather_fetcher(self.session_factory)
        weather_summary = rule_engine.summarize_weather(weather_raw)
        now = self.clock()
        history_summary = rule_engine.summarize_history(
            self._readings_to_history_dicts(inputs["readings"]), profile, now,
        )

        api_hash = cache_mod.compute_input_hash(
            snapshot=snapshot, history_summary=history_summary, weather_summary=weather_summary,
            profile_version=profile_version, analysis_version=a_version, method="external_model",
        )
        rule_hash = cache_mod.compute_input_hash(
            snapshot=snapshot, history_summary=history_summary, weather_summary=weather_summary,
            profile_version=profile_version, analysis_version=a_version, method="rule_engine",
        )

        async with await self._farm_lock(farm_id):
            # Re-check cache under the lock (a concurrent request may have filled it).
            if not force:
                cached_api = await self._find_cached(api_hash, "external_model")
                if cached_api is not None:
                    return AnalysisResponse(report=cached_api, from_cache=True, quota_state=(await self._quota_state(groq_api_key)))
                eligible = await self._groq_eligible(groq_api_key)
                if not eligible:
                    cached_rule = await self._find_cached(rule_hash, "rule_engine")
                    if cached_rule is not None:
                        return AnalysisResponse(report=cached_rule, from_cache=True, quota_state=(await self._quota_state(groq_api_key)))

            report = await self._produce_report(
                api_hash=api_hash, rule_hash=rule_hash,
                snapshot=snapshot, profile=profile, profile_name=inputs["profile_name"],
                profile_version=profile_version, analysis_version=a_version,
                weather_summary=weather_summary, history_summary=history_summary,
                groq_api_key=groq_api_key,
            )
            await self._persist_report(report, farm_id)
            return AnalysisResponse(
                report=report, from_cache=False,
                quota_state=(await self._quota_state(groq_api_key)), forced=force,
            )

    async def _quota_state(self, api_key: str | None) -> str:
        view = await self.quota.get_view(api_key)
        if view.state == "unconfigured":
            return "rule_engine_only"
        if view.state == "CREDENTIAL_INVALID":
            return "credential_invalid"
        if view.state == "COOLDOWN" and view.reset_at:
            return f"cooldown_until_{view.reset_at}"
        return "available"

    async def _produce_report(
        self, *, api_hash, rule_hash, snapshot, profile, profile_name, profile_version,
        analysis_version, weather_summary, history_summary, groq_api_key,
    ) -> AnalysisReport:
        if groq_api_key:
            claim = await self.quota.claim_attempt(groq_api_key)
            if claim.allowed:
                report = await self._try_groq(
                    api_hash=api_hash, snapshot=snapshot, profile=profile, profile_name=profile_name,
                    profile_version=profile_version, analysis_version=analysis_version,
                    weather_summary=weather_summary, history_summary=history_summary,
                    groq_api_key=groq_api_key,
                )
                if report is not None:
                    return report
        # Path B — deterministic rule engine.
        report = rule_engine.evaluate(
            sensor_snapshot=snapshot, profile=profile, weather_summary=weather_summary,
            history_summary=history_summary, analysis_version=analysis_version,
            profile_version=profile_version, clock=self.clock,
        )
        report.input_hash = rule_hash
        report.crop_profile = CropProfileSnapshot(
            name=profile_name, version=profile_version, thresholds=profile.get("thresholds", {}),
        )
        return report

    async def _try_groq(self, *, api_hash, snapshot, profile, profile_name, profile_version,
                       analysis_version, weather_summary, history_summary, groq_api_key) -> Optional[AnalysisReport]:
        """Attempt one Groq call. Returns a validated report, or None on any failure."""
        result = await asyncio.to_thread(
            groq_client.call_groq,
            api_key=groq_api_key, model=self.groq_model,
            sensor_snapshot=snapshot, profile=profile,
            weather_summary=weather_summary, history_summary=history_summary,
            timeout_seconds=self.groq_timeout,
        )
        if not result.completed:
            # Network/timeout → fallback only, no quota reset.
            await self.quota.record_other_failure(groq_api_key)
            return None
        if result.status_code in (401, 403):
            await self.quota.record_auth_failure(groq_api_key)
            return None
        if result.status_code == 429:
            await self.quota.record_quota_exhaustion(groq_api_key, result.headers, result.content)
            return None
        if result.status_code != 200:
            # 5xx / other → fallback only, no retry, no quota reset.
            await self.quota.record_other_failure(groq_api_key)
            return None
        # 200 — parse + validate. Invalid output is a failure → fallback,
        # and must NOT be cached as an API result (we return None so Path B runs).
        data = groq_client.extract_content_json(result)
        report = self._assemble_external_report(
            data=data, api_hash=api_hash, snapshot=snapshot, profile=profile,
            profile_name=profile_name, profile_version=profile_version,
            analysis_version=analysis_version, weather_summary=weather_summary,
            history_summary=history_summary,
        )
        if report is None:
            await self.quota.record_other_failure(groq_api_key)
            return None
        await self.quota.record_success(groq_api_key)
        return report

    def _assemble_external_report(self, *, data, api_hash, snapshot, profile, profile_name,
                                   profile_version, analysis_version, weather_summary,
                                   history_summary) -> Optional[AnalysisReport]:
        if not isinstance(data, dict):
            return None
        measured_at = None
        if snapshot.get("measured_at") is not None:
            try:
                from analysis.rule_engine import _parse_ts
                ts = _parse_ts(snapshot.get("measured_at"))
                measured_at = ts.isoformat().replace("+00:00", "Z") if ts else None
            except Exception:
                measured_at = None
        payload = dict(data)
        # Fill reproducibility context + provenance (the model must not set these).
        payload["analysis_method"] = "external_model"
        payload["engine_id"] = f"groq:{self.groq_model}"
        payload["analysis_version"] = analysis_version
        payload["generated_at"] = self.clock().isoformat().replace("+00:00", "Z")
        payload["sensor_data_timestamp"] = measured_at
        payload["crop_profile"] = {
            "name": profile_name, "version": profile_version,
            "thresholds": profile.get("thresholds", {}),
        }
        payload["weather_summary"] = weather_summary.model_dump() if hasattr(weather_summary, "model_dump") else weather_summary
        payload["history_summary"] = history_summary.model_dump() if hasattr(history_summary, "model_dump") else history_summary
        payload["input_hash"] = api_hash
        try:
            return AnalysisReport.model_validate(payload)
        except ValidationError as exc:
            logger.warning("Groq response failed schema validation: %s", exc)
            return None
