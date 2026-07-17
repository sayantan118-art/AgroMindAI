from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class FarmState:
    farm_id: str
    name: str
    crop_name: str
    soil_type: str
    climate_type: str
    area_acres: float
    description: str
    temperature: float = 24.0
    humidity: float = 65.0
    soil_moisture: float = 55.0
    rain_probability: float = 20.0
    wind_speed: float = 10.0
    light_level: float = 6000.0
    uv_index: float = 4.0
    tank_level: float = 85.0
    health_score: float = 78.0
    pump_status: str = "OFF"
    pump_runtime_minutes: float = 0.0
    water_consumption_liters: float = 0.0
    recommendation: str = "DO_NOT_IRRIGATE"
    recommendation_reason: str = "Soil moisture is adequate."
    alerts: List[str] = field(default_factory=list)
    timeline: List[Dict[str, Any]] = field(default_factory=list)
    history: List[Dict[str, Any]] = field(default_factory=list)
    rule_triggers: List[str] = field(default_factory=list)
    user_decisions: List[Dict[str, Any]] = field(default_factory=list)
    last_updated: Optional[str] = None
