"""Deterministic map/heat SVG for rich MCP content.

Presentation-only, derived exclusively from the R8 aggregation buckets and
consented match locations already in the DTO -- nothing here can see hidden
users or influence ranking. stdlib string assembly; no rendering deps.
"""

from __future__ import annotations

from typing import Any, Mapping

WIDTH, HEIGHT = 640, 360


def _esc(text: str) -> str:
    return (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                .replace('"', "&quot;"))


def map_svg(response: Mapping[str, Any]) -> str:
    """Equirectangular scatter of consented match locations + bucket bars."""
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" '
             f'height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}">',
             f'<rect width="{WIDTH}" height="{HEIGHT}" fill="#14110f"/>',
             '<text x="16" y="28" fill="#d8cfc2" font-family="monospace" '
             'font-size="16">Resonance map · consented coarse locations only</text>']
    for match in response.get("matches", []):
        location = match.get("display", {}).get("location")
        if not location:
            continue
        lon, lat = float(location.get("lon", 0.0)), float(location.get("lat", 0.0))
        x = (lon + 180.0) / 360.0 * WIDTH
        y = (90.0 - lat) / 180.0 * HEIGHT
        label = _esc(match.get("person_pseudonym", "?"))
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="6" fill="#d97757" '
                     f'fill-opacity="0.85"/>')
        parts.append(f'<text x="{x + 9:.1f}" y="{y + 4:.1f}" fill="#bfae9c" '
                     f'font-family="monospace" font-size="11">{label}</text>')
    buckets = response.get("aggregation", {}).get("buckets", [])
    base_y = HEIGHT - 18
    for i, bucket in enumerate(buckets[:8]):
        bar_h = max(4.0, 40.0 * float(bucket.get("intensity", 0.0)))
        x = 16 + i * 76
        parts.append(f'<rect x="{x}" y="{base_y - bar_h:.1f}" width="60" '
                     f'height="{bar_h:.1f}" fill="#7a5c44"/>')
        parts.append(f'<text x="{x}" y="{HEIGHT - 4}" fill="#8a7d6d" '
                     f'font-family="monospace" font-size="9">'
                     f'{_esc(str(bucket.get("bucket_id", ""))[:12])}</text>')
    parts.append("</svg>")
    return "".join(parts)
