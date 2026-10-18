"""Quota manager tests: persistent cooldown, atomic claims, header parsing.

Groq is never called here; we exercise the gate's claim/record state machine
directly against a temp DB.
"""

import asyncio
import datetime
from datetime import timedelta, timezone

import pytest

from analysis.quota_manager import (
    QuotaManager, AVAILABLE, COOLDOWN, CREDENTIAL_INVALID,
    TOKEN_QUOTA, REQUEST_QUOTA, TEMP_RATE_LIMIT,
    parse_duration, classify_quota_failure,
)

KEY = "test-key-123"


@pytest.fixture
def qm(temp_db, fixed_clock):
    return QuotaManager.for_session_factory(temp_db, clock=fixed_clock, lease_seconds=60,
                                            conservative_backoff_seconds=300)


async def test_initial_claim_allowed(qm):
    claim = await qm.claim_attempt(KEY)
    assert claim.allowed
    await qm.record_success(KEY)
    view = await qm.get_view(KEY)
    assert view.state == AVAILABLE


async def test_cooldown_persists_across_restart(temp_db, fixed_clock, qm):
    headers = {"Retry-After": "120", "x-ratelimit-reset-tokens": "1m30s",
               "x-ratelimit-remaining-tokens": "0"}
    await qm.record_quota_exhaustion(KEY, headers)
    view = await qm.get_view(KEY)
    assert view.state == COOLDOWN
    assert view.reset_at is not None

    # New manager on the SAME db file (simulated restart) retains cooldown.
    qm2 = QuotaManager.for_session_factory(temp_db, clock=fixed_clock, conservative_backoff_seconds=300)
    view2 = await qm2.get_view(KEY)
    assert view2.state == COOLDOWN
    assert view2.reset_at == view.reset_at
    # No API call during cooldown.
    claim = await qm2.claim_attempt(KEY)
    assert not claim.allowed


async def test_one_attempt_after_reset_then_new_cooldown(qm, fixed_clock):
    headers = {"Retry-After": "60"}
    await qm.record_quota_exhaustion(KEY, headers)
    fixed_clock.advance(120)  # past reset_at
    claim = await qm.claim_attempt(KEY)
    assert claim.allowed  # exactly one attempt
    # Another claim before outcome recorded: denied (in-flight lease).
    claim2 = await qm.claim_attempt(KEY)
    assert not claim2.allowed
    # Repeat quota failure -> new cooldown.
    await qm.record_quota_exhaustion(KEY, {"Retry-After": "60"})
    view = await qm.get_view(KEY)
    assert view.state == COOLDOWN


async def test_auth_failure_persists_credential_invalid(qm):
    await qm.record_auth_failure(KEY)
    view = await qm.get_view(KEY)
    assert view.state == CREDENTIAL_INVALID
    # Same key: no retry loop, claims denied.
    claim = await qm.claim_attempt(KEY)
    assert not claim.allowed
    assert "credential" in claim.reason


async def test_rotated_key_clears_credential_invalid(qm):
    await qm.record_auth_failure(KEY)
    new_key = "rotated-key-456"
    claim = await qm.claim_attempt(new_key)
    assert claim.allowed  # different fingerprint = new scope = available
    await qm.record_success(new_key)


async def test_concurrent_claims_allow_exactly_one(temp_db, fixed_clock):
    qm = QuotaManager.for_session_factory(temp_db, clock=fixed_clock, lease_seconds=60)
    results = await asyncio.gather(*[qm.claim_attempt(KEY) for _ in range(8)])
    allowed = [r for r in results if r.allowed]
    assert len(allowed) == 1
    await qm.record_success(KEY)


async def test_fail_closed_when_db_unavailable(temp_db, fixed_clock, monkeypatch):
    qm = QuotaManager.for_session_factory(temp_db, clock=fixed_clock)
    # Simulate DB unavailability by making the store's session factory raise.
    from contextlib import asynccontextmanager
    @asynccontextmanager
    async def failing_factory():
        raise RuntimeError("DB unavailable")
        yield
    monkeypatch.setattr(qm.store, "session_factory", failing_factory)
    claim = await qm.claim_attempt(KEY)
    assert not claim.allowed
    assert claim.reason == "denied"


def test_parse_duration_variants():
    assert parse_duration("2m59.56s") == pytest.approx(179.56, rel=1e-3)
    assert parse_duration("1h") == 3600
    assert parse_duration("1d") == 86400
    assert parse_duration("500ms") == 0.5
    assert parse_duration("30") == 30
    assert parse_duration(None) is None
    assert parse_duration("garbage") is None


def test_classify_quota_failure_uses_headers():
    # Retry-After takes precedence when present
    cls, delta = classify_quota_failure(
        {"Retry-After": "120", "x-ratelimit-reset-tokens": "2m",
         "x-ratelimit-remaining-tokens": "0"}, None)
    assert cls == TEMP_RATE_LIMIT
    assert delta.total_seconds() == 120

    cls, delta = classify_quota_failure(
        {"x-ratelimit-reset-requests": "5m", "x-ratelimit-remaining-requests": "0"}, None)
    assert cls == REQUEST_QUOTA
    assert delta.total_seconds() == pytest.approx(300, rel=1e-2)

    cls, delta = classify_quota_failure({"Retry-After": "30"}, None)
    assert cls == TEMP_RATE_LIMIT
    assert delta.total_seconds() == 30

    cls, delta = classify_quota_failure({}, None)
    assert cls == TEMP_RATE_LIMIT
    # Conservative backoff when no trustworthy reset.
    assert delta.total_seconds() == 300


