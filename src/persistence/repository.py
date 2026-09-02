"""Repository protocol. Storage implementations must not score thoughts."""

from __future__ import annotations

from typing import Any, Mapping, Protocol, Sequence

from .models import AuditEvent, SessionRecord, UserRecord


class PersistenceRepository(Protocol):
    backend_name: str

    def migrate(self) -> tuple[str, ...]:
        ...

    def health(self) -> dict[str, Any]:
        ...

    def reset(self) -> None:
        ...

    def close(self) -> None:
        ...

    def put_user(self, user: UserRecord) -> UserRecord:
        ...

    def get_user(self, user_id: str) -> UserRecord | None:
        ...

    def list_users(self) -> Sequence[UserRecord]:
        ...

    def put_session(self, session: SessionRecord) -> SessionRecord:
        ...

    def get_session(self, session_id: str) -> SessionRecord | None:
        ...

    def get_session_by_thought(self, thought_id: str) -> SessionRecord | None:
        ...

    def list_sessions(self, *, include_deleted: bool = False) -> Sequence[SessionRecord]:
        ...

    def list_discoverable_sessions(self) -> Sequence[SessionRecord]:
        ...

    def append_audit(self, event: AuditEvent) -> AuditEvent:
        ...

    def list_audit(self) -> Sequence[AuditEvent]:
        ...

    def export_payload(self) -> dict[str, Any]:
        ...

    def import_payload(self, payload: Mapping[str, Any]) -> None:
        ...
