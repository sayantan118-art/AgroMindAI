"""
analytics.py — AgroMind AI Pure-Python Analytics Engine
Computes ET₀, Crop Stress Index, Pest Risk, Irrigation ETA, and Water Usage
from the existing sensor_logs and pump_log SQLite tables. No external APIs.
"""
import math
import datetime
from typing import Optional

# ── ET₀ (Hargreaves simplified) ───────────────────────────────────────────────
def compute_et0(temp_c: float, humidity_pct: float, light_raw: float) -> dict:
    """
    Estimate evapotranspiration in mm/day.
    Uses Hargreaves-Samani simplified formula adapted for indoor light sensors.
    light_raw → approximate solar radiation (W/m²) assuming max sensor=4095→1200 W/m²
    """
    solar_wm2 = (light_raw / 4095.0) * 1200.0
    # Convert to MJ/m²/day (1 W/m² = 0.0864 MJ/m²/day)
    Ra = solar_wm2 * 0.0864
    # Actual vs saturation vapour pressure
    es = 0.6108 * math.exp((17.27 * temp_c) / (temp_c + 237.3))
    ea = es * (humidity_pct / 100.0)
    vpd = max(es - ea, 0)
    # Hargreaves approximation: ET₀ ≈ 0.0023 * Ra * (T + 17.8) * VPD^0.5
    et0 = 0.0023 * Ra * (temp_c + 17.8) * math.sqrt(max(vpd, 0.001))
    et0 = round(max(et0, 0), 2)
    if et0 < 2:
        level = "Low"
    elif et0 < 5:
        level = "Moderate"
    else:
        level = "High"
    return {"et0_mm_per_day": et0, "level": level, "vpd_kpa": round(vpd, 3)}


# ── Crop Stress Index ─────────────────────────────────────────────────────────
def compute_stress_index(
    soil: float, temp: float, humidity: float,
    light: float, rain: bool,
    target_soil_min: float = 40.0, target_soil_max: float = 70.0
) -> dict:
    """
    0 = no stress (perfect conditions), 100 = maximum stress.
    Weighted from: soil moisture, temperature, humidity, light, rain.
    """
    # Soil score: 0 if in target range, increases outside
    if soil < target_soil_min:
        soil_stress = min((target_soil_min - soil) / target_soil_min, 1.0)
    elif soil > target_soil_max:
        soil_stress = min((soil - target_soil_max) / (100 - target_soil_max), 1.0)
    else:
        soil_stress = 0.0

    # Temperature stress: optimal 18–28°C
    if 18 <= temp <= 28:
        temp_stress = 0.0
    elif temp < 18:
        temp_stress = min((18 - temp) / 18, 1.0)
    else:
        temp_stress = min((temp - 28) / 20, 1.0)

    # Humidity stress: optimal 40–80%
    if 40 <= humidity <= 80:
        hum_stress = 0.0
    elif humidity < 40:
        hum_stress = min((40 - humidity) / 40, 1.0)
    else:
        hum_stress = min((humidity - 80) / 20, 1.0)

    # Light stress: low light = stress (< 500 raw = stress)
    light_stress = max(0.0, 1.0 - (light / 1500.0))
    light_stress = min(light_stress, 1.0)

    # Rain bonus: reduces stress slightly
    rain_relief = -0.05 if rain else 0.0

    # Weighted total
    raw = (soil_stress * 0.4 + temp_stress * 0.25 + hum_stress * 0.2 +
           light_stress * 0.15 + rain_relief)
    score = round(min(max(raw * 100, 0), 100), 1)

    if score < 25:
        label = "Healthy"
        color = "green"
    elif score < 55:
        label = "Mild Stress"
        color = "yellow"
    elif score < 75:
        label = "Moderate Stress"
        color = "orange"
    else:
        label = "Severe Stress"
        color = "red"

    return {
        "stress_index": score,
        "label": label,
        "color": color,
        "breakdown": {
            "soil": round(soil_stress * 100, 1),
            "temperature": round(temp_stress * 100, 1),
            "humidity": round(hum_stress * 100, 1),
            "light": round(light_stress * 100, 1),
        }
    }


