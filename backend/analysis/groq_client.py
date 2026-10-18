"""Path A — single Groq call behind the quota gate.

Reuses the existing Groq integration's request format (httpx POST to
``https://api.groq.com/openai/v1/chat/completions`` with a Bearer key, the
``llama-3.3-70b-versatile`` model) — exactly one call per user-triggered
analysis, with **no automatic retries** and an explicit timeout. The quota
gate (``quota_manager``) decides whether this call may happen at all; this
module only performs the HTTP call and returns the raw result so the caller can
classify quota/auth/other failures and record the outcome.

Schema validation happens in ``service`` (against ``schemas.AnalysisReport``);
an invalid Groq response is a failure for that request and falls back to the
rule engine without being cached as an API result.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger(__name__)

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_MODEL = "llama-3.3-70b-versatile"
DEFAULT_TIMEOUT_SECONDS = 30.0


@dataclass
class GroqResult:
    status_code: int
    headers: dict[str, str]
    content: str | None  # raw text body
    error: str | None = None  # network/timeout error message when the request did not complete

    @property
    def completed(self) -> bool:
        """True when an HTTP response was received (not a network/timeout error)."""
        return self.error is None


SYSTEM_PROMPT = (
    "You are an agronomic assessment assistant for a precision-irrigation system. "
    "You receive a sensor snapshot, a summarized SQLite history, a weather summary and a crop profile. "
    "Assess crop health using ONLY the provided data. Never invent diseases, measurements or weather. "
    "If data is missing, stale or implausible, say so explicitly. "
    "Respond with STRICT JSON only (no markdown, no prose) matching this shape:\n"
    "{\n"
    "  \"overall_status\": \"healthy\" | \"moderate\" | \"stressed\" | \"critical\" | \"insufficient_data\",\n"
    "  \"health_score\": integer 0-100 or null,\n"
    "  \"irrigation_recommendation\": \"IRRIGATE\" | \"DELAY\" | \"SKIP\" | \"INSUFFICIENT_DATA\",\n"
    "  \"dashboard_summary\": string,\n"
    "  \"per_sensor_assessments\": [{\"sensor\":\"soil_moisture|temperature|humidity|light|rain\","
    " \"status\":\"valid|missing|out_of_range|stale|implausible\",\"value\": number|bool|null,"
    " \"unit\": string, \"classification\": string|null, \"note\": string}],\n"
    "  \"risks\": [{\"name\": string, \"severity\": \"low|medium|high|critical\","
    " \"evidence\": string, \"source\": \"measured|inferred|forecast|history\"}],\n"
    "  \"evidence\": [{\"finding\": string, \"basis\": \"measured|inferred|forecast|history|config\","
    " \"detail\": string}],\n"
    "  \"recommended_actions\": [string],\n"
    "  \"data_quality_warnings\": [string]\n"
    "}\n"
    "Keep measured facts, inferred risks and recommendations separate. A moisture threshold alone is "
    "never a diagnosis. Recommendations are advisory only."
)


def build_user_message(
    sensor_snapshot: dict[str, Any],
    profile: dict[str, Any],
    weather_summary: Any,
    history_summary: Any,
) -> str:
    """Build the user message with the full, deterministic input context."""
    return json.dumps({
        "sensor_snapshot": sensor_snapshot,
        "crop_profile": {
            "name": profile.get("crop_type") or profile.get("name"),
            "growth_stage": profile.get("growth_stage"),
            "thresholds": profile.get("thresholds", {}),
            "version_note": "thresholds are general starting values, not research-backed",
        },
        "weather_summary": _summary_dict(weather_summary),
        "history_summary": _summary_dict(history_summary),
        "sensor_note": "soil_moisture is 0-100% (firmware-calibrated), light is a unitless raw ADC reading, rain is boolean. No device timestamp is sent.",
    }, default=str)


def _summary_dict(obj: Any) -> dict[str, Any]:
    if obj is None:
        return {"available": False}
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if isinstance(obj, dict):
        return obj
    return {"available": False, "value": str(obj)}


def call_groq(
    *,
    api_key: str,
    model: str = DEFAULT_MODEL,
    sensor_snapshot: dict[str, Any],
    profile: dict[str, Any],
    weather_summary: Any,
    history_summary: Any,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> GroqResult:
    """Perform exactly one Groq chat completion. No retries.

    Returns a :class:`GroqResult` describing the raw HTTP outcome (or a
    network/timeout error). The caller is responsible for classification and
    quota-state updates.
    """
    user_message = build_user_message(sensor_snapshot, profile, weather_summary, history_summary)
    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        "temperature": 0.2,
        "max_tokens": 900,
        "response_format": {"type": "json_object"},
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    try:
        with httpx.Client(timeout=timeout_seconds) as client:
            resp = client.post(GROQ_URL, headers=headers, json=payload)
        return GroqResult(
            status_code=resp.status_code,
            headers={k: v for k, v in resp.headers.items()},
            content=resp.text,
        )
    except (httpx.TimeoutException, httpx.TransportError) as exc:
        logger.warning("Groq request failed (network/timeout): %s", exc)
        return GroqResult(status_code=0, headers={}, content=None, error=str(exc))


def extract_content_json(result: GroqResult) -> dict[str, Any] | None:
    """Parse the JSON content from a successful Groq response. Best-effort."""
    if not result.completed or result.content is None:
        return None
    try:
        return json.loads(result.content)
    except (ValueError, TypeError):
        # Some models wrap JSON in ``` fences despite json_object mode.
        text = result.content
        if "```" in text:
            inner = text.split("```")
            if len(inner) >= 2:
                candidate = inner[1]
                if candidate.lstrip().lower().startswith("json"):
                    candidate = candidate[4:]
                try:
                    return json.loads(candidate)
                except (ValueError, TypeError):
                    return None
        return None
