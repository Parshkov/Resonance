"""Transport-neutral live corpus service.

This is the product/service layer R10 WebMCP, R13 UI, and R15 remote MCP
should call. It does not implement matching. It:

- validates Thought DNA before a session becomes discoverable;
- persists users/sessions/consent/audit;
- rebuilds the accepted engine index from discoverable rows only;
- joins metadata after engine.find via the frozen ConsentRegistry.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from src.discovery import ConsentRegistry, DiscoveryService, SessionProfile
from src.engine import ResonanceEngine
from src.graph import ThoughtDNAValidationError, ThoughtGraph, validate_thought

from .errors import (
    PersistenceNotFoundError,
    PersistenceStateError,
    PersistenceValidationError,
)
from .models import (
    CORPUS_SCHEMA_VERSION,
    PERSISTENCE_SCHEMA_VERSION,
    THOUGHT_DNA_SCHEMA_VERSION,
    AuditEvent,
    ConsentState,
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
    details: Mapping[str, Any]


class LiveCorpusService:
    """Durable corpus + accepted engine rebuild."""

    def __init__(self, repo: PersistenceRepository, *, engine: ResonanceEngine | None = None) -> None:
        self.repo = repo
        self.engine = engine or ResonanceEngine()
        self.registry = ConsentRegistry({})
        self.discovery = DiscoveryService(self.engine, self.registry)
        self.rebuild_index()

    def health(self) -> PersistenceHealth:
        raw = self.repo.health()
        discoverable = len(self.repo.list_discoverable_sessions())
        return PersistenceHealth(
            ok=bool(raw.get("ok")) and self._index_bound(),
            backend=self.repo.backend_name,
            schema_version=PERSISTENCE_SCHEMA_VERSION,
            users=int(raw.get("users") or 0),
            sessions=int(raw.get("sessions") or 0),
            discoverable=discoverable,
            engine_snapshot=self.engine.candidate_index.corpus_snapshot,
            details=raw,
        )

    def reset(self) -> None:
        self.repo.reset()
        self.engine = ResonanceEngine()
        self.registry = ConsentRegistry({})
        self.discovery = DiscoveryService(self.engine, self.registry)

    def export_backup(self, path: str | Path | None = None) -> dict[str, Any]:
        payload = self.repo.export_payload()
        payload["exported_at"] = _now()
        payload["engine_snapshot"] = self.engine.candidate_index.corpus_snapshot
        if path is not None:
            Path(path).write_text(
                json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
                encoding="utf-8",
            )
        return payload

    def import_backup(self, payload: Mapping[str, Any] | str | Path) -> None:
        if isinstance(payload, (str, Path)) and Path(payload).exists():
            payload = json.loads(Path(payload).read_text(encoding="utf-8"))
        if not isinstance(payload, Mapping):
            raise PersistenceValidationError("backup payload must be an object")
        self.repo.import_payload(payload)
        self.rebuild_index()

    def create_user(
        self,
        user_id: str,
        *,
        display_label: str,
        avatar_placeholder: str | None = None,
    ) -> UserRecord:
        if not user_id.startswith("person-"):
            raise PersistenceValidationError("user_id must start with 'person-'")
        now = _now()
        existing = self.repo.get_user(user_id)
        user = UserRecord(
            user_id=user_id,
            display_label=display_label,
            avatar_placeholder=avatar_placeholder or display_label,
            created_at=existing.created_at if existing else now,
            updated_at=now,
            revoked_at=existing.revoked_at if existing else None,
        )
        stored = self.repo.put_user(user)
        self._audit("user.upsert", user_id=user_id, payload={"display_label": display_label})
        return stored

    def revoke_user(self, user_id: str) -> UserRecord:
        user = self.repo.get_user(user_id)
        if user is None:
            raise PersistenceNotFoundError(user_id)
        now = _now()
        hidden = replace(user, revoked_at=now, updated_at=now)
        self.repo.put_user(hidden)
        for session in self.repo.list_sessions():
            if session.user_id == user_id and session.is_live():
                self.revoke_session(session.session_id, reason="user_revoked")
        self._audit("user.revoke", user_id=user_id)
        self.rebuild_index()
        return hidden

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
        builder_id: str = "r11-persistence",
        notes: str = "",
        rebuild: bool = True,
    ) -> SessionRecord:
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
        now = _now()
        existing = self.repo.get_session(session_id)
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
        )
        stored = self.repo.put_session(record)
        self._audit(
            "session.upsert",
            user_id=user_id,
            session_id=session_id,
            payload={"thought_id": stored.thought_id, "share_state": stored.share_state},
        )
        if rebuild:
            self.rebuild_index()
        return stored

    def update_consent(self, session_id: str, consent: Mapping[str, Any] | ConsentState) -> SessionRecord:
        session = self._require_session(session_id)
        state = consent if isinstance(consent, ConsentState) else ConsentState.from_mapping(consent)
        updated = replace(session, consent=state, updated_at=_now())
        stored = self.repo.put_session(updated)
        self._audit(
            "session.consent",
            user_id=stored.user_id,
            session_id=session_id,
            payload={"share_state": stored.share_state},
        )
        self.rebuild_index()
        return stored

    def update_presentation(
        self,
        session_id: str,
        *,
        location: Mapping[str, Any] | None = None,
        presentation: Mapping[str, Any] | None = None,
    ) -> SessionRecord:
        session = self._require_session(session_id)
        updated = replace(
            session,
            location=dict(location) if location is not None else session.location,
            presentation=dict(presentation) if presentation is not None else session.presentation,
            updated_at=_now(),
        )
        stored = self.repo.put_session(updated)
        self._audit("session.metadata", user_id=stored.user_id, session_id=session_id)
        self._rebuild_registry()
        return stored

    def revoke_session(self, session_id: str, *, reason: str = "revoked") -> SessionRecord:
        session = self._require_session(session_id)
        if session.deleted_at is not None:
            raise PersistenceStateError(f"{session_id} is deleted")
        now = _now()
        hidden = replace(
            session,
            consent=ConsentState(False, False, False, False),
            revoked_at=now,
            updated_at=now,
        )
        stored = self.repo.put_session(hidden)
        self._audit(
            "session.revoke",
            user_id=stored.user_id,
            session_id=session_id,
            payload={"reason": reason},
        )
        self.rebuild_index()
        return stored

    def delete_session(self, session_id: str) -> SessionRecord:
        session = self._require_session(session_id)
        now = _now()
        deleted = replace(
            session,
            consent=ConsentState(False, False, False, False),
            revoked_at=session.revoked_at or now,
            deleted_at=now,
            updated_at=now,
        )
        stored = self.repo.put_session(deleted)
        self._audit("session.delete", user_id=stored.user_id, session_id=session_id)
        self.rebuild_index()
        return stored

    def get_user(self, user_id: str) -> UserRecord | None:
        return self.repo.get_user(user_id)

    def get_session(self, session_id: str) -> SessionRecord | None:
        return self.repo.get_session(session_id)

    def public_session_view(self, session_id: str) -> dict[str, Any] | None:
        session = self.repo.get_session(session_id)
        if session is None or not session.is_discoverable():
            return None
        user = self.repo.get_user(session.user_id)
        if user is not None and user.hidden:
            return None
        from demo.corpus.discovery import presentation_view
        return presentation_view(session_to_r7(session, user))

    def list_public_sessions(self) -> list[dict[str, Any]]:
        views = []
        for session in self.repo.list_discoverable_sessions():
            view = self.public_session_view(session.session_id)
            if view is not None:
                views.append(view)
        return views

    def discover(self, graph: ThoughtGraph, *, mode: str, k: int = 8) -> dict[str, Any]:
        return self.discovery.discover(graph, mode=mode, k=k)

    def audit_log(self) -> list[dict[str, Any]]:
        return [e.to_public_dict() for e in self.repo.list_audit()]

    def rebuild_index(self) -> str:
        """Deterministic rebuild: sorted thought_id order, discoverable only."""
        engine = ResonanceEngine()
        sessions = list(self.repo.list_discoverable_sessions())
        sessions.sort(key=lambda s: s.thought_id)
        for session in sessions:
            user = self.repo.get_user(session.user_id)
            if user is None or user.hidden:
                continue
            try:
                validate_thought(session.thought_dna)
            except ThoughtDNAValidationError:
                continue
            graph = ThoughtGraph.from_dict(session.thought_dna)
            engine.index(graph)
        self.engine = engine
        self._rebuild_registry()
        self.discovery = DiscoveryService(self.engine, self.registry)
        return self.engine.candidate_index.corpus_snapshot

    def _rebuild_registry(self) -> None:
        records = []
        for session in self.repo.list_discoverable_sessions():
            user = self.repo.get_user(session.user_id)
            if user is None or user.hidden:
                continue
            records.append(session_to_r7(session, user))
        self.registry = ConsentRegistry.from_r7_sessions(records)
        self.discovery = DiscoveryService(self.engine, self.registry)

    def _index_bound(self) -> bool:
        try:
            return self.engine.store.snapshot() == self.engine.candidate_index.corpus_snapshot
        except Exception:
            return False

    def _require_session(self, session_id: str) -> SessionRecord:
        session = self.repo.get_session(session_id)
        if session is None:
            raise PersistenceNotFoundError(session_id)
        return session

    def _audit(
        self,
        event_type: str,
        *,
        user_id: str | None = None,
        session_id: str | None = None,
        payload: Mapping[str, Any] | None = None,
    ) -> AuditEvent:
        event = AuditEvent(
            event_id=_sha(["audit", event_type, user_id, session_id, _now(), payload or {}])[:24],
            event_type=event_type,
            user_id=user_id,
            session_id=session_id,
            payload=dict(payload or {}),
            created_at=_now(),
        )
        return self.repo.append_audit(event)

    def profile_for_thought(self, thought_id: str) -> SessionProfile | None:
        return self.registry.get(thought_id)
