"""Narrow seam from R12 identity/consent to R11 durable persistence.

The identity layer owns policy and authorization, not storage.  The production
adapter wraps R11 LiveCorpusService + its PersistenceRepository.  The protocol
is intentionally structural so this module remains importable before R11 is
accepted/merged into main.
"""

from __future__ import annotations

from typing import Any, Mapping, Protocol, Sequence

from .models import IdentityEvent


class IdentityBackend(Protocol):
    def create_user(self, user_id: str, *, display_label: str, avatar_placeholder: str | None = None) -> Any:
        ...

    def get_user(self, user_id: str) -> Any | None:
        ...

    def revoke_user(self, user_id: str) -> Any:
        ...

    def create_session(
        self,
        *,
        session_id: str,
        user_id: str,
        thought_dna: Mapping[str, Any],
        consent: Mapping[str, Any],
        location: Mapping[str, Any],
        presentation: Mapping[str, Any],
        record_kind: str,
        builder_id: str,
        notes: str,
    ) -> Any:
        ...

    def get_session(self, session_id: str) -> Any | None:
        ...

    def list_sessions(self) -> Sequence[Any]:
        ...

    def update_consent(self, session_id: str, consent: Mapping[str, Any]) -> Any:
        ...

    def update_presentation(
        self,
        session_id: str,
        *,
        location: Mapping[str, Any] | None = None,
        presentation: Mapping[str, Any] | None = None,
    ) -> Any:
        ...

    def revoke_session(self, session_id: str, *, reason: str = "revoked") -> Any:
        ...

    def delete_session(self, session_id: str) -> Any:
        ...

    def append_identity_event(self, event: IdentityEvent) -> None:
        ...

    def list_identity_events(self) -> Sequence[IdentityEvent]:
        ...


class R11IdentityBackend:
    """Adapter over the declared R11 service/repository seam.

    No database implementation lives here.  `live_corpus` is expected to be an
    R11 `LiveCorpusService`.  Importing R12 before R11 lands on main remains
    safe because the persistence AuditEvent import is lazy.
    """

    _EVENT_PREFIX = "identity."

    def __init__(self, live_corpus: Any) -> None:
        self.live_corpus = live_corpus
        self.repo = live_corpus.repo

    def create_user(self, *args: Any, **kwargs: Any) -> Any:
        return self.live_corpus.create_user(*args, **kwargs)

    def get_user(self, user_id: str) -> Any | None:
        return self.live_corpus.get_user(user_id)

    def revoke_user(self, user_id: str) -> Any:
        return self.live_corpus.revoke_user(user_id)

    def create_session(self, **kwargs: Any) -> Any:
        return self.live_corpus.create_session(**kwargs)

    def get_session(self, session_id: str) -> Any | None:
        return self.live_corpus.get_session(session_id)

    def list_sessions(self) -> Sequence[Any]:
        return self.repo.list_sessions()

    def update_consent(self, session_id: str, consent: Mapping[str, Any]) -> Any:
        return self.live_corpus.update_consent(session_id, consent)

    def update_presentation(self, session_id: str, **kwargs: Any) -> Any:
        return self.live_corpus.update_presentation(session_id, **kwargs)

    def revoke_session(self, session_id: str, *, reason: str = "revoked") -> Any:
        return self.live_corpus.revoke_session(session_id, reason=reason)

    def delete_session(self, session_id: str) -> Any:
        return self.live_corpus.delete_session(session_id)

    def append_identity_event(self, event: IdentityEvent) -> None:
        # Lazy import keeps the R12 branch buildable while R11 is still a
        # separately submitted canonical lane.
        from src.persistence.models import AuditEvent  # type: ignore[import-not-found]

        self.repo.append_audit(
            AuditEvent(
                event_id=event.event_id,
                event_type=event.event_type,
                user_id=event.user_id,
                session_id=event.session_id,
                payload=dict(event.payload),
                created_at=event.created_at,
            )
        )

    def list_identity_events(self) -> Sequence[IdentityEvent]:
        result: list[IdentityEvent] = []
        for raw in self.repo.list_audit():
            event_type = str(getattr(raw, "event_type", ""))
            if not event_type.startswith(self._EVENT_PREFIX):
                continue
            result.append(
                IdentityEvent(
                    event_id=str(getattr(raw, "event_id")),
                    event_type=event_type,
                    user_id=getattr(raw, "user_id", None),
                    session_id=getattr(raw, "session_id", None),
                    payload=dict(getattr(raw, "payload", {}) or {}),
                    created_at=str(getattr(raw, "created_at", "")),
                )
            )
        return result
