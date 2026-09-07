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
        # A column is as wide as the glyphs allow (8 px each at scale 1), so a
        # label of ordinary length is not cut to an ellipsis and misquoted.
        column = (middle - 40 - 2 * _MARGIN) // 8
        canvas.text(_MARGIN, y, fit(str(pair.get("query_label", "")), column), ACCENT, 1)
        canvas.line(middle - 40, y + 6, middle + 24, y + 6, INK_3, 2)
        canvas.text(middle + 36, y, fit(str(pair.get("candidate_label", "")), column),
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


# Kinds of match, coloured the way the page colours them: the same subject in
# the sage, another subject in the accent, not a resonance in grey.
_SAGE = (0x3F, 0x75, 0x48)
# One colour per polygon, so two thoughts are told apart even when the engine
# gives them the same verdict. The page colours by series for the same reason;
# the verdict is carried by the words in the legend, not by the ink.
_SERIES = ((0x7A, 0x2E, 0x6B), (0x2E, 0x5A, 0x7A), (0x3F, 0x75, 0x48),
           (0x8A, 0x5A, 0x2B), (0x6B, 0x3F, 0x2E), (0x4A, 0x4A, 0x7A),
           (0x7A, 0x6B, 0x2E), (0x2E, 0x7A, 0x6B))


# The engine's own dimensions, as radar axes -- the same seven, in the same
# order, with the same two inversions as `demo/ui/main.mjs` PROFILE_AXES, so
# that the picture in a chat and the picture on the page are one drawing.
# "More" always means "closer": contradiction and sign conflict are inverted.
PROFILE_AXES = (
    ("structural", "structure", lambda s: s.get("structural")),
    ("semantic", "meaning", lambda s: s.get("semantic")),
    ("r_direct", "direct links", lambda s: s.get("r_direct")),
    ("y_systematicity", "systematic", lambda s: s.get("y_systematicity")),
    ("coverage_containment", "coverage", lambda s: s.get("coverage_containment")),
    ("contradiction", "no contradiction", lambda s: 1 - _number(s.get("contradiction"))),
    ("h_sign_conflict", "same direction", lambda s: 1 - _number(s.get("h_sign_conflict"))),
)


def _number(value: Any) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


def _axis_value(scores: Mapping[str, Any], read) -> float:
    try:
        return _number(read(scores))
    except (TypeError, ValueError, AttributeError):
        return 0.0


def render_resonance_png(rich: Mapping[str, Any]) -> bytes:
    """The same radar the page draws, for a chat that can only show a picture.

    Seven axes, the engine's own dimensions, in the page's order and with the
    page's two inversions so that further out always means closer
    (`demo/ui/main.mjs`, PROFILE_AXES). One polygon per match, drawn over each
    other, exactly as the person sees on screen.

    This used to be a different drawing entirely -- dots on concentric rings,
    placed by the structural score alone. It told a different story from the
    page for the same data, and it could not show WHY two people were close or
    far, which is the whole point of showing the working. It also printed the
    same pseudonym twice when one person had two matching thoughts, with no
    way to tell which dot was which; each row now names the thought.
    """
    matches = [row for row in (rich.get("matches") or rich.get("matches_in_backend_order") or [])
               if (row.get("display") or {}).get("share_state", "discoverable") == "discoverable"
               and row.get("hard_rejection") is None]
    width, height = 720, 470
    canvas = Canvas(width, height)
    y = _heading(canvas, "how each person measures on every axis",
                 "further out is closer to you")
    if not matches:
        canvas.text(_MARGIN, y, "nobody has matched yet; the thought keeps looking", INK_2, 1)
        return canvas.to_png()

    import math
    cx, cy, R = 248, 60 + 190, 150
    n = len(PROFILE_AXES)

    def point(index: int, value: float) -> tuple[int, int]:
        angle = -math.pi / 2 + 2 * math.pi * index / n
        r = R * max(0.0, min(1.0, value))
        return int(cx + r * math.cos(angle)), int(cy + r * math.sin(angle))

    # rings and their ticks, as on the page
    for ring in (0.25, 0.5, 0.75, 1.0):
        corners = [point(i, ring) for i in range(n)]
        for i in range(n):
            a, b = corners[i], corners[(i + 1) % n]
            canvas.line(a[0], a[1], b[0], b[1], (0xD8, 0xD2, 0xC6), 1)
        if ring < 1.0:
            # on the upper-left diagonal, away from the vertical spoke a
            # polygon edge runs along
            tx, ty = point(0, ring)
            canvas.text(tx - 34, ty - 4, f"{ring:.2f}", INK_3, 1)
    for i in range(n):
        edge = point(i, 1.0)
        canvas.line(cx, cy, edge[0], edge[1], (0xE2, 0xDD, 0xD2), 1)
        label = PROFILE_AXES[i][1]
        lx, ly = point(i, 1.14)
        if abs(lx - cx) < 14:                      # straight up or straight down
            canvas.text(cx - 4 * len(label), ly - 4, label, INK_2, 1)
        elif lx < cx:                              # left half: end the text at the spoke
            canvas.text(max(4, lx - 8 * len(label)), ly - 4, label, INK_2, 1)
        else:                                      # right half: start at the spoke
            canvas.text(min(lx + 6, width - 8 * len(label) - 4), ly - 4, label, INK_2, 1)

    legend_y = 58
    for index, row in enumerate(matches[:8]):
        scores = row.get("scores") or {}
        kind = str(row.get("mode_classification") or "")
        colour = _SERIES[index % len(_SERIES)]
        values = [_axis_value(scores, read) for _key, _word, read in PROFILE_AXES]
        corners = [point(i, v) for i, v in enumerate(values)]
        for i in range(n):
            a, b = corners[i], corners[(i + 1) % n]
            canvas.line(a[0], a[1], b[0], b[1], colour, 2)
        for a in corners:
            canvas.disc(a[0], a[1], 3, colour)
        # the list on the right says which thought each polygon is
        topic = str((row.get("display") or {}).get("topic") or "").strip()
        canvas.disc(470, legend_y + 7, 5, colour)
        canvas.text(482, legend_y, fit(str(row.get("person_pseudonym") or ""), 29), INK, 1)
        if topic:
            canvas.text(482, legend_y + 14, fit(topic, 29), INK_2, 1)
            canvas.text(482, legend_y + 28, fit(phrasing.classification(kind), 29), INK_3, 1)
            legend_y += 46
        else:
            canvas.text(482, legend_y + 15, fit(phrasing.classification(kind), 29), INK_2, 1)
            legend_y += 34
        if legend_y > height - 46:
            break
    return canvas.to_png()

def _ring(canvas: Canvas, cx: int, cy: int, r: int, colour) -> None:
    import math
    steps = max(24, r)
    last = None
    for i in range(steps + 1):
        a = 2 * math.pi * i / steps
        point = (int(cx + r * math.cos(a)), int(cy + r * math.sin(a)))
        if last is not None:
            canvas.line(last[0], last[1], point[0], point[1], colour, 1)
        last = point
