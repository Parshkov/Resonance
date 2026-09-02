"""File-backed SQLite repository. Restart-safe; stdlib only."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

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


class SQLiteRepository:
    backend_name = "sqlite"

    def __init__(self, path: str | Path = ":memory:") -> None:
        self.path = str(path)
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.execute("PRAGMA journal_mode = WAL")
        self.migrate()

    def migrate(self) -> tuple[str, ...]:
        applied: list[str] = []
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            "version TEXT PRIMARY KEY, applied_at TEXT NOT NULL)"
        )
        have = {row[0] for row in self._conn.execute("SELECT version FROM schema_migrations")}
        for version, sql in load_migration_sql():
            if version in have:
                continue
            self._conn.executescript(sql)
            self._conn.execute(
                "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                (version, _now()),
            )
            applied.append(version)
        self._conn.commit()
        return tuple(applied)

    def health(self) -> dict[str, Any]:
        versions = [r[0] for r in self._conn.execute(
            "SELECT version FROM schema_migrations ORDER BY version")]
        users = self._conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        sessions = self._conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
        return {
            "ok": True,
            "backend": self.backend_name,
            "path": self.path,
            "schema_version": PERSISTENCE_SCHEMA_VERSION,
            "migrations": versions,
            "users": int(users),
            "sessions": int(sessions),
        }

    def reset(self) -> None:
        for table in ("messages", "channels", "intros", "audit_events", "sessions", "users"):
            self._conn.execute(f"DELETE FROM {table}")
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def put_user(self, user: UserRecord) -> UserRecord:
        self._conn.execute(
            "INSERT INTO users(user_id, display_label, avatar_placeholder, "
            "created_at, updated_at, revoked_at) VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET "
            "display_label=excluded.display_label, "
            "avatar_placeholder=excluded.avatar_placeholder, "
            "updated_at=excluded.updated_at, "
            "revoked_at=excluded.revoked_at",
            (user.user_id, user.display_label, user.avatar_placeholder,
             user.created_at, user.updated_at, user.revoked_at),
        )
        self._conn.commit()
        return user

    def get_user(self, user_id: str) -> UserRecord | None:
        row = self._conn.execute(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        ).fetchone()
        return row_user(row) if row else None

    def list_users(self) -> Sequence[UserRecord]:
        rows = self._conn.execute("SELECT * FROM users ORDER BY user_id").fetchall()
        return tuple(row_user(r) for r in rows)

    def put_session(self, session: SessionRecord) -> SessionRecord:
        params = session_params(session)
        self._conn.execute(
            "INSERT INTO sessions("
            "session_id, user_id, thought_id, schema_version, thought_dna, "
            "thought_dna_sha256, thought_dna_schema_version, share_enabled, "
            "share_thought_dna, share_coarse_location, share_display_profile, "
            "location_json, presentation_json, record_kind, builder_id, notes, "
            "created_at, updated_at, revoked_at, deleted_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(session_id) DO UPDATE SET "
            "user_id=excluded.user_id, thought_id=excluded.thought_id, "
            "schema_version=excluded.schema_version, thought_dna=excluded.thought_dna, "
            "thought_dna_sha256=excluded.thought_dna_sha256, "
            "thought_dna_schema_version=excluded.thought_dna_schema_version, "
            "share_enabled=excluded.share_enabled, "
            "share_thought_dna=excluded.share_thought_dna, "
            "share_coarse_location=excluded.share_coarse_location, "
            "share_display_profile=excluded.share_display_profile, "
            "location_json=excluded.location_json, "
            "presentation_json=excluded.presentation_json, "
            "record_kind=excluded.record_kind, builder_id=excluded.builder_id, "
            "notes=excluded.notes, updated_at=excluded.updated_at, "
            "revoked_at=excluded.revoked_at, deleted_at=excluded.deleted_at",
            params,
        )
        self._conn.commit()
        return session

    def get_session(self, session_id: str) -> SessionRecord | None:
        row = self._conn.execute(
            "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
        ).fetchone()
        return row_session(row) if row else None

    def get_session_by_thought(self, thought_id: str) -> SessionRecord | None:
        row = self._conn.execute(
            "SELECT * FROM sessions WHERE thought_id = ?", (thought_id,)
        ).fetchone()
        return row_session(row) if row else None

    def list_sessions(self, *, include_deleted: bool = False) -> Sequence[SessionRecord]:
        if include_deleted:
            rows = self._conn.execute(
                "SELECT * FROM sessions ORDER BY session_id"
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM sessions WHERE deleted_at IS NULL ORDER BY session_id"
            ).fetchall()
        return tuple(row_session(r) for r in rows)

    def list_discoverable_sessions(self) -> Sequence[SessionRecord]:
        rows = self._conn.execute(
            "SELECT * FROM sessions WHERE share_enabled = 1 AND share_thought_dna = 1 "
            "AND revoked_at IS NULL AND deleted_at IS NULL ORDER BY thought_id"
        ).fetchall()
        return tuple(row_session(r) for r in rows)

    def append_audit(self, event: AuditEvent) -> AuditEvent:
        self._conn.execute(
            "INSERT INTO audit_events(event_id, event_type, user_id, session_id, "
            "payload_json, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (event.event_id, event.event_type, event.user_id, event.session_id,
             dumps(event.payload), event.created_at),
        )
        self._conn.commit()
        return event

    def list_audit(self) -> Sequence[AuditEvent]:
        rows = self._conn.execute(
            "SELECT * FROM audit_events ORDER BY created_at, event_id"
        ).fetchall()
        return tuple(row_audit(r) for r in rows)

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
