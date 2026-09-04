"""File-backed SQLite repository. Restart-safe; stdlib only.

All product-visible writes bump the durable corpus generation in the same
transaction. Session ownership/version checks and idempotency reservations are
also transactional, so retries cannot silently replay a second mutation.
"""

from __future__ import annotations

import sqlite3
import threading
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

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


class SQLiteRepository:
    backend_name = "sqlite"

    def __init__(self, path: str | Path = ":memory:") -> None:
        self.path = str(path)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(
            self.path,
            check_same_thread=False,
            isolation_level=None,
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.execute("PRAGMA journal_mode = WAL")
        try:
            self.migrate()
        except Exception:
            self._conn.close()
            raise

    def _execute_migration_sql(self, sql: str) -> None:
        statement = ""
        for line in sql.splitlines(keepends=True):
            statement += line
            if sqlite3.complete_statement(statement):
                self._conn.execute(statement)
                statement = ""
        if statement.strip():
            self._conn.execute(statement)

    def _record_migration(self, version: str) -> None:
        self._conn.execute(
            "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
            (version, _now()),
        )

    def migrate(self) -> tuple[str, ...]:
        with self._lock:
            applied: list[str] = []
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS schema_migrations ("
                "version TEXT PRIMARY KEY, applied_at TEXT NOT NULL)"
            )
            have = {
                row[0]
                for row in self._conn.execute("SELECT version FROM schema_migrations")
            }
            for version, sql in load_migration_sql():
                if version in have:
                    continue
                self._begin()
                try:
                    self._execute_migration_sql(sql)
                    self._record_migration(version)
                    self._conn.commit()
                except Exception:
                    self._conn.rollback()
                    raise
                applied.append(version)
            return tuple(applied)

    def _begin(self) -> None:
        self._conn.execute("BEGIN IMMEDIATE")

    def _bump_generation(self) -> int:
        now = _now()
        self._conn.execute(
            "UPDATE persistence_state SET corpus_generation = corpus_generation + 1, "
            "updated_at = ? WHERE state_id = 1",
            (now,),
        )
        row = self._conn.execute(
            "SELECT corpus_generation FROM persistence_state WHERE state_id = 1"
        ).fetchone()
        if row is None:
            raise RuntimeError("persistence_state row is missing")
        return int(row[0])

    def get_corpus_generation(self) -> int:
        with self._lock:
            row = self._conn.execute(
                "SELECT corpus_generation FROM persistence_state WHERE state_id = 1"
            ).fetchone()
            if row is None:
                raise RuntimeError("persistence_state row is missing")
            return int(row[0])

    def health(self) -> dict[str, Any]:
        with self._lock:
            versions = [
                r[0]
                for r in self._conn.execute(
                    "SELECT version FROM schema_migrations ORDER BY version"
                )
            ]
            users = self._conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            sessions = self._conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
            generation = self.get_corpus_generation()
            return {
                "ok": True,
                "backend": self.backend_name,
                "path": self.path,
                "schema_version": PERSISTENCE_SCHEMA_VERSION,
                "migrations": versions,
                "users": int(users),
                "sessions": int(sessions),
                "corpus_generation": generation,
            }

    def reset(self) -> None:
        with self._lock:
            self._begin()
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
                    self._conn.execute(f"DELETE FROM {table}")
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
        self._conn.execute(
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
            self._begin()
            try:
                replay = self._claim_idempotency(idempotency)
                if replay is not None:
                    self._conn.commit()
                    return UserRecord.from_mapping(replay)
                self._conn.execute(
                    "INSERT INTO users(user_id, display_label, avatar_placeholder, "
                    "created_at, updated_at, revoked_at) VALUES (?, ?, ?, ?, ?, ?) "
                    "ON CONFLICT(user_id) DO UPDATE SET "
                    "display_label=excluded.display_label, "
                    "avatar_placeholder=excluded.avatar_placeholder, "
                    "updated_at=excluded.updated_at, "
                    "revoked_at=CASE WHEN users.revoked_at IS NOT NULL "
                    "THEN users.revoked_at ELSE excluded.revoked_at END",
                    (
                        user.user_id,
                        user.display_label,
                        user.avatar_placeholder,
                        user.created_at,
                        user.updated_at,
                        user.revoked_at,
                    ),
                )
                row = self._conn.execute(
                    "SELECT * FROM users WHERE user_id = ?", (user.user_id,)
                ).fetchone()
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
            row = self._conn.execute(
                "SELECT * FROM users WHERE user_id = ?", (user_id,)
            ).fetchone()
            return row_user(row) if row else None

    def list_users(self) -> Sequence[UserRecord]:
        with self._lock:
            rows = self._conn.execute("SELECT * FROM users ORDER BY user_id").fetchall()
            return tuple(row_user(r) for r in rows)

    def _claim_idempotency(self, key: IdempotencyKey | None) -> Mapping[str, Any] | None:
        if key is None:
            return None
        cur = self._conn.execute(
            "INSERT OR IGNORE INTO idempotency_keys("
            "request_id, operation, request_hash, response_json, created_at) "
            "VALUES (?, ?, ?, '', ?)",
            (key.request_id, key.operation, key.request_hash, _now()),
        )
        if cur.rowcount == 1:
            return None
        row = self._conn.execute(
            "SELECT * FROM idempotency_keys WHERE request_id = ?", (key.request_id,)
        ).fetchone()
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
            self._conn.execute(
                "INSERT INTO oauth_grants(kind, grant_key, user_id, record_json, expires_at, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(kind, grant_key) DO UPDATE SET user_id = excluded.user_id, "
                "record_json = excluded.record_json, expires_at = excluded.expires_at",
                (kind, key, user_id, dumps(dict(record)), expires_at, _now()),
            )

    def get_grant(self, kind: str, key: str) -> Mapping[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT record_json FROM oauth_grants WHERE kind = ? AND grant_key = ?", (kind, key)
            ).fetchone()
            return loads(row["record_json"]) if row is not None else None

    def pop_grant(self, kind: str, key: str) -> Mapping[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT record_json FROM oauth_grants WHERE kind = ? AND grant_key = ?", (kind, key)
            ).fetchone()
            if row is None:
                return None
            self._conn.execute(
                "DELETE FROM oauth_grants WHERE kind = ? AND grant_key = ?", (kind, key)
            )
            return loads(row["record_json"])

    def delete_grants_for_user(self, kind: str, user_id: str) -> int:
        with self._lock:
            cur = self._conn.execute(
                "DELETE FROM oauth_grants WHERE kind = ? AND user_id = ?", (kind, user_id)
            )
            return int(cur.rowcount or 0)

    def lookup_idempotency(self, key: IdempotencyKey) -> Mapping[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM idempotency_keys WHERE request_id = ?", (key.request_id,)
            ).fetchone()
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
        if key is None:
            return
        self._conn.execute(
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
            self._begin()
            try:
                replay = self._claim_idempotency(idempotency)
                if replay is not None:
                    self._conn.commit()
                    return SessionRecord.from_mapping(replay)

                row = self._conn.execute(
                    "SELECT * FROM sessions WHERE session_id = ?", (session.session_id,)
                ).fetchone()
                if row is None:
                    if expected_version not in (None, 0):
                        raise PersistenceConflictError(
                            f"{session.session_id} does not exist at expected version {expected_version}"
                        )
                    stored = replace(session, version=1)
                    self._conn.execute(
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
                    cur = self._conn.execute(
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
            row = self._conn.execute(
                "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
            ).fetchone()
            return row_session(row) if row else None

    def get_session_by_thought(self, thought_id: str) -> SessionRecord | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM sessions WHERE thought_id = ?", (thought_id,)
            ).fetchone()
            return row_session(row) if row else None

    def list_sessions(self, *, include_deleted: bool = False) -> Sequence[SessionRecord]:
        with self._lock:
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
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM sessions WHERE share_enabled = 1 AND share_thought_dna = 1 "
                "AND revoked_at IS NULL AND deleted_at IS NULL ORDER BY thought_id"
            ).fetchall()
            return tuple(row_session(r) for r in rows)

    def append_audit(self, event: AuditEvent) -> AuditEvent:
        with self._lock:
            self._begin()
            try:
                self._insert_audit(event)
                self._conn.commit()
                return event
            except Exception:
                self._conn.rollback()
                raise

    def list_audit(self) -> Sequence[AuditEvent]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM audit_events ORDER BY created_at, event_id"
            ).fetchall()
            return tuple(row_audit(r) for r in rows)

    def list_idempotency(self) -> Sequence[IdempotencyRecord]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM idempotency_keys WHERE response_json <> '' "
                "ORDER BY created_at, request_id"
            ).fetchall()
            return tuple(row_idempotency(r) for r in rows)

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
        """Privileged restore path. Atomically replaces product data.

        Normal product mutations must use put_user/put_session; this method is
        deliberately repository-admin-only and preserves stored session versions.
        """
        with self._lock:
            self._begin()
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
                    self._conn.execute(f"DELETE FROM {table}")
                for raw in payload.get("users", []):
                    user = UserRecord.from_mapping(raw)
                    self._conn.execute(
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
                    self._conn.execute(
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
                    self._conn.execute(
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
    # Connection state is not discoverable corpus content: none of these
    # methods bump the corpus generation, so chat can never force a rebuild.
    def create_intro(self, intro, *, idempotency=None, audit=None):
        from .models import IntroRecord
        with self._lock:
            self._begin()
            try:
                replay = self._claim_idempotency(idempotency)
                if replay is not None:
                    self._conn.commit()
                    return IntroRecord.from_mapping(replay)
                try:
                    self._conn.execute(
                        "INSERT INTO intros(intro_id, from_session_id, to_session_id, "
                        "state, created_at, accepted_at, declined_at, message, "
                        "from_user_id, to_user_id, cancelled_at, updated_at) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (intro.intro_id, intro.from_session_id, intro.to_session_id,
                         intro.state, intro.created_at, intro.accepted_at,
                         intro.declined_at, intro.message, intro.from_user_id,
                         intro.to_user_id, intro.cancelled_at, intro.updated_at),
                    )
                except sqlite3.IntegrityError as exc:
                    raise PersistenceConflictError(
                        "intro identifier conflicts with durable state") from exc
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
            row = self._conn.execute(
                "SELECT * FROM intros WHERE intro_id = ?", (intro_id,)).fetchone()
            return row_intro(row) if row else None

    def transition_intro(self, intro_id, *, from_state, to_state,
                         timestamp_field, now, idempotency=None, audit=None):
        """State-machine transition enforced at the durable row level."""
        from .models import IntroRecord
        from .sql import row_intro
        if timestamp_field not in {"accepted_at", "declined_at", "cancelled_at"}:
            raise PersistenceConflictError("unknown intro timestamp field")
        with self._lock:
            self._begin()
            try:
                replay = self._claim_idempotency(idempotency)
                if replay is not None:
                    self._conn.commit()
                    return IntroRecord.from_mapping(replay)
                cur = self._conn.execute(
                    f"UPDATE intros SET state = ?, updated_at = ?, "
                    f"{timestamp_field} = ? WHERE intro_id = ? AND state = ?",
                    (to_state, now, now, intro_id, from_state),
                )
                if cur.rowcount != 1:
                    raise PersistenceConflictError(
                        f"intro {intro_id!r} is not in state {from_state!r}")
                row = self._conn.execute(
                    "SELECT * FROM intros WHERE intro_id = ?", (intro_id,)).fetchone()
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
        """Atomic accept: transition requested->accepted AND create the single
        channel in ONE transaction. The unique channels.intro_id index makes a
        replay/concurrent accept converge on the existing channel rather than
        minting a second one."""
        from .models import IntroRecord
        from .sql import row_intro, row_channel
        with self._lock:
            self._begin()
            try:
                replay = self._claim_idempotency(idempotency)
                if replay is not None:
                    self._conn.commit()
                    return IntroRecord.from_mapping(replay), self._channel_for(intro_id)
                cur = self._conn.execute(
                    "UPDATE intros SET state = 'accepted', updated_at = ?, "
                    "accepted_at = ? WHERE intro_id = ? AND state = 'requested'",
                    (now, now, intro_id))
                if cur.rowcount != 1:
                    raise PersistenceConflictError(
                        f"intro {intro_id!r} is not in state 'requested'")
                # INSERT OR IGNORE + unique(intro_id): idempotent channel row.
                self._conn.execute(
                    "INSERT OR IGNORE INTO channels(channel_id, intro_id, "
                    "created_at, closed_at) VALUES (?, ?, ?, NULL)",
                    (channel_id, intro_id, now))
                row = self._conn.execute(
                    "SELECT * FROM intros WHERE intro_id = ?", (intro_id,)).fetchone()
                stored = row_intro(row)
                chan_row = self._conn.execute(
                    "SELECT * FROM channels WHERE intro_id = ?", (intro_id,)).fetchone()
                channel = row_channel(chan_row)
                self._insert_audit(audit)
                self._finish_idempotency(idempotency, stored.to_dict())
                self._conn.commit()
                return stored, channel
            except Exception:
                self._conn.rollback()
                raise

    def _channel_for(self, intro_id):
        from .sql import row_channel
        row = self._conn.execute(
            "SELECT * FROM channels WHERE intro_id = ?", (intro_id,)).fetchone()
        return row_channel(row) if row else None

    def list_intros_for_user(self, user_id):
        from .sql import row_intro
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM intros WHERE from_user_id = ? OR to_user_id = ? "
                "ORDER BY created_at, intro_id", (user_id, user_id)).fetchall()
            return tuple(row_intro(r) for r in rows)

    def latest_intro_between(self, user_a, user_b):
        from .sql import row_intro
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM intros WHERE (from_user_id = ? AND to_user_id = ?) "
                "OR (from_user_id = ? AND to_user_id = ?) "
                "ORDER BY created_at DESC, intro_id DESC LIMIT 1",
                (user_a, user_b, user_b, user_a)).fetchone()
            return row_intro(row) if row else None

    def accepted_user_pairs(self):
        with self._lock:
            rows = self._conn.execute(
                "SELECT from_user_id, to_user_id FROM intros "
                "WHERE state = 'accepted'").fetchall()
            return {frozenset((r[0], r[1])) for r in rows}

    def create_channel(self, channel, *, audit=None):
        with self._lock:
            self._begin()
            try:
                try:
                    self._conn.execute(
                        "INSERT INTO channels(channel_id, intro_id, created_at, "
                        "closed_at) VALUES (?, ?, ?, ?)",
                        (channel.channel_id, channel.intro_id,
                         channel.created_at, channel.closed_at),
                    )
                except sqlite3.IntegrityError as exc:
                    raise PersistenceConflictError(
                        "channel identifier conflicts with durable state") from exc
                self._insert_audit(audit)
                self._conn.commit()
                return channel
            except Exception:
                self._conn.rollback()
                raise

    def get_channel_by_intro(self, intro_id):
        from .sql import row_channel
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM channels WHERE intro_id = ? "
                "ORDER BY created_at, channel_id LIMIT 1", (intro_id,)).fetchone()
            return row_channel(row) if row else None

    def get_channel(self, channel_id):
        from .sql import row_channel
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM channels WHERE channel_id = ?", (channel_id,)).fetchone()
            return row_channel(row) if row else None

    def add_message(self, message, *, idempotency=None, audit=None):
        from .models import MessageRecord
        with self._lock:
            self._begin()
            try:
                replay = self._claim_idempotency(idempotency)
                if replay is not None:
                    self._conn.commit()
                    return MessageRecord(**replay)
                try:
                    self._conn.execute(
                        "INSERT INTO messages(message_id, channel_id, author_user_id, "
                        "body, created_at) VALUES (?, ?, ?, ?, ?)",
                        (message.message_id, message.channel_id,
                         message.author_user_id, message.body, message.created_at),
                    )
                except sqlite3.IntegrityError as exc:
                    raise PersistenceConflictError(
                        "message identifier conflicts with durable state") from exc
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
            rows = self._conn.execute(
                "SELECT * FROM messages WHERE channel_id = ? "
                "ORDER BY created_at, message_id", (channel_id,)).fetchall()
            return tuple(row_message(r) for r in rows)

    # -- workspaces (R14B) ----------------------------------------------
    # No workspace write bumps the corpus generation.
    def create_workspace(self, workspace, members, *, audit=None):
        with self._lock:
            self._begin()
            try:
                self._conn.execute(
                    "INSERT INTO workspaces(workspace_id, title, brief, "
                    "owner_user_id, origin_intro_id, created_at, updated_at, "
                    "version) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (workspace.workspace_id, workspace.title, workspace.brief,
                     workspace.owner_user_id, workspace.origin_intro_id,
                     workspace.created_at, workspace.updated_at, workspace.version))
                for m in members:
                    self._conn.execute(
                        "INSERT INTO workspace_members(workspace_id, user_id, "
                        "role, state, invited_by, invited_at, joined_at) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (m.workspace_id, m.user_id, m.role, m.state,
                         m.invited_by, m.invited_at, m.joined_at))
                self._insert_audit(audit)
                self._conn.commit()
                return workspace
            except sqlite3.IntegrityError as exc:
                self._conn.rollback()
                raise PersistenceConflictError(
                    "workspace or member conflicts with durable state") from exc
            except Exception:
                self._conn.rollback()
                raise

    def get_workspace(self, workspace_id):
        from .models import WorkspaceRecord
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM workspaces WHERE workspace_id = ?", (workspace_id,)).fetchone()
            if row is None:
                return None
            return WorkspaceRecord(row["workspace_id"], row["title"], row["brief"],
                                   row["owner_user_id"], row["origin_intro_id"],
                                   row["created_at"], row["updated_at"], int(row["version"]))

    def get_member(self, workspace_id, user_id):
        from .models import MemberRecord
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM workspace_members WHERE workspace_id = ? AND user_id = ?",
                (workspace_id, user_id)).fetchone()
            if row is None:
                return None
            return MemberRecord(row["workspace_id"], row["user_id"], row["role"],
                                row["state"], row["invited_by"], row["invited_at"],
                                row["joined_at"])

    def list_members(self, workspace_id):
        from .models import MemberRecord
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM workspace_members WHERE workspace_id = ? ORDER BY invited_at, user_id",
                (workspace_id,)).fetchall()
            return tuple(MemberRecord(r["workspace_id"], r["user_id"], r["role"],
                                      r["state"], r["invited_by"], r["invited_at"],
                                      r["joined_at"]) for r in rows)

    def list_workspaces_for_user(self, user_id):
        from .models import WorkspaceRecord
        with self._lock:
            rows = self._conn.execute(
                "SELECT w.* FROM workspaces w JOIN workspace_members m "
                "ON w.workspace_id = m.workspace_id WHERE m.user_id = ? "
                "AND m.state IN ('invited','active') ORDER BY w.created_at",
                (user_id,)).fetchall()
            return tuple(WorkspaceRecord(r["workspace_id"], r["title"], r["brief"],
                                         r["owner_user_id"], r["origin_intro_id"],
                                         r["created_at"], r["updated_at"], int(r["version"]))
                         for r in rows)

    def upsert_member(self, member, *, audit=None):
        with self._lock:
            self._begin()
            try:
                self._conn.execute(
                    "INSERT INTO workspace_members(workspace_id, user_id, role, "
                    "state, invited_by, invited_at, joined_at) VALUES (?, ?, ?, ?, ?, ?, ?) "
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

    def add_workspace_row(self, table, columns, values, *, audit=None):
        """Generic single-row insert for notes/tasks/artifacts/links/activity."""
        with self._lock:
            self._begin()
            try:
                placeholders = ", ".join("?" for _ in columns)
                self._conn.execute(
                    f"INSERT INTO {table}({', '.join(columns)}) VALUES ({placeholders})",
                    values)
                self._insert_audit(audit)
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise

    def update_task_state(self, task_id, state, now):
        with self._lock:
            self._begin()
            try:
                cur = self._conn.execute(
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
            rows = self._conn.execute(
                f"SELECT * FROM {table} WHERE workspace_id = ? ORDER BY {order}",
                (workspace_id,)).fetchall()
            return [dict(r) for r in rows]

    def bump_workspace(self, workspace_id, *, expected_version, brief=None, now=None):
        with self._lock:
            self._begin()
            try:
                if brief is not None:
                    cur = self._conn.execute(
                        "UPDATE workspaces SET brief = ?, updated_at = ?, version = version + 1 "
                        "WHERE workspace_id = ? AND version = ?",
                        (brief, now, workspace_id, expected_version))
                else:
                    cur = self._conn.execute(
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
