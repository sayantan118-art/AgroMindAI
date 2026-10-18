"""Pydantic schemas for the crop-health analysis report.

The same schema validates both the deterministic rule-engine output and the
Groq (external_model) output. A Groq response that fails validation is a
failure for that request: the service falls back to the rule engine and never
caches the invalid output as an API result.

Measured facts, inferred risks and recommendations are kept in separate
fields so the dashboard can show them distinctly and never present an inferred
risk as a measured fact (a moisture threshold alone is never a diagnosis).
"""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

AnalysisMethod = Literal["external_model", "rule_engine"]
OverallStatus = Literal["healthy", "moderate", "stressed", "critical", "insufficient_data"]
Severity = Literal["low", "medium", "high", "critical"]
IrrigationRecommendation = Literal["IRRIGATE", "DELAY", "SKIP", "INSUFFICIENT_DATA"]
SensorName = Literal["soil_moisture", "temperature", "humidity", "light", "rain"]
SensorStatus = Literal["valid", "missing", "out_of_range", "stale", "implausible"]
EvidenceBasis = Literal["measured", "inferred", "forecast", "history", "config"]


class SensorAssessment(BaseModel):
    """A single sensor's measured fact + validity + classification."""

    model_config = ConfigDict(extra="forbid")

    sensor: SensorName
    status: SensorStatus
    value: Optional[Any] = None  # number, bool or None when missing
    unit: str = ""
    classification: Optional[str] = None  # e.g. "dry", "optimal", "wet", "heat_stress"
    note: Optional[str] = None  # measured-fact statement only


class Risk(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    severity: Severity
    evidence: str  # what was measured/observed that supports the risk
    source: Literal["measured", "inferred", "forecast", "history"] = "inferred"


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    finding: str
    basis: EvidenceBasis
    detail: str


class CropProfileSnapshot(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str
    version: str
    thresholds: dict[str, Any] = Field(default_factory=dict)


class WeatherSummary(BaseModel):
    """Bucketed weather context used in the input hash."""

    model_config = ConfigDict(extra="allow")

    rain_probability_bucket: Optional[int] = None  # quantized to 10% buckets
    rain_expected: Optional[bool] = None
    max_temperature_bucket: Optional[float] = None  # quantized to 1°C
    source: str = "open-meteo"
    available: bool = False


class HistorySummary(BaseModel):
    """Quantized history context used in the input hash."""

    model_config = ConfigDict(extra="allow")

    point_count: int = 0
    soil_moisture_trend: Optional[Literal["increasing", "decreasing", "stable", "insufficient"]] = None
    temperature_trend: Optional[Literal["increasing", "decreasing", "stable", "insufficient"]] = None
    available: bool = False


class AnalysisReport(BaseModel):
    """Full structured report. Stored verbatim as JSON in ``analysis_reports``."""

    model_config = ConfigDict(extra="forbid")

    # Headline
    overall_status: OverallStatus
    health_score: Optional[int] = Field(default=None, ge=0, le=100)
    irrigation_recommendation: IrrigationRecommendation
    dashboard_summary: str

    # Structured detail
    per_sensor_assessments: list[SensorAssessment] = Field(default_factory=list)
    risks: list[Risk] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    data_quality_warnings: list[str] = Field(default_factory=list)

    # Provenance / reproducibility
    analysis_method: AnalysisMethod
    engine_id: str
    analysis_version: str
    generated_at: str  # ISO-8601 UTC
    sensor_data_timestamp: Optional[str] = None  # ISO-8601 UTC of the data used

    # Reproducibility context (also stored as indexed columns / separate JSON)
    crop_profile: CropProfileSnapshot
    weather_summary: WeatherSummary = Field(default_factory=WeatherSummary)
    history_summary: HistorySummary = Field(default_factory=HistorySummary)
    input_hash: str


class AnalysisResponse(BaseModel):
    """API response for ``POST /analysis/analyze``."""

    model_config = ConfigDict(extra="forbid")

    report: AnalysisReport
    from_cache: bool = False
    quota_state: Optional[str] = None  # human-readable, no secrets
    forced: bool = False
