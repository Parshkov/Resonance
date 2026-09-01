"""Consented presentation metadata for discovery (PROVISIONAL until the
R7-CORPUS schema freezes; strict-loaded so the freeze can only tighten it).

This module carries NO matching semantics: it says who may be shown and how,
never who matches whom.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

METADATA_SCHEMA_VERSION = "resonance-demo-metadata/0.1-provisional"

SHARE_STATES = ("hidden", "discoverable")


@dataclass(frozen=True)
class SessionProfile:
    session_id: str
    person_pseudonym: str
    share_state: str                       # hidden | discoverable
    location_bucket: str | None = None     # coarse/synthetic only
    location_shareable: bool = False
    topic_tag: str | None = None

    def __post_init__(self) -> None:
        if self.share_state not in SHARE_STATES:
            raise ValueError(f"share_state must be one of {SHARE_STATES}")
        if self.location_shareable and not self.location_bucket:
            raise ValueError("location_shareable requires a location_bucket")


_PROFILE_FIELDS = {"session_id", "person_pseudonym", "share_state",
                   "location_bucket", "location_shareable", "topic_tag"}


class ConsentRegistry:
    """session_id -> SessionProfile; strict, closed schema."""

    def __init__(self, profiles: dict[str, SessionProfile]):
        self._profiles = dict(profiles)

    @classmethod
    def from_payload(cls, payload: dict) -> "ConsentRegistry":
        if payload.get("schema_version") != METADATA_SCHEMA_VERSION:
            raise ValueError(
                f"unsupported metadata schema: {payload.get('schema_version')!r}")
        profiles: dict[str, SessionProfile] = {}
        for record in payload.get("sessions", []):
            extra = set(record) - _PROFILE_FIELDS
            missing = {"session_id", "person_pseudonym", "share_state"} - set(record)
            if extra or missing:
                raise ValueError(
                    f"closed metadata record mismatch: extra={sorted(extra)}, "
                    f"missing={sorted(missing)}")
            profile = SessionProfile(**record)
            if profile.session_id in profiles:
                raise ValueError(f"duplicate session_id {profile.session_id!r}")
            profiles[profile.session_id] = profile
        return cls(profiles)

    @classmethod
    def load(cls, path: Path) -> "ConsentRegistry":
        return cls.from_payload(json.loads(Path(path).read_text(encoding="utf-8")))

    def get(self, session_id: str) -> SessionProfile | None:
        return self._profiles.get(session_id)

    def discoverable(self, session_id: str) -> bool:
        profile = self._profiles.get(session_id)
        return bool(profile and profile.share_state == "discoverable")
