"""Path B — deterministic crop-health rule engine.

No LLM, no network. Same inputs + same config => identical output. Reuses and
consolidates the rule-based fallback logic that previously lived in
``agents/sensor_interpreter.py``, ``agents/crop_doctor.py``,
``agents/weather_intelligence.py`` and ``agents/irrigation_planner.py`` so the
behaviour stays consistent with the simulator's local ``compute_health_score``.

The engine only reasons about sensors that actually exist on the wire (see
``firmware/agromind_esp32.ino`` and ``simulator.py``):

* ``soil_moisture``  – 0–100 % (firmware pre-calibrates the raw ADC to a %)
* ``temperature``    – °C (DHT22)
* ``humidity``       – % (DHT22)
* ``light``          – unitless raw ADC/LDR reading (NOT lux; used only as a
                      relative brightness hint)
* ``rain``           – bool (digital rain sensor)

The firmware/simulator send NO device timestamp and NO numeric rain value, so
device time defaults to server-receive time and rain is boolean only. Trends
come from the supplied ``history_summary`` (computed from SQLite by the caller
via :func:`summarize_history`).

Measured facts, inferred risks and recommendations are deliberately kept in
separate fields. A moisture threshold alone is never a diagnosis.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Optional

from analysis.schemas import (
    AnalysisReport,
    CropProfileSnapshot,
    Evidence,
    HistorySummary,
    Risk,
    SensorAssessment,
    WeatherSummary,
)

Clock = Callable[[], datetime]

ENGINE_ID = "rule_engine"
# Conservative fallback if no reset header is trustworthy — kept here so tests
# can assert the documented backoff the rule engine implies for the quota gate.
CONSERVATIVE_BACKOFF_SECONDS = 300


def _utcnow(clock: Clock) -> datetime:
    now = clock()
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return now.astimezone(timezone.utc)


def _parse_ts(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        try:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _is_fresh(ts: Optional[datetime], now: datetime, staleness_seconds: int) -> bool:
    if ts is None:
        # No timestamp => treat as fresh (server just received it). This is the
        # normal case because the firmware sends no device clock.
        return True
    return (now - ts).total_seconds() <= staleness_seconds


def _in_range(value: Optional[float], lo: float, hi: float) -> bool:
    return value is not None and lo <= value <= hi


def summarize_history(
    readings: list[dict[str, Any]],
    profile: dict[str, Any],
    now: datetime,
) -> HistorySummary:
    """Build a deterministic, hash-stable history summary from recent readings.

    Only valid, non-stale points within the configured window count toward
    trends. Returns ``available=False`` when there are too few points.
    """
    hist_cfg = profile.get("history", {})
    window = int(hist_cfg.get("window_points", 20))
    min_points = int(hist_cfg.get("min_points_for_trend", 4))
    max_age = int(hist_cfg.get("max_age_seconds", 3600))

    candidates: list[dict[str, Any]] = []
    for r in readings[:window]:
        ts = _parse_ts(r.get("ts") or r.get("timestamp") or r.get("created_at"))
        if ts is not None and (now - ts).total_seconds() > max_age:
            continue
        soil = r.get("soil_moisture")
        temp = r.get("temperature")
        if soil is None and temp is None:
            continue
        candidates.append({"soil": soil, "temp": temp, "ts": ts})

    summary = HistorySummary(point_count=len(candidates))
    if len(candidates) < min_points:
        summary.soil_moisture_trend = "insufficient"
        summary.temperature_trend = "insufficient"
        return summary

    soils = [c["soil"] for c in candidates if c["soil"] is not None]
    temps = [c["temp"] for c in candidates if c["temp"] is not None]
    summary.available = True
    summary.soil_moisture_trend = _trend(soils)
    summary.temperature_trend = _trend(temps)
    return summary


def _trend(values: list[float | None]) -> str:
    vals = [v for v in values if v is not None]
    if len(vals) < 2:
        return "insufficient"
    mid = len(vals) // 2
    first = sum(vals[:mid]) / max(1, mid)
    second = sum(vals[mid:]) / max(1, len(vals) - mid)
    diff = second - first
    if diff > 2:
        return "increasing"
    if diff < -2:
        return "decreasing"
    return "stable"


def summarize_weather(raw: dict[str, Any] | None) -> WeatherSummary:
    """Build a deterministic, bucketed weather summary for hashing + reasoning."""
    if not raw:
        return WeatherSummary(available=False)
    rain_prob = raw.get("rain_probability_next_hour")
    rain_prob = float(rain_prob) if isinstance(rain_prob, (int, float)) else None
    max_temp = raw.get("temperature_2m_max")
    max_temp = float(max_temp) if isinstance(max_temp, (int, float)) else None
    rain_expected = bool(raw.get("rain_expected"))
    if rain_prob is not None and not rain_expected:
        rain_expected = rain_prob > 60
    return WeatherSummary(
        available=True,
        rain_probability_bucket=(int(rain_prob // 10) * 10) if rain_prob is not None else None,
        rain_expected=rain_expected,
        max_temperature_bucket=(round(max_temp) if max_temp is not None else None),
        source=str(raw.get("source", "open-meteo")),
    )


def _thresholds(profile: dict[str, Any]) -> dict[str, Any]:
    return profile.get("thresholds", {})


def evaluate(
    *,
    sensor_snapshot: dict[str, Any],
    profile: dict[str, Any],
    weather_summary: WeatherSummary,
    history_summary: HistorySummary,
    analysis_version: str,
    profile_version: str,
    clock: Clock = lambda: datetime.now(timezone.utc),
) -> AnalysisReport:
    """Produce a deterministic AnalysisReport. Pure: no I/O, no randomness."""
    now = _utcnow(clock)
    th = _thresholds(profile)
    soil_th = th.get("soil_moisture_percent", {})
    temp_th = th.get("temperature_celsius", {})
    hum_th = th.get("humidity_percent", {})
    rain_th = th.get("rain", {})
    light_th = th.get("light_raw_adc", {})
    staleness = int(profile.get("staleness_limit_seconds", 900))

    soil = sensor_snapshot.get("soil_moisture")
    temp = sensor_snapshot.get("temperature")
    hum = sensor_snapshot.get("humidity")
    light = sensor_snapshot.get("light")
    rain = sensor_snapshot.get("rain")
    measured_at = _parse_ts(sensor_snapshot.get("measured_at") or sensor_snapshot.get("received_at"))

    assessments: list[SensorAssessment] = []
    warnings: list[str] = []

    # ── Soil moisture ────────────────────────────────────────────────────
    soil_status, soil_class, soil_note = _assess_soil(
        soil, measured_at, now, staleness, soil_th, warnings
    )
    assessments.append(SensorAssessment(
        sensor="soil_moisture", status=soil_status, value=soil, unit="%",
        classification=soil_class, note=soil_note,
    ))

    # ── Temperature ─────────────────────────────────────────────────────
    temp_status, temp_class, temp_note = _assess_temperature(
        temp, measured_at, now, staleness, temp_th, warnings
    )
    assessments.append(SensorAssessment(
        sensor="temperature", status=temp_status, value=temp, unit="°C",
        classification=temp_class, note=temp_note,
    ))

    # ── Humidity ────────────────────────────────────────────────────────
    hum_status, hum_class, hum_note = _assess_humidity(
        hum, measured_at, now, staleness, hum_th, warnings
    )
    assessments.append(SensorAssessment(
        sensor="humidity", status=hum_status, value=hum, unit="%",
        classification=hum_class, note=hum_note,
    ))

    # ── Rain (boolean; skip entirely if the rain sensor is disabled) ────
    if rain_th.get("valid", True):
        rain_status, rain_class, rain_note = _assess_rain(rain, measured_at, now, staleness, warnings)
        assessments.append(SensorAssessment(
            sensor="rain", status=rain_status, value=rain, unit="",
            classification=rain_class, note=rain_note,
        ))
    else:
        warnings.append("Rain sensor not configured; rain excluded from assessment.")

    # ── Light (unitless raw reading; hint only) ─────────────────────────
    light_status, light_class, light_note = _assess_light(light, light_th, warnings)
    assessments.append(SensorAssessment(
        sensor="light", status=light_status, value=light, unit="raw",
        classification=light_class, note=light_note,
    ))

    # ── Minimum evidence for a health score ─────────────────────────────
    soil_valid_fresh = soil_status == "valid"
    other_valid_fresh = temp_status == "valid" or hum_status == "valid" or any(
        a.sensor == "rain" and a.status == "valid" for a in assessments
    )
    has_min_evidence = soil_valid_fresh and other_valid_fresh

    # ── Risks (inferred from measured facts) ────────────────────────────
    risks: list[Risk] = []
    evidence: list[Evidence] = []
    if soil_valid_fresh:
        stress_low = float(soil_th.get("stress_low", 30.0))
        waterlog = float(soil_th.get("waterlogging_high", 85.0))
        if soil is not None and soil < stress_low:
            sev = "critical" if soil < stress_low - 10 else "high"
            risks.append(Risk(name="dehydration", severity=sev,
                              evidence=f"soil moisture {soil}% below stress threshold {stress_low}%",
                              source="measured"))
        if soil is not None and soil > waterlog:
            risks.append(Risk(name="waterlogging", severity="medium",
                              evidence=f"soil moisture {soil}% above waterlogging threshold {waterlog}%",
                              source="measured"))
        evidence.append(Evidence(finding="soil_moisture", basis="measured",
                                 detail=f"{soil}% ({soil_class})"))
    if temp_status == "valid" and temp is not None:
        heat = float(temp_th.get("heat_stress_above", 34.0))
        extreme = float(temp_th.get("extreme_heat_above", 38.0))
        cold = float(temp_th.get("cold_stress_below", 15.0))
        if temp > extreme:
            risks.append(Risk(name="extreme_heat", severity="critical",
                              evidence=f"temperature {temp}°C above extreme heat threshold {extreme}°C",
                              source="measured"))
        elif temp > heat:
            risks.append(Risk(name="heat_stress", severity="high",
                              evidence=f"temperature {temp}°C above heat stress threshold {heat}°C",
                              source="measured"))
        if temp < cold:
            risks.append(Risk(name="cold_stress", severity="medium",
                              evidence=f"temperature {temp}°C below cold stress threshold {cold}°C",
                              source="measured"))
        if temp > heat and hum_status == "valid" and hum is not None and hum < float(hum_th.get("low_below", 30.0)):
            risks.append(Risk(name="high_evaporation", severity="high",
                              evidence=f"temperature {temp}°C with humidity {hum}% raises evaporation risk",
                              source="inferred"))
        evidence.append(Evidence(finding="temperature", basis="measured",
                                 detail=f"{temp}°C ({temp_class})"))
    if hum_status == "valid" and hum is not None:
        evidence.append(Evidence(finding="humidity", basis="measured",
                                 detail=f"{hum}% ({hum_class})"))
    if weather_summary.available and weather_summary.rain_expected:
        evidence.append(Evidence(finding="rain_expected", basis="forecast",
                                 detail=f"rain probability bucket ~{weather_summary.rain_probability_bucket}%"))
    if history_summary.available:
        evidence.append(Evidence(
            finding="trend", basis="history",
            detail=f"soil {history_summary.soil_moisture_trend}, temp {history_summary.temperature_trend} "
                   f"over {history_summary.point_count} points",
        ))

    # ── Health score (only with minimum evidence) ───────────────────────
    health_score: Optional[int] = None
    if has_min_evidence:
        health_score = _compute_health_score(soil, temp, hum, rain, soil_th, temp_th, hum_th)
    else:
        warnings.append("Insufficient evidence for a health score (need valid fresh soil moisture plus one other valid reading).")

    # ── Irrigation recommendation (advisory; never actuates) ─────────────
    irr_rec = _irrigation_recommendation(
        soil=soil, soil_status=soil_status, rain=rain, weather=weather_summary,
        soil_th=soil_th, history=history_summary,
    )

    # ── Recommended actions (advisory only) ─────────────────────────────
    actions = _recommended_actions(irr_rec, risks, warnings)

    overall = _overall_status(health_score, irr_rec)
    summary = _dashboard_summary(overall, health_score, irr_rec, risks)

    report = AnalysisReport(
        overall_status=overall,
        health_score=health_score,
        irrigation_recommendation=irr_rec,
        dashboard_summary=summary,
        per_sensor_assessments=assessments,
        risks=risks,
        evidence=evidence,
        recommended_actions=actions,
        data_quality_warnings=warnings,
        analysis_method="rule_engine",
        engine_id=ENGINE_ID,
        analysis_version=analysis_version,
        generated_at=now.isoformat().replace("+00:00", "Z"),
        sensor_data_timestamp=measured_at.isoformat().replace("+00:00", "Z") if measured_at else None,
        crop_profile=CropProfileSnapshot(
            name=str(profile.get("crop_type") or profile.get("name") or "default"),
            version=profile_version,
            thresholds=th,
        ),
        weather_summary=weather_summary,
        history_summary=history_summary,
        input_hash="",  # filled by the service/cache layer
    )
    return report


def _assess_soil(value, ts, now, staleness, th, warnings):
    lo, hi = 0.0, 100.0
    if value is None:
        warnings.append("Soil moisture missing.")
        return "missing", None, "No soil moisture reading."
    if not _in_range(value, lo, hi):
        warnings.append(f"Soil moisture {value}% out of plausible range (0–100%).")
        return "out_of_range", None, f"Reading {value}% outside 0–100%."
    if not _is_fresh(ts, now, staleness):
        warnings.append(f"Soil moisture reading stale (older than {staleness}s).")
        return "stale", None, "Reading is stale."
    stress_low = float(th.get("stress_low", 30.0))
    opt_min = float(th.get("optimal_min", 40.0))
    opt_max = float(th.get("optimal_max", 70.0))
    waterlog = float(th.get("waterlogging_high", 85.0))
    if value < stress_low:
        cls = "dry"
    elif value > waterlog:
        cls = "waterlogged"
    elif value < opt_min or value > opt_max:
        cls = "suboptimal"
    else:
        cls = "optimal"
    return "valid", cls, f"Soil moisture {value}% ({cls})."


def _assess_temperature(value, ts, now, staleness, th, warnings):
    valid_min = float(th.get("valid_min", -10.0))
    valid_max = float(th.get("valid_max", 60.0))
    if value is None:
        warnings.append("Temperature missing.")
        return "missing", None, "No temperature reading."
    if not _in_range(value, valid_min, valid_max):
        warnings.append(f"Temperature {value}°C out of plausible range.")
        return "out_of_range", None, f"Reading {value}°C outside valid range."
    if not _is_fresh(ts, now, staleness):
        warnings.append(f"Temperature reading stale (older than {staleness}s).")
        return "stale", None, "Reading is stale."
    heat = float(th.get("heat_stress_above", 34.0))
    extreme = float(th.get("extreme_heat_above", 38.0))
    cold = float(th.get("cold_stress_below", 15.0))
    if value > extreme:
        cls = "extreme_heat"
    elif value > heat:
        cls = "heat_stress"
    elif value < cold:
        cls = "cold_stress"
    else:
        cls = "optimal"
    return "valid", cls, f"Temperature {value}°C ({cls})."


def _assess_humidity(value, ts, now, staleness, th, warnings):
    valid_min = float(th.get("valid_min", 0.0))
    valid_max = float(th.get("valid_max", 100.0))
    if value is None:
        warnings.append("Humidity missing.")
        return "missing", None, "No humidity reading."
    if not _in_range(value, valid_min, valid_max):
        warnings.append(f"Humidity {value}% out of plausible range.")
        return "out_of_range", None, f"Reading {value}% outside 0–100%."
    if not _is_fresh(ts, now, staleness):
        warnings.append(f"Humidity reading stale (older than {staleness}s).")
        return "stale", None, "Reading is stale."
    low = float(th.get("low_below", 30.0))
    high = float(th.get("high_above", 90.0))
    if value < low:
        cls = "low"
    elif value > high:
        cls = "high"
    else:
        cls = "optimal"
    return "valid", cls, f"Humidity {value}% ({cls})."


def _assess_rain(value, ts, now, staleness, warnings):
    if value is None:
        warnings.append("Rain reading missing.")
        return "missing", None, "No rain reading."
    if not isinstance(value, bool):
        # Accept truthy/falsy from the wire but coerce.
        value = bool(value)
    if not _is_fresh(ts, now, staleness):
        warnings.append("Rain reading stale.")
        return "stale", None, "Reading is stale."
    cls = "raining" if value else "dry"
    return "valid", cls, f"Rain sensor: {cls}."


def _assess_light(value, th, warnings):
    if value is None:
        return "missing", None, "No light reading (unitless)."
    dark = float(th.get("dark_below", 500))
    bright = float(th.get("bright_above", 2000))
    try:
        v = float(value)
    except (TypeError, ValueError):
        warnings.append("Light reading not numeric.")
        return "implausible", None, "Light reading not numeric."
    if v < dark:
        cls = "dark"
    elif v > bright:
        cls = "bright"
    else:
        cls = "dim"
    return "valid", cls, f"Light {v} (raw, {cls} — relative hint only)."


def _compute_health_score(soil, temp, hum, rain, soil_th, temp_th, hum_th) -> int:
    # Additive penalties, threshold-driven. Mirrors the simulator's
    # compute_health_score when the default/Tomato profile is used so the live
    # WebSocket health_score and the rule-engine health_score stay consistent.
    score = 100
    if soil is not None:
        stress_low = float(soil_th.get("stress_low", 30.0))
        waterlog = float(soil_th.get("waterlogging_high", 85.0))
        if soil < stress_low - 10:
            score -= 40
        elif soil < stress_low:
            score -= 25
        elif soil > waterlog:
            score -= 15
    if temp is not None:
        extreme = float(temp_th.get("extreme_heat_above", 38.0))
        heat = float(temp_th.get("heat_stress_above", 34.0))
        cold = float(temp_th.get("cold_stress_below", 15.0))
        if temp > extreme:
            score -= 30
        elif temp > heat:
            score -= 20
        elif temp < cold:
            score -= 15
    if hum is not None:
        low = float(hum_th.get("low_below", 30.0))
        high = float(hum_th.get("high_above", 90.0))
        if hum < low:
            score -= 15
        elif hum > high:
            score -= 10
    if rain:
        score = min(100, score + 5)
    return max(0, min(100, int(round(score))))


def _irrigation_recommendation(*, soil, soil_status, rain, weather, soil_th, history) -> str:
    if soil_status != "valid" or soil is None:
        return "INSUFFICIENT_DATA"
    skip_threshold = 60.0
    if weather.available and weather.rain_expected:
        return "DELAY"
    if weather.available and weather.rain_probability_bucket is not None and weather.rain_probability_bucket >= skip_threshold:
        return "DELAY"
    if rain:
        return "DELAY"
    stress_low = float(soil_th.get("stress_low", 30.0))
    opt_min = float(soil_th.get("optimal_min", 40.0))
    waterlog = float(soil_th.get("waterlogging_high", 85.0))
    if soil > waterlog:
        return "SKIP"
    if soil < stress_low:
        return "IRRIGATE"
    if soil < opt_min:
        # Mild deficit with no imminent rain: advise a light irrigation.
        return "IRRIGATE"
    return "SKIP"


def _recommended_actions(irr_rec, risks, warnings) -> list[str]:
    actions: list[str] = []
    if irr_rec == "IRRIGATE":
        actions.append("Advisory: soil moisture is low and no rain is expected — consider a manual irrigation (subject to the safety gate).")
    elif irr_rec == "DELAY":
        actions.append("Advisory: rain is expected — delay irrigation and re-check after the forecast window.")
    elif irr_rec == "SKIP":
        actions.append("Advisory: soil moisture is within range — no irrigation needed now.")
    elif irr_rec == "INSUFFICIENT_DATA":
        actions.append("Advisory: not enough valid sensor data to recommend irrigation; verify sensors.")
    for r in risks:
        if r.name in ("heat_stress", "extreme_heat"):
            actions.append("Monitor temperature — provide shade/cooling if extreme heat persists.")
        if r.name == "high_evaporation":
            actions.append("High evaporation risk — consider mulching or irrigating during cooler hours.")
        if r.name == "waterlogging":
            actions.append("Soil is waterlogged — pause irrigation and improve drainage.")
        if r.name == "cold_stress":
            actions.append("Cold stress detected — protect crop if low temperatures persist.")
    if warnings:
        actions.append("Resolve sensor data-quality issues before relying on this assessment.")
    return actions


def _overall_status(health_score: Optional[int], irr_rec: str) -> str:
    if health_score is None:
        return "insufficient_data"
    if health_score >= 70:
        return "healthy"
    if health_score >= 50:
        return "moderate"
    if health_score >= 30:
        return "stressed"
    return "critical"


def _dashboard_summary(overall, health_score, irr_rec, risks) -> str:
    parts = [f"Status: {overall.replace('_', ' ')}."]
    if health_score is not None:
        parts.append(f"Health score {health_score}/100.")
    parts.append(f"Irrigation: {irr_rec}.")
    if risks:
        top = sorted(risks, key=lambda r: ["low", "medium", "high", "critical"].index(r.severity), reverse=True)[0]
        parts.append(f"Top risk: {top.name} ({top.severity}).")
    return " ".join(parts)
