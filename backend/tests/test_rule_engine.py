"""Deterministic rule-engine tests (Path B). Pure — no DB, no network."""

import datetime
from datetime import timezone

from analysis import rule_engine
from analysis.crop_profiles import resolve_profile, analysis_version, config_version
from analysis.schemas import WeatherSummary, HistorySummary


NOW = datetime.datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


def _profile():
    return resolve_profile("Tomato")[0]


def _summarize(snapshot, weather=None, history=None):
    profile, _name, ver = resolve_profile("Tomato")
    ws = rule_engine.summarize_weather(weather)
    hs = history or rule_engine.summarize_history([], profile, NOW)
    return profile, ws, hs


def test_deterministic_same_inputs_same_output():
    profile, ws, hs = _summarize({"soil_moisture": 25, "temperature": 35, "humidity": 38, "light": 2000, "rain": False})
    r1 = rule_engine.evaluate(sensor_snapshot={"soil_moisture": 25, "temperature": 35, "humidity": 38, "light": 2000, "rain": False},
                              profile=profile, weather_summary=ws, history_summary=hs,
                              analysis_version=analysis_version(), profile_version=config_version(), clock=lambda: NOW)
    r2 = rule_engine.evaluate(sensor_snapshot={"soil_moisture": 25, "temperature": 35, "humidity": 38, "light": 2000, "rain": False},
                              profile=profile, weather_summary=ws, history_summary=hs,
                              analysis_version=analysis_version(), profile_version=config_version(), clock=lambda: NOW)
    assert r1.model_dump() == r2.model_dump()
    assert r1.analysis_method == "rule_engine"
    assert r1.irrigation_recommendation == "IRRIGATE"
    assert r1.health_score is not None and r1.health_score < 60

def test_health_score_requires_minimum_evidence():
    # Soil valid but no other valid reading -> no health score.
    profile, ws, hs = _summarize({"soil_moisture": 40, "temperature": None, "humidity": None, "light": None, "rain": None})
    r = rule_engine.evaluate(sensor_snapshot={"soil_moisture": 40, "temperature": None, "humidity": None, "light": None, "rain": None},
                              profile=profile, weather_summary=ws, history_summary=hs,
                              analysis_version=analysis_version(), profile_version=config_version(), clock=lambda: NOW)
    assert r.health_score is None
    assert r.overall_status == "insufficient_data"
    assert r.irrigation_recommendation == "IRRIGATE"  # soil low enough vs optimal_min


def test_missing_soil_yields_insufficient_data():
    profile, ws, hs = _summarize({"soil_moisture": None, "temperature": 26, "humidity": 65, "light": 2000, "rain": False})
    r = rule_engine.evaluate(sensor_snapshot={"soil_moisture": None, "temperature": 26, "humidity": 65, "light": 2000, "rain": False},
                              profile=profile, weather_summary=ws, history_summary=hs,
                              analysis_version=analysis_version(), profile_version=config_version(), clock=lambda: NOW)
    assert r.health_score is None
    assert r.irrigation_recommendation == "INSUFFICIENT_DATA"


def test_out_of_range_flagged_not_used_as_valid():
    profile, ws, hs = _summarize({"soil_moisture": 150, "temperature": 26, "humidity": 65, "light": 2000, "rain": False})
    r = rule_engine.evaluate(sensor_snapshot={"soil_moisture": 150, "temperature": 26, "humidity": 65, "light": 2000, "rain": False},
                              profile=profile, weather_summary=ws, history_summary=hs,
                              analysis_version=analysis_version(), profile_version=config_version(), clock=lambda: NOW)
    soil_a = next(a for a in r.per_sensor_assessments if a.sensor == "soil_moisture")
    assert soil_a.status == "out_of_range"
    assert any("out of" in w.lower() or "range" in w.lower() for w in r.data_quality_warnings)
    assert r.health_score is None  # soil not valid -> no score


def test_rain_expected_delays_irrigation():
    profile, ws, hs = _summarize({"soil_moisture": 25, "temperature": 30, "humidity": 60, "light": 2000, "rain": False},
                                  weather={"rain_probability_next_hour": 80, "rain_expected": True, "temperature_2m_max": 30})
    r = rule_engine.evaluate(sensor_snapshot={"soil_moisture": 25, "temperature": 30, "humidity": 60, "light": 2000, "rain": False},
                              profile=profile, weather_summary=ws, history_summary=hs,
                              analysis_version=analysis_version(), profile_version=config_version(), clock=lambda: NOW)
    assert r.irrigation_recommendation == "DELAY"


def test_waterlogging_skips_and_flags_risk():
    profile, ws, hs = _summarize({"soil_moisture": 90, "temperature": 26, "humidity": 65, "light": 2000, "rain": False})
    r = rule_engine.evaluate(sensor_snapshot={"soil_moisture": 90, "temperature": 26, "humidity": 65, "light": 2000, "rain": False},
                              profile=profile, weather_summary=ws, history_summary=hs,
                              analysis_version=analysis_version(), profile_version=config_version(), clock=lambda: NOW)
    assert r.irrigation_recommendation == "SKIP"
    assert any(risk.name == "waterlogging" for risk in r.risks)


def test_risks_and_actions_are_advisory_and_separate_from_measurements():
    profile, ws, hs = _summarize({"soil_moisture": 22, "temperature": 39, "humidity": 30, "light": 2000, "rain": False})
    r = rule_engine.evaluate(sensor_snapshot={"soil_moisture": 22, "temperature": 39, "humidity": 30, "light": 2000, "rain": False},
                              profile=profile, weather_summary=ws, history_summary=hs,
                              analysis_version=analysis_version(), profile_version=config_version(), clock=lambda: NOW)
    # Risk evidence must cite measured values, not invented diagnoses.
    for risk in r.risks:
        assert risk.evidence
        assert "diagnos" not in risk.evidence.lower()
    assert any("advisory" in a.lower() for a in r.recommended_actions)
    assert r.analysis_method == "rule_engine"


def test_history_summary_requires_min_points():
    profile, _n, _v = resolve_profile("Tomato")
    readings = [
        {"ts": NOW, "soil_moisture": 40, "temperature": 25},
        {"ts": NOW, "soil_moisture": 41, "temperature": 26},
    ]
    hs = rule_engine.summarize_history(readings, profile, NOW)
    assert hs.available is False
    assert hs.soil_moisture_trend == "insufficient"


def test_weather_summary_buckets_rain_probability():
    ws = rule_engine.summarize_weather({"rain_probability_next_hour": 73, "rain_expected": True, "temperature_2m_max": 28.4})
    assert ws.available is True
    assert ws.rain_probability_bucket == 70  # quantized to 10% buckets
    assert ws.max_temperature_bucket == 28   # quantized to 1°C
