"""Load and resolve versioned crop profiles from ``backend/config/crop_profiles.json``.

This module only reads the config file. After the database is seeded the DB is
authoritative for the *active* profile (see ``migrations_runner`` / repository),
but the deterministic engine itself is pure: it receives a resolved profile
dict plus the analysis version, so it can be tested without a database.

Soil-sensor calibration assumption (documented in README/docs): the firmware
already converts the capacitive soil sensor's raw ADC value to a 0–100 %
volumetric reading using ``map(raw, 4095, 1500, 0, 100)`` before publishing.
The engine therefore treats ``soil_moisture`` as a percentage. This mapping is a
rough factory calibration and should be validated against the user's actual
soil and sensor — see the warning in ``crop_profiles.json``.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from typing import Any

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "crop_profiles.json")


@lru_cache(maxsize=1)
def load_config() -> dict[str, Any]:
    """Load and cache the crop-profile config. Raises if the file is malformed."""
    path = os.path.abspath(CONFIG_PATH)
    with open(path, "r", encoding="utf-8") as fh:
        cfg = json.load(fh)
    _validate(cfg)
    return cfg


def _validate(cfg: dict[str, Any]) -> None:
    if not isinstance(cfg, dict):
        raise ValueError("crop_profiles.json must be a JSON object")
    for key in ("analysis_version", "config_version", "default", "profiles"):
        if key not in cfg:
            raise ValueError(f"crop_profiles.json missing required key: {key}")
    if not isinstance(cfg["profiles"], dict):
        raise ValueError("crop_profiles.json 'profiles' must be an object")


def analysis_version() -> str:
    return str(load_config()["analysis_version"])


def config_version() -> str:
    return str(load_config()["config_version"])


def resolve_profile(crop_name: str | None) -> tuple[dict[str, Any], str, str]:
    """Return ``(profile_dict, profile_name, profile_version)`` for a crop.

    Falls back to the ``default`` profile when the crop is unknown or unset.
    ``profile_version`` is the ``config_version`` (profiles move together with
    the config file). The DB-backed version is preferred by callers when a DB
    row exists; this is the seed/source-of-truth resolver.
    """
    cfg = load_config()
    profiles = cfg["profiles"]
    name = (crop_name or "").strip()
    if name and name in profiles:
        profile = profiles[name]
        profile_name = name
    else:
        profile = cfg["default"]
        profile_name = "default"
    return profile, profile_name, config_version()


def profile_thresholds(profile: dict[str, Any]) -> dict[str, Any]:
    return profile.get("thresholds", {})


def pump_limits(profile: dict[str, Any]) -> dict[str, Any]:
    return profile.get("pump_limits", {})
