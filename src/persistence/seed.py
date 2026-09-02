"""Seed and synthetic-pilot helpers.

The accepted R7 JSONL corpus is an import fixture only. It is never itself the
product database. Seed operations are create-only: rerunning a fixture import
never overwrites live user/session consent or presentation state.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Mapping

from demo.corpus.discovery import load_sessions
from src.graph import ThoughtGraph

from .errors import PersistenceConflictError
from .models import ConsentState
from .service import LiveCorpusService, thought_sha256


def _assert_seed_identity(existing, *, user_id: str, thought_dna: Mapping[str, Any]) -> None:
    if existing.user_id != user_id:
        raise PersistenceConflictError(
            f"seed session {existing.session_id!r} already belongs to {existing.user_id!r}"
        )
    incoming_hash = thought_sha256(thought_dna)
    if existing.thought_dna_sha256 != incoming_hash:
        raise PersistenceConflictError(
            f"seed session {existing.session_id!r} already exists with different Thought DNA"
        )


def seed_r7(service: LiveCorpusService, sessions: list[Mapping[str, Any]] | None = None) -> int:
    """Create missing R7 fixture records, never overwrite existing product state."""
    records = list(sessions) if sessions is not None else load_sessions()
    for session in records:
        person = session["person"]
        if service.get_user(person["person_id"]) is None:
            service.create_user(
                person["person_id"],
                display_label=person["display_label"],
                avatar_placeholder=person["avatar_placeholder"],
                rebuild=False,
            )
        existing = service.get_session(session["session_id"])
        if existing is not None:
            _assert_seed_identity(
                existing,
                user_id=person["person_id"],
                thought_dna=session["thought_dna"],
            )
            continue
        provenance = session["record_provenance"]
        service.create_session(
            session_id=session["session_id"],
            user_id=person["person_id"],
            thought_dna=session["thought_dna"],
            consent=session["consent"],
            location=session["location"],
            presentation=session["presentation"],
            record_kind=provenance["record_kind"],
            builder_id=provenance["builder_id"],
            notes=provenance["notes"],
            rebuild=False,
        )
    service.rebuild_index()
    return len(records)


def minimal_thought(thought_id: str, label: str = "heat") -> dict[str, Any]:
    """Valid synthetic manual Thought DNA used only for persistence smoke tests."""
    text = f"{label} accumulation causes failure"
    sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
    payload = {
        "schema_version": "thought-dna/0.1",
        "thought_id": thought_id,
        "source": {"text": text, "sha256": sha},
        "provenance": {"kind": "manual", "extractor": None, "human_id": "r11-pilot"},
        "nodes": [
            {
                "id": "n1",
                "label": label,
                "role": "mechanism",
                "spans": [],
                "extract_conf": 1.0,
                "atomic": True,
                "assertion": "asserted",
                "modality": "actual",
            },
            {
                "id": "n2",
                "label": "failure",
                "role": "outcome",
                "spans": [],
                "extract_conf": 1.0,
                "atomic": True,
                "assertion": "asserted",
                "modality": "actual",
            },
        ],
        "relations": [
            {
                "id": "r1",
                "source": "n1",
                "target": "n2",
                "type": "causes",
                "extract_conf": 1.0,
                "spans": [],
                "assertion": "asserted",
                "modality": "actual",
            }
        ],
    }
    return ThoughtGraph.from_dict(payload).to_dict()


def seed_pilot_scale(service: LiveCorpusService, n: int = 100) -> int:
    """Create missing synthetic pilot records without rewriting existing rows."""
    default_location = {
        "kind": "synthetic_coarse",
        "region": "TestRegion",
        "city": "TestCity",
        "lat": 10.0,
        "lon": 20.0,
        "precision": "city",
    }
    default_presentation = {
        "domain": "pilot",
        "topic": "scale-smoke",
        "cluster_id": "pilot-cluster",
    }
    for i in range(n):
        user_id = f"person-pilot-{i:04d}"
        session_id = f"ses-pilot-{i:04d}"
        thought_id = f"thought-pilot-{i:04d}"
        share = i % 17 != 0
        if service.get_user(user_id) is None:
            service.create_user(
                user_id,
                display_label=f"Pilot {i:04d}",
                avatar_placeholder="pilot",
                rebuild=False,
            )
        thought = minimal_thought(thought_id, label=f"signal-{i % 11}")
        existing = service.get_session(session_id)
        if existing is not None:
            _assert_seed_identity(existing, user_id=user_id, thought_dna=thought)
            continue
        service.create_session(
            session_id=session_id,
            user_id=user_id,
            thought_dna=thought,
            consent=ConsentState(
                share_enabled=share,
                share_thought_dna=share,
                share_coarse_location=i % 3 == 0,
                share_display_profile=True,
            ),
            location=default_location,
            presentation=default_presentation,
            record_kind="synthetic",
            builder_id="r11-pilot-scale",
            notes="synthetic persistence scale seed",
            rebuild=False,
        )
    service.rebuild_index()
    return n


def default_sqlite_path(root: Path | None = None) -> Path:
    base = root or Path.cwd()
    return base / "var" / "resonance-pilot.sqlite"
