"""PostgreSQL repository for the hosted pilot.

Uses the same schema and records as SQLite. The driver is optional so the
engine and the fixture path stay runnable without extra packages.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping, Sequence
from urllib.parse import urlparse

from .models import (
    PERSISTENCE_SCHEMA_VERSION,
    AuditEvent,
    ConsentState,
    SessionRecord,
    UserRecord,
)
from .sql import (
    dumps,
    export_document,
    load_migration_sql,
    row_audit,
    row_session,
    row_user,
    session_params,
)


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def postgres_available() -> bool:
    try:
        import psycopg  # noqa: F401
        return True
    except ImportError:
        try:
            import psycopg2  # noqa: F401
            return True
        except ImportError:
            return False


def _connect(dsn: str):
    try:
        import psycopg
        return psycopg.connect(dsn, row_factory=psycopg.rows.dict_row)
    except ImportError:
        import psycopg2
        conn = psycopg2.connect(dsn)
        return conn


def _pg_sql(sql: str) -> str:
    return sql.replace("INTEGER NOT NULL", "SMALLINT NOT NULL")


class PostgresRepository:
    backend_name = "postgres"

    def __init__(self, dsn: str) -> None:
        if not postgres_available():
            raise RuntimeError(
                "PostgreSQL driver not installed. Install psycopg or psycopg2 "
                "for the hosted-pilot backend. Tests use SQLite."
            )
        parsed = urlparse(dsn)
        if parsed.scheme not in {"postgres", "postgresql"}:
            raise ValueError("PostgreSQL DSN must start with postgres:// or postgresql://")
        self.dsn = dsn
        self._conn = _connect(dsn)
        self.migrate()

    def _execute(self, sql: str, params: Sequence[Any] = ()) -> Any:
        cur = self._conn.cursor()
        cur.execute(sql.replace("?", "%s"), params)
        return cur

    def migrate(self) -> tuple[str, ...]:
        applied: list[str] = []
        cur = self._conn.cursor()
        cur.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            "version TEXT PRIMARY KEY, applied_at TEXT NOT NULL)"
        )
        cur.execute("SELECT version FROM schema_migrations")
        have = {row[0] if not isinstance(row, dict) else row["version"] for row in cur.fetchall()}
        for version, sql in load_migration_sql():
            if version in have:
                continue
            cur.execute(_pg_sql(sql))
            cur.execute(
                "INSERT INTO schema_migrations(version, applied_at) VALUES (%s, %s) "
                "ON CONFLICT (version) DO NOTHING",
                (version, _now()),
            )
            applied.append(version)
        self._conn.commit()
        return tuple(applied)

    def health(self) -> dict[str, Any]:
        cur = self._execute("SELECT version FROM schema_migrations ORDER BY version")
        versions = [r[0] if not isinstance(r, dict) else r["version"] for r in cur.fetchall()]
        users = self._execute("SELECT COUNT(*) AS n FROM users").fetchone()
        sessions = self._execute("SELECT COUNT(*) AS n FROM sessions").fetchone()
        n_users = users[0] if not isinstance(users, dict) else users["n"]
        n_sessions = sessions[0] if not isinstance(sessions, dict) else sessions["n"]
        return {
            "ok": True,
            "backend": self.backend_name,
            "schema_version": PERSISTENCE_SCHEMA_VERSION,
            "migrations": versions,
            "users": int(n_users),
            "sessions": int(n_sessions),
        }

    def reset(self) -> None:
        for table in ("messages", "channels", "intros", "audit_events", "sessions", "users"):
            self._execute(f"DELETE FROM {table}")
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def _fetchone_map(self, sql: str, params: Sequence[Any] = ()) -> dict[str, Any] | None:
        cur = self._execute(sql, params)
        row = cur.fetchone()
        if row is None:
            return None
        if isinstance(row, dict):
            return row
        cols = [d[0] for d in cur.description]
        return dict(zip(cols, row))

    def _fetchall_map(self, sql: str, params: Sequence[Any] = ()) -> list[dict[str, Any]]:
        cur = self._execute(sql, params)
        rows = cur.fetchall()
        if not rows:
            return []
        if isinstance(rows[0], dict):
            return list(rows)
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in rows]

    def put_user(self, user: UserRecord) -> UserRecord:
        self._execute(
            "INSERT INTO users(user_id, display_label, avatar_placeholder, "
            "created_at, updated_at, revoked_at) VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT (user_id) DO UPDATE SET "
            "display_label=EXCLUDED.display_label, "
            "avatar_placeholder=EXCLUDED.avatar_placeholder, "
            "updated_at=EXCLUDED.updated_at, "
            "revoked_at=EXCLUDED.revoked_at",
            (user.user_id, user.display_label, user.avatar_placeholder,
             user.created_at, user.updated_at, user.revoked_at),
        )
        self._conn.commit()
        return user

    def get_user(self, user_id: str) -> UserRecord | None:
        row = self._fetchone_map("SELECT * FROM users WHERE user_id = ?", (user_id,))
        return row_user(row) if row else None

    def list_users(self) -> Sequence[UserRecord]:
        return tuple(row_user(r) for r in self._fetchall_map(
            "SELECT * FROM users ORDER BY user_id"))

    def put_session(self, session: SessionRecord) -> SessionRecord:
        self._execute(
            "INSERT INTO sessions("
            "session_id, user_id, thought_id, schema_version, thought_dna, "
            "thought_dna_sha256, thought_dna_schema_version, share_enabled, "
            "share_thought_dna, share_coarse_location, share_display_profile, "
            "location_json, presentation_json, record_kind, builder_id, notes, "
            "created_at, updated_at, revoked_at, deleted_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT (session_id) DO UPDATE SET "
            "user_id=EXCLUDED.user_id, thought_id=EXCLUDED.thought_id, "
            "schema_version=EXCLUDED.schema_version, thought_dna=EXCLUDED.thought_dna, "
            "thought_dna_sha256=EXCLUDED.thought_dna_sha256, "
            "thought_dna_schema_version=EXCLUDED.thought_dna_schema_version, "
            "share_enabled=EXCLUDED.share_enabled, "
            "share_thought_dna=EXCLUDED.share_thought_dna, "
            "share_coarse_location=EXCLUDED.share_coarse_location, "
            "share_display_profile=EXCLUDED.share_display_profile, "
            "location_json=EXCLUDED.location_json, "
            "presentation_json=EXCLUDED.presentation_json, "
            "record_kind=EXCLUDED.record_kind, builder_id=EXCLUDED.builder_id, "
            "notes=EXCLUDED.notes, updated_at=EXCLUDED.updated_at, "
            "revoked_at=EXCLUDED.revoked_at, deleted_at=EXCLUDED.deleted_at",
            session_params(session),
        )
        self._conn.commit()
        return session

    def get_session(self, session_id: str) -> SessionRecord | None:
        row = self._fetchone_map("SELECT * FROM sessions WHERE session_id = ?", (session_id,))
        return row_session(row) if row else None

    def get_session_by_thought(self, thought_id: str) -> SessionRecord | None:
        row = self._fetchone_map("SELECT * FROM sessions WHERE thought_id = ?", (thought_id,))
        return row_session(row) if row else None

    def list_sessions(self, *, include_deleted: bool = False) -> Sequence[SessionRecord]:
        if include_deleted:
            rows = self._fetchall_map("SELECT * FROM sessions ORDER BY session_id")
        else:
            rows = self._fetchall_map(
                "SELECT * FROM sessions WHERE deleted_at IS NULL ORDER BY session_id")
        return tuple(row_session(r) for r in rows)

    def list_discoverable_sessions(self) -> Sequence[SessionRecord]:
        rows = self._fetchall_map(
            "SELECT * FROM sessions WHERE share_enabled = 1 AND share_thought_dna = 1 "
            "AND revoked_at IS NULL AND deleted_at IS NULL ORDER BY thought_id")
        return tuple(row_session(r) for r in rows)

    def append_audit(self, event: AuditEvent) -> AuditEvent:
        self._execute(
            "INSERT INTO audit_events(event_id, event_type, user_id, session_id, "
            "payload_json, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (event.event_id, event.event_type, event.user_id, event.session_id,
             dumps(event.payload), event.created_at),
        )
        self._conn.commit()
        return event

    def list_audit(self) -> Sequence[AuditEvent]:
        return tuple(row_audit(r) for r in self._fetchall_map(
            "SELECT * FROM audit_events ORDER BY created_at, event_id"))

    def export_payload(self) -> dict[str, Any]:
        return export_document(
            backend=self.backend_name,
            users=list(self.list_users()),
            sessions=list(self.list_sessions(include_deleted=True)),
            audit=list(self.list_audit()),
        )

    def import_payload(self, payload: Mapping[str, Any]) -> None:
        self.reset()
        for raw in payload.get("users", []):
            self.put_user(UserRecord(
                user_id=raw["user_id"],
                display_label=raw["display_label"],
                avatar_placeholder=raw["avatar_placeholder"],
                created_at=raw["created_at"],
                updated_at=raw["updated_at"],
                revoked_at=raw.get("revoked_at"),
            ))
        for raw in payload.get("sessions", []):
            self.put_session(SessionRecord(
                session_id=raw["session_id"],
                user_id=raw["user_id"],
                thought_id=raw["thought_id"],
                schema_version=raw["schema_version"],
                thought_dna=raw["thought_dna"],
                thought_dna_sha256=raw["thought_dna_sha256"],
                thought_dna_schema_version=raw["thought_dna_schema_version"],
                consent=ConsentState.from_mapping(raw["consent"]),
                location=raw["location"],
                presentation=raw["presentation"],
                record_kind=raw["record_kind"],
                builder_id=raw["builder_id"],
                notes=raw["notes"],
                created_at=raw["created_at"],
                updated_at=raw["updated_at"],
                revoked_at=raw.get("revoked_at"),
                deleted_at=raw.get("deleted_at"),
            ))
        for raw in payload.get("audit", []):
            self.append_audit(AuditEvent(
                event_id=raw["event_id"],
                event_type=raw["event_type"],
                user_id=raw.get("user_id"),
                session_id=raw.get("session_id"),
                payload=raw.get("payload") or {},
                created_at=raw["created_at"],
            ))
