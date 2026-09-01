"""Deterministic SVG poster of the canonical 16:9 competition frame."""

from __future__ import annotations

from typing import Any


def _proj(lat: float, lon: float, x: float, y: float, w: float, h: float) -> tuple[float, float]:
    px = x + (lon + 180.0) / 360.0 * w
    py = y + (90.0 - lat) / 180.0 * h
    return px, py


def render_svg(view: dict[str, Any]) -> str:
    cards = view["featured"]
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080" viewBox="0 0 1920 1080">',
        '<rect width="1920" height="1080" fill="#0b1020"/>',
        '<text x="48" y="56" fill="#e8eefc" font-family="Georgia, serif" font-size="28">Resonance</text>',
        f'<text x="1700" y="56" fill="#8fd3ff" font-family="ui-sans-serif, system-ui" font-size="20">{view["mode_indicator"]}</text>',
        '<rect x="48" y="80" width="420" height="920" rx="18" fill="#151b2e"/>',
        '<rect x="492" y="80" width="720" height="920" rx="18" fill="#101628"/>',
        '<rect x="1236" y="80" width="636" height="920" rx="18" fill="#151b2e"/>',
        f'<text x="72" y="120" fill="#9be7c4" font-size="16">CONSENT · {view["query"]["share_state"]}</text>',
        f'<text x="72" y="160" fill="#e8eefc" font-size="22">{view["query"]["person_pseudonym"]}</text>',
        f'<text x="72" y="190" fill="#b7c3e0" font-size="16">{view["query"]["topic"]}</text>',
        '<rect x="528" y="160" width="648" height="420" rx="12" fill="#0b1020"/>',
    ]
    for marker in view["markers"]:
        color = {"query": "#8fd3ff", "featured": "#f3c16b", "other": "#6f7a99", "contradiction": "#ef8b8b"}[marker["kind"]]
        px, py = _proj(marker["lat"], marker["lon"], 528, 160, 648, 420)
        parts.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="8" fill="{color}" opacity="0.95"/>')
    y = 130
    for card in cards:
        loc = (card.get("location") or {}).get("city") or "location withheld"
        score = card["structural"]
        parts.append(f'<text x="1260" y="{y}" fill="#e8eefc" font-size="20">{card["person_pseudonym"]} · {card["mode_classification"]}</text>')
        parts.append(f'<text x="1260" y="{y+24}" fill="#b7c3e0" font-size="14">{card["domain"]} · {loc} · S={score}</text>')
        y += 90
    parts.append("</svg>")
    return "\n".join(parts) + "\n"
