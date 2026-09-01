"""Consent/presentation adapter over the ACCEPTED R7 corpus schema
(resonance-demo-corpus/0.1).

Single source of consent truth: this module re-uses demo.corpus.discovery's
accepted primitives (is_discoverable, presentation_view) and only reshapes
their output for the discovery DTO. It carries NO matching semantics and NO
consent rules of its own.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from demo.corpus.discovery import is_discoverable, presentation_view
from demo.corpus.validate import CORPUS_SCHEMA_VERSION

METADATA_SCHEMA_VERSION = CORPUS_SCHEMA_VERSION      # frozen by R7 acceptance


@dataclass(frozen=True)
class SessionProfile:
    session_id: str                     # R7 session id
    thought_id: str                     # engine-side key
    person_pseudonym: str               # display_label via presentation_view
    share_state: str                    # hidden | discoverable (R7 rule)
    cluster_id: str
    topic: str
    domain: str
    location: Mapping[str, Any] | None  # R7 coarse location, only if consented


class ConsentRegistry:
    """thought_id -> SessionProfile derived from accepted R7 records."""

    def __init__(self, profiles: dict[str, SessionProfile]):
        self._profiles = dict(profiles)

    @classmethod
    def from_r7_sessions(cls, sessions: Iterable[Mapping[str, Any]]) -> "ConsentRegistry":
        profiles: dict[str, SessionProfile] = {}
        for session in sessions:
            thought_id = session["thought_dna"]["thought_id"]
            if not is_discoverable(session):
                # Hidden sessions get NO profile at all: nothing downstream
                # can even ask about them (R7 rule; defense in depth on top
                # of never indexing them).
                continue
            view = presentation_view(session)
            profiles[thought_id] = SessionProfile(
                session_id=view["session_id"],
                thought_id=thought_id,
                person_pseudonym=view["person"]["display_label"],
                share_state="discoverable",
                cluster_id=view["presentation"]["cluster_id"],
                topic=view["presentation"]["topic"],
                domain=view["presentation"]["domain"],
                location=view.get("location"))
        return cls(profiles)

    def get(self, thought_id: str) -> SessionProfile | None:
        return self._profiles.get(thought_id)

    def discoverable(self, thought_id: str) -> bool:
        return thought_id in self._profiles
