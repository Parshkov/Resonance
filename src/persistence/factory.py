"""Choose SQLite or PostgreSQL from an explicit path/DSN or environment."""

from __future__ import annotations

import os
from pathlib import Path

from .postgres_store import PostgresRepository, postgres_available
from .sqlite_store import SQLiteRepository


def open_repository(target: str | Path | None = None):
    raw = str(target) if target is not None else os.environ.get("RESONANCE_DATABASE_URL", "")
    raw = raw.strip()
    if raw.startswith("postgres://") or raw.startswith("postgresql://"):
        if not postgres_available():
            raise RuntimeError(
                "RESONANCE_DATABASE_URL points at PostgreSQL but no driver is installed"
            )
        return PostgresRepository(raw)
    if not raw:
        raw = str(Path(os.environ.get("RESONANCE_SQLITE_PATH", "var/resonance-pilot.sqlite")))
    Path(raw).parent.mkdir(parents=True, exist_ok=True)
    return SQLiteRepository(raw)
