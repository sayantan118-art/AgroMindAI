"""Multi-Agent System endpoints (legacy compatibility).

The automatic per-message AI pipeline and the direct Groq ``/agents/decide``
path were removed: analysis is now on-demand only via ``POST /analysis/analyze``
(Groq behind the persistent quota gate, with a deterministic rule-engine
fallback). This router keeps the legacy health and memory endpoints (which
never used Groq) for backward compatibility and points callers at the new
endpoint.
"""

import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any

from agents.memory_agent import MemoryAgent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agents", tags=["Multi-Agent System (legacy)"])

# Pure-Python short-term memory; no LLM, no network.
memory = MemoryAgent(max_records=5)


class AgentDecisionRequest(BaseModel):
    sensor_data: dict[str, Any] | None = None
    weather_data: dict[str, Any] | None = None


@router.post("/decide", status_code=410)
async def agent_decision(request: AgentDecisionRequest) -> Dict[str, Any]:
    """Deprecated. On-demand analysis lives at ``POST /analysis/analyze``.

    The old endpoint ran the multi-agent pipeline (multiple Groq calls per
    request) outside the quota gate. It is intentionally disabled to ensure
    exactly one Groq analysis path. Use the new endpoint, which serves Groq
    when the quota gate allows and a deterministic rule-engine report otherwise.
    """
    raise HTTPException(
        status_code=410,
        detail="Deprecated: use POST /analysis/analyze for on-demand crop analysis.",
    )


@router.get("/health")
async def agent_health() -> Dict[str, Any]:
    """Status of the (now on-demand) analysis system."""
    return {
        "status": "ok",
        "mode": "on_demand",
        "analysis_endpoint": "/analysis/analyze",
        "note": "Per-message AI pipeline removed; analysis is user-triggered.",
        "memory_stats": memory.get_context(),
    }


@router.post("/memory/clear")
async def clear_memory() -> Dict[str, str]:
    memory.clear_history()
    return {"status": "memory cleared"}


@router.get("/memory/context")
async def get_memory_context() -> Dict[str, Any]:
    return memory.get_context()
