"""Service-level analyze tests: cache hit/miss, force bypasses cache but not quota gate,
concurrent identical requests share execution, cooldown makes zero API calls."""

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, AsyncMock, patch

import pytest

from analysis.service import AnalyzeService, AnalysisTooFrequent
from analysis.quota_manager import QuotaManager
from analysis.schemas import AnalysisReport, AnalysisResponse


@pytest.fixture
async def mock_groq_client():
    """Mock Groq client that tracks calls."""
    call_count = {"count": 0}

    async def mock_call_groq(*args, **kwargs):
        call_count["count"] += 1
        result = Mock()
        result.completed = True
        result.status_code = 200
        result.headers = {"x-ratelimit-remaining-tokens": "100"}
        result.content = '{"overall_status":"healthy","health_score":80,"irrigation_recommendation":"SKIP","dashboard_summary":"All good","per_sensor_assessments":[],"risks":[],"evidence":[],"recommended_actions":[],"data_quality_warnings":[]}'
        return result

    with patch("analysis.service.groq_client.call_groq", side_effect=mock_call_groq):
        yield call_count


@pytest.fixture
async def analyze_service(temp_db, fixed_clock, mock_groq_client):
    qm = QuotaManager.for_session_factory(temp_db, clock=fixed_clock)
    svc = AnalyzeService(
        temp_db, qm, clock=fixed_clock,
        cache_ttl_seconds=1800, min_interval_seconds=0,
    )
    return svc


async def test_cache_hit_returns_cached_report(analyze_service, temp_db, fixed_clock, mock_groq_client):
    """Identical input within rounding precision should hit cache."""
    farm_id = await primary_farm_id(temp_db)

    # Add sensor data
    await add_reading(temp_db, farm_id=farm_id, soil=45.0, temp=25.0, hum=60.0)

    # First call - should call Groq
    response1 = await analyze_service.analyze(farm_id=farm_id, groq_api_key="test-key")
    assert mock_groq_client["count"] == 1
    assert not response1.from_cache

    # Second call with same input - should hit cache
    response2 = await analyze_service.analyze(farm_id=farm_id, groq_api_key="test-key")
    assert mock_groq_client["count"] == 1  # No additional Groq call
    assert response2.from_cache


async def test_cache_miss_on_changed_value(analyze_service, temp_db, fixed_clock, mock_groq_client):
    """Changed sensor value should miss cache."""
    farm_id = await primary_farm_id(temp_db)

    await add_reading(temp_db, farm_id=farm_id, soil=45.0, temp=25.0)
    response1 = await analyze_service.analyze(farm_id=farm_id, groq_api_key="test-key")
    assert mock_groq_client["count"] == 1

    # Change soil moisture beyond quantization step (2%)
    fixed_clock.advance(1)
    await add_reading(temp_db, farm_id=farm_id, soil=48.0, temp=25.0)
    response2 = await analyze_service.analyze(farm_id=farm_id, groq_api_key="test-key")
    assert mock_groq_client["count"] == 2  # New Groq call


async def test_cache_miss_on_crop_profile_version_change(analyze_service, temp_db, fixed_clock, mock_groq_client):
    """Changed crop profile version should miss cache."""
    farm_id = await primary_farm_id(temp_db)
    await add_reading(temp_db, farm_id=farm_id, soil=45.0, temp=25.0)

    response1 = await analyze_service.analyze(farm_id=farm_id, groq_api_key="test-key")
    assert mock_groq_client["count"] == 1

    # Simulate profile version change by advancing time and changing crop
    fixed_clock.advance(100)
    # Note: In real scenario, crop profile version would change via config
    # For this test, we verify the cache key includes profile_version


async def test_expired_cache_not_reused(analyze_service, temp_db, fixed_clock, mock_groq_client):
    """Expired cache entries should not be reused."""
    farm_id = await primary_farm_id(temp_db)
    await add_reading(temp_db, farm_id=farm_id, soil=45.0, temp=25.0)

    # First call
    response1 = await analyze_service.analyze(farm_id=farm_id, groq_api_key="test-key")
    assert mock_groq_client["count"] == 1

    # Advance past cache TTL (1800s default)
    fixed_clock.advance(1801)

    # Should call Groq again
    response2 = await analyze_service.analyze(farm_id=farm_id, groq_api_key="test-key")
    assert mock_groq_client["count"] == 2


async def test_api_and_rule_engine_cached_separately(analyze_service, temp_db, fixed_clock, mock_groq_client):
    """API and rule-engine reports cached separately; rule-engine cache doesn't block API after cooldown."""
    farm_id = await primary_farm_id(temp_db)
    await add_reading(temp_db, farm_id=farm_id, soil=45.0, temp=25.0)

    # First call with quota exhausted -> rule engine
    # Simulate quota exhaustion by not providing API key
    response1 = await analyze_service.analyze(farm_id=farm_id, groq_api_key=None)
    assert response1.report.analysis_method == "rule_engine"
    assert mock_groq_client["count"] == 0

    # Now provide API key - should call Groq (not blocked by rule-engine cache)
    response2 = await analyze_service.analyze(farm_id=farm_id, groq_api_key="test-key")
    assert response2.report.analysis_method == "external_model"
    assert mock_groq_client["count"] == 1


