"""R13B rich results: versioned structured result + deterministic visuals.

Presentation only. Every field comes from the already-authorized R13 live
payload (order/scores byte-unchanged); visuals are rendered exclusively from
that same consent-filtered data, deterministically (no clocks, no randomness),
so a rendered image can never contain more than the JSON the same viewer got.
"""

from __future__ import annotations

import hashlib
import html
import json
from typing import Any, Mapping, Sequence

from src.product.service import LOCATION_NOTE

RICH_RESULT_CONTRACT = "resonance-rich-result/0.1"

# Declared output schema for MCP structuredContent (current MCP content model).
RICH_RESULT_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "resonance-rich-result/0.1",
    "type": "object",
    "required": ["contract_version", "result_id", "query_ref", "freshness",
                 "provenance", "matches", "aggregation", "location_note"],
    "properties": {
        "contract_version": {"const": RICH_RESULT_CONTRACT},
        "result_id": {"type": "string", "pattern": "^result-[0-9a-f]{24}$"},
        "query_ref": {
            "type": "object",
            "required": ["session_id", "thought_id", "mode"],
            "properties": {"session_id": {"type": "string"},
                           "thought_id": {"type": "string"},
                           "mode": {"type": "string"}},
        },
        "freshness": {"type": "object"},
        "provenance": {"type": "object"},
        "matches": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["session_id", "person_pseudonym",
                             "mode_classification", "scores", "confidence",
                             "evidence", "display", "intro_state", "ui_ref"],
                "properties": {
                    "intro_state": {
                        "type": "string",
                        # `requested`/`accepted` arrive with the R14
                        # collaboration records; the enum reserves them now.
                        "enum": ["available", "unavailable",
                                 "requested", "accepted"],
                    },
                    "ui_ref": {"type": "string"},
                },
            },
        },
        "rejected": {"type": "array"},
        "aggregation": {"type": "object"},
        "location_note": {"type": "string"},
    },
}


def _intro_state(policy_source: Any, candidate_session: str,
                 viewer_id: str | None = None) -> str:
    """Connection state from the R12B-authoritative consent source.

    Blocked pairs never reach a rich result (rows are dropped upstream), and
    contact details do not exist anywhere in the pipeline. With R14's durable
    intro records present, a live `requested`/`accepted` state between the
    viewer and the candidate's owner takes precedence over consent-derived
    availability — one derivation function, no second source of truth.
    """
    if viewer_id:
        owner = policy_source.owner_of("session", candidate_session)
        repo = getattr(getattr(policy_source, "backend", None), "repo", None)
        if owner and repo is not None and hasattr(repo, "latest_intro_between"):
            latest = repo.latest_intro_between(viewer_id, owner)
            if latest is not None and latest.state in {"requested", "accepted"}:
                return latest.state
    consent = policy_source.session_consent(candidate_session)
    if consent and consent.get("allow_intro_requests"):
        return "available"
    return "unavailable"


def build_rich_result(payload: Mapping[str, Any], *, policy_source: Any,
                      viewer_id: str | None = None) -> dict[str, Any]:
    """Wrap an authorized R13 discover payload into the versioned rich shape.

    Rows pass through with order and scores untouched; the wrapper only adds
    `intro_state` and a stable human-UI reference per row.
    """
    query = dict(payload.get("query", {}))
    result_id = str(payload["result_id"])

    def enrich(row: Mapping[str, Any]) -> dict[str, Any]:
        session_id = str(row.get("session_id", ""))
        out = dict(row)
        out["intro_state"] = _intro_state(policy_source, session_id, viewer_id)
        out["ui_ref"] = f"/#match={result_id}:{session_id}"
        return out

    return {
        "contract_version": RICH_RESULT_CONTRACT,
        "result_id": result_id,
        "query_ref": {
            "session_id": str(payload.get("query_session_id", "")) or
                          str(query.get("session_id", "")),
            "thought_id": str(query.get("thought_id", "")),
            "mode": str(query.get("mode", "")),
        },
        "freshness": dict(payload.get("freshness", {})),
        "provenance": dict(query.get("provenance", {})),
        "matches": [enrich(row) for row in payload.get("matches", [])],
        "rejected": [enrich(row) for row in payload.get("rejected", [])],
        "aggregation": dict(payload.get("aggregation", {})),
        "location_note": str(payload.get("location_note", LOCATION_NOTE)),
        "shape_note": str(payload.get("shape_note", "") or ""),
    }


