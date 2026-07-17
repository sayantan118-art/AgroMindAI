from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class DecisionInput:
    soil_moisture: float
    temperature: float
    humidity: float
    rain_probability: float = 0.0
    wind_speed: float = 0.0
    light_level: float = 0.0
    tank_level: float = 100.0
    rain_detected: bool = False


@dataclass
class RuleResult:
    description: str
    applies: bool


@dataclass
class DecisionOutput:
    decision: str
    recommended_duration_minutes: int
    priority: str
    reasons: List[str] = field(default_factory=list)
    confidence: str = "medium"
    validation_status: str = "valid"
    alerts: List[str] = field(default_factory=list)


class RuleEngine:
    """Deterministic irrigation rule engine with a clean interface for future AI replacement."""

    def __init__(self) -> None:
        self.rules = [
            ("tank_empty", self._tank_empty_rule),
            ("heavy_rain", self._heavy_rain_rule),
            ("very_dry_soil", self._very_dry_soil_rule),
            ("high_temperature", self._high_temperature_rule),
            ("high_wind", self._high_wind_rule),
            ("default_irrigate", self._default_rule),
        ]

    def evaluate(self, data: DecisionInput) -> DecisionOutput:
        reasons: List[str] = []
        alerts: List[str] = []

        if data.tank_level <= 0:
            return DecisionOutput(
                decision="BLOCK",
                recommended_duration_minutes=0,
                priority="high",
                reasons=["Water tank is empty, so irrigation is blocked."],
                confidence="high",
                validation_status="invalid",
                alerts=["Tank empty"],
            )

        if data.rain_detected or data.rain_probability >= 70:
            reasons.append("Rain is expected or detected, so irrigation is delayed.")
            alerts.append("Heavy rain expected")
            return DecisionOutput(
                decision="DELAY",
                recommended_duration_minutes=0,
                priority="medium",
                reasons=reasons,
                confidence="high",
                validation_status="valid",
                alerts=alerts,
            )

        if data.soil_moisture < 25:
            reasons.append("Soil moisture is low.")
        elif data.soil_moisture < 45:
            reasons.append("Soil moisture is below the preferred range.")
        else:
            reasons.append("Soil moisture is adequate.")

        if data.temperature > 35:
            reasons.append("Temperature is very high and may increase crop water demand.")
            alerts.append("Extreme heat")
        elif data.temperature > 28:
            reasons.append("Temperature is elevated.")

        if data.wind_speed > 25:
            reasons.append("Wind speed is high, so avoid spraying.")
            alerts.append("High wind")

        if data.soil_moisture > 60:
            return DecisionOutput(
                decision="DO_NOT_IRRIGATE",
                recommended_duration_minutes=0,
                priority="low",
                reasons=["Soil moisture is already high."],
                confidence="high",
                validation_status="valid",
                alerts=alerts,
            )

        if data.soil_moisture < 25 and data.rain_probability < 40:
            duration = 15
            if data.temperature > 35:
                duration = 20
            return DecisionOutput(
                decision="IRRIGATE",
                recommended_duration_minutes=duration,
                priority="high",
                reasons=reasons,
                confidence="high",
                validation_status="valid",
                alerts=alerts,
            )

        if data.soil_moisture < 40 and data.rain_probability < 60:
            return DecisionOutput(
                decision="IRRIGATE",
                recommended_duration_minutes=10,
                priority="medium",
                reasons=reasons,
                confidence="medium",
                validation_status="valid",
                alerts=alerts,
            )

        return DecisionOutput(
            decision="DO_NOT_IRRIGATE",
            recommended_duration_minutes=0,
            priority="low",
            reasons=reasons,
            confidence="medium",
            validation_status="valid",
            alerts=alerts,
        )

    def evaluate_with_rules(self, data: DecisionInput) -> List[RuleResult]:
        return [
            RuleResult(description="Water tank empty", applies=data.tank_level <= 0),
            RuleResult(description="Heavy rain expected", applies=data.rain_detected or data.rain_probability >= 70),
            RuleResult(description="Soil very dry", applies=data.soil_moisture < 25),
            RuleResult(description="High temperature", applies=data.temperature > 35),
            RuleResult(description="High wind", applies=data.wind_speed > 25),
        ]

    def _tank_empty_rule(self, data: DecisionInput) -> bool:
        return data.tank_level <= 0

    def _heavy_rain_rule(self, data: DecisionInput) -> bool:
        return data.rain_detected or data.rain_probability >= 70

    def _very_dry_soil_rule(self, data: DecisionInput) -> bool:
        return data.soil_moisture < 25

    def _high_temperature_rule(self, data: DecisionInput) -> bool:
        return data.temperature > 35

    def _high_wind_rule(self, data: DecisionInput) -> bool:
        return data.wind_speed > 25

    def _default_rule(self, data: DecisionInput) -> bool:
        return True
