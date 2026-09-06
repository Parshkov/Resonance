"""One isolated store for a test, on the database production runs.

Resonance runs on PostgreSQL everywhere, so a test cannot reach for a
lighter-weight engine without testing something the product never executes --
which is exactly what the retired SQLite repository did for 45% of this suite.

`repository()` gives a throwaway schema nobody else can collide with.
`repository(name)` gives a *stable* schema for that name, so opening it twice
is a restart with the data still there: that is how the recovery and
idempotency cases keep their meaning. The name may be anything, including a
temp path -- it is sanitized into an identifier.
"""

from __future__ import annotations

from src.persistence import open_repository


def repository(target: str | object = ""):
    name = str(target or "").strip()
    if name in ("", ":ephemeral:"):
        return open_repository(":ephemeral:")
    if name.startswith(":ephemeral:") or name.startswith("postgres"):
        return open_repository(name)
    return open_repository(f":ephemeral:{name}")
