"""Render the Resonance mark to PNG at any size, with no dependencies.

The directories want a raster icon (OpenAI: square PNG, at least 256x256), and
the mark only existed as `demo/ui/favicon.svg`. Rather than add a rasteriser to
the toolchain for one asset, this draws the same geometry directly: a dark
rounded square, three concentric rings thinning outward, and a solid centre —
a resonance spreading from a point.

Coverage is computed analytically per pixel rather than by supersampling, so
edges are smooth and the whole thing runs in a second.

    python3 brand/make_logo.py brand/logo-512.png 512
"""

from __future__ import annotations

import struct
import sys
import zlib

# The same values as demo/ui/favicon.svg, expressed against its 64-unit box.
BOX = 64.0
BACKGROUND = (0x10, 0x10, 0x0F)
RING = (0xC9, 0xB8, 0xA0)
CENTRE = (0xE8, 0xD5, 0xB7)
CORNER_RADIUS = 14.0
RINGS = (          # radius, stroke width, opacity
    (22.0, 2.0, 0.55),
    (13.0, 1.5, 0.30),
)
CENTRE_RADIUS = 5.0


def _coverage(distance: float, edge: float, feather: float) -> float:
    """How much of a pixel falls inside an edge, as a 0..1 fraction."""
    if feather <= 0:
        return 1.0 if distance <= edge else 0.0
    t = (edge - distance) / feather + 0.5
    return 0.0 if t <= 0 else 1.0 if t >= 1 else t


def _rounded_square_distance(x: float, y: float, half: float, radius: float) -> float:
    """Signed distance to a rounded square centred on the origin."""
    dx, dy = abs(x) - (half - radius), abs(y) - (half - radius)
    if dx <= 0 and dy <= 0:
        return max(dx, dy) - radius
    dx, dy = max(dx, 0.0), max(dy, 0.0)
    return (dx * dx + dy * dy) ** 0.5 - radius


def _blend(base, colour, alpha):
    return tuple(round(b + (c - b) * alpha) for b, c in zip(base, colour))


def render(size: int) -> bytes:
    scale = size / BOX
    feather = 1.0                      # one output pixel of anti-aliasing
    half = size / 2.0
    rows = bytearray()
    for py in range(size):
        rows.append(0)                 # PNG filter type 0 for this scanline
        y = py + 0.5 - half
        for px in range(size):
            x = px + 0.5 - half
            square = _rounded_square_distance(x, y, half, CORNER_RADIUS * scale)
            inside = _coverage(square, 0.0, feather)
            if inside <= 0.0:
                rows.extend((0, 0, 0, 0))
                continue
            radial = (x * x + y * y) ** 0.5
            colour = BACKGROUND
            for radius, width, opacity in RINGS:
                r, w = radius * scale, width * scale / 2.0
                band = _coverage(abs(radial - r), w, feather)
                if band > 0:
                    colour = _blend(colour, RING, band * opacity)
            disc = _coverage(radial, CENTRE_RADIUS * scale, feather)
            if disc > 0:
                colour = _blend(colour, CENTRE, disc)
            rows.extend((*colour, round(inside * 255)))

    def chunk(tag: bytes, payload: bytes) -> bytes:
        return (struct.pack(">I", len(payload)) + tag + payload
                + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF))

    header = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)   # 8-bit RGBA
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", header)
            + chunk(b"IDAT", zlib.compress(bytes(rows), 9))
            + chunk(b"IEND", b""))


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "brand/logo-512.png"
    size = int(sys.argv[2]) if len(sys.argv) > 2 else 512
    with open(target, "wb") as handle:
        handle.write(render(size))
    print(f"{target} {size}x{size}")