# ── Pest / Disease Risk ───────────────────────────────────────────────────────
def compute_pest_risk(temp: float, humidity: float) -> dict:
    """
    Fungal disease thrives at high humidity + warm temperatures.
    Bacterial blight risk increases with sustained wetness.
    """
    if humidity >= 80 and 20 <= temp <= 30:
        risk = "HIGH"
        risk_score = 85
        advice = "High fungal risk. Avoid overhead irrigation. Improve airflow."
    elif humidity >= 70 and 15 <= temp <= 32:
        risk = "MEDIUM"
        risk_score = 50
        advice = "Moderate risk. Monitor for early mildew or blight signs."
    else:
        risk = "LOW"
        risk_score = 15
        advice = "Conditions unfavorable for fungal diseases."

    return {"risk_level": risk, "risk_score": risk_score, "advice": advice,
            "temp_c": temp, "humidity_pct": humidity}


# ── Irrigation ETA (linear regression on soil drying) ────────────────────────
def compute_irrigation_eta(history: list[dict], threshold: float = 30.0) -> dict:
    """
    Fit a simple linear trend to recent soil moisture readings and
    predict how many hours until soil hits the threshold needing irrigation.
    history: list of {soil_moisture, ts} dicts ordered newest first.
    """
    if len(history) < 3:
        return {"eta_hours": None, "message": "Not enough history (need 3+ readings)"}

    # Use up to last 24 readings
    pts = history[:24]
    # Convert ts to hours-ago
    now = datetime.datetime.now()
    xs, ys = [], []
    for p in pts:
        try:
            ts = datetime.datetime.fromisoformat(
                str(p.get("ts", "")).replace("T", " ").split(".")[0]
            )
            hours_ago = (now - ts).total_seconds() / 3600.0
            soil = float(p.get("soil_moisture") or 0)
            xs.append(hours_ago)
            ys.append(soil)
        except Exception:
            continue

    if len(xs) < 2:
        return {"eta_hours": None, "message": "Cannot parse timestamps"}

    # Linear regression: y = m*x + b (x = hours ago, y = soil moisture)
    n = len(xs)
    sx, sy = sum(xs), sum(ys)
    sxy = sum(x * y for x, y in zip(xs, ys))
    sx2 = sum(x * x for x in xs)
    denom = n * sx2 - sx * sx
    if abs(denom) < 1e-9:
        return {"eta_hours": None, "message": "Soil level is flat — no drying trend"}

    m = (n * sxy - sx * sy) / denom  # slope (soil drop per hour)
    b = (sy - m * sx) / n            # intercept at hours_ago=0 (current value)

    current_soil = b  # predicted current value
    if m >= 0:
        # Soil is not drying out — increasing or flat
        return {
            "eta_hours": None,
            "current_soil_pct": round(current_soil, 1),
            "message": "Soil is stable or recovering — no irrigation needed soon"
        }

    # Time until soil hits threshold: threshold = m*eta + b => eta = (threshold-b)/m
    eta_hours = (threshold - b) / m
    if eta_hours < 0:
        return {
            "eta_hours": 0,
            "current_soil_pct": round(current_soil, 1),
            "message": "Soil already at or below threshold — irrigate now!"
        }

    return {
        "eta_hours": round(eta_hours, 1),
        "current_soil_pct": round(current_soil, 1),
        "drying_rate_pct_per_hour": round(-m, 2),
        "message": f"Estimated {round(eta_hours, 1)}h until irrigation needed"
    }


# ── Water Usage ───────────────────────────────────────────────────────────────
FLOW_RATE_LPM = 2.0  # litres per minute — adjust if your pump is different

def compute_water_usage(pump_rows: list[dict]) -> dict:
    """Compute litres used today and this week from pump_log rows."""
    today = datetime.date.today()
    week_start = today - datetime.timedelta(days=today.weekday())

    today_sec = 0
    week_sec = 0
    for row in pump_rows:
        if row.get("action") != "ON":
            continue
        try:
            ts = datetime.datetime.fromisoformat(
                str(row.get("ts", "")).replace("T", " ").split(".")[0]
            ).date()
        except Exception:
            continue
        dur = int(row.get("duration_sec") or 0)
        if ts == today:
            today_sec += dur
        if ts >= week_start:
            week_sec += dur

    def to_litres(sec): return round(sec / 60.0 * FLOW_RATE_LPM, 2)

    return {
        "today": {"seconds": today_sec, "litres": to_litres(today_sec)},
        "this_week": {"seconds": week_sec, "litres": to_litres(week_sec)},
        "flow_rate_lpm": FLOW_RATE_LPM,
    }
