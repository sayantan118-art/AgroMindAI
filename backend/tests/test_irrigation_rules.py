import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from irrigation_engine import RuleEngine, DecisionInput, DecisionOutput


def test_irrigate_when_soil_is_dry_and_rain_is_low():
    engine = RuleEngine()
    result = engine.evaluate(
        DecisionInput(
            soil_moisture=20,
            temperature=32,
            humidity=45,
            rain_probability=10,
            wind_speed=12,
            light_level=7000,
            tank_level=80,
            rain_detected=False,
        )
    )

    assert result.decision == "IRRIGATE"
    assert result.recommended_duration_minutes == 15
    assert "soil moisture is low" in result.reasons[0].lower()
    assert result.confidence == "high"


def test_delay_when_rain_probability_is_high():
    engine = RuleEngine()
    result = engine.evaluate(
        DecisionInput(
            soil_moisture=45,
            temperature=24,
            humidity=70,
            rain_probability=80,
            wind_speed=12,
            light_level=5000,
            tank_level=70,
            rain_detected=True,
        )
    )

    assert result.decision == "DELAY"
    assert result.recommended_duration_minutes == 0
    assert result.confidence == "high"


def test_block_when_tank_is_empty():
    engine = RuleEngine()
    result = engine.evaluate(
        DecisionInput(
            soil_moisture=20,
            temperature=30,
            humidity=40,
            rain_probability=20,
            wind_speed=10,
            light_level=6000,
            tank_level=0,
            rain_detected=False,
        )
    )

    assert result.decision == "BLOCK"
    assert result.recommended_duration_minutes == 0
    assert "water tank" in result.reasons[0].lower()
