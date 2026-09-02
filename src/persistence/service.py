"""Transport-neutral live corpus service.

Recovery of the useful PR #95 foundation with stricter invariants:

* durable DB is authoritative;
* every public-state mutation advances a durable corpus generation;
* discovery serves only when its in-memory engine/registry generation equals DB;
* session ownership is immutable and updates are optimistic-versioned;
* request IDs make agent/client retries idempotent across process restarts.

This module is an INTERNAL product data-layer seam. R12/R12B authenticated,
subject-scoped authorization is the only transport-facing mutation boundary.
No matching/scoring semantics are implemented here.
"""

from __future__ import annotations

import hashlib
import json
import threading
import uuid
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from src.discovery import ConsentRegistry, DiscoveryService, SessionProfile
from src.engine import ResonanceEngine
from src.graph import ThoughtDNAValidationError, ThoughtGraph, validate_thought

from .errors import (
    PersistenceConflictError,
    PersistenceNotFoundError,
    PersistenceOwnershipError,
    PersistenceStaleIndexError,
    PersistenceStateError,
    PersistenceValidationError,
)
from .models import (
    CORPUS_SCHEMA_VERSION,
    PERSISTENCE_SCHEMA_VERSION,
    THOUGHT_DNA_SCHEMA_VERSION,
    AuditEvent,
    ConsentState,
    IdempotencyKey,
    SessionRecord,
    UserRecord,
)
from .repository import PersistenceRepository


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sha(value: Any) -> str:
    if isinstance(value, (bytes, bytearray)):
        return hashlib.sha256(value).hexdigest()
    if isinstance(value, str):
        return hashlib.sha256(value.encode("utf-8")).hexdigest()
    blob = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def thought_sha256(thought_dna: Mapping[str, Any]) -> str:
    return _sha(thought_dna)


def session_to_r7(session: SessionRecord, user: UserRecord | None) -> dict[str, Any]:
    if session.consent.share_display_profile and user is not None and not user.hidden:
        person = {
            "person_id": session.user_id,
            "display_label": user.display_label,
            "avatar_placeholder": user.avatar_placeholder,
        }
    else:
        person = {
            "person_id": session.user_id,
            "display_label": "anonymous",
            "avatar_placeholder": "anonymous",
        }
    return {
        "schema_version": CORPUS_SCHEMA_VERSION,
        "session_id": session.session_id,
        "person": person,
        "consent": session.consent.to_dict(),
        "location": dict(session.location),
        "presentation": dict(session.presentation),
        "record_provenance": {
            "record_kind": session.record_kind,
            "builder_id": session.builder_id,
            "notes": session.notes,
        },
        "thought_dna": dict(session.thought_dna),
    }


@dataclass(frozen=True)
class PersistenceHealth:
    ok: bool
    backend: str
    schema_version: str
    users: int
    sessions: int
    discoverable: int
    engine_snapshot: str | None
    db_generation: int
    serving_generation: int | None
    index_current: bool
    details: Mapping[str, Any]


