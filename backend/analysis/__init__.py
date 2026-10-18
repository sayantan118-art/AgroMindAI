"""On-demand crop-health analysis.

Two analysis paths, exactly one user-triggered entry point:

* Path A — ``external_model``: a single Groq call behind the persistent quota
  gate (``quota_manager``). Schema-validated; invalid output is treated as a
  failure for that request and falls back to Path B without being cached as an
  API result.
* Path B — ``rule_engine``: a consolidated deterministic engine with no LLM and
  no network. Same inputs + same config => identical output.

The MQTT ingestion path (``mqtt_worker``) deliberately never calls either path:
sensor data keeps flowing, but analysis happens only on explicit request via
``service.AnalyzeService.analyze``.
"""

from analysis.schemas import (  # noqa: F401
    AnalysisReport,
    AnalysisResponse,
    SensorAssessment,
    Risk,
    Evidence,
    WeatherSummary,
    HistorySummary,
)
from analysis.service import AnalyzeService  # noqa: F401