# ---------------------------------------------------------------------------
# deterministic visuals — derived ONLY from the authorized structured result
# ---------------------------------------------------------------------------
_MAP_W, _MAP_H = 1000, 520
_BAR_AREA_Y = 470


def _esc(text: str) -> str:
    return html.escape(str(text), quote=True)


def _project(lat: float, lon: float) -> tuple[float, float]:
    x = (lon + 180.0) / 360.0 * _MAP_W
    y = (90.0 - lat) / 180.0 * (_BAR_AREA_Y - 40) + 20
    return round(x, 1), round(y, 1)



# The drawings use the product's own light palette (the tokens the site and
# the consent page share). They were hard-coded dark, which read as a terminal
# rather than as Resonance, and contradicted the theme a person had chosen.
# An SVG sent into a chat cannot follow that choice -- there is no viewer to
# ask -- so it carries its own ground and stays legible whatever the chat
# around it is doing.

def _short(value: Any) -> str:
    """A score a person can read. 0.7071067811865476 printed inside a picture
    is the same wall of digits as printing the JSON, only harder to skip."""
    try:
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        return str(value)


def render_map_svg(rich: Mapping[str, Any]) -> str:
    """Equirectangular map of CONSENTED match locations + k-anonymous buckets.

    Inputs are only fields the same viewer already received in JSON:
    per-match `display.location` (present only with candidate consent) and the
    suppressed aggregation buckets. Pseudonyms label points; session ids and
    any other identifiers never enter the image. Deterministic: sorted inputs,
    no clocks, no randomness.
    """
    parts: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {_MAP_W} {_MAP_H}" '
        f'role="img" aria-label="Resonance coarse map (presentation only)">',
        f'<rect width="{_MAP_W}" height="{_MAP_H}" fill="#f4f1eb"/>',
        f'<rect width="{_MAP_W}" height="{_BAR_AREA_Y}" fill="#ece7de"/>',
        '<text x="12" y="18" fill="#57524a" font-size="13" '
        'font-family="monospace">coarse locations are presentation-only and '
        'never influence matching</text>',
    ]
    points = []
    for row in rich.get("matches", []):
        display = row.get("display") or {}
        location = display.get("location")
        if not location:
            continue
        lat, lon = location.get("lat"), location.get("lon")
        if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
            continue
        points.append((str(row.get("person_pseudonym", "anonymous")),
                       float(lat), float(lon)))
    for pseudonym, lat, lon in sorted(points):
        x, y = _project(lat, lon)
        parts.append(f'<circle cx="{x}" cy="{y}" r="6" fill="#8a5a2b" '
                     f'stroke="#1d1a16" stroke-width="1.5"/>')
        parts.append(f'<text x="{x + 9}" y="{y + 4}" fill="#1d1a16" '
                     f'font-size="12" font-family="monospace">{_esc(pseudonym)}</text>')
    buckets = sorted(
        (str(b.get("bucket_id", "")), int(b.get("count", 0)))
        for b in (rich.get("aggregation", {}) or {}).get("buckets", [])
    )
    bar_x = 12
    for bucket_id, count in buckets:
        width = 24 + count * 18
        parts.append(f'<rect x="{bar_x}" y="{_BAR_AREA_Y + 10}" width="{width}" '
                     f'height="14" fill="#8a5a2b"/>')
        parts.append(f'<text x="{bar_x + 4}" y="{_BAR_AREA_Y + 21}" fill="#1d1a16" '
                     f'font-size="11" font-family="monospace">'
                     f'{_esc(bucket_id)}: {count}</text>')
        bar_x += width + 10
    if not buckets:
        parts.append(f'<text x="12" y="{_BAR_AREA_Y + 21}" fill="#57524a" '
                     f'font-size="11" font-family="monospace">no aggregate '
                     f'buckets above the anti-inference minimum</text>')
    parts.append("</svg>")
    return "".join(parts)


