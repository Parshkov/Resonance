"""Deterministic presentation projection over an R8 discovery payload.

The projection may filter rows for the competition highlight strip using an
explicit rule on already-ranked backend fields. It never sorts by score,
never recomputes scores, and never invents matches.
"""

from __future__ import annotations

from typing import Any

from .contract import (
    CONTRACT_VERSION,
    FEATURE_CLASSIFICATION,
    FEATURE_LIMIT,
    INTRO_STATUS,
    PINNED_K,
    PINNED_MODE,
    QUERY_SESSION_ID,
    QUERY_THOUGHT_ID,
)


QUERY_CHROME = {
    "session_id": QUERY_SESSION_ID,
    "thought_id": QUERY_THOUGHT_ID,
    "person_pseudonym": "Aria K.",
    "topic": "plasma lens thermal bloom",
    "domain": "plasma-optics",
    "share_state": "Shared with Resonance",
    "location": {
        "city": "Portland",
        "region": "Pacific Northwest",
        "lat": 45.5,
        "lon": -122.7,
        "kind": "synthetic_coarse",
    },
    "nodes": [
        {"id": "n0", "label": "plasma lens heat", "role": "problem"},
        {"id": "n1", "label": "ionization cascade", "role": "mechanism"},
        {"id": "n2", "label": "beam wander", "role": "state"},
        {"id": "n3", "label": "aperture budget", "role": "constraint"},
        {"id": "n4", "label": "adaptive cooling", "role": "method"},
    ],
    "conversation": [
        {"who": "Aria", "text": "The plasma lens is dumping heat into the ionization cascade. Beam wander is eating the aperture budget."},
        {"who": "Agent", "text": "Shared with Resonance. Looking for thoughts with the same accumulating-intermediary structure — even in other domains."},
    ],
}


def _why(match: dict[str, Any]) -> str:
    evidence = match.get("evidence") or {}
    top = evidence.get("top_correspondences") or []
    if not top:
        return "Backend mapping evidence not included in this row."
    first = top[0]
    q = first.get("query_label") or first.get("query_node")
    c = first.get("candidate_label") or first.get("candidate_node")
    mapped = evidence.get("mapped_node_count")
    preserved = evidence.get("preserved_relation_count")
    return f"{q} ↔ {c} · {mapped} mapped nodes, {preserved} preserved relations"


def _card(match: dict[str, Any], *, featured: bool) -> dict[str, Any]:
    display = match.get("display") or {}
    location = display.get("location")
    scores = match.get("scores") or {}
    return {
        "match_id": match.get("match_id"),
        "session_id": match.get("session_id"),
        "person_pseudonym": match.get("person_pseudonym"),
        "topic": display.get("topic"),
        "domain": display.get("domain"),
        "cluster_id": display.get("cluster_id"),
        "share_state": display.get("share_state"),
        "location": dict(location) if location else None,
        "mode_classification": match.get("mode_classification"),
        "hard_rejection": match.get("hard_rejection"),
        "scores": dict(scores),
        "structural": scores.get("structural"),
        "confidence": match.get("confidence"),
        "evidence": match.get("evidence") or {},
        "why": _why(match),
        "featured": featured,
        "intro_status": INTRO_STATUS,
    }


def project(payload: dict[str, Any], *, source: str) -> dict[str, Any]:
    if payload.get("contract_version") != CONTRACT_VERSION:
        raise ValueError(f"unexpected contract_version: {payload.get('contract_version')!r}")
    matches = list(payload.get("matches") or [])
    rejected = list(payload.get("rejected") or [])
    featured_src = [
        m for m in matches
        if m.get("mode_classification") == FEATURE_CLASSIFICATION
        and m.get("hard_rejection") is None
    ][:FEATURE_LIMIT]
    featured_ids = {m.get("session_id") for m in featured_src}
    featured = [_card(m, featured=True) for m in featured_src]
    other = [_card(m, featured=False) for m in matches if m.get("session_id") not in featured_ids]
    contradictions = [_card(m, featured=False) for m in rejected]
    markers = []
    qloc = QUERY_CHROME["location"]
    markers.append({
        "kind": "query",
        "session_id": QUERY_SESSION_ID,
        "label": QUERY_CHROME["person_pseudonym"],
        "lat": qloc["lat"],
        "lon": qloc["lon"],
        "region": qloc["region"],
    })
    for card in featured + other + contradictions:
        loc = card.get("location") or {}
        if loc.get("lat") is None or loc.get("lon") is None:
            continue
        markers.append({
            "kind": "contradiction" if card in contradictions else (
                "featured" if card["featured"] else "other"
            ),
            "session_id": card["session_id"],
            "label": card["person_pseudonym"],
            "lat": loc["lat"],
            "lon": loc["lon"],
            "region": loc.get("region"),
            "classification": card["mode_classification"],
        })
    return {
        "source": source,
        "mode_indicator": source.upper(),
        "pinned": {"mode": PINNED_MODE, "k": PINNED_K, "contract": CONTRACT_VERSION},
        "query": QUERY_CHROME,
        "provenance": (payload.get("query") or {}).get("provenance") or {},
        "featured": featured,
        "other_matches": other,
        "contradictions": contradictions,
        "aggregation": payload.get("aggregation") or {},
        "unsupported_fields": list(payload.get("unsupported_fields") or []),
        "markers": markers,
        "counts": {
            "featured": len(featured),
            "other_matches": len(other),
            "contradictions": len(contradictions),
            "backend_matches": len(matches),
            "backend_rejected": len(rejected),
        },
        "intro_status": INTRO_STATUS,
    }


def featured_session_ids(view: dict[str, Any]) -> list[str]:
    return [card["session_id"] for card in view["featured"]]
