"""Lightweight, forward-only, idempotent SQL migration runner.

The project already had Alembic configured but with no migration versions and
the documented start command runs plain ``uvicorn`` (no ``alembic upgrade``),
so schema was created via ``Base.metadata.create_all`` with no versioning. This
runner adds what the task requires without a heavy framework:

* a ``schema_version`` record of applied migration ids,
* ordered forward-only migrations applied automatically at startup in a
  transaction,
* idempotent (safe to re-run), and
* an automatic backup (``VACUUM INTO``) is taken before any pending migration
  that touches an existing populated DB.

Migrations are non-destructive. A destructive change (drop/rewrite a column
holding data) would require copy-then-swap and MUST be called out before it is
run — none of the current migrations do this.

How to add a migration: append a ``(id, async up(conn))`` to ``MIGRATIONS``
below. How to roll back: restore from the backup taken before migration (see
``docs/DATABASE_AND_PERSISTENCE.md``).
"""

from __future__ import annotations

import asyncio
import glob
import logging
import os
import shutil
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine

from sqlalchemy import text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

SCHEMA_VERSION_TABLE = "schema_version"
BACKUP_KEEP_N = int(os.getenv("ANALYSIS_BACKUP_KEEP", "5"))
DEFAULT_BACKUP_DIR = os.getenv("ANALYSIS_BACKUP_DIR", "")


MigrationFn = Callable[[Any], Coroutine[Any, Any, None]]
MIGRATIONS: list[tuple[str, MigrationFn]] = []


def _has_column(conn, table: str, col: str) -> bool:
    rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
    return any(row[1] == col for row in rows)


def _has_table(conn, table: str) -> bool:
    row = conn.execute(
        text("SELECT name FROM sqlite_master WHERE type='table' AND name=:n"), {"n": table}
    ).fetchone()
    return row is not None


def _m001_add_sensor_quality_fields(conn) -> None:
    if not _has_table(conn, "sensor_readings"):
        return
    for col, ddl in [
        ("quality_status", "VARCHAR(32)"),
        ("quality_reason", "TEXT"),
        ("dedup_key", "VARCHAR(128)"),
        ("received_at", "DATETIME"),
    ]:
        if not _has_column(conn, "sensor_readings", col):
            conn.execute(text(f"ALTER TABLE sensor_readings ADD COLUMN {col} {ddl}"))
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_sensor_readings_dedup_key ON sensor_readings(dedup_key)"
    ))


def _m002_add_crop_profile_versioning(conn) -> None:
    if not _has_table(conn, "crop_profiles"):
        return
    for col, ddl in [
        ("version", "VARCHAR(50)"),
        ("is_active", "BOOLEAN DEFAULT 1"),
        ("thresholds_json", "TEXT"),
        ("updated_at", "DATETIME"),
    ]:
        if not _has_column(conn, "crop_profiles", col):
            conn.execute(text(f"ALTER TABLE crop_profiles ADD COLUMN {col} {ddl}"))


