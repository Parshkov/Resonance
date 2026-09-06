"""PostgreSQL repository for the hosted pilot.

The optional driver keeps the deterministic engine/test path dependency-light.
Transaction semantics: public-state writes, generation bumps,
optimistic versions, audit evidence, and idempotency completion commit together.
"""

from __future__ import annotations

import re
import threading
from dataclasses import replace
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence
from urllib.parse import urlparse

from .errors import PersistenceConflictError, PersistenceOwnershipError
# Latent since this path had no test: `put_session` called this and it was
# never imported, so a duplicate thought_id raised NameError -- a 500 --
# instead of the PersistenceConflictError the caller handles.
from .projection import postgres_unique_violation
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


_SAFE_SCHEMA = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,54}")


class PostgresRepository:
    backend_name = "postgres"

    def __init__(self, dsn: str, *, schema: str | None = None) -> None:
        """`schema` puts this repository in its own PostgreSQL schema on the
        same server. That is what replaced the old ephemeral SQLite database:
        the tests need a clean, isolated store per case, and the only honest
        way to give them one is the engine production actually runs. Migrations
        name their tables unqualified, so a `search_path` of one schema is
        complete isolation -- and reopening the same schema name is a restart,
        which is how the recovery tests keep working."""
        if not postgres_available():
            raise RuntimeError(
                "PostgreSQL driver not installed. Install psycopg or psycopg2 "
                "for the hosted-pilot backend."
            )
        parsed = urlparse(dsn)
        if parsed.scheme not in {"postgres", "postgresql"}:
            raise ValueError("PostgreSQL DSN must start with postgres:// or postgresql://")
        if schema is not None and not _SAFE_SCHEMA.fullmatch(schema):
            # Interpolated into DDL, so it may never come from anywhere but a
            # caller-chosen identifier.
            raise ValueError(f"unsafe schema name: {schema!r}")
        self.dsn = dsn
        self.schema = schema
        self._lock = threading.RLock()
        self._conn = _connect(dsn)
        if schema is not None:
            cur = self._conn.cursor()
            cur.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema}"')
            cur.execute(f'SET search_path TO "{schema}"')
            self._conn.commit()
        self.migrate()

    def drop_schema(self) -> None:
        """Throw away an isolated schema and everything in it. Only ever called
        on a schema this repository created; refuses to touch `public`."""
        if not self.schema:
            raise RuntimeError("refusing to drop the default schema")
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(f'DROP SCHEMA IF EXISTS "{self.schema}" CASCADE')
            self._conn.commit()

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
                    "oauth_grants",
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

    # ------------------------------------------------------------------
    # OAuth grants (opaque records; never corpus content)
    # ------------------------------------------------------------------
    def put_grant(self, kind: str, key: str, record: Mapping[str, Any], *,
                  user_id: str | None = None, expires_at: float | None = None) -> None:
        with self._lock:
            try:
                self._execute(
                    "INSERT INTO oauth_grants(kind, grant_key, user_id, record_json, expires_at, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?) "
                    "ON CONFLICT(kind, grant_key) DO UPDATE SET user_id = EXCLUDED.user_id, "
                    "record_json = EXCLUDED.record_json, expires_at = EXCLUDED.expires_at",
                    (kind, key, user_id, dumps(dict(record)), expires_at, _now()),
                )
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise

    def get_grant(self, kind: str, key: str) -> Mapping[str, Any] | None:
        with self._lock:
            row = self._fetchone_map(
                "SELECT record_json FROM oauth_grants WHERE kind = ? AND grant_key = ?", (kind, key)
            )
            self._conn.commit()
            return loads(row["record_json"]) if row is not None else None

    def pop_grant(self, kind: str, key: str) -> Mapping[str, Any] | None:
        with self._lock:
            try:
                row = self._fetchone_map(
                    "SELECT record_json FROM oauth_grants WHERE kind = ? AND grant_key = ? FOR UPDATE",
                    (kind, key),
                )
                if row is None:
                    self._conn.commit()
                    return None
                self._execute("DELETE FROM oauth_grants WHERE kind = ? AND grant_key = ?", (kind, key))
                self._conn.commit()
                return loads(row["record_json"])
            except Exception:
                self._conn.rollback()
                raise

    def list_grants_for_user(self, kind: str, user_id: str) -> Sequence[Mapping[str, Any]]:
        """Every record of one kind belonging to one account, oldest first."""
        with self._lock:
            rows = self._fetchall_map(
                "SELECT record_json FROM oauth_grants WHERE kind = ? AND user_id = ? "
                "ORDER BY created_at, grant_key",
                (kind, user_id),
            )
            self._conn.commit()
            return [loads(row["record_json"]) for row in rows]

    def delete_grants_for_user(self, kind: str, user_id: str) -> int:
        with self._lock:
            try:
                cur = self._execute(
                    "DELETE FROM oauth_grants WHERE kind = ? AND user_id = ?", (kind, user_id)
                )
                count = int(cur.rowcount or 0)
                self._conn.commit()
                return count
            except Exception:
                self._conn.rollback()
                raise

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
        try:
            return self._put_session(session, expected_version=expected_version,
                                     idempotency=idempotency, audit=audit)
        except Exception as exc:
            if postgres_unique_violation(exc):
                raise PersistenceConflictError(
                    "session identifier or thought_id conflicts with durable state") from exc
            raise

    def _put_session(
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

    # -- collaboration (R14) --------------------------------------------
    @staticmethod
    def _is_unique_violation(exc: BaseException) -> bool:
        code = getattr(exc, "sqlstate", None) or getattr(exc, "pgcode", None)
        return code == "23505" or (
            "duplicate key value violates unique constraint" in str(exc).lower())

    def create_intro(self, intro, *, idempotency=None, audit=None):
        from .models import IntroRecord
        with self._lock:
            try:
                replay = self._claim_idempotency(idempotency)
                if replay is not None:
                    self._conn.commit()
                    return IntroRecord.from_mapping(replay)
                try:
                    self._execute(
                        "INSERT INTO intros(intro_id, from_session_id, to_session_id, "
                        "state, created_at, accepted_at, declined_at, message, "
                        "from_user_id, to_user_id, cancelled_at, updated_at) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (intro.intro_id, intro.from_session_id, intro.to_session_id,
                         intro.state, intro.created_at, intro.accepted_at,
                         intro.declined_at, intro.message, intro.from_user_id,
                         intro.to_user_id, intro.cancelled_at, intro.updated_at))
                except Exception as exc:
                    if self._is_unique_violation(exc):
                        raise PersistenceConflictError(
                            "intro identifier conflicts with durable state") from exc
                    raise
                self._insert_audit(audit)
                self._finish_idempotency(idempotency, intro.to_dict())
                self._conn.commit()
                return intro
            except Exception:
                self._conn.rollback()
                raise

    def get_intro(self, intro_id):
        from .sql import row_intro
        with self._lock:
            row = self._fetchone_map("SELECT * FROM intros WHERE intro_id = ?",
                                     (intro_id,))
            return row_intro(row) if row else None

    def transition_intro(self, intro_id, *, from_state, to_state,
                         timestamp_field, now, idempotency=None, audit=None):
        from .models import IntroRecord
        from .sql import row_intro
        if timestamp_field not in {"accepted_at", "declined_at", "cancelled_at"}:
            raise PersistenceConflictError("unknown intro timestamp field")
        with self._lock:
            try:
                replay = self._claim_idempotency(idempotency)
                if replay is not None:
                    self._conn.commit()
                    return IntroRecord.from_mapping(replay)
                cur = self._execute(
                    f"UPDATE intros SET state = ?, updated_at = ?, "
                    f"{timestamp_field} = ? WHERE intro_id = ? AND state = ?",
                    (to_state, now, now, intro_id, from_state))
                if cur.rowcount != 1:
                    raise PersistenceConflictError(
                        f"intro {intro_id!r} is not in state {from_state!r}")
                row = self._fetchone_map(
                    "SELECT * FROM intros WHERE intro_id = ?", (intro_id,))
                stored = row_intro(row)
                self._insert_audit(audit)
                self._finish_idempotency(idempotency, stored.to_dict())
                self._conn.commit()
                return stored
            except Exception:
                self._conn.rollback()
                raise

    def accept_intro(self, intro_id, *, channel_id, now,
                     idempotency=None, audit=None):
        from .models import IntroRecord
        from .sql import row_intro, row_channel
        with self._lock:
            try:
                replay = self._claim_idempotency(idempotency)
                if replay is not None:
                    self._conn.commit()
                    chan = self._fetchone_map(
                        "SELECT * FROM channels WHERE intro_id = ?", (intro_id,))
                    return (IntroRecord.from_mapping(replay),
                            row_channel(chan) if chan else None)
                cur = self._execute(
                    "UPDATE intros SET state = 'accepted', updated_at = ?, "
                    "accepted_at = ? WHERE intro_id = ? AND state = 'requested'",
                    (now, now, intro_id))
                if cur.rowcount != 1:
                    raise PersistenceConflictError(
                        f"intro {intro_id!r} is not in state 'requested'")
                self._execute(
                    "INSERT INTO channels(channel_id, intro_id, created_at, "
                    "closed_at) VALUES (?, ?, ?, NULL) "
                    "ON CONFLICT (intro_id) DO NOTHING",
                    (channel_id, intro_id, now))
                row = self._fetchone_map(
                    "SELECT * FROM intros WHERE intro_id = ?", (intro_id,))
                stored = row_intro(row)
                chan = self._fetchone_map(
                    "SELECT * FROM channels WHERE intro_id = ?", (intro_id,))
                channel = row_channel(chan)
                self._insert_audit(audit)
                self._finish_idempotency(idempotency, stored.to_dict())
                self._conn.commit()
                return stored, channel
            except Exception:
                self._conn.rollback()
                raise

    def list_intros_for_user(self, user_id):
        from .sql import row_intro
        with self._lock:
            rows = self._fetchall_map(
                "SELECT * FROM intros WHERE from_user_id = ? OR to_user_id = ? "
                "ORDER BY created_at, intro_id", (user_id, user_id))
            return tuple(row_intro(r) for r in rows)

    def latest_intro_between(self, user_a, user_b):
        from .sql import row_intro
        with self._lock:
            row = self._fetchone_map(
                "SELECT * FROM intros WHERE (from_user_id = ? AND to_user_id = ?) "
                "OR (from_user_id = ? AND to_user_id = ?) "
                "ORDER BY created_at DESC, intro_id DESC LIMIT 1",
                (user_a, user_b, user_b, user_a))
            return row_intro(row) if row else None

    def accepted_user_pairs(self):
        with self._lock:
            rows = self._fetchall_map(
                "SELECT from_user_id, to_user_id FROM intros WHERE state = 'accepted'")
            return {frozenset((r["from_user_id"], r["to_user_id"])) for r in rows}

    def create_channel(self, channel, *, audit=None):
        with self._lock:
            try:
                try:
                    self._execute(
                        "INSERT INTO channels(channel_id, intro_id, created_at, "
                        "closed_at) VALUES (?, ?, ?, ?)",
                        (channel.channel_id, channel.intro_id,
                         channel.created_at, channel.closed_at))
                except Exception as exc:
                    if self._is_unique_violation(exc):
                        raise PersistenceConflictError(
                            "channel identifier conflicts with durable state") from exc
                    raise
                self._insert_audit(audit)
                self._conn.commit()
                return channel
            except Exception:
                self._conn.rollback()
                raise

    def get_channel_by_intro(self, intro_id):
        from .sql import row_channel
        with self._lock:
            row = self._fetchone_map(
                "SELECT * FROM channels WHERE intro_id = ? "
                "ORDER BY created_at, channel_id LIMIT 1", (intro_id,))
            return row_channel(row) if row else None

    def get_channel(self, channel_id):
        from .sql import row_channel
        with self._lock:
            row = self._fetchone_map(
                "SELECT * FROM channels WHERE channel_id = ?", (channel_id,))
            return row_channel(row) if row else None

    def add_message(self, message, *, idempotency=None, audit=None):
        from .models import MessageRecord
        with self._lock:
            try:
                replay = self._claim_idempotency(idempotency)
                if replay is not None:
                    self._conn.commit()
                    return MessageRecord(**replay)
                try:
                    self._execute(
                        "INSERT INTO messages(message_id, channel_id, author_user_id, "
                        "body, created_at) VALUES (?, ?, ?, ?, ?)",
                        (message.message_id, message.channel_id,
                         message.author_user_id, message.body, message.created_at))
                except Exception as exc:
                    if self._is_unique_violation(exc):
                        raise PersistenceConflictError(
                            "message identifier conflicts with durable state") from exc
                    raise
                self._insert_audit(audit)
                self._finish_idempotency(idempotency, message.to_dict())
                self._conn.commit()
                return message
            except Exception:
                self._conn.rollback()
                raise

    def list_messages(self, channel_id):
        from .sql import row_message
        with self._lock:
            rows = self._fetchall_map(
                "SELECT * FROM messages WHERE channel_id = ? "
                "ORDER BY created_at, message_id", (channel_id,))
            return tuple(row_message(r) for r in rows)

    # -- workspaces (R14B) ----------------------------------------------
    def create_workspace(self, workspace, members, *, audit=None):
        with self._lock:
            try:
                self._execute(
                    "INSERT INTO workspaces(workspace_id, title, brief, "
                    "owner_user_id, origin_intro_id, created_at, updated_at, version) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (workspace.workspace_id, workspace.title, workspace.brief,
                     workspace.owner_user_id, workspace.origin_intro_id,
                     workspace.created_at, workspace.updated_at, workspace.version))
                for m in members:
                    self._execute(
                        "INSERT INTO workspace_members(workspace_id, user_id, role, "
                        "state, invited_by, invited_at, joined_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (m.workspace_id, m.user_id, m.role, m.state, m.invited_by,
                         m.invited_at, m.joined_at))
                self._insert_audit(audit)
                self._conn.commit()
                return workspace
            except Exception as exc:
                self._conn.rollback()
                if self._is_unique_violation(exc):
                    raise PersistenceConflictError(
                        "workspace or member conflicts with durable state") from exc
                raise

    def get_workspace(self, workspace_id):
        from .models import WorkspaceRecord
        with self._lock:
            row = self._fetchone_map("SELECT * FROM workspaces WHERE workspace_id = ?", (workspace_id,))
            if row is None:
                return None
            return WorkspaceRecord(row["workspace_id"], row["title"], row["brief"],
                                   row["owner_user_id"], row["origin_intro_id"],
                                   row["created_at"], row["updated_at"], int(row["version"]))

    def get_member(self, workspace_id, user_id):
        from .models import MemberRecord
        with self._lock:
            row = self._fetchone_map(
                "SELECT * FROM workspace_members WHERE workspace_id = ? AND user_id = ?",
                (workspace_id, user_id))
            if row is None:
                return None
            return MemberRecord(row["workspace_id"], row["user_id"], row["role"],
                                row["state"], row["invited_by"], row["invited_at"], row["joined_at"])

    def list_members(self, workspace_id):
        from .models import MemberRecord
        with self._lock:
            rows = self._fetchall_map(
                "SELECT * FROM workspace_members WHERE workspace_id = ? ORDER BY invited_at, user_id",
                (workspace_id,))
            return tuple(MemberRecord(r["workspace_id"], r["user_id"], r["role"],
                                      r["state"], r["invited_by"], r["invited_at"], r["joined_at"])
                         for r in rows)

    def list_workspaces_for_user(self, user_id):
        from .models import WorkspaceRecord
        with self._lock:
            rows = self._fetchall_map(
                "SELECT w.* FROM workspaces w JOIN workspace_members m "
                "ON w.workspace_id = m.workspace_id WHERE m.user_id = ? "
                "AND m.state IN ('invited','active') ORDER BY w.created_at", (user_id,))
            return tuple(WorkspaceRecord(r["workspace_id"], r["title"], r["brief"],
                                         r["owner_user_id"], r["origin_intro_id"],
                                         r["created_at"], r["updated_at"], int(r["version"]))
                         for r in rows)

    def upsert_member(self, member, *, audit=None):
        with self._lock:
            try:
                self._execute(
                    "INSERT INTO workspace_members(workspace_id, user_id, role, state, "
                    "invited_by, invited_at, joined_at) VALUES (?, ?, ?, ?, ?, ?, ?) "
                    "ON CONFLICT(workspace_id, user_id) DO UPDATE SET "
                    "role=excluded.role, state=excluded.state, joined_at=excluded.joined_at",
                    (member.workspace_id, member.user_id, member.role, member.state,
                     member.invited_by, member.invited_at, member.joined_at))
                self._insert_audit(audit)
                self._conn.commit()
                return member
            except Exception:
                self._conn.rollback()
                raise

    # The generic helpers below interpolate the table name into SQL. Every
    # caller passes a literal, but "every caller today" is not a guarantee, so
    # the set of tables they may touch is stated once here.
    WORKSPACE_ROW_TABLES = frozenset({
        "workspace_notes", "workspace_tasks", "workspace_artifacts",
        "workspace_links", "workspace_activity", "workspace_contributions",
    })

    def _workspace_table(self, table: str) -> str:
        if table not in self.WORKSPACE_ROW_TABLES:
            raise ValueError(f"unknown workspace table {table!r}")
        return table

    def add_workspace_row(self, table, columns, values, *, audit=None):
        with self._lock:
            try:
                table = self._workspace_table(table)
                placeholders = ", ".join("?" for _ in columns)
                self._execute(f"INSERT INTO {table}({', '.join(columns)}) VALUES ({placeholders})", values)
                self._insert_audit(audit)
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise

    def update_task_state(self, task_id, state, now):
        with self._lock:
            try:
                cur = self._execute(
                    "UPDATE workspace_tasks SET state = ?, updated_at = ? WHERE task_id = ?",
                    (state, now, task_id))
                if cur.rowcount != 1:
                    raise PersistenceConflictError(f"task {task_id!r} not found")
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise

    def list_workspace_rows(self, table, workspace_id, order="created_at"):
        with self._lock:
            return self._fetchall_map(
                f"SELECT * FROM {self._workspace_table(table)} WHERE workspace_id = ? ORDER BY {order}", (workspace_id,))

    def bump_workspace(self, workspace_id, *, expected_version, brief=None, now=None):
        with self._lock:
            try:
                if brief is not None:
                    cur = self._execute(
                        "UPDATE workspaces SET brief = ?, updated_at = ?, version = version + 1 "
                        "WHERE workspace_id = ? AND version = ?",
                        (brief, now, workspace_id, expected_version))
                else:
                    cur = self._execute(
                        "UPDATE workspaces SET updated_at = ?, version = version + 1 "
                        "WHERE workspace_id = ? AND version = ?",
                        (now, workspace_id, expected_version))
                if cur.rowcount != 1:
                    raise PersistenceConflictError(
                        f"workspace {workspace_id!r} stale or missing at version {expected_version}")
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise
