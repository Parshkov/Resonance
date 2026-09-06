"""Open the one store Resonance runs on: PostgreSQL.

There used to be two repositories behind this function -- SQLite and
PostgreSQL -- and the split was not a choice anybody was making. Production has
always run PostgreSQL (`db: postgresql://...` in the deploy log), while 682
tests and every local run went through SQLite. So the implementation under the
product was the one nobody exercised, and the one 45% of the suite exercised
was the one nobody shipped. Two independent implementations of a 53-method
protocol, and the divergence could only ever be found in production.

SQLite is gone. Everything -- production, local development, the whole test
suite -- runs on PostgreSQL now, so the tested path and the shipped path are
the same code.

Targets:

    postgresql://... / postgres://...   a real database
    :ephemeral:                         a fresh, isolated schema, dropped by
                                        the caller; this is what tests use
    :ephemeral:<name>                   a *stable* isolated schema, so opening
                                        the same name twice is a restart --
                                        which is what the recovery tests need

The ephemeral forms need a server to make schemas on. It comes from
RESONANCE_TEST_POSTGRES_URL, else RESONANCE_DATABASE_URL, else the local
default below (a container is one command; see ops/DEPLOY.md).
"""

from __future__ import annotations

import hashlib
import os
import re
import secrets

from .postgres_store import PostgresRepository, postgres_available

EPHEMERAL = ":ephemeral:"
DEFAULT_TEST_DSN = "postgresql://postgres:postgres@127.0.0.1:55432/resonance_test"

_NO_SERVER = (
    "no PostgreSQL to run against. Resonance runs on PostgreSQL everywhere, "
    "including its tests, so that the tested store is the shipped store.\n\n"
    "    docker run -d --name resonance-test-pg -e POSTGRES_PASSWORD=postgres \\\n"
    "        -e POSTGRES_DB=resonance_test -p 55432:5432 postgres:16\n\n"
    "Then either accept the default DSN (" + DEFAULT_TEST_DSN + ") or set "
    "RESONANCE_TEST_POSTGRES_URL to your own."
)


def _schema_name(name: str) -> str:
    """A caller-chosen name -> a stable, safe PostgreSQL identifier."""
    safe = re.sub(r"[^A-Za-z0-9_]", "_", name).strip("_")
    if safe and len(safe) <= 40 and not safe[0].isdigit():
        return safe.lower()
    return "h" + hashlib.sha256(name.encode()).hexdigest()[:16]


def ephemeral_dsn() -> str:
    """The server that ephemeral schemas are created on."""
    return (os.environ.get("RESONANCE_TEST_POSTGRES_URL")
            or os.environ.get("RESONANCE_DATABASE_URL")
            or DEFAULT_TEST_DSN).strip()


def open_repository(target: str | None = None) -> PostgresRepository:
    raw = str(target).strip() if target is not None else os.environ.get("RESONANCE_DATABASE_URL", "").strip()
    if not postgres_available():
        raise RuntimeError(
            "PostgreSQL driver not installed: pip install 'psycopg[binary]'"
        )
    if raw.startswith(EPHEMERAL):
        name = raw[len(EPHEMERAL):].strip()
        # A name makes the schema stable, so reopening it is a restart with the
        # data still there. No name means a throwaway nobody else can collide
        # with, even when tests run side by side. Callers name schemas after
        # test cases and temp paths, so the name is hashed into an identifier
        # rather than rejected: same name in, same schema out.
        schema = f"eph_{_schema_name(name)}" if name else f"eph_{secrets.token_hex(8)}"
        try:
            return PostgresRepository(ephemeral_dsn(), schema=schema)
        except OSError as exc:
            raise RuntimeError(f"{_NO_SERVER}\n\nunderlying error: {exc}") from exc
        except Exception as exc:  # noqa: BLE001
            # A driver that cannot reach the server reports its own class, not
            # OSError, so fall back to matching the connection failure rather
            # than dressing every error up as a missing server.
            if "connect" in str(exc).lower() or "could not translate" in str(exc).lower():
                raise RuntimeError(f"{_NO_SERVER}\n\nunderlying error: {exc}") from exc
            raise
    if raw.startswith("postgres://") or raw.startswith("postgresql://"):
        return PostgresRepository(raw)
    if not raw:
        raise ValueError(
            "no database target: pass a postgresql:// DSN, set "
            "RESONANCE_DATABASE_URL, or use ':ephemeral:' for a throwaway schema"
        )
    raise ValueError(
        f"unsupported database target {raw!r}. Resonance runs on PostgreSQL only; "
        "SQLite file paths and ':memory:' are no longer accepted. Use a "
        "postgresql:// DSN, or ':ephemeral:' for a throwaway schema."
    )