def _m003_create_analysis_tables(conn) -> None:
    conn.execute(text(f"""CREATE TABLE IF NOT EXISTS {SCHEMA_VERSION_TABLE} (
        id VARCHAR(64) PRIMARY KEY,
        applied_at DATETIME NOT NULL
    )"""))
    conn.execute(text("""CREATE TABLE IF NOT EXISTS analysis_reports (
        id VARCHAR(64) PRIMARY KEY,
        farm_id VARCHAR(64) NOT NULL,
        input_hash VARCHAR(64) NOT NULL,
        analysis_method VARCHAR(32) NOT NULL,
        engine_id VARCHAR(100),
        analysis_version VARCHAR(50),
        profile_name VARCHAR(100),
        profile_version VARCHAR(50),
        overall_status VARCHAR(32),
        health_score INTEGER,
        irrigation_recommendation VARCHAR(32),
        dashboard_summary TEXT,
        sensor_data_timestamp DATETIME,
        report_json TEXT NOT NULL,
        created_at DATETIME NOT NULL
    )"""))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_ar_farm ON analysis_reports(farm_id)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_ar_hash ON analysis_reports(input_hash)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_ar_method ON analysis_reports(analysis_method)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_ar_created ON analysis_reports(created_at)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_ar_aversion ON analysis_reports(analysis_version)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_ar_pversion ON analysis_reports(profile_version)"))
    conn.execute(text("""CREATE TABLE IF NOT EXISTS analysis_cache_index (
        id VARCHAR(64) PRIMARY KEY,
        input_hash VARCHAR(64) NOT NULL,
        analysis_method VARCHAR(32) NOT NULL,
        analysis_version VARCHAR(50),
        profile_version VARCHAR(50),
        report_id VARCHAR(64) NOT NULL,
        created_at DATETIME NOT NULL,
        expires_at DATETIME NOT NULL,
        FOREIGN KEY (report_id) REFERENCES analysis_reports(id) ON DELETE CASCADE
    )"""))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_aci_hash ON analysis_cache_index(input_hash)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_aci_method ON analysis_cache_index(analysis_method)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_aci_expires ON analysis_cache_index(expires_at)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_aci_report ON analysis_cache_index(report_id)"))
    conn.execute(text("""CREATE TABLE IF NOT EXISTS api_quota_state (
        provider VARCHAR(50) NOT NULL,
        model VARCHAR(100) NOT NULL,
        key_fingerprint VARCHAR(64) NOT NULL,
        state VARCHAR(32) NOT NULL DEFAULT 'AVAILABLE',
        reset_at DATETIME,
        last_attempt_at DATETIME,
        in_flight_claim_until DATETIME,
        last_failure_classification VARCHAR(50),
        header_meta TEXT,
        updated_at DATETIME,
        PRIMARY KEY (provider, model, key_fingerprint)
    )"""))
    conn.execute(text("""CREATE TABLE IF NOT EXISTS irrigation_audit (
        id VARCHAR(64) PRIMARY KEY,
        farm_id VARCHAR(64) NOT NULL,
        action VARCHAR(10) NOT NULL,
        requested_duration_sec INTEGER,
        allowed_duration_sec INTEGER,
        allowed BOOLEAN NOT NULL DEFAULT 0,
        clamped BOOLEAN NOT NULL DEFAULT 0,
        reason TEXT,
        source VARCHAR(100),
        actor VARCHAR(100),
        published BOOLEAN NOT NULL DEFAULT 0,
        published_at DATETIME,
        created_at DATETIME NOT NULL
    )"""))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_ia_farm ON irrigation_audit(farm_id)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_ia_created ON irrigation_audit(created_at)"))


def _m004_seed_crop_profile_versions(conn) -> None:
    """Backfill version + thresholds_json onto existing crop_profiles from the
    versioned config. After seeding the DB is authoritative; this keeps the
    existing seeded rows in sync with the config version on first migration."""
    if not _has_table(conn, "crop_profiles"):
        return
    try:
        from analysis.crop_profiles import load_config, config_version
        cfg = load_config()
        ver = config_version()
    except Exception as exc:
        logger.warning("Could not load crop profiles config for backfill: %s", exc)
        return
    profiles = cfg.get("profiles", {})
    import json as _json
    for name, profile in profiles.items():
        th_json = _json.dumps(profile.get("thresholds", {}))
        row = conn.execute(
            text("SELECT id FROM crop_profiles WHERE name = :n"), {"n": name}
        ).fetchone()
        now = datetime.now(timezone.utc)
        if row is None:
            conn.execute(text(
                "INSERT INTO crop_profiles (id, name, growth_stage, version, is_active, thresholds_json, created_at, updated_at) "
                "VALUES (lower(hex(randomblob(16))), :n, :gs, :v, 1, :th, :now, :now)"
            ), {"n": name, "gs": profile.get("growth_stage"), "v": ver, "th": th_json, "now": now})
        else:
            conn.execute(text(
                "UPDATE crop_profiles SET version = :v, thresholds_json = :th, is_active = 1, updated_at = :now WHERE id = :id"
            ), {"v": ver, "th": th_json, "now": now, "id": row[0]})


MIGRATIONS.append(("001_sensor_quality_fields", _m001_add_sensor_quality_fields))
MIGRATIONS.append(("002_crop_profile_versioning", _m002_add_crop_profile_versioning))
MIGRATIONS.append(("003_analysis_tables", _m003_create_analysis_tables))
MIGRATIONS.append(("004_seed_crop_profile_versions", _m004_seed_crop_profile_versions))


# ── PRAGMA setup ──────────────────────────────────────────────────────────────

