"""PostgreSQL repository for the hosted pilot.

The optional driver keeps the deterministic engine/test path dependency-light.
The transaction semantics mirror SQLite: public-state writes, generation bumps,
optimistic versions, audit evidence, and idempotency completion commit together.
"""

from __future__ import annotations

import threading
from dataclasses import replace
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence
from urllib.parse import urlparse

from .errors import PersistenceConflictError, PersistenceOwnershipError
from .models import (
    PERSISTENCE_SCHEMA_VERSION,
    AuditEvent,
    IdempotencyKey,
    IdempotencyRecord,
    SessionRecord,
    UserRecord,
)
from .sql import (
    dumps,
    export_document,
    load_migration_sql,
    loads,
    row_audit,
    row_idempotency,
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
        from psycopg.rows import dict_row
        return psycopg.connect(dsn, row_factory=dict_row)
    except ImportError:
        import psycopg2
        return psycopg2.connect(dsn)


class PostgresRepository:
    backend_name = "postgres"

    def __init__(self, dsn: str) -> None:
        if not postgres_available():
            raise RuntimeError(
                "PostgreSQL driver not installed. Install psycopg or psycopg2 "
                "for the hosted-pilot backend."
            )
        parsed = urlparse(dsn)
        if parsed.scheme not in {"postgres", "postgresql"}:
            raise ValueError("PostgreSQL DSN must start with postgres:// or postgresql://")
        self.dsn = dsn
        self._lock = threading.RLock()
        self._conn = _connect(dsn)
        self.migrate()

    def _execute(self, sql: str, params: Sequence[Any] = ()) -> Any:
        cur = self._conn.cursor()
        cur.execute(sql.replace("?", "%s"), params)
        return cur

    def _execute_script(self, sql: str) -> None:
        # R11 migrations intentionally contain only simple DDL/DML statements.
        for statement in sql.split(";"):
            statement = statement.strip()
            if statement:
                self._execute(statement)

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
        return [dict(zip(cols, row)) for row in rows]

    def migrate(self) -> tuple[str, ...]:
        with self._lock:
            applied: list[str] = []
            try:
                self._execute(
                    "CREATE TABLE IF NOT EXISTS schema_migrations ("
                    "version TEXT PRIMARY KEY, applied_at TEXT NOT NULL)"
                )
                have = {
                    row["version"]
                    for row in self._fetchall_map("SELECT version FROM schema_migrations")
                }
                for version, sql in load_migration_sql():
                    if version in have:
                        continue
                    self._execute_script(sql)
                    self._execute(
                        "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?) "
                        "ON CONFLICT (version) DO NOTHING",
                        (version, _now()),
                    )
                    applied.append(version)
                self._conn.commit()
                return tuple(applied)
            except Exception:
                self._conn.rollback()
                raise

    def _bump_generation(self) -> int:
        cur = self._execute(
            "UPDATE persistence_state SET corpus_generation = corpus_generation + 1, "
            "updated_at = ? WHERE state_id = 1 RETURNING corpus_generation",
            (_now(),),
        )
        row = cur.fetchone()
        if row is None:
            raise RuntimeError("persistence_state row is missing")
        return int(row["corpus_generation"] if isinstance(row, dict) else row[0])

    def get_corpus_generation(self) -> int:
        with self._lock:
            row = self._fetchone_map(
                "SELECT corpus_generation FROM persistence_state WHERE state_id = 1"
            )
            if row is None:
                raise RuntimeError("persistence_state row is missing")
            return int(row["corpus_generation"])

    def health(self) -> dict[str, Any]:
        with self._lock:
            versions = [
                r["version"]
                for r in self._fetchall_map(
                    "SELECT version FROM schema_migrations ORDER BY version"
                )
            ]
            users = self._fetchone_map("SELECT COUNT(*) AS n FROM users")
            sessions = self._fetchone_map("SELECT COUNT(*) AS n FROM sessions")
            return {
                "ok": True,
                "backend": self.backend_name,
                "schema_version": PERSISTENCE_SCHEMA_VERSION,
                "migrations": versions,
                "users": int(users["n"]),
                "sessions": int(sessions["n"]),
                "corpus_generation": self.get_corpus_generation(),
            }

    def reset(self) -> None:
        with self._lock:
            try:
                for table in (
                    "messages",
                    "channels",
                    "intros",
                    "idempotency_keys",
                    "audit_events",
                    "sessions",
                    "users",
                ):
                    self._execute(f"DELETE FROM {table}")
                self._bump_generation()
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def _insert_audit(self, event: AuditEvent | None) -> None:
        if event is None:
            return
        self._execute(
            "INSERT INTO audit_events(event_id, event_type, user_id, session_id, "
            "payload_json, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (
                event.event_id,
                event.event_type,
                event.user_id,
                event.session_id,
                dumps(event.payload),
                event.created_at,
            ),
        )

    def put_user(
        self,
        user: UserRecord,
        *,
        idempotency: IdempotencyKey | None = None,
        audit: AuditEvent | None = None,
    ) -> UserRecord:
        with self._lock:
            try:
                replay = self._claim_idempotency(idempotency)
                if replay is not None:
                    self._conn.commit()
                    return UserRecord.from_mapping(replay)
                self._execute(
                    "INSERT INTO users(user_id, display_label, avatar_placeholder, "
                    "created_at, updated_at, revoked_at) VALUES (?, ?, ?, ?, ?, ?) "
                    "ON CONFLICT (user_id) DO UPDATE SET "
                    "display_label=EXCLUDED.display_label, "
                    "avatar_placeholder=EXCLUDED.avatar_placeholder, "
                    "updated_at=EXCLUDED.updated_at, "
                    "revoked_at=CASE WHEN users.revoked_at IS NOT NULL "
                    "THEN users.revoked_at ELSE EXCLUDED.revoked_at END",
                    (
                        user.user_id,
                        user.display_label,
                        user.avatar_placeholder,
                        user.created_at,
                        user.updated_at,
                        user.revoked_at,
                    ),
                )
                row = self._fetchone_map(
                    "SELECT * FROM users WHERE user_id = ?", (user.user_id,)
                )
                if row is None:
                    raise PersistenceConflictError("user upsert did not persist a row")
                stored = row_user(row)
                self._insert_audit(audit)
                self._finish_idempotency(idempotency, stored.to_dict())
                self._bump_generation()
                self._conn.commit()
                return stored
            except Exception:
                self._conn.rollback()
                raise

    def get_user(self, user_id: str) -> UserRecord | None:
        with self._lock:
            row = self._fetchone_map("SELECT * FROM users WHERE user_id = ?", (user_id,))
            return row_user(row) if row else None

    def list_users(self) -> Sequence[UserRecord]:
        with self._lock:
            return tuple(
                row_user(r) for r in self._fetchall_map("SELECT * FROM users ORDER BY user_id")
            )

    def _claim_idempotency(self, key: IdempotencyKey | None) -> Mapping[str, Any] | None:
        if key is None:
            return None
        cur = self._execute(
            "INSERT INTO idempotency_keys("
            "request_id, operation, request_hash, response_json, created_at) "
            "VALUES (?, ?, ?, '', ?) ON CONFLICT (request_id) DO NOTHING",
            (key.request_id, key.operation, key.request_hash, _now()),
        )
        if cur.rowcount == 1:
            return None
        row = self._fetchone_map(
            "SELECT * FROM idempotency_keys WHERE request_id = ?", (key.request_id,)
        )
        if row is None:
            raise PersistenceConflictError("idempotency reservation disappeared")
        if row["operation"] != key.operation or row["request_hash"] != key.request_hash:
            raise PersistenceConflictError(
                f"request_id {key.request_id!r} was already used for a different request"
            )
        if not row["response_json"]:
            raise PersistenceConflictError(f"request_id {key.request_id!r} is still in progress")
        return loads(row["response_json"])

    def lookup_idempotency(self, key: IdempotencyKey) -> Mapping[str, Any] | None:
        with self._lock:
            row = self._fetchone_map(
                "SELECT * FROM idempotency_keys WHERE request_id = ?", (key.request_id,)
            )
            if row is None:
                return None
            if row["operation"] != key.operation or row["request_hash"] != key.request_hash:
                raise PersistenceConflictError(
                    f"request_id {key.request_id!r} was already used for a different request"
                )
            if not row["response_json"]:
                raise PersistenceConflictError(f"request_id {key.request_id!r} is still in progress")
            return loads(row["response_json"])

    def _finish_idempotency(
        self, key: IdempotencyKey | None, response: Mapping[str, Any]
    ) -> None:
        if key is not None:
            self._execute(
                "UPDATE idempotency_keys SET response_json = ? WHERE request_id = ?",
                (dumps(response), key.request_id),
            )

    def put_session(
        self,
        session: SessionRecord,
        *,
        expected_version: int | None = None,
        idempotency: IdempotencyKey | None = None,
        audit: AuditEvent | None = None,
    ) -> SessionRecord:
        with self._lock:
            try:
                replay = self._claim_idempotency(idempotency)
                if replay is not None:
                    self._conn.commit()
                    return SessionRecord.from_mapping(replay)

                row = self._fetchone_map(
                    "SELECT * FROM sessions WHERE session_id = ? FOR UPDATE",
                    (session.session_id,),
                )
                if row is None:
                    if expected_version not in (None, 0):
                        raise PersistenceConflictError(
                            f"{session.session_id} does not exist at expected version {expected_version}"
                        )
                    stored = replace(session, version=1)
                    self._execute(
                        "INSERT INTO sessions("
                        "session_id, user_id, thought_id, schema_version, thought_dna, "
                        "thought_dna_sha256, thought_dna_schema_version, share_enabled, "
                        "share_thought_dna, share_coarse_location, share_display_profile, "
                        "location_json, presentation_json, record_kind, builder_id, notes, "
                        "created_at, updated_at, revoked_at, deleted_at, version) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        session_params(stored),
                    )
                else:
                    existing = row_session(row)
                    if existing.user_id != session.user_id:
                        raise PersistenceOwnershipError(
                            f"{session.session_id} belongs to {existing.user_id!r}; "
                            f"cannot reassign it to {session.user_id!r}"
                        )
                    if expected_version is None:
                        raise PersistenceConflictError(
                            f"expected_version is required to update existing {session.session_id}"
                        )
                    if existing.version != expected_version:
                        raise PersistenceConflictError(
                            f"stale version for {session.session_id}: expected {expected_version}, "
                            f"current {existing.version}"
                        )
                    stored = replace(
                        session,
                        created_at=existing.created_at,
                        version=existing.version + 1,
                    )
                    p = session_params(stored)
                    cur = self._execute(
                        "UPDATE sessions SET user_id=?, thought_id=?, schema_version=?, "
                        "thought_dna=?, thought_dna_sha256=?, thought_dna_schema_version=?, "
                        "share_enabled=?, share_thought_dna=?, share_coarse_location=?, "
                        "share_display_profile=?, location_json=?, presentation_json=?, "
                        "record_kind=?, builder_id=?, notes=?, created_at=?, updated_at=?, "
                        "revoked_at=?, deleted_at=?, version=? "
                        "WHERE session_id=? AND version=?",
                        p[1:] + (stored.session_id, existing.version),
                    )
                    if cur.rowcount != 1:
                        raise PersistenceConflictError(
                            f"concurrent update detected for {session.session_id}"
                        )

                self._insert_audit(audit)
                self._finish_idempotency(idempotency, stored.to_dict())
                self._bump_generation()
                self._conn.commit()
                return stored
            except Exception:
                self._conn.rollback()
                raise

    def get_session(self, session_id: str) -> SessionRecord | None:
        with self._lock:
            row = self._fetchone_map("SELECT * FROM sessions WHERE session_id = ?", (session_id,))
            return row_session(row) if row else None

    def get_session_by_thought(self, thought_id: str) -> SessionRecord | None:
        with self._lock:
            row = self._fetchone_map("SELECT * FROM sessions WHERE thought_id = ?", (thought_id,))
            return row_session(row) if row else None

    def list_sessions(self, *, include_deleted: bool = False) -> Sequence[SessionRecord]:
        with self._lock:
            sql = (
                "SELECT * FROM sessions ORDER BY session_id"
                if include_deleted
                else "SELECT * FROM sessions WHERE deleted_at IS NULL ORDER BY session_id"
            )
            return tuple(row_session(r) for r in self._fetchall_map(sql))

    def list_discoverable_sessions(self) -> Sequence[SessionRecord]:
        with self._lock:
            rows = self._fetchall_map(
                "SELECT * FROM sessions WHERE share_enabled = 1 AND share_thought_dna = 1 "
                "AND revoked_at IS NULL AND deleted_at IS NULL ORDER BY thought_id"
            )
            return tuple(row_session(r) for r in rows)

    def append_audit(self, event: AuditEvent) -> AuditEvent:
        with self._lock:
            try:
                self._insert_audit(event)
                self._conn.commit()
                return event
            except Exception:
                self._conn.rollback()
                raise

    def list_audit(self) -> Sequence[AuditEvent]:
        with self._lock:
            return tuple(
                row_audit(r)
                for r in self._fetchall_map(
                    "SELECT * FROM audit_events ORDER BY created_at, event_id"
                )
            )

    def list_idempotency(self) -> Sequence[IdempotencyRecord]:
        with self._lock:
            return tuple(
                row_idempotency(r)
                for r in self._fetchall_map(
                    "SELECT * FROM idempotency_keys WHERE response_json <> '' "
                    "ORDER BY created_at, request_id"
                )
            )

    def export_payload(self) -> dict[str, Any]:
        return export_document(
            backend=self.backend_name,
            corpus_generation=self.get_corpus_generation(),
            users=list(self.list_users()),
            sessions=list(self.list_sessions(include_deleted=True)),
            audit=list(self.list_audit()),
            idempotency=list(self.list_idempotency()),
        )

    def import_payload(self, payload: Mapping[str, Any]) -> None:
        with self._lock:
            try:
                for table in (
                    "messages",
                    "channels",
                    "intros",
                    "idempotency_keys",
                    "audit_events",
                    "sessions",
                    "users",
                ):
                    self._execute(f"DELETE FROM {table}")
                for raw in payload.get("users", []):
                    user = UserRecord.from_mapping(raw)
                    self._execute(
                        "INSERT INTO users(user_id, display_label, avatar_placeholder, "
                        "created_at, updated_at, revoked_at) VALUES (?, ?, ?, ?, ?, ?)",
                        (
                            user.user_id,
                            user.display_label,
                            user.avatar_placeholder,
                            user.created_at,
                            user.updated_at,
                            user.revoked_at,
                        ),
                    )
                for raw in payload.get("sessions", []):
                    session = SessionRecord.from_mapping(raw)
                    self._execute(
                        "INSERT INTO sessions("
                        "session_id, user_id, thought_id, schema_version, thought_dna, "
                        "thought_dna_sha256, thought_dna_schema_version, share_enabled, "
                        "share_thought_dna, share_coarse_location, share_display_profile, "
                        "location_json, presentation_json, record_kind, builder_id, notes, "
                        "created_at, updated_at, revoked_at, deleted_at, version) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        session_params(session),
                    )
                for raw in payload.get("audit", []):
                    self._insert_audit(
                        AuditEvent(
                            event_id=raw["event_id"],
                            event_type=raw["event_type"],
                            user_id=raw.get("user_id"),
                            session_id=raw.get("session_id"),
                            payload=raw.get("payload") or {},
                            created_at=raw["created_at"],
                        )
                    )
                for raw in payload.get("idempotency", []):
                    self._execute(
                        "INSERT INTO idempotency_keys("
                        "request_id, operation, request_hash, response_json, created_at) "
                        "VALUES (?, ?, ?, ?, ?)",
                        (
                            raw["request_id"],
                            raw["operation"],
                            raw["request_hash"],
                            dumps(raw.get("response") or {}),
                            raw["created_at"],
                        ),
                    )
                self._bump_generation()
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise
