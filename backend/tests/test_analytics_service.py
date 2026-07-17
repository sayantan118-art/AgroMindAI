import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from services.analytics_service import summarize_history


def test_summarize_history_returns_safe_defaults_and_averages():
    rows = [
        {"soil_moisture": 20.0, "temperature": 28.0, "humidity": 50.0, "health_score": 70.0},
        {"soil_moisture": 40.0, "temperature": 32.0, "humidity": 60.0, "health_score": 80.0},
    ]

    summary = summarize_history(rows, pump_events=[{"duration_sec": 120}, {"duration_sec": 180}])

    assert summary["average_soil_moisture"] == 30.0
    assert summary["average_temperature"] == 30.0
    assert summary["average_humidity"] == 55.0
    assert summary["average_health_score"] == 75.0
    assert summary["pump_runtime_minutes"] == 5.0
    assert summary["water_usage_liters"] == 300.0