class LiveCorpusService:
    """Durable corpus + deterministic accepted-engine rebuild.

    Repository methods are intentionally not an authorization API. R12/R12B
    must scope every transport mutation to the authenticated subject/object.
    """

    def __init__(
        self,
        repo: PersistenceRepository,
        *,
        engine: ResonanceEngine | None = None,
    ) -> None:
        self.repo = repo
        self._lock = threading.RLock()
        self.engine = engine or ResonanceEngine()
        self.registry = ConsentRegistry({})
        self.discovery = DiscoveryService(self.engine, self.registry)
        self._serving_generation: int | None = None
        self.rebuild_index()

    # ------------------------------------------------------------------
    # generation / health
    # ------------------------------------------------------------------
    def _index_bound(self) -> bool:
        try:
            return self.engine.store.snapshot() == self.engine.candidate_index.corpus_snapshot
        except Exception:
            return False

    def _index_current(self) -> bool:
        try:
            return (
                self._serving_generation is not None
                and self._serving_generation == self.repo.get_corpus_generation()
                and self._index_bound()
            )
        except Exception:
            return False

    def _require_fresh_index(self) -> None:
        db_generation = self.repo.get_corpus_generation()
        if (
            self._serving_generation is None
            or self._serving_generation != db_generation
            or not self._index_bound()
        ):
            raise PersistenceStaleIndexError(
                "discovery index is not proven current with durable DB; "
                f"serving_generation={self._serving_generation!r}, "
                f"db_generation={db_generation}; rebuild required"
            )

    def _visible_sessions(self) -> list[SessionRecord]:
        visible: list[SessionRecord] = []
        for session in self.repo.list_discoverable_sessions():
            user = self.repo.get_user(session.user_id)
            if user is not None and not user.hidden:
                visible.append(session)
        return visible

    def health(self) -> PersistenceHealth:
        with self._lock:
            raw = self.repo.health()
            db_generation = self.repo.get_corpus_generation()
            current = self._index_current()
            return PersistenceHealth(
                ok=bool(raw.get("ok")) and current,
                backend=self.repo.backend_name,
                schema_version=PERSISTENCE_SCHEMA_VERSION,
                users=int(raw.get("users") or 0),
                sessions=int(raw.get("sessions") or 0),
                discoverable=len(self._visible_sessions()),
                engine_snapshot=(
                    self.engine.candidate_index.corpus_snapshot if current else None
                ),
                db_generation=db_generation,
                serving_generation=self._serving_generation,
                index_current=current,
                details={
                    **dict(raw),
                    "db_generation": db_generation,
                    "serving_generation": self._serving_generation,
                    "index_current": current,
                },
            )

    def _mark_stale_before_write(self) -> tuple[int, int | None]:
        before_db = self.repo.get_corpus_generation()
        before_serving = self._serving_generation
        self._serving_generation = None
        return before_db, before_serving

    def _restore_if_write_did_not_commit(
        self, before_db: int, before_serving: int | None
    ) -> None:
        try:
            if self.repo.get_corpus_generation() == before_db:
                self._serving_generation = before_serving
        except Exception:
            self._serving_generation = None

    # ------------------------------------------------------------------
    # operational paths
    # ------------------------------------------------------------------
    def reset(self) -> None:
        with self._lock:
            before_db, before_serving = self._mark_stale_before_write()
            try:
                self.repo.reset()
            except Exception:
                self._restore_if_write_did_not_commit(before_db, before_serving)
                raise
            self.rebuild_index()

    def export_backup(self, path: str | Path | None = None) -> dict[str, Any]:
        with self._lock:
            payload = self.repo.export_payload()
            payload["exported_at"] = _now()
            payload["serving_generation"] = self._serving_generation
            payload["engine_snapshot"] = (
                self.engine.candidate_index.corpus_snapshot if self._index_current() else None
            )
            if path is not None:
                Path(path).write_text(
                    json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
                    encoding="utf-8",
                )
            return payload

    def import_backup(self, payload: Mapping[str, Any] | str | Path) -> None:
        with self._lock:
            if isinstance(payload, (str, Path)) and Path(payload).exists():
                payload = json.loads(Path(payload).read_text(encoding="utf-8"))
            if not isinstance(payload, Mapping):
                raise PersistenceValidationError("backup payload must be an object")
            before_db, before_serving = self._mark_stale_before_write()
            try:
                self.repo.import_payload(payload)
            except Exception:
                self._restore_if_write_did_not_commit(before_db, before_serving)
                raise
            self.rebuild_index()

    # ------------------------------------------------------------------
    # users
    # ------------------------------------------------------------------
    def create_user(
        self,
        user_id: str,
        *,
        display_label: str,
        avatar_placeholder: str | None = None,
        rebuild: bool = True,
    ) -> UserRecord:
        with self._lock:
            if not user_id.startswith("person-"):
                raise PersistenceValidationError("user_id must start with 'person-'")
            if not display_label.strip():
                raise PersistenceValidationError("display_label must be non-empty")
            now = _now()
            existing = self.repo.get_user(user_id)
            user = UserRecord(
                user_id=user_id,
                display_label=display_label,
                avatar_placeholder=avatar_placeholder or display_label,
                created_at=existing.created_at if existing else now,
                updated_at=now,
                # Ordinary profile upsert cannot silently un-revoke an identity.
                revoked_at=existing.revoked_at if existing else None,
            )
            audit = self._audit_event(
                "user.upsert",
                user_id=user_id,
                payload={"profile_updated": bool(existing)},
            )
            before_db, before_serving = self._mark_stale_before_write()
            try:
                stored = self.repo.put_user(user, audit=audit)
            except Exception:
                self._restore_if_write_did_not_commit(before_db, before_serving)
                raise
            if rebuild:
                self.rebuild_index()
            return stored

    def revoke_user(self, user_id: str) -> UserRecord:
        with self._lock:
            user = self.repo.get_user(user_id)
            if user is None:
                raise PersistenceNotFoundError(user_id)
            if user.revoked_at is not None:
                return user
            now = _now()
            hidden = replace(user, revoked_at=now, updated_at=now)
            before_db, before_serving = self._mark_stale_before_write()
            try:
                stored_user = self.repo.put_user(
                    hidden,
                    audit=self._audit_event("user.revoke", user_id=user_id),
                )
                for session in self.repo.list_sessions():
                    if session.user_id != user_id or not session.is_live():
                        continue
                    disabled = replace(
                        session,
                        consent=ConsentState(False, False, False, False),
                        revoked_at=now,
                        updated_at=now,
                    )
                    self.repo.put_session(
                        disabled,
                        expected_version=session.version,
                        audit=self._audit_event(
                            "session.revoke",
                            user_id=user_id,
                            session_id=session.session_id,
                            payload={"reason": "user_revoked"},
                        ),
                    )
            except Exception:
                self._restore_if_write_did_not_commit(before_db, before_serving)
                raise
            self.rebuild_index()
            return stored_user

    # ------------------------------------------------------------------
    # session mutation helpers
    # ------------------------------------------------------------------
    def _idempotency_key(
        self,
        request_id: str | None,
        operation: str,
        payload: Mapping[str, Any],
    ) -> IdempotencyKey | None:
        if request_id is None:
            return None
        if not isinstance(request_id, str) or not request_id.strip() or len(request_id) > 200:
            raise PersistenceValidationError("request_id must be 1..200 characters")
        return IdempotencyKey(
            request_id=request_id,
            operation=operation,
            request_hash=_sha({"operation": operation, "payload": payload}),
        )

    def _replay(self, key: IdempotencyKey | None) -> SessionRecord | None:
        if key is None:
            return None
        replay = self.repo.lookup_idempotency(key)
        if replay is not None and not self._index_current():
            # A previous attempt may have committed DB state and timed out during
            # rebuild. Retrying the same request heals the serving generation
            # without applying the mutation twice.
            self.rebuild_index()
        return replay

    def _store_session(
        self,
        candidate: SessionRecord,
        *,
        expected_version: int | None,
        idempotency: IdempotencyKey | None,
        audit: AuditEvent,
        rebuild: bool,
    ) -> SessionRecord:
        before_db, before_serving = self._mark_stale_before_write()
        try:
            stored = self.repo.put_session(
                candidate,
                expected_version=expected_version,
                idempotency=idempotency,
                audit=audit,
            )
        except Exception:
            self._restore_if_write_did_not_commit(before_db, before_serving)
            raise
        if rebuild:
            # If this raises, serving_generation deliberately remains None.
            self.rebuild_index()
        return stored

    def create_session(
        self,
        *,
        session_id: str,
        user_id: str,
        thought_dna: Mapping[str, Any],
        consent: Mapping[str, Any] | ConsentState,
        location: Mapping[str, Any],
        presentation: Mapping[str, Any],
        record_kind: str = "synthetic",
        builder_id: str = "r11-persistence-recovery",
        notes: str = "",
        expected_version: int | None = None,
        request_id: str | None = None,
        rebuild: bool = True,
    ) -> SessionRecord:
        """Create a session, or explicitly version-update an existing one.

        Existing session IDs require immutable ownership and an expected_version.
        A retry with the same request_id returns the original committed result.
        """
        with self._lock:
            if self.repo.get_user(user_id) is None:
                raise PersistenceNotFoundError(user_id)
            if not session_id.startswith("ses-"):
                raise PersistenceValidationError("session_id must start with 'ses-'")
            try:
                validate_thought(thought_dna)
            except ThoughtDNAValidationError as exc:
                raise PersistenceValidationError(str(exc)) from exc
            graph = ThoughtGraph.from_dict(thought_dna)
            if graph.schema_version != THOUGHT_DNA_SCHEMA_VERSION:
                raise PersistenceValidationError(
                    f"unsupported Thought DNA schema {graph.schema_version!r}"
                )
            state = consent if isinstance(consent, ConsentState) else ConsentState.from_mapping(consent)
            request_payload = {
                "session_id": session_id,
                "user_id": user_id,
                "thought_dna_sha256": thought_sha256(graph.to_dict()),
                "consent": state.to_dict(),
                "location": dict(location),
                "presentation": dict(presentation),
                "record_kind": record_kind,
                "builder_id": builder_id,
                "notes": notes,
                "expected_version": expected_version,
            }
            key = self._idempotency_key(request_id, "session.upsert", request_payload)
            replay = self._replay(key)
            if replay is not None:
                return replay

            now = _now()
            existing = self.repo.get_session(session_id)
            if existing is not None:
                if existing.user_id != user_id:
                    raise PersistenceOwnershipError(
                        f"{session_id} belongs to {existing.user_id!r}; cannot reassign to {user_id!r}"
                    )
                if not existing.is_live():
                    raise PersistenceStateError(
                        f"{session_id} is revoked/deleted and cannot be resurrected by upsert"
                    )
            record = SessionRecord(
                session_id=session_id,
                user_id=user_id,
                thought_id=graph.thought_id,
                schema_version=CORPUS_SCHEMA_VERSION,
                thought_dna=graph.to_dict(),
                thought_dna_sha256=thought_sha256(graph.to_dict()),
                thought_dna_schema_version=graph.schema_version,
                consent=state,
                location=dict(location),
                presentation=dict(presentation),
                record_kind=record_kind,
                builder_id=builder_id,
                notes=notes,
                created_at=existing.created_at if existing else now,
                updated_at=now,
                revoked_at=existing.revoked_at if existing else None,
                deleted_at=existing.deleted_at if existing else None,
                version=existing.version if existing else 0,
            )
            return self._store_session(
                record,
                expected_version=expected_version,
                idempotency=key,
                audit=self._audit_event(
                    "session.upsert",
                    user_id=user_id,
                    session_id=session_id,
                    payload={"thought_id": graph.thought_id, "share_state": record.share_state},
                ),
                rebuild=rebuild,
            )

    def update_consent(
        self,
        session_id: str,
        consent: Mapping[str, Any] | ConsentState,
        *,
        expected_version: int | None = None,
        request_id: str | None = None,
        rebuild: bool = True,
    ) -> SessionRecord:
        with self._lock:
            state = consent if isinstance(consent, ConsentState) else ConsentState.from_mapping(consent)
            key = self._idempotency_key(
                request_id,
                "session.consent",
                {
                    "session_id": session_id,
                    "consent": state.to_dict(),
                    "expected_version": expected_version,
                },
            )
            replay = self._replay(key)
            if replay is not None:
                return replay
            session = self._require_session(session_id)
            if not session.is_live():
                raise PersistenceStateError(f"{session_id} is revoked/deleted")
            expected = session.version if expected_version is None else expected_version
            updated = replace(session, consent=state, updated_at=_now())
            return self._store_session(
                updated,
                expected_version=expected,
                idempotency=key,
                audit=self._audit_event(
                    "session.consent",
                    user_id=session.user_id,
                    session_id=session_id,
                    payload={"share_state": updated.share_state},
                ),
                rebuild=rebuild,
            )

    def update_presentation(
        self,
        session_id: str,
        *,
        location: Mapping[str, Any] | None = None,
        presentation: Mapping[str, Any] | None = None,
        expected_version: int | None = None,
        request_id: str | None = None,
        rebuild: bool = True,
    ) -> SessionRecord:
        with self._lock:
            key = self._idempotency_key(
                request_id,
                "session.metadata",
                {
                    "session_id": session_id,
                    "location": dict(location) if location is not None else None,
                    "presentation": dict(presentation) if presentation is not None else None,
                    "expected_version": expected_version,
                },
            )
            replay = self._replay(key)
            if replay is not None:
                return replay
            session = self._require_session(session_id)
            if not session.is_live():
                raise PersistenceStateError(f"{session_id} is revoked/deleted")
            expected = session.version if expected_version is None else expected_version
            updated = replace(
                session,
                location=dict(location) if location is not None else session.location,
                presentation=(
                    dict(presentation) if presentation is not None else session.presentation
                ),
                updated_at=_now(),
            )
            return self._store_session(
                updated,
                expected_version=expected,
                idempotency=key,
                audit=self._audit_event(
                    "session.metadata",
                    user_id=session.user_id,
                    session_id=session_id,
                ),
                rebuild=rebuild,
            )

    def revoke_session(
        self,
        session_id: str,
        *,
        reason: str = "revoked",
        expected_version: int | None = None,
        request_id: str | None = None,
        rebuild: bool = True,
    ) -> SessionRecord:
        with self._lock:
            key = self._idempotency_key(
                request_id,
                "session.revoke",
                {
                    "session_id": session_id,
                    "reason": reason,
                    "expected_version": expected_version,
                },
            )
            replay = self._replay(key)
            if replay is not None:
                return replay
            session = self._require_session(session_id)
            if session.deleted_at is not None:
                raise PersistenceStateError(f"{session_id} is deleted")
            if session.revoked_at is not None:
                raise PersistenceStateError(
                    f"{session_id} is already revoked; use the original request_id for retry"
                )
            expected = session.version if expected_version is None else expected_version
            now = _now()
            hidden = replace(
                session,
                consent=ConsentState(False, False, False, False),
                revoked_at=now,
                updated_at=now,
            )
            return self._store_session(
                hidden,
                expected_version=expected,
                idempotency=key,
                audit=self._audit_event(
                    "session.revoke",
                    user_id=session.user_id,
                    session_id=session_id,
                    payload={"reason": reason},
                ),
                rebuild=rebuild,
            )

    def delete_session(
        self,
        session_id: str,
        *,
        expected_version: int | None = None,
        request_id: str | None = None,
        rebuild: bool = True,
    ) -> SessionRecord:
        with self._lock:
            key = self._idempotency_key(
                request_id,
                "session.delete",
                {"session_id": session_id, "expected_version": expected_version},
            )
            replay = self._replay(key)
            if replay is not None:
                return replay
            session = self._require_session(session_id)
            if session.deleted_at is not None:
                raise PersistenceStateError(
                    f"{session_id} is already deleted; use the original request_id for retry"
                )
            expected = session.version if expected_version is None else expected_version
            now = _now()
            deleted = replace(
                session,
                consent=ConsentState(False, False, False, False),
                revoked_at=session.revoked_at or now,
                deleted_at=now,
                updated_at=now,
            )
            return self._store_session(
                deleted,
                expected_version=expected,
                idempotency=key,
                audit=self._audit_event(
                    "session.delete",
                    user_id=session.user_id,
                    session_id=session_id,
                ),
                rebuild=rebuild,
            )

    # ------------------------------------------------------------------
    # reads / discovery
    # ------------------------------------------------------------------
    def get_user(self, user_id: str) -> UserRecord | None:
        return self.repo.get_user(user_id)

    def get_session(self, session_id: str) -> SessionRecord | None:
        return self.repo.get_session(session_id)

    def public_session_view(self, session_id: str) -> dict[str, Any] | None:
        """DB-authoritative public projection; safe even while index is stale."""
        with self._lock:
            session = self.repo.get_session(session_id)
            if session is None or not session.is_discoverable():
                return None
            user = self.repo.get_user(session.user_id)
            if user is None or user.hidden:
                return None
            try:
                validate_thought(session.thought_dna)
            except ThoughtDNAValidationError as exc:
                raise PersistenceStateError(
                    f"discoverable DB row {session_id!r} contains invalid Thought DNA"
                ) from exc
            from demo.corpus.discovery import presentation_view
            return presentation_view(session_to_r7(session, user))

    def list_public_sessions(self) -> list[dict[str, Any]]:
        with self._lock:
            views: list[dict[str, Any]] = []
            for session in self.repo.list_discoverable_sessions():
                view = self.public_session_view(session.session_id)
                if view is not None:
                    views.append(view)
            return views

    def discover(self, graph: ThoughtGraph, *, mode: str, k: int = 8) -> dict[str, Any]:
        with self._lock:
            self._require_fresh_index()
            return self.discovery.discover(graph, mode=mode, k=k)

    def profile_for_thought(self, thought_id: str) -> SessionProfile | None:
        with self._lock:
            self._require_fresh_index()
            return self.registry.get(thought_id)

    def audit_log(self) -> list[dict[str, Any]]:
        return [event.to_public_dict() for event in self.repo.list_audit()]

    # ------------------------------------------------------------------
    # deterministic rebuild
    # ------------------------------------------------------------------
    def rebuild_index(self) -> str:
        """Build off to the side; publish atomically only for one DB generation."""
        with self._lock:
            start_generation = self.repo.get_corpus_generation()
            engine = ResonanceEngine()
            records: list[dict[str, Any]] = []
            sessions = list(self.repo.list_discoverable_sessions())
            sessions.sort(key=lambda session: session.thought_id)
            for session in sessions:
                user = self.repo.get_user(session.user_id)
                if user is None or user.hidden:
                    continue
                try:
                    validate_thought(session.thought_dna)
                except ThoughtDNAValidationError as exc:
                    self._serving_generation = None
                    raise PersistenceStateError(
                        f"discoverable DB row {session.session_id!r} contains invalid Thought DNA"
                    ) from exc
                graph = ThoughtGraph.from_dict(session.thought_dna)
                if graph.schema_version != THOUGHT_DNA_SCHEMA_VERSION:
                    self._serving_generation = None
                    raise PersistenceStateError(
                        f"unsupported Thought DNA schema in {session.session_id!r}: "
                        f"{graph.schema_version!r}"
                    )
                engine.index(graph)
                records.append(session_to_r7(session, user))

            registry = ConsentRegistry.from_r7_sessions(records)
            discovery = DiscoveryService(engine, registry)
            end_generation = self.repo.get_corpus_generation()
            if end_generation != start_generation:
                self._serving_generation = None
                raise PersistenceStaleIndexError(
                    "durable corpus changed during rebuild; refusing to publish stale generation"
                )

            self.engine = engine
            self.registry = registry
            self.discovery = discovery
            self._serving_generation = end_generation
            return self.engine.candidate_index.corpus_snapshot

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _require_session(self, session_id: str) -> SessionRecord:
        session = self.repo.get_session(session_id)
        if session is None:
            raise PersistenceNotFoundError(session_id)
        return session

    def _audit_event(
        self,
        event_type: str,
        *,
        user_id: str | None = None,
        session_id: str | None = None,
        payload: Mapping[str, Any] | None = None,
    ) -> AuditEvent:
        return AuditEvent(
            event_id=uuid.uuid4().hex,
            event_type=event_type,
            user_id=user_id,
            session_id=session_id,
            payload=dict(payload or {}),
            created_at=_now(),
        )
