"""The drawings, as pictures a chat will show (2026-09-05).

src/product/rich.py renders these as SVG, and SVG is the better medium: it
carries live text at any size and never blurs. It is also, as Claude reported
when asked directly, not an image type any of these clients accept -- so every
drawing Resonance has ever sent into a chat arrived as markup and was shown as
nothing.

Both go now. The SVG stays for anything that can render it; these PNGs are
what a person actually sees. They say the same things from the same data, and
neither carries anything the JSON did not already have: no identifiers, no
locations beyond the coarse ones their owners consented to, no scores at more
precision than a person can act on.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from src.product import phrasing
from src.product.raster import (ACCENT, INK, INK_2, INK_3, PAPER_2, Canvas,
                                fit, wrap)

_CHARS = 46          # label width, in glyphs, at scale 1
_LINE = 20           # baseline-to-baseline for body text
_MARGIN = 16


def _heading(canvas: Canvas, title: str, subtitle: str = "") -> int:
    canvas.rectangle(0, 0, canvas.width, 44 if subtitle else 32, PAPER_2)
    canvas.text(_MARGIN, 9, fit(title, _CHARS + 8), INK, 1)
    if subtitle:
        canvas.text(_MARGIN, 26, fit(subtitle, _CHARS + 14), INK_2, 1)
    return 56 if subtitle else 44


def render_thought_png(thought_dna: Mapping[str, Any], *, topic: str = "") -> bytes:
    """The person's own thought, drawn as its causal spine.

    This is the one picture that exists before anyone has matched, which is
    most of the time for most people -- exactly when they are asking what they
    actually shared.
    """
    nodes = list(thought_dna.get("nodes") or [])
    relations = list(thought_dna.get("relations") or [])
    incoming: dict[str, list[Mapping[str, Any]]] = {}
    for relation in relations:
        incoming.setdefault(str(relation.get("target")), []).append(relation)

    width = 560
    height = 60 + max(1, len(nodes)) * 44 + _MARGIN
    canvas = Canvas(width, height)
    y = _heading(canvas, topic or "Your thought", "what causes what, as you described it")

    # A relation is drawn once both of its ends have a place on the page. Only
    # the ones running downwards were drawn before, so a link like "jittered
    # backoff PREVENTS request amplification" -- whose source sits below what
    # it points at -- left its node floating with no line to anything. Claude,
    # looking at the picture, said so: "separated by a gap with no connecting
    # line, a fourth node".
    outgoing: dict[str, list[Mapping[str, Any]]] = {}
    for relation in relations:
        outgoing.setdefault(str(relation.get("source")), []).append(relation)

    placed: dict[str, int] = {}

    def draw_link(relation: Mapping[str, Any], top: int, bottom: int) -> None:
        canvas.line(_MARGIN + 6, top + 10, _MARGIN + 6, bottom + 2, ACCENT, 2)
        canvas.text(_MARGIN + 18, min(top, bottom) + 22,
                    fit(str(relation.get("type", "")), 18), ACCENT, 1)

    for node in nodes:
        node_id = str(node.get("id"))
        for relation in incoming.get(node_id, []):
            source = str(relation.get("source"))
            if source in placed:
                draw_link(relation, placed[source], y)
        for relation in outgoing.get(node_id, []):
            target = str(relation.get("target"))
            if target in placed:
                # Runs upwards: draw it now that this end exists.
                draw_link(relation, placed[target], y)
        canvas.disc(_MARGIN + 6, y + 12, 5, ACCENT)
        canvas.text(_MARGIN + 22, y + 5, fit(str(node.get("label", "")), _CHARS),
                    INK, 1)
        role = str(node.get("role", ""))
        if role:
            canvas.text_right(width - _MARGIN, y + 6, fit(role, 14), INK_3, 1)
        placed[node_id] = y + 12
        y += 44
    return canvas.to_png()


def render_structure_png(match: Mapping[str, Any]) -> bytes:
    """Which of their ideas answers which of yours, and what held."""
    evidence = match.get("evidence") or {}
    pairs: Sequence[Mapping[str, Any]] = evidence.get("top_correspondences", [])
    scores = match.get("scores") or {}
    try:
        structural = f"{float(scores.get('structural', 0)):.2f}"
    except (TypeError, ValueError):
        structural = "?"

    width = 720
    height = 64 + max(1, len(pairs)) * 34 + _MARGIN
    canvas = Canvas(width, height)
    who = str(match.get("person_pseudonym", "someone"))
    # The engine's word for the relation, said the way the page and the
    # sentence beside this picture say it.
    kind = phrasing.classification(match.get("mode_classification"))
    y = _heading(canvas, f"{who} · {kind}",
                 f"structural agreement {structural} of 1 · "
                 f"{int(evidence.get('preserved_relation_count', 0) or 0)} links held")

    middle = width // 2
    for pair in pairs:
        canvas.text(_MARGIN, y, fit(str(pair.get("query_label", "")), 26), ACCENT, 1)
        canvas.line(middle - 40, y + 6, middle + 24, y + 6, INK_3, 2)
        canvas.text(middle + 36, y, fit(str(pair.get("candidate_label", "")), 26),
                    INK, 1)
        y += 34
    if not pairs:
        canvas.text(_MARGIN, y, "no correspondence to show", INK_2, 1)
    return canvas.to_png()


def render_map_png(rich: Mapping[str, Any]) -> bytes:
    """Where the consented matches are.

    Equirectangular, like the SVG: the same rounded coordinates, the same
    suppressed buckets. Location is presentation only and never influences a
    match, and the picture says so where it cannot be cropped away.
    """
    width, height = 720, 400
    map_height = 300
    canvas = Canvas(width, height)
    canvas.rectangle(0, 0, width, 26, PAPER_2)
    canvas.text(_MARGIN, 7,
                "coarse locations, shared on purpose; never used to match", INK_2, 1)

    def place(lat: float, lon: float) -> tuple[int, int]:
        x = int((float(lon) + 180.0) / 360.0 * (width - 2 * _MARGIN)) + _MARGIN
        y = int((90.0 - float(lat)) / 180.0 * (map_height - 40)) + 40
        return x, y

    # A faint graticule, so a dot has somewhere to be rather than floating.
    for degrees in range(-150, 180, 30):
        x, _ = place(0, degrees)
        canvas.line(x, 32, x, map_height, (0xE4, 0xDE, 0xD3), 1)
    for degrees in range(-60, 90, 30):
        _, y = place(degrees, 0)
        canvas.line(_MARGIN, y, width - _MARGIN, y, (0xE4, 0xDE, 0xD3), 1)

    drawn = 0
    for row in rich.get("matches") or []:
        location = (row.get("display") or {}).get("location") or {}
        if location.get("lat") is None or location.get("lon") is None:
            continue
        x, y = place(location["lat"], location["lon"])
        canvas.disc(x, y, 5, ACCENT)
        canvas.text(x + 11, y - 5,
                    fit(str(row.get("person_pseudonym", "")), 22), INK, 1)
        drawn += 1

    y = map_height + 20
    buckets = (rich.get("aggregation") or {}).get("buckets") or []
    if not drawn and not buckets:
        canvas.text(_MARGIN, y,
                    "nobody has offered to say where they are", INK_2, 1)
        return canvas.to_png()
    for bucket in buckets[:3]:
        label = fit(f"{bucket.get('region', 'somewhere')} · "
                    f"{bucket.get('count', 0)}", 40)
        canvas.text(_MARGIN, y, label, INK_2, 1)
        y += _LINE
    return canvas.to_png()
