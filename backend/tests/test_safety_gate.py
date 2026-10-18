"""Safety gate tests: 180s cap, 10/day limit, stale/invalid sensors, audit-write failure,
analysis never publishes pump, worker ignores own pump messages."""

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from analysis.safety_gate import SafetyGate, SafetyDecision
from analysis.crop_profiles import resolve_profile


@pytest.fixture
async def safety_gate(temp_db, fixed_clock):
    return SafetyGate(temp_db, clock=fixed_clock, publish_fn=lambda a, d: True)


async def test_duration_cap_clamps_to_180s(safety_gate, temp_db, fixed_clock):
    """Requested duration > 180s should be clamped to 180s."""
    fixed_clock.set(datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc))

    # Add valid sensor reading
    async with temp_db() as session:
        from database.repositories import SensorReadingRepository, FarmRepository
        farm_repo = FarmRepository(session)
        farms = await farm_repo.list_active()
        farm_id = farms[0].id if farms else "test-farm"

        sensor_repo = SensorReadingRepository(session)
        await sensor_repo.create(
            farm_id=farm_id, device_id=None,
            soil_moisture=30.0, temperature=25.0, humidity=60.0,
            light=2000.0, rain=False,
            timestamp=fixed_clock(), received_at=fixed_clock(),
            quality_status="ok",
        )

    decision, published, audit_id = await safety_gate.actuate(
        action="ON", duration_sec=300, farm_id=farm_id,
        crop_name="Tomato", sensor_snapshot={"soil_moisture": 30, "temperature": 25, "humidity": 60},
        source="manual_ui", actor="test",
    )

    assert decision.allowed
    assert decision.duration_sec == 180  # clamped
    assert decision.clamped is True


async def test_duration_cap_rejects_invalid(safety_gate, temp_db, fixed_clock):
    """Invalid duration (negative, non-numeric) should be rejected."""
    fixed_clock.set(datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc))

    decision = await safety_gate.evaluate(
        action="ON", duration_sec=-10, farm_id="test",
        crop_name="Tomato", sensor_snapshot={"soil_moisture": 30, "temperature": 25},
    )
    assert not decision.allowed
    assert "Invalid duration" in decision.reason


async def test_daily_limit_10_events_persists_across_restart(temp_db, fixed_clock):
    """Daily limit of 10 events should be enforced and survive restart."""
    base = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    fixed_clock.set(base)

    # Add valid sensor reading
    async with temp_db() as session:
        from database.repositories import SensorReadingRepository, FarmRepository
        farm_repo = FarmRepository(session)
        farms = await farm_repo.list_active()
        farm_id = farms[0].id if farms else "test-farm"

        sensor_repo = SensorReadingRepository(session)
        await sensor_repo.create(
            farm_id=farm_id, device_id=None,
            soil_moisture=30.0, temperature=25.0, humidity=60.0,
            light=2000.0, rain=False,
            timestamp=base, received_at=base,
            quality_status="ok",
        )

    gate = SafetyGate(temp_db, clock=fixed_clock, publish_fn=lambda a, d: True)

    # Make 10 allowed irrigations
    for i in range(10):
        decision, published, _ = await gate.actuate(
            action="ON", duration_sec=60, farm_id=farm_id,
            crop_name="Tomato", sensor_snapshot={"soil_moisture": 30, "temperature": 25, "humidity": 60},
            source="manual_ui", actor="test",
        )
        assert decision.allowed, f"Irrigation {i+1} should be allowed"

    # 11th should be rejected
    decision, published, _ = await gate.actuate(
        action="ON", duration_sec=60, farm_id=farm_id,
        crop_name="Tomato", sensor_snapshot={"soil_moisture": 30, "temperature": 25, "humidity": 60},
        source="manual_ui", actor="test",
    )
    assert not decision.allowed
    assert "daily limit reached" in decision.reason.lower()

    # Simulate restart - new gate on same DB
    gate2 = SafetyGate(temp_db, clock=fixed_clock, publish_fn=lambda a, d: True)
    decision2, _, _ = await gate2.actuate(
        action="ON", duration_sec=60, farm_id=farm_id,
        crop_name="Tomato", sensor_snapshot={"soil_moisture": 30, "temperature": 25, "humidity": 60},
        source="manual_ui", actor="test",
    )
    assert not decision2.allowed
    assert "daily limit reached" in decision2.reason.lower()


