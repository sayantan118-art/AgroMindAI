"""Input hashing + quantization for the analysis cache.

The cache is an *index* over immutable reports (see ``AnalysisCacheIndex``),
never a duplicate store of report contents. The hash is computed over a
quantized sensor snapshot (timestamps excluded), the bucketed history
summary, the bucketed weather summary, the crop-profile version and the
analysis version. Without quantization the cache would never hit. Entries are
stored per ``analysis_method`` so a cached rule-engine report does not block an
eligible Groq attempt after a cooldown ends, and a cached API report may be
returned during cooldown.
"""

from __future__ import annotations

import hashlib
import json
import os
from typing import Any

from analysis.schemas import HistorySummary, WeatherSummary

# Configurable quantization precision (env-overridable for tests/tuning).
SOIL_STEP = float(os.getenv("ANALYSIS_QUANT_SOIL", "2"))
TEMP_STEP = float(os.getenv("ANALYSIS_QUANT_TEMP", "0.5"))
HUM_STEP = float(os.getenv("ANALYSIS_QUANT_HUM", "1"))
LIGHT_STEP = float(os.getenv("ANALYSIS_QUANT_LIGHT", "100"))


def _quantize(value: Any, step: float) -> Any:
    if value is None or step is None or step <= 0:
        return value
    try:
        return round(float(value) / step) * step
    except (TypeError, ValueError):
        return value


def quantize_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Quantize sensor values and drop timestamps so small noise still hits."""
    soil = snapshot.get("soil_moisture")
    temp = snapshot.get("temperature")
    hum = snapshot.get("humidity")
    light = snapshot.get("light")
    rain = snapshot.get("rain")
    return {
        "soil_moisture": _quantize(soil, SOIL_STEP),
        "temperature": _quantize(temp, TEMP_STEP),
        "humidity": _quantize(hum, HUM_STEP),
        "light": _quantize(light, LIGHT_STEP),
        "rain": None if rain is None else bool(rain),
        # NOTE: measured_at / received_at deliberately excluded.
    }


def _summary_dict(obj: Any) -> dict[str, Any]:
    if obj is None:
        return {"available": False}
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if isinstance(obj, dict):
        return obj
    return {"value": str(obj)}


def compute_input_hash(
    *,
    snapshot: dict[str, Any],
    history_summary: Any,
    weather_summary: Any,
    profile_version: str,
    analysis_version: str,
    method: str,
) -> str:
    """Deterministic SHA-256 over the quantized inputs + versions + method."""
    payload = {
        "snapshot": quantize_snapshot(snapshot),
        "history": _summary_dict(history_summary),
        "weather": _summary_dict(weather_summary),
        "profile_version": str(profile_version),
        "analysis_version": str(analysis_version),
        "method": str(method),
    }
    serialized = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