def render_structure_svg(match: Mapping[str, Any]) -> str:
    """Structural comparison diagram for one authorized match row.

    Renders the correspondence pairs and preserved-relation counts from the
    row's own evidence block — nothing outside what the viewer already has.
    """
    evidence = match.get("evidence") or {}
    pairs: Sequence[Mapping[str, Any]] = evidence.get("top_correspondences", [])
    scores = match.get("scores") or {}
    height = 120 + max(1, len(pairs)) * 34
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 {height}" '
        f'role="img" aria-label="Structural correspondence diagram">',
        f'<rect width="900" height="{height}" fill="#f4f1eb"/>',
        f'<text x="12" y="24" fill="#1d1a16" font-size="15" '
        f'font-family="monospace">{_esc(match.get("person_pseudonym", "anonymous"))} '
        f'&#183; {_esc(match.get("mode_classification", ""))} &#183; structural '
        f'{_esc(_short(scores.get("structural", "")))}</text>',
        '<text x="12" y="46" fill="#57524a" font-size="12" font-family="monospace">'
        f'mapped nodes: {int(evidence.get("mapped_node_count", 0))} &#183; '
        f'preserved relations: {int(evidence.get("preserved_relation_count", 0))} '
        f'&#183; contradictions: {int(evidence.get("contradiction_count", 0))}</text>',
    ]
    y = 84
    for pair in pairs:
        query_label = _esc(pair.get("query_label", ""))
        candidate_label = _esc(pair.get("candidate_label", ""))
        parts.append(f'<text x="12" y="{y}" fill="#8a5a2b" font-size="13" '
                     f'font-family="monospace" text-anchor="start">{query_label}</text>')
        parts.append(f'<line x1="330" y1="{y - 5}" x2="560" y2="{y - 5}" '
                     f'stroke="#8a5a2b" stroke-width="2"/>')
        parts.append(f'<text x="570" y="{y}" fill="#1d1a16" font-size="13" '
                     f'font-family="monospace">{candidate_label}</text>')
        y += 34
    parts.append("</svg>")
    return "".join(parts)



