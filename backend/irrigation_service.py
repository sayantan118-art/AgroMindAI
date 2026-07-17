from __future__ import annotations

from typing import Any, Dict

from irrigation_engine import DecisionInput, DecisionOutput, RuleEngine


class IrrigationService:
    def __init__(self, engine: RuleEngine | None = None) -> None:
        self.engine = engine or RuleEngine()

    def build_recommendation(self, sensor_data: Dict[str, Any], weather_data: Dict[str, Any] | None = None) -> DecisionOutput:
        input_data = DecisionInput(
            soil_moisture=float(sensor_data.get("soil_moisture", 0) or 0),
            temperature=float(sensor_data.get("temperature", 0) or 0),
            humidity=float(sensor_data.get("humidity", 0) or 0),
            rain_probability=float((weather_data or {}).get("rain_probability_next_hour", 0) or 0),
            wind_speed=float((weather_data or {}).get("wind_speed", 0) or 0),
            light_level=float(sensor_data.get("light", 0) or 0),
            tank_level=float((weather_data or {}).get("tank_level", 100) or 100),
            rain_detected=bool(sensor_data.get("rain_detected", False)),
        )
        return self.engine.evaluate(input_data)
