"""
crop_config.py — Crop Stage Management
Stores user's selected crop type and growth stage in SQLite.
Each combination has tuned soil moisture targets that the MQTT worker respects.
"""
import os, aiosqlite

DB_PATH = os.getenv("DB_PATH", "agromind.db")

# ── Crop thresholds by stage ───────────────────────────────────────────────────
CROP_PROFILES = {
    "generic":   {"seedling": (50, 70), "vegetative": (45, 65), "flowering": (50, 70), "harvest": (35, 55)},
    "rice":      {"seedling": (60, 80), "vegetative": (55, 75), "flowering": (60, 80), "harvest": (40, 60)},
    "wheat":     {"seedling": (45, 65), "vegetative": (40, 60), "flowering": (50, 70), "harvest": (30, 50)},
    "tomato":    {"seedling": (55, 75), "vegetative": (50, 70), "flowering": (55, 75), "harvest": (45, 65)},
    "potato":    {"seedling": (50, 70), "vegetative": (55, 75), "flowering": (50, 70), "harvest": (40, 60)},
    "maize":     {"seedling": (45, 65), "vegetative": (40, 60), "flowering": (50, 70), "harvest": (35, 55)},
    "sugarcane": {"seedling": (55, 75), "vegetative": (60, 80), "flowering": (55, 75), "harvest": (40, 60)},
}

VALID_STAGES = ["seedling", "vegetative", "flowering", "harvest"]

# ── DB helpers ─────────────────────────────────────────────────────────────────
async def init_crop_table():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS crop_config (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                crop TEXT DEFAULT 'generic',
                stage TEXT DEFAULT 'vegetative',
                updated_at TEXT DEFAULT (datetime('now','localtime'))
            )
        """)
        # Insert default row if not present
        await db.execute("""
            INSERT OR IGNORE INTO crop_config (id, crop, stage) VALUES (1, 'generic', 'vegetative')
        """)
        await db.commit()

async def get_crop_config() -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM crop_config WHERE id = 1")
        row = await cur.fetchone()
    if not row:
        return {"crop": "generic", "stage": "vegetative"}
    d = dict(row)
    crop = d.get("crop", "generic")
    stage = d.get("stage", "vegetative")
    profile = CROP_PROFILES.get(crop, CROP_PROFILES["generic"])
    thresholds = profile.get(stage, (40, 65))
    return {
        "crop": crop,
        "stage": stage,
        "updated_at": d.get("updated_at"),
        "soil_min_pct": thresholds[0],
        "soil_max_pct": thresholds[1],
        "available_crops": list(CROP_PROFILES.keys()),
        "available_stages": VALID_STAGES,
    }

async def set_crop_config(crop: str, stage: str) -> dict:
    crop = crop.lower().strip()
    stage = stage.lower().strip()
    if crop not in CROP_PROFILES:
        raise ValueError(f"Unknown crop '{crop}'. Choose from: {list(CROP_PROFILES.keys())}")
    if stage not in VALID_STAGES:
        raise ValueError(f"Unknown stage '{stage}'. Choose from: {VALID_STAGES}")
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE crop_config SET crop=?, stage=?, updated_at=datetime('now','localtime') WHERE id=1
        """, (crop, stage))
        await db.commit()
    return await get_crop_config()