def register_sqlite_pragmas(engine: Engine) -> None:
    """Per-connection: foreign_keys + busy_timeout. WAL is set once at startup."""
    from sqlalchemy import event

    @event.listens_for(engine, "connect")
    def _set_pragmas(dbapi_conn, _record):
        try:
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.execute("PRAGMA busy_timeout=30000")
            cur.close()
        except Exception as exc:  # pragma: no cover - best effort
            logger.warning("PRAGMA setup failed: %s", exc)


def set_wal_mode(db_path: str) -> None:
    """Set WAL journal mode (persistent in the DB file). Safe to call once."""
    try:
        import sqlite3
        conn = sqlite3.connect(db_path, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.close()
    except Exception as exc:
        logger.info("WAL not set (%s) — continuing with default journal mode.", exc)


# ── Backup ────────────────────────────────────────────────────────────────────

def _backup_dir(db_path: str) -> str:
    configured = DEFAULT_BACKUP_DIR
    if configured:
        return os.path.abspath(configured)
    return os.path.join(os.path.dirname(os.path.abspath(db_path)), ".backups")


def make_backup(db_path: str) -> str | None:
    """Online backup via VACUUM INTO (not a raw copy of a live WAL DB)."""
    if not os.path.exists(db_path):
        return None
    bdir = _backup_dir(db_path)
    os.makedirs(bdir, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    base = os.path.basename(db_path) or "agromind.db"
    dest = os.path.join(bdir, f"{base}.bak-{ts}")
    try:
        import sqlite3
        conn = sqlite3.connect(db_path, timeout=30)
        conn.execute(f"VACUUM INTO '{dest}'")
        conn.close()
    except Exception as exc:
        logger.warning("Backup (VACUUM INTO) failed: %s", exc)
        return None
    _rotate_backups(bdir, base)
    logger.info("DB backup created: %s", dest)
    return dest


def _rotate_backups(bdir: str, base: str) -> None:
    pattern = os.path.join(bdir, f"{base}.bak-*")
    files = sorted(glob.glob(pattern), key=lambda p: os.path.getmtime(p), reverse=True)
    for old in files[BACKUP_KEEP_N:]:
        try:
            os.remove(old)
        except OSError:
            pass


# ── Runner ────────────────────────────────────────────────────────────────────

async def run_pending_migrations(engine, db_path: str | None) -> list[str]:
    """Apply pending migrations in a transaction. Returns applied ids.

    For SQLite, takes a backup before applying any pending migration that
    touches an existing populated DB.
    """
    applied: list[str] = []
    async with engine.begin() as conn:
        # Ensure schema_version table exists (created by m003 too, but we need it
        # before listing migrations).
        await conn.execute(text(f"""CREATE TABLE IF NOT EXISTS {SCHEMA_VERSION_TABLE} (
            id VARCHAR(64) PRIMARY KEY,
            applied_at DATETIME NOT NULL
        )"""))
        rows = (await conn.execute(text(f"SELECT id FROM {SCHEMA_VERSION_TABLE}"))).fetchall()
        done = {r[0] for r in rows}
        pending = [(mid, fn) for mid, fn in MIGRATIONS if mid not in done]
        if not pending:
            return applied

    # Backup OUTSIDE the transaction (VACUUM INTO cannot run inside one).
    is_sqlite = str(engine.url).startswith("sqlite")
    if is_sqlite and db_path:
        populated = _db_has_data(db_path)
        if populated:
            make_backup(db_path)

    async with engine.begin() as conn:
        rows = (await conn.execute(text(f"SELECT id FROM {SCHEMA_VERSION_TABLE}"))).fetchall()
        done = {r[0] for r in rows}
        for mid, fn in MIGRATIONS:
            if mid in done:
                continue
            logger.info("Applying migration %s", mid)
            await conn.run_sync(fn)
            await conn.execute(text(
                f"INSERT INTO {SCHEMA_VERSION_TABLE} (id, applied_at) VALUES (:id, :now)"
            ), {"id": mid, "now": datetime.now(timezone.utc)})
            applied.append(mid)
    return applied


def _db_has_data(db_path: str) -> bool:
    try:
        import sqlite3
        conn = sqlite3.connect(db_path, timeout=10)
        row = conn.execute(
            "SELECT count(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchone()
        conn.close()
        return bool(row and row[0] > 0)
    except Exception:
        return False