async def test_other_failure_does_not_set_cooldown(qm):
    claim = await qm.claim_attempt(KEY)
    assert claim.allowed
    await qm.record_other_failure(KEY)  # e.g. 5xx
    view = await qm.get_view(KEY)
    assert view.state == AVAILABLE  # no cooldown for non-quota failures


def test_classify_per_minute_token_exhaustion_with_daily_reset():
    """Per-minute token limit hit, but daily reset header present -> use per-minute reset (short cooldown)."""
    # Per-minute token exhaustion: remaining-tokens=0, reset-tokens=60s (1 minute)
    # Daily reset header also present but should be ignored for per-minute limit
    headers = {
        "x-ratelimit-reset-tokens": "60",        # 1 minute = per-minute limit
        "x-ratelimit-remaining-tokens": "0",
        "x-ratelimit-reset-requests": "86400",   # 24 hours = daily limit (should not apply)
        "x-ratelimit-remaining-requests": "100", # requests still available
    }
    cls, delta = classify_quota_failure(headers, None)
    assert cls == TOKEN_QUOTA
    assert delta.total_seconds() == pytest.approx(60, rel=1e-2)  # short cooldown


def test_classify_daily_request_exhaustion():
    """Daily request limit exhausted -> long cooldown (daily reset)."""
    headers = {
        "x-ratelimit-reset-requests": "86400",   # 24 hours
        "x-ratelimit-remaining-requests": "0",
        "x-ratelimit-reset-tokens": "60",        # per-minute reset also present
        "x-ratelimit-remaining-tokens": "1000",  # tokens still available
    }
    cls, delta = classify_quota_failure(headers, None)
    assert cls == REQUEST_QUOTA
    assert delta.total_seconds() == pytest.approx(86400, rel=1e-2)  # long cooldown


def test_classify_no_headers_uses_conservative_fallback():
    """No rate-limit headers -> documented conservative fallback (300s)."""
    cls, delta = classify_quota_failure({}, None)
    assert cls == TEMP_RATE_LIMIT
    assert delta.total_seconds() == 300


def test_classify_malformed_values_handled_gracefully():
    """Malformed header values -> fall back to conservative backoff."""
    headers = {
        "Retry-After": "not-a-number",
        "x-ratelimit-reset-tokens": "invalid",
        "x-ratelimit-remaining-tokens": "0",
    }
    cls, delta = classify_quota_failure(headers, None)
    assert cls == TEMP_RATE_LIMIT
    assert delta.total_seconds() == 300


def test_classify_retry_after_takes_precedence_when_explicit():
    """Retry-After header is explicit -> use it even if other headers present."""
    headers = {
        "Retry-After": "45",                     # explicit 45 seconds
        "x-ratelimit-reset-tokens": "300",       # 5 minutes
        "x-ratelimit-remaining-tokens": "0",
    }
    cls, delta = classify_quota_failure(headers, None)
    assert cls == TEMP_RATE_LIMIT
    assert delta.total_seconds() == 45  # Retry-After wins


def test_classify_both_token_and_request_exhausted():
    """Both token and request exhausted -> longest reset wins, classification matches that resource."""
    headers = {
        "x-ratelimit-reset-tokens": "120",
        "x-ratelimit-remaining-tokens": "0",
        "x-ratelimit-reset-requests": "180",
        "x-ratelimit-remaining-requests": "0",
    }
    cls, delta = classify_quota_failure(headers, None)
    # Request reset is longer (180s vs 120s), so REQUEST_QUOTA wins
    assert cls == REQUEST_QUOTA
    assert delta.total_seconds() == 180


def test_classify_malformed_remaining_values():
    """Non-numeric remaining values -> treated as not exhausted."""
    headers = {
        "x-ratelimit-reset-tokens": "60",
        "x-ratelimit-remaining-tokens": "abc",  # malformed
        "x-ratelimit-reset-requests": "300",
        "x-ratelimit-remaining-requests": "0",
    }
    cls, delta = classify_quota_failure(headers, None)
    # tokens not exhausted (malformed), requests exhausted -> REQUEST_QUOTA
    assert cls == REQUEST_QUOTA
    assert delta.total_seconds() == pytest.approx(300, rel=1e-2)


def test_classify_partial_headers_only_token_exhausted():
    """Only token exhaustion headers present -> TOKEN_QUOTA."""
    headers = {
        "x-ratelimit-reset-tokens": "90",
        "x-ratelimit-remaining-tokens": "0",
    }
    cls, delta = classify_quota_failure(headers, None)
    assert cls == TOKEN_QUOTA
    assert delta.total_seconds() == pytest.approx(90, rel=1e-2)
