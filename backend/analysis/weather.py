"""Weather helper for on-demand analysis.

Reads the most recent persisted Open-Meteo snapshot from ``weather_history``
(fast, no extra network call) and, when none is available, fetches a fresh
snapshot from Open-Meteo using ``LATITUDE``/``LONGITUDE``. This keeps analysis
self-contained without importing ``mqtt_worker`` (avoids a circular import).
"""

from __future__ import annotations

import logging
import os
from typing import Any, Callable, Optional

import httpx

logger = logging.getLogger(__name__)

OPEN_METEO_URL = os.getenv("OPEN_METEO_URL", "https://api.open-meteo.com/v1/forecast")


async def fetch_weather_snapshot(session_factory: Callable[[], Any]) -> dict[str, Any] | None:
    """Return a weather dict suitable for ``rule_engine.summarize_weather``.

    Prefers the newest persisted ``weather_history`` row; falls back to a live
    Open-Meteo fetch. Never raises — returns ``None`` on failure.
    """
    # 1) Try the latest persisted weather row for the primary farm.
    try:
        from database.repositories import WeatherRepository, FarmRepository
        async with session_factory() as session:
            farms = await FarmRepository(session).list_active()
            if farms:
                rows = await WeatherRepository(session).list_by_farm(farms[0].id, limit=1)
                if rows:
                    w = rows[0]
                    return {
                        "rain_probability_next_hour": float(w.rain_probability or 0),
                        "temperature_2m_max": w.temperature,
                        "rain_expected": bool((w.rain_probability or 0) > 60),
                        "source": "open-meteo-persisted",
                    }
    except Exception as exc:
        logger.debug("Could not read persisted weather: %s", exc)

    # 2) Live fetch fallback.
    try:
        lat = os.getenv("LATITUDE", "22.5726")
        lon = os.getenv("LONGITUDE", "88.3639")
        params = {
            "latitude": lat, "longitude": lon,
            "hourly": "precipitation_probability,rain",
            "daily": "precipitation_probability_max,temperature_2m_max",
            "forecast_days": 1, "timezone": "auto",
        }
        async with httpx.AsyncClient(timeout=8.0) as client:
            r = await client.get(OPEN_METEO_URL, params=params)
        d = r.json()
        prob = (d.get("hourly", {}).get("precipitation_probability") or [0])[0]
        return {
            "rain_probability_next_hour": float(prob or 0),
            "temperature_2m_max": (d.get("daily", {}).get("temperature_2m_max") or [None])[0],
            "rain_expected": float(prob or 0) > 60,
            "source": "open-meteo-live",
        }
    except Exception as exc:
        logger.warning("Weather fetch failed: %s", exc)
        return None
