from __future__ import annotations

from typing import Any, Dict, List


def summarize_history(rows: List[Dict[str, Any]], pump_events: List[Dict[str, Any]] | None = None) -> Dict[str, Any]:
    """Create a compact analytics summary for a farm history list."""
    safe_rows = [row for row in rows if isinstance(row, dict)]
    if not safe_rows:
        return {
            "average_soil_moisture": 0.0,
            "average_temperature": 0.0,
            "average_humidity": 0.0,
            "average_health_score": 0.0,
            "pump_runtime_minutes": 0.0,
            "water_usage_liters": 0.0,
        }

    soil_values = [float(row.get("soil_moisture", 0) or 0) for row in safe_rows]
    temp_values = [float(row.get("temperature", 0) or 0) for row in safe_rows]
    humidity_values = [float(row.get("humidity", 0) or 0) for row in safe_rows]
    health_values = [float(row.get("health_score", 0) or 0) for row in safe_rows]

    pump_events = pump_events or []
    pump_runtime_minutes = round(sum(float(event.get("duration_sec", 0) or 0) for event in pump_events) / 60.0, 1)
    water_usage_liters = round(pump_runtime_minutes * 60.0, 1)

    return {
        "average_soil_moisture": round(sum(soil_values) / len(soil_values), 1),
        "average_temperature": round(sum(temp_values) / len(temp_values), 1),
        "average_humidity": round(sum(humidity_values) / len(humidity_values), 1),
        "average_health_score": round(sum(health_values) / len(health_values), 1),
        "pump_runtime_minutes": pump_runtime_minutes,
        "water_usage_liters": water_usage_liters,
    }