def render_thought_svg(thought_dna: Mapping[str, Any], *, topic: str = "") -> str:
    """The person's own thought, drawn as its causal spine.

    The site has shown someone their own structure since the redesign; a chat
    could only describe it. This is the same picture, and it is the one drawing
    that exists before anybody has matched -- which is most of the time, for
    most people, and exactly when they are wondering what they actually shared.

    Only the labels and relations the person already approved in the preview
    are drawn. No ids, no scores, no other person.
    """
    nodes = list(thought_dna.get("nodes") or [])
    relations = list(thought_dna.get("relations") or [])
    by_id = {str(n.get("id")): n for n in nodes}
    order = [str(n.get("id")) for n in nodes]
    width = 900
    row = 52
    top = 64 if topic else 34
    height = top + max(1, len(nodes)) * row + 16
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'role="img" aria-label="Your thought, drawn as its causal spine">',
        f'<rect width="{width}" height="{height}" fill="#f4f1eb"/>',
    ]
    if topic:
        parts.append(f'<text x="24" y="34" fill="#1d1a16" font-size="17" '
                     f'font-family="monospace">{_esc(topic)}</text>')
        parts.append(f'<text x="24" y="54" fill="#57524a" font-size="12" '
                     f'font-family="monospace">what causes what, as you '
                     f'described it</text>')
    # One label per line, in the order the person gave them, with the relation
    # that leads into each drawn beside the line above it.
    # A relation is drawn once both of its ends have a place. Only the ones
    # running downwards were, so "backoff PREVENTS amplification" -- whose
    # source sits below what it points at -- left its node with no line to
    # anything. Claude, ChatGPT and Grok each said so, unprompted, looking at
    # the same drawing; the PNG was fixed first and this one was missed.
    incoming = {}
    outgoing = {}
    for rel in relations:
        incoming.setdefault(str(rel.get("target")), []).append(rel)
        outgoing.setdefault(str(rel.get("source")), []).append(rel)
    y = top + 26
    centres = {}

    def link(rel, top_y, bottom_y):
        parts.append(f'<line x1="34" y1="{top_y + 8}" x2="34" '
                     f'y2="{bottom_y - 16}" stroke="#8a5a2b" stroke-width="2"/>')
        parts.append(f'<text x="46" y="{bottom_y - 18}" fill="#8a5a2b" '
                     f'font-size="12" font-family="monospace">'
                     f'{_esc(str(rel.get("type", "")))}</text>')

    for node_id in order:
        node = by_id.get(node_id) or {}
        label = _esc(str(node.get("label", "")))
        role = _esc(str(node.get("role", "")))
        for rel in incoming.get(node_id, []):
            source = str(rel.get("source"))
            if source in centres:
                link(rel, centres[source], y)
        for rel in outgoing.get(node_id, []):
            target = str(rel.get("target"))
            if target in centres:
                # Runs upwards: draw it now that this end exists.
                link(rel, centres[target], y)
        parts.append(f'<circle cx="34" cy="{y}" r="5" fill="#8a5a2b"/>')
        parts.append(f'<text x="52" y="{y + 5}" fill="#1d1a16" font-size="15" '
                     f'font-family="monospace">{label}</text>')
        if role:
            parts.append(f'<text x="{width - 24}" y="{y + 5}" fill="#57524a" '
                         f'font-size="12" font-family="monospace" '
                         f'text-anchor="end">{role}</text>')
        centres[node_id] = y
        y += row
    parts.append("</svg>")
    return "".join(parts)


def svg_sha256(svg: str) -> str:
    return hashlib.sha256(svg.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# MCP content-model packaging (structuredContent + rich content blocks)
# ---------------------------------------------------------------------------
def to_mcp_content(rich: Mapping[str, Any], *, map_svg: str | None = None,
                   structure_svg: str | None = None) -> dict[str, Any]:
    """Package per the current MCP content model.

    `structuredContent` always carries the complete result (declared schema:
    RICH_RESULT_SCHEMA); a text block keeps image-less clients fully usable;
    visuals ride as EmbeddedResource blocks only when provided.
    """
    matches = rich.get("matches", [])
    lines = [f"{len(matches)} resonance match(es) for "
             f"{rich.get('query_ref', {}).get('thought_id', '')}"]
    for row in matches[:5]:
        scores = row.get("scores") or {}
        lines.append(
            f"- {row.get('person_pseudonym', 'anonymous')}: "
            f"{row.get('mode_classification', '')} "
            f"(structural {scores.get('structural', '')}, "
            f"intro {row.get('intro_state', '')})")
    lines.append(str(rich.get("location_note", "")))
    content: list[dict[str, Any]] = [{"type": "text", "text": "\n".join(lines)}]
    for name, svg in (("map", map_svg), ("structure", structure_svg)):
        if svg is None:
            continue
        content.append({
            "type": "resource",
            "resource": {
                "uri": f"resonance://visual/{name}/{rich.get('result_id', '')}",
                "mimeType": "image/svg+xml",
                "text": svg,
            },
        })
    return {
        "structuredContent": dict(rich),
        "content": content,
        "outputSchema": RICH_RESULT_SCHEMA,
    }
