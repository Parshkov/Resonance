"""Consent-aware demo discovery over the accepted Resonance engine.

Presentation metadata is joined after matching. It is never passed into
ingest/index/find/compare. Hidden sessions are not indexed.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from src.engine import ResonanceEngine
from src.graph import ThoughtGraph
from src.interfaces import RESONANCE_MODES, require_mode

from .validate import CORPUS_SCHEMA_VERSION, validate_corpus

PACKAGE_DIR = Path(__file__).resolve().parent
SESSIONS_PATH = PACKAGE_DIR / "sessions.jsonl"
MANIFEST_PATH = PACKAGE_DIR / "manifest.json"


def is_discoverable(session: Mapping[str, Any]) -> bool:
    consent = session["consent"]
    return bool(consent["share_enabled"] and consent["share_thought_dna"])


def load_sessions(path: Path | None = None) -> list[dict[str, Any]]:
    target = path or SESSIONS_PATH
    sessions = [json.loads(line) for line in target.read_text(encoding="utf-8").splitlines() if line.strip()]
    validate_corpus(sessions)
    return sessions


def presentation_view(session: Mapping[str, Any]) -> dict[str, Any]:
    """Public fields a client may render. Location is omitted unless consented."""
    consent = session["consent"]
    person = session["person"] if consent["share_display_profile"] else {
        "person_id": session["person"]["person_id"],
        "display_label": "anonymous",
        "avatar_placeholder": "anonymous",
    }
    view = {
        "session_id": session["session_id"],
        "thought_id": session["thought_dna"]["thought_id"],
        "person": dict(person),
        "presentation": dict(session["presentation"]),
        "record_kind": session["record_provenance"]["record_kind"],
    }
    if consent["share_coarse_location"]:
        loc = session["location"]
        view["location"] = {
            "kind": loc["kind"],
            "region": loc["region"],
            "city": loc["city"],
            "lat": loc["lat"],
            "lon": loc["lon"],
            "precision": loc["precision"],
        }
    return view


def index_discoverable(engine: ResonanceEngine, sessions: Iterable[Mapping[str, Any]]) -> tuple[str, ...]:
    indexed: list[str] = []
    for session in sessions:
        if not is_discoverable(session):
            continue
        graph = ThoughtGraph.from_dict(session["thought_dna"])
        engine.index(graph)
        indexed.append(graph.thought_id)
    return tuple(indexed)


def discover(
    query: Mapping[str, Any] | ThoughtGraph,
    sessions: Iterable[Mapping[str, Any]],
    *,
    mode: str,
    k: int = 20,
    engine: ResonanceEngine | None = None,
) -> list[dict[str, Any]]:
    """Return visualization-ready hits for discoverable sessions only.

    Ranking and classification come from the engine. Session metadata is
    attached afterwards and cannot change the order.
    """
    require_mode(mode)
    if mode not in RESONANCE_MODES:
        raise ValueError(f"unsupported mode {mode!r}")
    records = list(sessions)
    by_thought = {s["thought_dna"]["thought_id"]: s for s in records if is_discoverable(s)}
    if isinstance(query, ThoughtGraph):
        query_graph = query
    elif isinstance(query, Mapping) and "thought_dna" in query:
        query_graph = ThoughtGraph.from_dict(query["thought_dna"])
    else:
        query_graph = ThoughtGraph.from_dict(query)
    engine = engine or ResonanceEngine()
    index_discoverable(engine, records)
    hits = []
    for hit in engine.find(query_graph, mode=mode, k=k):
        session = by_thought.get(hit.candidate.candidate_id)
        if session is None:
            continue
        if session["thought_dna"]["thought_id"] == query_graph.thought_id:
            continue
        hits.append({
            "session": presentation_view(session),
            "thought_id": hit.candidate.candidate_id,
            "classification": hit.verification.classification,
            "structural": hit.verification.components.structural,
            "semantic": hit.verification.components.semantic,
            "hard_rejection": hit.verification.hard_rejection,
            "mapping": [
                {"query_node": m.query_node, "candidate_node": m.candidate_node}
                for m in hit.verification.mapping
            ],
        })
    return hits
