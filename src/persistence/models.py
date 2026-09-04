"""Transport-neutral persistence records. No matching semantics live here."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

PERSISTENCE_SCHEMA_VERSION = "resonance-persistence/0.2"
THOUGHT_DNA_SCHEMA_VERSION = "thought-dna/0.1"
CORPUS_SCHEMA_VERSION = "resonance-demo-corpus/0.1"

DISCOVERABLE = "discoverable"
HIDDEN = "hidden"
REVOKED = "revoked"
DELETED = "deleted"


@dataclass(frozen=True, slots=True)
class ConsentState:
    share_enabled: bool
    share_thought_dna: bool
    share_coarse_location: bool
    share_display_profile: bool

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "ConsentState":
        return cls(
            share_enabled=bool(data["share_enabled"]),
            share_thought_dna=bool(data["share_thought_dna"]),
            share_coarse_location=bool(data["share_coarse_location"]),
            share_display_profile=bool(data["share_display_profile"]),
        )

    def to_dict(self) -> dict[str, bool]:
        return {
            "share_enabled": self.share_enabled,
            "share_thought_dna": self.share_thought_dna,
            "share_coarse_location": self.share_coarse_location,
            "share_display_profile": self.share_display_profile,
        }

    def is_discoverable(self) -> bool:
        return bool(self.share_enabled and self.share_thought_dna)


@dataclass(frozen=True, slots=True)
class UserRecord:
    user_id: str
    display_label: str
    avatar_placeholder: str
    created_at: str
    updated_at: str
    revoked_at: str | None = None

    @property
    def hidden(self) -> bool:
        return self.revoked_at is not None

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "display_label": self.display_label,
            "avatar_placeholder": self.avatar_placeholder,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "revoked_at": self.revoked_at,
        }

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "UserRecord":
        return cls(
            user_id=str(raw["user_id"]),
            display_label=str(raw["display_label"]),
            avatar_placeholder=str(raw["avatar_placeholder"]),
            created_at=str(raw["created_at"]),
            updated_at=str(raw["updated_at"]),
            revoked_at=raw.get("revoked_at"),
        )


@dataclass(frozen=True, slots=True)
class SessionRecord:
    session_id: str
    user_id: str
    thought_id: str
    schema_version: str
    thought_dna: Mapping[str, Any]
    thought_dna_sha256: str
    thought_dna_schema_version: str
    consent: ConsentState
    location: Mapping[str, Any]
    presentation: Mapping[str, Any]
    record_kind: str
    builder_id: str
    notes: str
    created_at: str
    updated_at: str
    revoked_at: str | None = None
    deleted_at: str | None = None
    version: int = 0

    @property
    def share_state(self) -> str:
        if self.deleted_at is not None:
            return DELETED
        if self.revoked_at is not None:
            return REVOKED
        if self.consent.is_discoverable():
            return DISCOVERABLE
        return HIDDEN

    def is_live(self) -> bool:
        return self.revoked_at is None and self.deleted_at is None

    def is_discoverable(self) -> bool:
        return self.is_live() and self.consent.is_discoverable()

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "thought_id": self.thought_id,
            "schema_version": self.schema_version,
            "thought_dna": dict(self.thought_dna),
            "thought_dna_sha256": self.thought_dna_sha256,
            "thought_dna_schema_version": self.thought_dna_schema_version,
            "consent": self.consent.to_dict(),
            "location": dict(self.location),
            "presentation": dict(self.presentation),
            "record_kind": self.record_kind,
            "builder_id": self.builder_id,
            "notes": self.notes,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "revoked_at": self.revoked_at,
            "deleted_at": self.deleted_at,
            "share_state": self.share_state,
            "version": self.version,
        }

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "SessionRecord":
        return cls(
            session_id=str(raw["session_id"]),
            user_id=str(raw["user_id"]),
            thought_id=str(raw["thought_id"]),
            schema_version=str(raw["schema_version"]),
            thought_dna=dict(raw["thought_dna"]),
            thought_dna_sha256=str(raw["thought_dna_sha256"]),
            thought_dna_schema_version=str(raw["thought_dna_schema_version"]),
            consent=ConsentState.from_mapping(raw["consent"]),
            location=dict(raw.get("location") or {}),
            presentation=dict(raw.get("presentation") or {}),
            record_kind=str(raw.get("record_kind") or ""),
            builder_id=str(raw.get("builder_id") or ""),
            notes=str(raw.get("notes") or ""),
            created_at=str(raw["created_at"]),
            updated_at=str(raw["updated_at"]),
            revoked_at=raw.get("revoked_at"),
            deleted_at=raw.get("deleted_at"),
            version=int(raw.get("version") or 0),
        )


@dataclass(frozen=True, slots=True)
class AuditEvent:
    event_id: str
    event_type: str
    user_id: str | None
    session_id: str | None
    payload: Mapping[str, Any] = field(default_factory=dict)
    created_at: str = ""

    def to_public_dict(self) -> dict[str, Any]:
        """Public audit view: never includes raw conversation text or credentials."""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "payload": dict(self.payload),
            "created_at": self.created_at,
        }


@dataclass(frozen=True, slots=True)
class IdempotencyKey:
    request_id: str
    operation: str
    request_hash: str


@dataclass(frozen=True, slots=True)
class IdempotencyRecord:
    request_id: str
    operation: str
    request_hash: str
    response: Mapping[str, Any]
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "operation": self.operation,
            "request_hash": self.request_hash,
            "response": dict(self.response),
            "created_at": self.created_at,
        }


INTRO_STATES = ("requested", "accepted", "declined", "cancelled")


@dataclass(frozen=True, slots=True)
class IntroRecord:
    """Durable pairwise connection request (R14). Never corpus content."""

    intro_id: str
    from_user_id: str
    to_user_id: str
    from_session_id: str
    to_session_id: str
    state: str
    message: str
    created_at: str
    updated_at: str
    accepted_at: str | None = None
    declined_at: str | None = None
    cancelled_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "intro_id": self.intro_id,
            "from_user_id": self.from_user_id,
            "to_user_id": self.to_user_id,
            "from_session_id": self.from_session_id,
            "to_session_id": self.to_session_id,
            "state": self.state,
            "message": self.message,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "accepted_at": self.accepted_at,
            "declined_at": self.declined_at,
            "cancelled_at": self.cancelled_at,
        }

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "IntroRecord":
        return cls(**{key: raw.get(key) for key in (
            "intro_id", "from_user_id", "to_user_id", "from_session_id",
            "to_session_id", "state", "message", "created_at", "updated_at",
            "accepted_at", "declined_at", "cancelled_at")})


@dataclass(frozen=True, slots=True)
class ChannelRecord:
    channel_id: str
    intro_id: str
    created_at: str
    closed_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"channel_id": self.channel_id, "intro_id": self.intro_id,
                "created_at": self.created_at, "closed_at": self.closed_at}


@dataclass(frozen=True, slots=True)
class MessageRecord:
    message_id: str
    channel_id: str
    author_user_id: str
    body: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {"message_id": self.message_id, "channel_id": self.channel_id,
                "author_user_id": self.author_user_id, "body": self.body,
                "created_at": self.created_at}


WORKSPACE_ROLES = ("owner", "member", "viewer")
MEMBER_STATES = ("invited", "active", "removed", "left")
TASK_STATES = ("todo", "doing", "done")


@dataclass(frozen=True, slots=True)
class WorkspaceRecord:
    workspace_id: str
    title: str
    brief: str
    owner_user_id: str
    origin_intro_id: str | None
    created_at: str
    updated_at: str
    version: int = 1

    def to_dict(self) -> dict[str, Any]:
        return {"workspace_id": self.workspace_id, "title": self.title,
                "brief": self.brief, "owner_user_id": self.owner_user_id,
                "origin_intro_id": self.origin_intro_id,
                "created_at": self.created_at, "updated_at": self.updated_at,
                "version": self.version}


@dataclass(frozen=True, slots=True)
class MemberRecord:
    workspace_id: str
    user_id: str
    role: str
    state: str
    invited_by: str | None
    invited_at: str
    joined_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"workspace_id": self.workspace_id, "user_id": self.user_id,
                "role": self.role, "state": self.state,
                "invited_by": self.invited_by, "invited_at": self.invited_at,
                "joined_at": self.joined_at}
