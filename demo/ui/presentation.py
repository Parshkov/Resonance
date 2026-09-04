"""Pure presentation projection for the R9 demo UI.

This module is intentionally boring: it validates the public R8 DTO, takes
the first four non-hard-rejected matches in their existing order, and copies
wire values into a comparison signature. It contains no matching, scoring,
threshold, or ranking behavior.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

DISCOVERY_CONTRACT = "resonance-discovery/0.1"
CANONICAL_MODE = "analogical"
CANONICAL_K = 15
PRIMARY_MATCH_LIMIT = 4
PRIMARY_CLASSIFICATION = "analogical"
NEGATIVE_CLASSIFICATION = "negative"


def _is_discoverable(row: Mapping[str, Any]) -> bool:
    display = row.get("display")
    return isinstance(display, Mapping) and display.get("share_state") == "discoverable"


def validate_discovery(payload: Mapping[str, Any]) -> None:
    """Fail closed when a response is not the accepted R8 render contract."""
    if payload.get("contract_version") != DISCOVERY_CONTRACT:
        raise ValueError("unsupported discovery contract")
    query = payload.get("query")
    if not isinstance(query, Mapping) or query.get("mode") != CANONICAL_MODE:
        raise ValueError("canonical discovery mode is not analogical")
    if not isinstance(payload.get("matches"), list):
        raise ValueError("discovery response is missing matches[]")
    if not isinstance(payload.get("rejected"), list):
        raise ValueError("discovery response is missing rejected[]")


def primary_matches(
    payload: Mapping[str, Any], limit: int = PRIMARY_MATCH_LIMIT
) -> tuple[Mapping[str, Any], ...]:
    """Return the first flagship analogues without sorting or rescoring.

    Analogical resonances come first (the R9 presentation rule). A live
    person's thought may resonate only directly or approximately (same
    domain); those are resonances too, so when fewer than `limit` analogues
    exist the remaining slots take the next eligible non-negative matches in
    backend order rather than rendering nothing.
    """
    validate_discovery(payload)
    eligible: list[Mapping[str, Any]] = []
    for match in payload["matches"]:
        if not isinstance(match, Mapping):
            raise ValueError("matches[] entries must be objects")
        if not _is_discoverable(match):
            continue
        if match.get("hard_rejection") is not None:
            continue
        if match.get("mode_classification") == NEGATIVE_CLASSIFICATION:
            continue
        eligible.append(match)
    selected = [m for m in eligible if m.get("mode_classification") == PRIMARY_CLASSIFICATION][:limit]
    for match in eligible:
        if len(selected) >= limit:
            break
        if match not in selected:
            selected.append(match)
    return tuple(selected)


def remaining_match_count(payload: Mapping[str, Any]) -> int:
    """Count useful backend rows not emphasized in the competition frame."""
    visible = [
        match for match in payload["matches"]
        if isinstance(match, Mapping)
        and _is_discoverable(match)
        and match.get("hard_rejection") is None
    ]
    return max(0, len(visible) - len(primary_matches(payload)))


def visible_signature(payload: Mapping[str, Any]) -> tuple[dict[str, Any], ...]:
    """Exact payload-derived values used to compare LIVE with REPLAY."""
    signature = []
    for match in primary_matches(payload):
        signature.append({
            "match_id": match["match_id"],
            "person_pseudonym": match["person_pseudonym"],
            "session_id": match["session_id"],
            "mode_classification": match["mode_classification"],
            "structural": match["scores"]["structural"],
            "confidence": match["confidence"],
            "display": match["display"],
            "evidence": match["evidence"],
        })
    return tuple(signature)


def first_contradiction(payload: Mapping[str, Any]) -> Mapping[str, Any] | None:
    """Expose one backend-rejected item on a separate contradiction rail."""
    rejected: Sequence[Mapping[str, Any]] = payload["rejected"]
    for row in rejected:
        if _is_discoverable(row) and row.get("hard_rejection") is not None:
            return row
    return None
