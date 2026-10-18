"""Persistent quota manager — the single gate for every Groq call.

State lives in SQLite (table ``api_quota_state``), scoped to ``provider +
model + key_fingerprint`` where ``key_fingerprint`` is a one-way hash of the
API key (the key itself is never stored or logged). A rotated key produces a
different fingerprint → a different scope, which clears a persisted
credential-invalid marker automatically.

States:

* ``AVAILABLE``       — a claim may proceed
* ``COOLDOWN``         — with ``reset_at``; no calls until then (no polling)
* ``CREDENTIAL_INVALID`` — persisted for 401/403; cleared only by a key change

Atomicity (works across processes, not only within one): a claim is a single
write transaction that conditionally ``UPDATE``s the row —
``state != CREDENTIAL_INVALID AND (state=AVAILABLE OR reset_at<=now) AND
(in_flight IS NULL OR in_flight<now)`` — and only proceeds if ``rowcount == 1``.
A lease (``in_flight_claim_until``) ensures a crash mid-request cannot leave the
gate stuck. The quota state is loaded from the DB only, so a restart retains
state (provided the DB file is on durable storage — see docs).

All time logic uses an injectable clock (tests control time). Fail-closed: if
the quota state cannot be read or written (DB locked/unavailable), no API call
is made and the caller serves the rule-engine report.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Callable, Optional, Protocol

from sqlalchemy import select, update

logger = logging.getLogger(__name__)

PROVIDER = "groq"
DEFAULT_MODEL = "llama-3.3-70b-versatile"
DEFAULT_LEASE_SECONDS = 60
DEFAULT_BACKOFF_SECONDS = 300
DEFAULT_BUSY_TIMEOUT_MS = 30000

AVAILABLE = "AVAILABLE"
COOLDOWN = "COOLDOWN"
CREDENTIAL_INVALID = "CREDENTIAL_INVALID"

REQUEST_QUOTA = "request_quota"
TOKEN_QUOTA = "token_quota"
TEMP_RATE_LIMIT = "temporary_rate_limit"
AUTH = "auth"
OTHER = "other"

Clock = Callable[[], datetime]


def _now_utc(clock: Clock) -> datetime:
    now = clock()
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return now.astimezone(timezone.utc)


def key_fingerprint(api_key: str, provider: str = PROVIDER, model: str = DEFAULT_MODEL) -> str:
    """One-way fingerprint of the API key. Never store or log the key itself."""
    pepper = os.getenv("QUOTA_KEY_PEPPER", "agromind")
    raw = f"{provider}:{model}:{pepper}:{api_key}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:32]


@dataclass
class ClaimResult:
    allowed: bool
    reason: str  # human-readable, no secrets


@dataclass
class QuotaStateView:
    provider: str
    model: str
    state: str
    cooldown_until: Optional[str]
    reset_at: Optional[str]
    last_attempt_at: Optional[str]
    in_flight: bool
    last_failure_classification: Optional[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "state": self.state,
            "cooldown_until": self.cooldown_until,
            "reset_at": self.reset_at,
            "last_attempt_at": self.last_attempt_at,
            "in_flight": self.in_flight,
            "last_failure_classification": self.last_failure_classification,
        }


class QuotaStore(Protocol):
    async def claim(self, provider: str, model: str, fingerprint: str, now: datetime, lease_until: datetime) -> bool: ...
    async def record_success(self, provider: str, model: str, fingerprint: str, now: datetime) -> None: ...
    async def record_cooldown(self, provider: str, model: str, fingerprint: str, now: datetime, reset_at: datetime, classification: str, header_meta: str) -> None: ...
    async def record_credential_invalid(self, provider: str, model: str, fingerprint: str, now: datetime) -> None: ...
    async def record_other_failure(self, provider: str, model: str, fingerprint: str, now: datetime) -> None: ...
    async def get_state(self, provider: str, model: str, fingerprint: str) -> dict[str, Any] | None: ...


def _conflict_safe_insert(session, model_cls, dialect_name: str, values: dict[str, Any]):
    """INSERT ... ON CONFLICT DO NOTHING across SQLite and PostgreSQL."""
    if dialect_name == "postgresql":
        from sqlalchemy.dialects.postgresql import insert as pg_insert
        stmt = pg_insert(model_cls).values(**values).on_conflict_do_nothing(
            index_elements=["provider", "model", "key_fingerprint"])
    else:
        from sqlalchemy.dialects.sqlite import insert as sqlite_insert
        stmt = sqlite_insert(model_cls).values(**values).on_conflict_do_nothing(
            index_elements=["provider", "model", "key_fingerprint"])
    return stmt


class SqlaQuotaStore:
    """SQLAlchemy-async quota store. Works on SQLite and PostgreSQL.

    The atomic claim is a conditional ``UPDATE ... WHERE <state conditions>`` with
    ``rowcount == 1`` as the gate, inside a transaction. The row is ensured to
    exist first with ``INSERT ... ON CONFLICT DO NOTHING``. Concurrent claims
    serialize via the database's row locking (SQLite busy_timeout / Postgres
    row locks), so this is safe across processes, not only within one.
    """

    def __init__(self, session_factory):
        self.session_factory = session_factory
        self._dialect: str | None = None

    async def _dialect_name(self) -> str:
        if self._dialect is None:
            from database.connection import get_database_url
            url = get_database_url()
            self._dialect = "postgresql" if url.startswith("postgresql") else "sqlite"
        return self._dialect

    async def claim(self, provider, model, fingerprint, now, lease_until) -> bool:
        from database.models.api_quota_state import ApiQuotaState
        try:
            dialect = await self._dialect_name()
            async with self.session_factory() as session:
                async with session.begin():
                    await session.execute(
                        _conflict_safe_insert(session, ApiQuotaState, dialect, {
                            "provider": provider, "model": model, "key_fingerprint": fingerprint,
                            "state": AVAILABLE, "updated_at": now,
                        })
                    )
                    result = await session.execute(
                        update(ApiQuotaState)
                        .values(in_flight_claim_until=lease_until, last_attempt_at=now, updated_at=now)
                        .where(
                            ApiQuotaState.provider == provider,
                            ApiQuotaState.model == model,
                            ApiQuotaState.key_fingerprint == fingerprint,
                            ApiQuotaState.state != CREDENTIAL_INVALID,
                            (ApiQuotaState.state == AVAILABLE)
                            | ((ApiQuotaState.state == COOLDOWN) & (ApiQuotaState.reset_at.is_not(None)) & (ApiQuotaState.reset_at <= now)),
                            (ApiQuotaState.in_flight_claim_until.is_(None))
                            | (ApiQuotaState.in_flight_claim_until < now),
                        )
                    )
                    return result.rowcount == 1
        except Exception as exc:  # DB locked/unavailable → fail closed
            logger.warning("Quota claim failed (DB unavailable): %s", exc)
            return False

    async def _update(self, provider, model, fingerprint, now, values: dict[str, Any]) -> None:
        from database.models.api_quota_state import ApiQuotaState
        try:
            dialect = await self._dialect_name()
            async with self.session_factory() as session:
                async with session.begin():
                    await session.execute(
                        _conflict_safe_insert(session, ApiQuotaState, dialect, {
                            "provider": provider, "model": model, "key_fingerprint": fingerprint,
                            "state": AVAILABLE, "updated_at": now,
                        })
                    )
                    await session.execute(
                        update(ApiQuotaState)
                        .values(in_flight_claim_until=None, updated_at=now, **values)
                        .where(
                            ApiQuotaState.provider == provider,
                            ApiQuotaState.model == model,
                            ApiQuotaState.key_fingerprint == fingerprint,
                        )
                    )
        except Exception as exc:
            logger.warning("Quota state update failed (DB unavailable): %s", exc)

    async def record_success(self, provider, model, fingerprint, now) -> None:
        await self._update(provider, model, fingerprint, now, {
            "state": AVAILABLE, "reset_at": None,
            "last_failure_classification": None, "header_meta": None,
        })

    async def record_cooldown(self, provider, model, fingerprint, now, reset_at, classification, header_meta) -> None:
        await self._update(provider, model, fingerprint, now, {
            "state": COOLDOWN, "reset_at": reset_at,
            "last_failure_classification": classification, "header_meta": header_meta,
        })

    async def record_credential_invalid(self, provider, model, fingerprint, now) -> None:
        await self._update(provider, model, fingerprint, now, {
            "state": CREDENTIAL_INVALID, "last_failure_classification": AUTH,
        })

    async def record_other_failure(self, provider, model, fingerprint, now) -> None:
        # Clear the in-flight lease only; do NOT change cooldown/availability.
        await self._update(provider, model, fingerprint, now, {})

    async def get_state(self, provider, model, fingerprint) -> dict[str, Any] | None:
        from database.models.api_quota_state import ApiQuotaState
        try:
            async with self.session_factory() as session:
                cur = await session.execute(
                    select(
                        ApiQuotaState.state, ApiQuotaState.reset_at,
                        ApiQuotaState.last_attempt_at, ApiQuotaState.in_flight_claim_until,
                        ApiQuotaState.last_failure_classification,
                    ).where(
                        ApiQuotaState.provider == provider,
                        ApiQuotaState.model == model,
                        ApiQuotaState.key_fingerprint == fingerprint,
                    )
                )
                row = cur.fetchone()
                if row is None:
                    return None
                def _iso(v):
                    return v.isoformat() if isinstance(v, datetime) else v
                return {
                    "state": row[0], "reset_at": _iso(row[1]), "last_attempt_at": _iso(row[2]),
                    "in_flight_claim_until": row[3], "last_failure_classification": row[4],
                }
        except Exception as exc:
            logger.warning("Quota state read failed (DB unavailable): %s", exc)
            return None


class QuotaManager:
    """Single gate for every Groq call."""

    def __init__(
        self,
        store: QuotaStore,
        *,
        clock: Clock = lambda: datetime.now(timezone.utc),
        lease_seconds: int = DEFAULT_LEASE_SECONDS,
        conservative_backoff_seconds: int = DEFAULT_BACKOFF_SECONDS,
        model: str = DEFAULT_MODEL,
        provider: str = PROVIDER,
    ):
        self.store = store
        self.clock = clock
        self.lease_seconds = lease_seconds
        self.backoff_seconds = conservative_backoff_seconds
        self.model = model
        self.provider = provider

    @classmethod
    def for_session_factory(cls, session_factory, **kwargs) -> "QuotaManager":
        return cls(SqlaQuotaStore(session_factory), **kwargs)

    def _fp(self, api_key: str) -> str:
        return key_fingerprint(api_key, self.provider, self.model)

    async def get_view(self, api_key: str | None) -> QuotaStateView:
        if not api_key:
            return QuotaStateView(self.provider, self.model, "unconfigured", None, None, None, False, None)
        row = await self.store.get_state(self.provider, self.model, self._fp(api_key))
        if row is None:
            return QuotaStateView(self.provider, self.model, AVAILABLE, None, None, None, False, None)
        return QuotaStateView(
            provider=self.provider, model=self.model, state=row["state"],
            cooldown_until=row["reset_at"], reset_at=row["reset_at"],
            last_attempt_at=row["last_attempt_at"],
            in_flight=bool(row["in_flight_claim_until"]),
            last_failure_classification=row["last_failure_classification"],
        )

    async def claim_attempt(self, api_key: str) -> ClaimResult:
        """Atomically claim one attempt. Returns whether the call may proceed."""
        if not api_key:
            return ClaimResult(False, "no_api_key")
        now = _now_utc(self.clock)
        lease_until = now + timedelta(seconds=self.lease_seconds)
        allowed = await self.store.claim(self.provider, self.model, self._fp(api_key), now, lease_until)
        if not allowed:
            view = await self.get_view(api_key)
            if view.state == CREDENTIAL_INVALID:
                return ClaimResult(False, "credential_invalid")
            if view.state == COOLDOWN and view.reset_at:
                return ClaimResult(False, f"cooldown_until_{view.reset_at}")
            if view.in_flight:
                return ClaimResult(False, "another_attempt_in_flight")
            return ClaimResult(False, "denied")
        return ClaimResult(True, "allowed")

    async def record_success(self, api_key: str) -> None:
        await self.store.record_success(self.provider, self.model, self._fp(api_key), _now_utc(self.clock))

    async def record_auth_failure(self, api_key: str) -> None:
        await self.store.record_credential_invalid(self.provider, self.model, self._fp(api_key), _now_utc(self.clock))

    async def record_other_failure(self, api_key: str) -> None:
        await self.store.record_other_failure(self.provider, self.model, self._fp(api_key), _now_utc(self.clock))

    async def record_quota_exhaustion(self, api_key: str, headers: dict[str, str], body: Any = None) -> datetime:
        """Classify a 429, compute reset_at from headers, persist cooldown, return reset_at."""
        now = _now_utc(self.clock)
        classification, reset_delta = classify_quota_failure(headers, body)
        reset_at = now + reset_delta
        header_meta = serialize_header_meta(headers)
        await self.store.record_cooldown(self.provider, self.model, self._fp(api_key), now, reset_at, classification, header_meta)
        logger.warning("Groq quota exhausted (%s); cooldown until %s", classification, reset_at.isoformat())
        return reset_at


# ── Header parsing ────────────────────────────────────────────────────────────

_DURATION_RE = re.compile(r"(?:(\d+)d)?(?:(\d+)h)?(?:(\d+)m(?!s))?(?:(\d+(?:\.\d+)?)s)?(?:(\d+(?:\.\d+)?)ms)?", re.IGNORECASE)


def parse_duration(value: str | None) -> float | None:
    """Parse Groq duration strings like '2m59.56s', '1h', '1d', '500ms', '30s'."""
    if value is None:
        return None
    v = str(value).strip().lower()
    if not v:
        return None
    if v.isdigit():
        return float(v)  # bare integer = seconds
    m = _DURATION_RE.fullmatch(v)
    if not m or not any(m.groups()):
        return None
    d, h, mi, s, ms = m.groups()
    total = 0.0
    if d: total += int(d) * 86400
    if h: total += int(h) * 3600
    if mi: total += int(mi) * 60
    if s: total += float(s)
    if ms: total += float(ms) / 1000.0
    return total if total > 0 else None


def _parse_retry_after(value: str | None) -> float | None:
    if value is None:
        return None
    v = str(value).strip()
    if not v:
        return None
    if v.isdigit():
        return float(v)
    try:
        dt = parsedate_to_datetime(v)  # HTTP-date
        if dt is None:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return max(0.0, (dt - datetime.now(timezone.utc)).total_seconds())
    except (TypeError, ValueError):
        return None


def _hget(headers: dict[str, str], name: str) -> str | None:
    if not headers:
        return None
    lower = {k.lower(): v for k, v in headers.items()}
    return lower.get(name.lower())


def classify_quota_failure(headers: dict[str, str], body: Any) -> tuple[str, timedelta]:
    """Return (classification, reset_delta). Conservative fallback when unsure.
    
    Priority (per Groq rate-limit docs):
    1. Retry-After (explicit server directive) - wins when present
    2. x-ratelimit-reset-tokens when x-ratelimit-remaining-tokens == 0
    3. x-ratelimit-reset-requests when x-ratelimit-remaining-requests == 0
    4. Conservative fallback (DEFAULT_BACKOFF_SECONDS)
    
    Per-minute limits use reset-tokens/reset-requests with small values (seconds).
    Daily limits use large values (86400s). We use the specific exhausted resource's reset.
    """
    retry_after = _parse_retry_after(_hget(headers, "retry-after"))
    reset_requests = parse_duration(_hget(headers, "x-ratelimit-reset-requests"))
    reset_tokens = parse_duration(_hget(headers, "x-ratelimit-reset-tokens"))
    remaining_requests = _hget(headers, "x-ratelimit-remaining-requests")
    remaining_tokens = _hget(headers, "x-ratelimit-remaining-tokens")

    token_exhausted = remaining_tokens is not None and str(remaining_tokens).strip() in ("0", "0.0")
    request_exhausted = remaining_requests is not None and str(remaining_requests).strip() in ("0", "0.0")

    # Retry-After is an explicit server directive - use it directly when present
    if retry_after is not None:
        return TEMP_RATE_LIMIT, timedelta(seconds=max(1.0, retry_after))

    candidates: list[tuple[str, float]] = []  # (classification, reset_seconds)
    if token_exhausted and reset_tokens is not None:
        candidates.append((TOKEN_QUOTA, reset_tokens))
    if request_exhausted and reset_requests is not None:
        candidates.append((REQUEST_QUOTA, reset_requests))
    # If neither explicitly exhausted but reset headers present, use the longest (conservative)
    if not candidates:
        if reset_tokens is not None:
            candidates.append((TOKEN_QUOTA, reset_tokens))
        if reset_requests is not None:
            candidates.append((REQUEST_QUOTA, reset_requests))

    if candidates:
        # Prefer the longest trustworthy reset so we never resume too early
        cls, delta = max(candidates, key=lambda x: x[1])
        return cls, timedelta(seconds=max(1.0, delta))

    # No trustworthy reset → documented conservative backoff.
    return TEMP_RATE_LIMIT, timedelta(seconds=DEFAULT_BACKOFF_SECONDS)


def serialize_header_meta(headers: dict[str, str]) -> str:
    """Keep only the reset/rate-limit headers we used (no secrets ever present)."""
    keep = (
        "retry-after", "x-ratelimit-reset-requests", "x-ratelimit-reset-tokens",
        "x-ratelimit-remaining-requests", "x-ratelimit-remaining-tokens",
        "x-ratelimit-limit-requests", "x-ratelimit-limit-tokens",
    )
    lower = {k.lower(): v for k, v in (headers or {}).items()}
    return "; ".join(f"{k}={lower[k]}" for k in keep if k in lower)