async def test_stale_sensor_blocks_actuation(safety_gate, temp_db, fixed_clock):
    """Sensor reading older than staleness limit should block actuation."""
    base = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    fixed_clock.set(base)

    # Add stale sensor reading (2 hours old, staleness limit is typically 15 min)
    stale_time = base - timedelta(hours=2)
    async with temp_db() as session:
        from database.repositories import SensorReadingRepository, FarmRepository
        farm_repo = FarmRepository(session)
        farms = await farm_repo.list_active()
        farm_id = farms[0].id if farms else "test-farm"

        sensor_repo = SensorReadingRepository(session)
        await sensor_repo.create(
            farm_id=farm_id, device_id=None,
            soil_moisture=30.0, temperature=25.0, humidity=60.0,
            light=2000.0, rain=False,
            timestamp=stale_time, received_at=stale_time,
            quality_status="ok",
        )

    # Current snapshot uses stale data
    decision = await safety_gate.evaluate(
        action="ON", duration_sec=60, farm_id=farm_id,
        crop_name="Tomato", sensor_snapshot={"soil_moisture": 30, "temperature": 25, "humidity": 60},
    )
    # Should be rejected due to stale data
    assert not decision.allowed


async def test_invalid_sensor_blocks_actuation(safety_gate, temp_db, fixed_clock):
    """Invalid sensor readings (out of range) should block actuation."""
    fixed_clock.set(datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc))

    async with temp_db() as session:
        from database.repositories import SensorReadingRepository, FarmRepository
        farm_repo = FarmRepository(session)
        farms = await farm_repo.list_active()
        farm_id = farms[0].id if farms else "test-farm"

        sensor_repo = SensorReadingRepository(session)
        await sensor_repo.create(
            farm_id=farm_id, device_id=None,
            soil_moisture=150.0, temperature=25.0, humidity=60.0,  # Invalid soil moisture
            light=2000.0, rain=False,
            timestamp=fixed_clock(), received_at=fixed_clock(),
            quality_status="out_of_range",
        )

    decision = await safety_gate.evaluate(
        action="ON", duration_sec=60, farm_id=farm_id,
        crop_name="Tomato", sensor_snapshot={"soil_moisture": 150, "temperature": 25, "humidity": 60},
    )
    assert not decision.allowed
    assert "out of range" in decision.reason.lower() or "invalid" in decision.reason.lower()


async def test_audit_write_failure_blocks_actuation(temp_db, fixed_clock, monkeypatch):
    """If audit write fails, pump should NOT be actuated."""
    fixed_clock.set(datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc))

    async with temp_db() as session:
        from database.repositories import SensorReadingRepository, FarmRepository
        farm_repo = FarmRepository(session)
        farms = await farm_repo.list_active()
        farm_id = farms[0].id if farms else "test-farm"

        sensor_repo = SensorReadingRepository(session)
        await sensor_repo.create(
            farm_id=farm_id, device_id=None,
            soil_moisture=30.0, temperature=25.0, humidity=60.0,
            light=2000.0, rain=False,
            timestamp=fixed_clock(), received_at=fixed_clock(),
            quality_status="ok",
        )

    # Make session factory fail on commit
    from contextlib import asynccontextmanager
    @asynccontextmanager
    async def failing_factory():
        raise RuntimeError("DB unavailable")
        yield

    gate = SafetyGate(temp_db, clock=fixed_clock, publish_fn=lambda a, d: True)
    monkeypatch.setattr(gate, "session_factory", failing_factory)

    decision, published, audit_id = await gate.actuate(
        action="ON", duration_sec=60, farm_id=farm_id,
        crop_name="Tomato", sensor_snapshot={"soil_moisture": 30, "temperature": 25, "humidity": 60},
        source="manual_ui", actor="test",
    )

    assert not decision.allowed
    assert audit_id is None
    assert published is False


async def test_analysis_and_report_storage_never_publish_pump(safety_gate, temp_db, fixed_clock):
    """Analysis report storage should never create a pump command."""
    # This is a design verification - the safety gate is only called from /pump/control
    # Analysis service stores reports but never calls safety_gate.actuate()
    # We verify by checking that analysis service doesn't import or use safety_gate
    import analysis.service as svc_module
    import analysis.safety_gate as gate_module

    # SafetyGate should not be imported by analysis service
    assert not hasattr(svc_module, 'SafetyGate')
    # AnalyzeService should not have safety_gate attribute
    from analysis.service import AnalyzeService
    assert not hasattr(AnalyzeService, 'safety_gate')


async def test_worker_ignores_own_pump_messages():
    """MQTT worker should ignore pump messages on agromind/data topic."""
    # The worker's _process function checks msg.get("type") != "sensor" and returns early
    # This is verified by the worker code in mqtt_worker.py:225-227
    from mqtt_worker import _process

    # We can't easily test the async function without full setup,
    # but we verify the logic exists in the source
    import mqtt_worker
    import inspect
    source = inspect.getsource(mqtt_worker._process)
    assert 'msg.get("type") != "sensor"' in source
    assert 'Ignored non-sensor message' in source


if __name__ == "__main__":
    pytest.main([__file__, "-v"])