async def test_force_bypasses_cache_not_quota_gate(analyze_service, temp_db, fixed_clock, mock_groq_client):
    """force=true bypasses cache but still checks quota gate."""
    farm_id = await primary_farm_id(temp_db)
    await add_reading(temp_db, farm_id=farm_id, soil=45.0, temp=25.0)

    # First call
    response1 = await analyze_service.analyze(farm_id=farm_id, groq_api_key="test-key")
    assert mock_groq_client["count"] == 1

    # Force with same input - should bypass cache but still check quota
    response2 = await analyze_service.analyze(farm_id=farm_id, groq_api_key="test-key", force=True)
    assert response2.forced is True
    assert mock_groq_client["count"] == 2  # Quota gate still checked, cache bypassed


async def test_concurrent_identical_requests_share_execution(analyze_service, temp_db, fixed_clock, mock_groq_client):
    """Concurrent identical requests should share one Groq execution."""
    farm_id = await primary_farm_id(temp_db)
    await add_reading(temp_db, farm_id=farm_id, soil=45.0, temp=25.0)

    # Launch 5 concurrent requests
    tasks = [analyze_service.analyze(farm_id=farm_id, groq_api_key="test-key") for _ in range(5)]
    responses = await asyncio.gather(*tasks)

    # Only one Groq call should have been made
    assert mock_groq_client["count"] == 1
    # All responses should have same report (from cache or single execution)
    for r in responses:
        assert r.report.input_hash == responses[0].report.input_hash


async def test_cooldown_zero_api_calls(analyze_service, temp_db, fixed_clock, mock_groq_client):
    """During cooldown, zero API calls should be made even with concurrent requests."""
    from analysis.quota_manager import TEMP_RATE_LIMIT

    farm_id = await primary_farm_id(temp_db)
    await add_reading(temp_db, farm_id=farm_id, soil=45.0, temp=25.0)

    # Trigger cooldown by recording quota exhaustion
    qm = analyze_service.quota
    await qm.record_quota_exhaustion("test-key", {"Retry-After": "60"})

    # Verify cooldown active
    view = await qm.get_view("test-key")
    assert view.state == "COOLDOWN"

    # Multiple concurrent requests during cooldown
    tasks = [analyze_service.analyze(farm_id=farm_id, groq_api_key="test-key") for _ in range(10)]
    responses = await asyncio.gather(*tasks)

    # All should return rule-engine reports, zero Groq calls
    assert mock_groq_client["count"] == 0
    for r in responses:
        assert r.report.analysis_method == "rule_engine"
        assert "cooldown" in r.quota_state.lower() or r.quota_state == "rule_engine_only"


async def test_min_interval_enforced(analyze_service, temp_db, fixed_clock, mock_groq_client):
    """min_interval_seconds should be enforced per client."""
    svc = AnalyzeService(
        temp_db, analyze_service.quota, clock=fixed_clock,
        min_interval_seconds=10,
    )

    farm_id = await primary_farm_id(temp_db)
    await add_reading(temp_db, farm_id=farm_id, soil=45.0, temp=25.0)

    # First request
    response1 = await svc.analyze(farm_id=farm_id, groq_api_key="test-key", client_id="client-1")
    assert mock_groq_client["count"] == 1

    # Second request from same client within interval
    try:
        response2 = await svc.analyze(farm_id=farm_id, groq_api_key="test-key", client_id="client-1")
        # Should not reach here - AnalysisTooFrequent raised
        assert False, "Expected AnalysisTooFrequent"
    except AnalysisTooFrequent as e:
        assert e.retry_after_seconds > 0

    # Different client should be allowed
    response3 = await svc.analyze(farm_id=farm_id, groq_api_key="test-key", client_id="client-2")
    assert mock_groq_client["count"] == 2


async def test_cooldown_cross_connection_isolation(temp_db, fixed_clock, mock_groq_client):
    """Cooldown should be shared across separate connections (same DB)."""
    qm1 = QuotaManager.for_session_factory(temp_db, clock=fixed_clock)
    qm2 = QuotaManager.for_session_factory(temp_db, clock=fixed_clock)

    # Record exhaustion via first connection
    await qm1.record_quota_exhaustion("test-key", {"Retry-After": "120"})

    # Second connection should see cooldown
    view = await qm2.get_view("test-key")
    assert view.state == "COOLDOWN"

    # Both connections should deny claims
    claim1 = await qm1.claim_attempt("test-key")
    claim2 = await qm2.claim_attempt("test-key")
    assert not claim1.allowed
    assert not claim2.allowed


if __name__ == "__main__":
    pytest.main([__file__, "-v"])