from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class CropProfile:
    name: str
    ideal_soil_moisture: float
    ideal_temperature: float
    ideal_humidity: float
    water_consumption: float
    stress_tolerance: float
    growth_stage: str


@dataclass(frozen=True)
class SoilProfile:
    name: str
    water_retention: float
    drainage: float
    evaporation_factor: float


@dataclass(frozen=True)
class ClimateProfile:
    name: str
    temperature_bias: float
    humidity_bias: float
    rainfall_bias: float
    wind_bias: float


@dataclass(frozen=True)
class FarmDefinition:
    id: str
    name: str
    crop: CropProfile
    soil: SoilProfile
    climate: ClimateProfile
    area_acres: float
    description: str


CROP_PROFILES: Dict[str, CropProfile] = {
    "rice": CropProfile("Rice", 65.0, 28.0, 80.0, 1.3, 0.7, "vegetative"),
    "tomato": CropProfile("Tomato", 55.0, 24.0, 60.0, 1.0, 0.85, "fruiting"),
    "maize": CropProfile("Maize", 50.0, 30.0, 45.0, 1.1, 0.8, "maturing"),
    "orchard": CropProfile("Fruit Orchard", 58.0, 20.0, 70.0, 0.8, 0.9, "fruiting"),
}

SOIL_PROFILES: Dict[str, SoilProfile] = {
    "clay": SoilProfile("Clay", 0.9, 0.3, 0.6),
    "loamy": SoilProfile("Loamy", 0.7, 0.7, 0.8),
    "sandy": SoilProfile("Sandy", 0.4, 0.95, 1.2),
}

CLIMATE_PROFILES: Dict[str, ClimateProfile] = {
    "humid_tropical": ClimateProfile("Humid Tropical", 2.0, 8.0, 0.6, 0.2),
    "warm": ClimateProfile("Warm", 1.5, 2.0, 0.25, 0.4),
    "dry": ClimateProfile("Dry", 3.0, -5.0, 0.08, 0.7),
    "cool": ClimateProfile("Cool", -1.0, 4.0, 0.15, 0.35),
}

VIRTUAL_FARMS: List[FarmDefinition] = [
    FarmDefinition(
        id="green-valley",
        name="Green Valley",
        crop=CROP_PROFILES["rice"],
        soil=SOIL_PROFILES["clay"],
        climate=CLIMATE_PROFILES["humid_tropical"],
        area_acres=25.0,
        description="Humid tropical rice paddies with slow drainage and frequent irrigation needs.",
    ),
    FarmDefinition(
        id="sunrise-farms",
        name="Sunrise Farms",
        crop=CROP_PROFILES["tomato"],
        soil=SOIL_PROFILES["loamy"],
        climate=CLIMATE_PROFILES["warm"],
        area_acres=18.0,
        description="Warm tomato greenhouse fields with moderate irrigation demand and weather sensitivity.",
    ),
    FarmDefinition(
        id="golden-fields",
        name="Golden Fields",
        crop=CROP_PROFILES["maize"],
        soil=SOIL_PROFILES["sandy"],
        climate=CLIMATE_PROFILES["dry"],
        area_acres=40.0,
        description="Dry maize fields with rapid evaporation and high irrigation demand.",
    ),
    FarmDefinition(
        id="hill-orchard",
        name="Hill Orchard",
        crop=CROP_PROFILES["orchard"],
        soil=SOIL_PROFILES["loamy"],
        climate=CLIMATE_PROFILES["cool"],
        area_acres=30.0,
        description="Cool orchard site with low irrigation frequency and frost risk.",
    ),
]
