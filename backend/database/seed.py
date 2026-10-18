from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any

from database.connection import SessionFactory
from database.models import (
    ActivityTimeline,
    CropProfile,
    Device,
    Farm,
    IrrigationEvent,
    Notification,
    Recommendation,
    Report,
    RuleTrigger,
    SensorReading,
    SimulationState,
    SoilProfile,
    WeatherHistory,
)


async def seed() -> None:
    async with SessionFactory() as session:
        existing = await session.get(Farm, "virtual-green-valley")
        if existing:
            return

        farms = [
            {
                "id": "virtual-green-valley",
                "name": "Green Valley",
                "description": "A mixed crop farm with stable irrigation needs.",
                "location": "Kolkata, India",
                "latitude": 22.5726,
                "longitude": 88.3639,
                "area": 120.0,
                "crop": "Tomato",
                "soil_type": "Loam",
                "climate": "Humid",
                "mode": "Virtual",
                "active": True,
            },
            {
                "id": "virtual-sunrise-farms",
                "name": "Sunrise Farms",
                "description": "Large-scale orchard with adaptive monitoring.",
                "location": "Bengaluru, India",
                "latitude": 12.9716,
                "longitude": 77.5946,
                "area": 220.0,
                "crop": "Mango",
                "soil_type": "Clay Loam",
                "climate": "Tropical",
                "mode": "Virtual",
                "active": True,
            },
            {
                "id": "virtual-golden-fields",
                "name": "Golden Fields",
                "description": "Wheat and pulses farm with moisture stress monitoring.",
                "location": "Ahmedabad, India",
                "latitude": 23.0225,
                "longitude": 72.5714,
                "area": 180.0,
                "crop": "Wheat",
                "soil_type": "Silt",
                "climate": "Semi-Arid",
                "mode": "Virtual",
                "active": True,
            },
            {
                "id": "virtual-hill-orchard",
                "name": "Hill Orchard",
                "description": "High-altitude orchard with remote monitoring.",
                "location": "Shimla, India",
                "latitude": 31.1048,
                "longitude": 77.1734,
                "area": 90.0,
                "crop": "Apple",
                "soil_type": "Loamy Sand",
                "climate": "Cool",
                "mode": "Virtual",
                "active": True,
            },
        ]

        crop_profiles = [
            CropProfile(name="Tomato", growth_stage="Vegetative", ideal_moisture=45.0, ideal_temperature=26.0, ideal_humidity=65.0, water_demand=2.5, stress_threshold=35.0, yield_target=120.0, description="Tomato crop profile"),
            CropProfile(name="Mango", growth_stage="Flowering", ideal_moisture=50.0, ideal_temperature=30.0, ideal_humidity=70.0, water_demand=3.0, stress_threshold=38.0, yield_target=80.0, description="Mango crop profile"),
            CropProfile(name="Wheat", growth_stage="Ripening", ideal_moisture=40.0, ideal_temperature=24.0, ideal_humidity=60.0, water_demand=1.8, stress_threshold=30.0, yield_target=90.0, description="Wheat crop profile"),
            CropProfile(name="Apple", growth_stage="Fruit Set", ideal_moisture=42.0, ideal_temperature=20.0, ideal_humidity=55.0, water_demand=2.2, stress_threshold=32.0, yield_target=75.0, description="Apple crop profile"),
        ]
        soil_profiles = [
            SoilProfile(soil_name="Loam", water_retention=0.72, drainage_rate=0.6, evaporation_rate=0.18, moisture_recovery=0.8, description="Balanced loam soil"),
            SoilProfile(soil_name="Clay Loam", water_retention=0.86, drainage_rate=0.45, evaporation_rate=0.12, moisture_recovery=0.7, description="High water retaining clay loam"),
            SoilProfile(soil_name="Silt", water_retention=0.68, drainage_rate=0.72, evaporation_rate=0.2, moisture_recovery=0.76, description="Fine silt soil"),
            SoilProfile(soil_name="Loamy Sand", water_retention=0.54, drainage_rate=0.84, evaporation_rate=0.24, moisture_recovery=0.82, description="Fast-draining sandy mix"),
        ]
        session.add_all(crop_profiles + soil_profiles)

        for index, farm_payload in enumerate(farms):
            farm = Farm(**farm_payload)
            session.add(farm)
            await session.flush()

            device = Device(farm_id=farm.id, device_name=f"ESP32-{index + 1}", serial_number=f"ESP32-{index + 1:02d}", firmware_version="1.2.0", connection_status="online", battery=98.0 - index, signal_strength=86.0 - index * 2, last_seen=datetime.utcnow())
            session.add(device)
            await session.flush()

            session.add(SimulationState(farm_id=farm.id, current_weather=json.dumps({"description": "Clear"}), current_soil_moisture=60.0 + index, current_tank_level=85.0 - index * 2, crop_health=80.0 + index, growth_stage="Growing", pump_status="OFF", simulation_time="2026-07-17T12:00:00", last_updated=datetime.utcnow()))

            base_time = datetime.utcnow() - timedelta(days=3)
            for offset in range(18):
                timestamp = base_time + timedelta(hours=offset * 2)
                session.add(SensorReading(
                    farm_id=farm.id,
                    device_id=device.id,
                    soil_moisture=45.0 + (offset % 5) * 1.2 + index,
                    temperature=24.0 + index + (offset % 4) * 0.4,
                    humidity=60.0 + (offset % 3) * 2.0,
                    light=6000.0 + offset * 120.0,
                    rain=(offset % 6) == 0,
                    wind_speed=8.0 + (offset % 4) * 0.5,
                    uv_index=4.0 + (offset % 5) * 0.2,
                    air_pressure=1012.0 + offset * 0.05,
                    timestamp=timestamp,
                ))
                session.add(WeatherHistory(
                    farm_id=farm.id,
                    temperature=24.0 + index + (offset % 3),
                    humidity=60.0 + offset,
                    wind=8.0 + (offset % 3),
                    forecast="Mostly clear",
                    rain_probability=12.0 + offset,
                    uv=4.0 + offset * 0.1,
                    weather_description="Clear sky",
                    timestamp=timestamp,
                ))
                if offset % 4 == 0:
                    rec = Recommendation(
                        farm_id=farm.id,
                        decision="IRRIGATE" if offset % 8 == 0 else "SKIP",
                        confidence=0.81 - (offset * 0.01),
                        reason="Historical recommendation",
                        risk_level="low",
                        generated_by="rule_engine",
                        timestamp=timestamp,
                        approved=offset % 5 != 0,
                    )
                    session.add(rec)
                    await session.flush()
                    session.add(IrrigationEvent(
                        farm_id=farm.id,
                        recommendation_id=rec.id,
                        pump_started=timestamp,
                        pump_stopped=timestamp + timedelta(minutes=12),
                        duration=12.0,
                        water_used=240.0,
                        tank_before=88.0,
                        tank_after=76.0,
                        status="completed",
                    ))
                    session.add(RuleTrigger(
                        farm_id=farm.id,
                        rule_name="soil_dryness_check",
                        sensor_values=json.dumps({"soil_moisture": 35.0 + index}),
                        trigger_reason="Below threshold",
                        timestamp=timestamp,
                    ))
                    session.add(Notification(
                        farm_id=farm.id,
                        title="Irrigation Reminder",
                        message="Scheduled irrigation completed successfully.",
                        severity="info",
                        read_status=False,
                        created_at=timestamp,
                    ))
                    session.add(ActivityTimeline(
                        farm_id=farm.id,
                        action_type="recommendation",
                        message="Recommendation recorded",
                        metadata_json=json.dumps({"source": "rule_engine"}),
                        created_at=timestamp,
                    ))
                    session.add(Report(
                        farm_id=farm.id,
                        report_type="daily",
                        title=f"Daily Report {index + 1}",
                        summary="Generated from seeded historical data.",
                        metadata_json=json.dumps({"period": "daily"}),
                        generated_at=timestamp,
                    ))

        await session.commit()


async def seed_if_needed() -> None:
    await seed()
