from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from farm_simulation.config import FarmDefinition, VIRTUAL_FARMS
from farm_simulation.models import FarmState


class VirtualFarmEngine:
    def __init__(self) -> None:
        self.farms: Dict[str, FarmState] = {}
        self._initialize_defaults()

    def _initialize_defaults(self) -> None:
        for farm_def in VIRTUAL_FARMS:
            state = FarmState(
                farm_id=farm_def.id,
                name=farm_def.name,
                crop_name=farm_def.crop.name,
                soil_type=farm_def.soil.name,
                climate_type=farm_def.climate.name,
                area_acres=farm_def.area_acres,
                description=farm_def.description,
            )
            state.temperature = 24.0 + farm_def.climate.temperature_bias
            state.humidity = 65.0 + farm_def.climate.humidity_bias
            state.soil_moisture = 58.0
            state.rain_probability = 25.0 + farm_def.climate.rainfall_bias * 10
            state.wind_speed = 10.0 + farm_def.climate.wind_bias * 4
            state.light_level = 6500.0
            state.uv_index = 4.0 + (state.temperature - 24) * 0.1
            state.tank_level = 82.0
            state.health_score = 80.0
            state.last_updated = datetime.utcnow().isoformat(timespec="seconds") + "Z"
            self.farms[farm_def.id] = state

    def list_farms(self) -> List[Dict[str, object]]:
        return [
            {
                "id": state.farm_id,
                "name": state.name,
                "crop": state.crop_name,
                "soil": state.soil_type,
                "climate": state.climate_type,
                "area_acres": state.area_acres,
                "description": state.description,
                "health_score": round(state.health_score, 1),
                "recommendation": state.recommendation,
                "pump_status": state.pump_status,
            }
            for state in self.farms.values()
        ]

    def get_farm(self, farm_id: str) -> Optional[FarmState]:
        return self.farms.get(farm_id)

    def step(self, farm_id: str) -> FarmState:
        state = self.farms[farm_id]
        farm_def = next(item for item in VIRTUAL_FARMS if item.id == farm_id)

        # Deterministic climate-driven progression.
        state.temperature += 0.2 + farm_def.climate.temperature_bias * 0.02
        state.humidity += 0.15 * (1 if state.rain_probability > 50 else -1)
        state.humidity = max(20.0, min(95.0, state.humidity))

        if state.pump_status == "ON":
            state.soil_moisture += 2.8 * farm_def.soil.water_retention
            state.tank_level -= 1.8 * farm_def.crop.water_consumption
            state.pump_runtime_minutes += 1.0
            state.water_consumption_liters += 120.0 * farm_def.crop.water_consumption
        else:
            evaporation = farm_def.soil.evaporation_factor * (0.6 + (state.temperature - 24) * 0.04)
            state.soil_moisture -= evaporation
            state.soil_moisture += max(0.0, min(2.0, (state.rain_probability - 40) * 0.02))

        state.soil_moisture = max(8.0, min(95.0, state.soil_moisture))
        state.tank_level = max(0.0, min(100.0, state.tank_level))
        state.rain_probability = max(0.0, min(100.0, state.rain_probability + math.sin(state.temperature / 8) * 6 + farm_def.climate.rainfall_bias * 3))
        state.wind_speed = max(0.0, min(40.0, state.wind_speed + 0.2 + farm_def.climate.wind_bias * 0.3))
        state.light_level = max(2000.0, min(12000.0, state.light_level + 40.0 + (state.temperature - 24) * 15))
        state.uv_index = max(0.0, min(12.0, 2.5 + state.temperature * 0.16 + state.wind_speed * 0.03))

        if state.soil_moisture < farm_def.crop.ideal_soil_moisture - 12:
            state.recommendation = "IRRIGATE"
            state.recommendation_reason = "Soil moisture has fallen below the crop target."
            state.alerts = ["Low soil moisture"]
            state.rule_triggers.append("low_soil_moisture")
            if state.tank_level <= 20:
                state.recommendation = "BLOCK"
                state.recommendation_reason = "Water tank is too low for irrigation."
                state.alerts = ["Tank low"]
                state.rule_triggers.append("tank_low")
        elif state.rain_probability > 70:
            state.recommendation = "DELAY"
            state.recommendation_reason = "Heavy rain is expected."
            state.alerts = ["Heavy rain expected"]
            state.rule_triggers.append("heavy_rain")
        else:
            state.recommendation = "DO_NOT_IRRIGATE"
            state.recommendation_reason = "Conditions are within the normal range."
            state.alerts = []

        state.pump_status = "ON" if state.recommendation == "IRRIGATE" else "OFF"
        state.health_score = max(40.0, min(100.0, state.health_score + (2.0 if state.recommendation == "IRRIGATE" else -0.8) + (0.8 if state.rain_probability > 60 else 0.0)))
        state.health_score = max(40.0, min(100.0, state.health_score - max(0.0, (state.temperature - farm_def.crop.ideal_temperature) * 0.2)))
        state.last_updated = datetime.utcnow().isoformat(timespec="seconds") + "Z"

        state.timeline.append(
            {
                "ts": state.last_updated,
                "event": "simulation_tick",
                "message": f"{state.name} updated with soil moisture {round(state.soil_moisture, 1)}% and recommendation {state.recommendation}.",
            }
        )
        state.history.append(
            {
                "ts": state.last_updated,
                "temperature": round(state.temperature, 1),
                "humidity": round(state.humidity, 1),
                "soil_moisture": round(state.soil_moisture, 1),
                "rain_probability": round(state.rain_probability, 1),
                "wind_speed": round(state.wind_speed, 1),
                "light_level": round(state.light_level, 1),
                "uv_index": round(state.uv_index, 1),
                "tank_level": round(state.tank_level, 1),
                "health_score": round(state.health_score, 1),
                "recommendation": state.recommendation,
                "alerts": state.alerts,
            }
        )
        return state

    def build_snapshot(self, farm_id: str) -> Dict[str, object]:
        state = self.step(farm_id)
        latest = state.history[-1] if state.history else {}
        return {
            "farm": {
                "id": state.farm_id,
                "name": state.name,
                "crop": state.crop_name,
                "soil": state.soil_type,
                "climate": state.climate_type,
                "area_acres": state.area_acres,
                "description": state.description,
            },
            "status": {
                "temperature": round(state.temperature, 1),
                "humidity": round(state.humidity, 1),
                "soil_moisture": round(state.soil_moisture, 1),
                "rain_probability": round(state.rain_probability, 1),
                "wind_speed": round(state.wind_speed, 1),
                "light_level": round(state.light_level, 1),
                "uv_index": round(state.uv_index, 1),
                "tank_level": round(state.tank_level, 1),
                "health_score": round(state.health_score, 1),
                "pump_status": state.pump_status,
                "pump_runtime_minutes": round(state.pump_runtime_minutes, 1),
                "water_consumption_liters": round(state.water_consumption_liters, 1),
                "recommendation": state.recommendation,
                "recommendation_reason": state.recommendation_reason,
                "alerts": state.alerts,
            },
            "history": state.history[-24:],
            "timeline": state.timeline[-12:],
            "metrics": {
                "avg_soil_moisture": round(sum(item["soil_moisture"] for item in state.history[-24:]) / max(1, len(state.history[-24:])), 1),
                "avg_temperature": round(sum(item["temperature"] for item in state.history[-24:]) / max(1, len(state.history[-24:])), 1),
                "avg_humidity": round(sum(item["humidity"] for item in state.history[-24:]) / max(1, len(state.history[-24:])), 1),
                "latest_recommendation": latest.get("recommendation", state.recommendation),
            },
        }
