"""Shared SQL helpers and row mapping. Dialect-agnostic on purpose."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from .models import (
    PERSISTENCE_SCHEMA_VERSION,
    AuditEvent,
    ConsentState,
    SessionRecord,
    UserRecord,
)

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


def load_migration_sql() -> list[tuple[str, str]]:
    files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    out: list[tuple[str, str]] = []
    for path in files:
        out.append((path.stem, path.read_text(encoding="utf-8")))
    return out


def dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def loads(value: str | None, default: Any = None) -> Any:
    if value is None:
        return default
    return json.loads(value)


def row_user(row: Mapping[str, Any]) -> UserRecord:
    return UserRecord(
        user_id=row["user_id"],
        display_label=row["display_label"],
        avatar_placeholder=row["avatar_placeholder"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        revoked_at=row["revoked_at"],
    )


def row_session(row: Mapping[str, Any]) -> SessionRecord:
    return SessionRecord(
        session_id=row["session_id"],
        user_id=row["user_id"],
        thought_id=row["thought_id"],
        schema_version=row["schema_version"],
        thought_dna=loads(row["thought_dna"]),
        thought_dna_sha256=row["thought_dna_sha256"],
        thought_dna_schema_version=row["thought_dna_schema_version"],
        consent=ConsentState(
            share_enabled=bool(row["share_enabled"]),
            share_thought_dna=bool(row["share_thought_dna"]),
            share_coarse_location=bool(row["share_coarse_location"]),
            share_display_profile=bool(row["share_display_profile"]),
        ),
        location=loads(row["location_json"]),
        presentation=loads(row["presentation_json"]),
        record_kind=row["record_kind"],
        builder_id=row["builder_id"],
        notes=row["notes"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        revoked_at=row["revoked_at"],
        deleted_at=row["deleted_at"],
    )


def row_audit(row: Mapping[str, Any]) -> AuditEvent:
    return AuditEvent(
        event_id=row["event_id"],
        event_type=row["event_type"],
        user_id=row["user_id"],
        session_id=row["session_id"],
        payload=loads(row["payload_json"], default={}),
        created_at=row["created_at"],
    )


def session_params(session: SessionRecord) -> tuple[Any, ...]:
    c = session.consent
    return (
        session.session_id,
        session.user_id,
        session.thought_id,
        session.schema_version,
        dumps(session.thought_dna),
        session.thought_dna_sha256,
        session.thought_dna_schema_version,
        int(c.share_enabled),
        int(c.share_thought_dna),
        int(c.share_coarse_location),
        int(c.share_display_profile),
        dumps(session.location),
        dumps(session.presentation),
        session.record_kind,
        session.builder_id,
        session.notes,
        session.created_at,
        session.updated_at,
        session.revoked_at,
        session.deleted_at,
    )


def export_document(
    *,
    backend: str,
    users: list[UserRecord],
    sessions: list[SessionRecord],
    audit: list[AuditEvent],
) -> dict[str, Any]:
    return {
        "schema_version": PERSISTENCE_SCHEMA_VERSION,
        "backend": backend,
        "users": [u.to_dict() for u in users],
        "sessions": [s.to_dict() for s in sessions],
        "audit": [e.to_public_dict() for e in audit],
    }
