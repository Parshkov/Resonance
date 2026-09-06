"""Draw a picture a chat client will actually show (2026-09-05).

Resonance had two drawings worth looking at -- the correspondence behind a
match, and where consented matches are -- and sent them as SVG. Asked directly,
Claude answered that image/svg+xml is not a supported image type (only GIF,
JPEG, PNG and WEBP) and that the markup was passed through as text rather than
displayed. So the pictures reached the chat and were shown as nothing, in
every client, all along.

This writes a PNG. Standard library only: zlib and struct are all a PNG needs,
and the glyphs live in src/product/bitmapfont.py, so there is no font file to
ship, no library to install, and nothing fetched at draw time.

Deliberately small: filled rectangles, one-pixel lines, discs, and text. That
is the whole vocabulary the existing SVG drawings use, and a drawing engine
nobody asked for would be a worse thing to maintain than a few dozen lines.
"""

from __future__ import annotations

import struct
import zlib
from typing import Sequence

from src.product import bitmapfont

Colour = tuple[int, int, int]

# The product's own light palette, so a drawing looks like the page it came
# from. A picture sent into a chat cannot follow the reader's colour scheme --
# there is nobody to ask -- so it carries its own ground.
PAPER: Colour = (0xF4, 0xF1, 0xEB)
PAPER_2: Colour = (0xEC, 0xE7, 0xDE)
INK: Colour = (0x1D, 0x1A, 0x16)
INK_2: Colour = (0x57, 0x52, 0x4A)
INK_3: Colour = (0x85, 0x7F, 0x75)
ACCENT: Colour = (0x8A, 0x5A, 0x2B)


class Canvas:
    """A plain RGB pixel buffer that can write itself out as a PNG."""

    def __init__(self, width: int, height: int, background: Colour = PAPER) -> None:
        if width <= 0 or height <= 0:
            raise ValueError("a canvas needs a positive width and height")
        self.width = width
        self.height = height
        self._pixels = bytearray(bytes(background) * (width * height))

    # -- primitives -----------------------------------------------------
    def _put(self, x: int, y: int, colour: Colour) -> None:
        if 0 <= x < self.width and 0 <= y < self.height:
            offset = (y * self.width + x) * 3
            self._pixels[offset:offset + 3] = bytes(colour)

    def rectangle(self, x: int, y: int, width: int, height: int,
                  colour: Colour) -> None:
        for row in range(y, y + height):
            for column in range(x, x + width):
                self._put(column, row, colour)

    def line(self, x0: int, y0: int, x1: int, y1: int, colour: Colour,
             thickness: int = 1) -> None:
        """Bresenham, thickened by drawing a small square at each step.

        Thickness is what makes a one-pixel hairline visible once a chat client
        scales the picture down to fit its column.
        """
        dx, dy = abs(x1 - x0), -abs(y1 - y0)
        step_x = 1 if x0 < x1 else -1
        step_y = 1 if y0 < y1 else -1
        error = dx + dy
        span = max(1, thickness)
        while True:
            for oy in range(span):
                for ox in range(span):
                    self._put(x0 + ox - span // 2, y0 + oy - span // 2, colour)
            if x0 == x1 and y0 == y1:
                return
            doubled = 2 * error
            if doubled >= dy:
                error += dy
                x0 += step_x
            if doubled <= dx:
                error += dx
                y0 += step_y

    def disc(self, cx: int, cy: int, radius: int, colour: Colour) -> None:
        for y in range(cy - radius, cy + radius + 1):
            for x in range(cx - radius, cx + radius + 1):
                if (x - cx) ** 2 + (y - cy) ** 2 <= radius * radius:
                    self._put(x, y, colour)

    def text(self, x: int, y: int, value: str, colour: Colour = INK,
             scale: int = 1) -> int:
        """Draw `value` with its top-left at (x, y); return the x it ended at."""
        cursor = x
        for character in value:
            rows = bitmapfont.rows(character)
            for row_index, bits in enumerate(rows):
                if not bits:
                    continue
                for column in range(bitmapfont.CELL_WIDTH):
                    if bits & (1 << (bitmapfont.CELL_WIDTH - 1 - column)):
                        self.rectangle(cursor + column * scale,
                                       y + row_index * scale,
                                       scale, scale, colour)
            cursor += bitmapfont.CELL_WIDTH * scale
        return cursor

    def text_right(self, right: int, y: int, value: str,
                   colour: Colour = INK, scale: int = 1) -> None:
        self.text(right - bitmapfont.width(value, scale), y, value, colour, scale)

    # -- output ---------------------------------------------------------
    def to_png(self) -> bytes:
        raw = bytearray()
        stride = self.width * 3
        for row in range(self.height):
            raw.append(0)                        # filter type 0: no filtering
            raw.extend(self._pixels[row * stride:(row + 1) * stride])

        def chunk(tag: bytes, payload: bytes) -> bytes:
            return (struct.pack(">I", len(payload)) + tag + payload
                    + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF))

        header = struct.pack(">IIBBBBB", self.width, self.height, 8, 2, 0, 0, 0)
        return (b"\x89PNG\r\n\x1a\n"
                + chunk(b"IHDR", header)
                + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
                + chunk(b"IEND", b""))


def fit(value: str, characters: int) -> str:
    """Cut a label to what will fit, with an ellipsis so nobody is misquoted."""
    if len(value) <= characters:
        return value
    if characters <= 3:
        return value[:characters]
    # Three dots, not the ellipsis glyph: the bitmap font has no "…", and a
    # missing glyph was drawn as a box at the end of every cut label.
    return value[:characters - 3] + "..."


def wrap(value: str, characters: int, lines: int) -> Sequence[str]:
    """Break a label across at most `lines` lines of `characters` each."""
    words = str(value).split()
    out: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if current and len(candidate) > characters:
            out.append(current)
            current = word
            if len(out) == lines:
                break
        else:
            current = candidate
    if current and len(out) < lines:
        out.append(current)
    if not out:
        return [""]
    if len(out) == lines and len(" ".join(words)) > sum(len(line) for line in out):
        out[-1] = fit(out[-1] + "…", characters)
    return out
