"""A picture that a chat will actually show (2026-09-05).

Every drawing Resonance sent into a chat was an SVG, and every one of them was
invisible. Asked directly what it had received, Claude answered that
image/svg+xml is not a supported image type — only GIF, JPEG, PNG and WEBP —
and that the markup had been passed through as text rather than displayed. The
feature had never worked, in any client, and nothing said so.

These hold the parts of that fix that can be checked without a browser: the
bytes really are a PNG, the drawing carries what the person needs, and a
failure to draw never costs the answer the drawing came with.
"""

from __future__ import annotations

import base64
import struct
import sys
import unittest
import zlib
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from src.product import bitmapfont, pictures  # noqa: E402
from src.product.mcp_bridge import RemoteMCPBridge  # noqa: E402
from src.product.raster import Canvas, fit  # noqa: E402
from src.product.server import build_runtime  # noqa: E402

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"

DNA = {"nodes": [{"id": "n0", "label": "deadline pressure", "role": "problem"},
                 {"id": "n1", "label": "skipped code review", "role": "mechanism"},
                 {"id": "n2", "label": "rework", "role": "outcome"}],
       "relations": [{"source": "n0", "target": "n1", "type": "causes"},
                     {"source": "n1", "target": "n2", "type": "causes"}]}
MATCH = {"person_pseudonym": "Rowan Magpie", "mode_classification": "analogical",
         "scores": {"structural": 0.7071067811865476},
         "evidence": {"preserved_relation_count": 2, "top_correspondences": [
             {"query_label": "deadline pressure", "candidate_label": "waiting-list pressure"},
             {"query_label": "rework", "candidate_label": "readmission"}]}}
THOUGHT = {"topic": "pressure", "domain": "organisations",
           "nodes": DNA["nodes"], "relations": DNA["relations"]}


def decode(png: bytes) -> tuple[int, int, bytes]:
    """Width, height and the raw pixels — so a test can read what was drawn."""
    assert png[:8] == PNG_MAGIC
    width, height = struct.unpack(">II", png[16:24])
    data = b""
    offset = 8
    while offset < len(png):
        length = struct.unpack(">I", png[offset:offset + 4])[0]
        tag = png[offset + 4:offset + 8]
        if tag == b"IDAT":
            data += png[offset + 8:offset + 8 + length]
        offset += 12 + length
    raw = zlib.decompress(data)
    stride = width * 3
    pixels = b"".join(raw[row * (stride + 1) + 1:(row + 1) * (stride + 1)]
                      for row in range(height))
    return width, height, pixels


class ItIsReallyAPngTests(unittest.TestCase):
    def test_each_drawing_decodes_as_a_png_of_its_own_size(self):
        for name, png in (
            ("thought", pictures.render_thought_png(DNA, topic="Deadline pressure")),
            ("structure", pictures.render_structure_png(MATCH)),
            ("map", pictures.render_map_png({"matches": [
                {"person_pseudonym": "Sable Lantern",
                 "display": {"location": {"lat": 52.5, "lon": 13.4}}}]})),
        ):
            with self.subTest(name):
                width, height, pixels = decode(png)
                self.assertGreater(width, 100)
                self.assertGreater(height, 60)
                self.assertEqual(len(pixels), width * height * 3)

    def test_something_was_actually_drawn(self):
        """A blank PNG is a picture of nothing, and would pass every check that
        only looks at the header."""
        _, _, pixels = decode(pictures.render_structure_png(MATCH))
        colours = {pixels[i:i + 3] for i in range(0, len(pixels), 3)}
        self.assertGreater(len(colours), 2, "the drawing is one flat colour")


class WhatThePictureSaysTests(unittest.TestCase):
    def test_it_speaks_the_same_words_the_page_and_the_sentence_do(self):
        """"analogical" beside a name reads as a verdict on the person. The
        picture must not be the one place it survives."""
        from src.product import phrasing
        self.assertEqual(phrasing.classification("analogical"),
                         "same shape, different subject")
        self.assertEqual(phrasing.classification("negative"), "not called a resonance")

    def test_a_long_label_is_cut_with_a_mark_rather_than_silently(self):
        self.assertEqual(fit("abcdefghij", 5), "abcd…")
        self.assertEqual(fit("short", 20), "short")

    def test_an_unknown_character_is_drawn_as_a_box_not_dropped(self):
        self.assertEqual(bitmapfont.rows("中"),
                         [int(bitmapfont.MISSING[i:i + 2], 16)
                          for i in range(0, len(bitmapfont.MISSING), 2)])

    def test_russian_is_in_the_font(self):
        """A person's topic can be in Russian, and a row of boxes where their
        words should be is worse than no picture."""
        for character in "Дневник":
            self.assertIn(ord(character), bitmapfont.GLYPHS, character)


    def test_a_link_running_upwards_is_still_drawn(self):
        """A relation whose source sits below what it points at -- "backoff
        prevents amplification" -- was drawn as no line at all, leaving the
        node floating. Claude, looking at the picture, said so.
        """
        upward = {"nodes": [{"id": "a0", "label": "outage", "role": "problem"},
                            {"id": "a1", "label": "amplification", "role": "state"},
                            {"id": "a2", "label": "backoff", "role": "method"}],
                  "relations": [{"source": "a0", "target": "a1", "type": "causes"},
                                {"source": "a2", "target": "a1", "type": "prevents"}]}
        without = {"nodes": upward["nodes"], "relations": upward["relations"][:1]}
        _, _, drawn = decode(pictures.render_thought_png(upward))
        _, _, fewer = decode(pictures.render_thought_png(without))
        accent = bytes((0x8A, 0x5A, 0x2B))
        self.assertGreater(drawn.count(accent), fewer.count(accent),
                           "the upward link left no mark on the picture")

class ItReachesTheChatTests(unittest.TestCase):
    def setUp(self):
        self.runtime = build_runtime(":memory:",
                                     allowed_origins=frozenset({"http://127.0.0.1"}),
                                     seed=False)
        self.bridge = RemoteMCPBridge(self.runtime.product)
        self.token = self.runtime.product.register_guest().access_token

    def call(self, name, arguments=None):
        return self.bridge.handle(
            {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
             "params": {"name": name, "arguments": arguments or {}}}, self.token)["result"]

    def test_the_image_block_is_a_png_not_an_svg(self):
        draft = self.bridge.tool_prepare_thought(
            self.token, {"authorship": "their_own_words", "thought": THOUGHT,
                         "request_id": "p-1"})
        self.bridge.tool_share_thought(
            self.token, {"draft_id": draft["draft_id"], "confirm": True,
                         "confirmation_token": draft["confirmation_token"],
                         "request_id": "p-2"})
        result = self.call("resonance_my_thoughts")
        images = [c for c in result["content"] if c["type"] == "image"]
        self.assertTrue(images, "no picture reached the chat")
        for image in images:
            self.assertEqual(image["mimeType"], "image/png")
            self.assertTrue(base64.b64decode(image["data"]).startswith(PNG_MAGIC))

    def test_a_drawing_that_fails_never_costs_the_answer(self):
        original = pictures.render_thought_png
        pictures.render_thought_png = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("nope"))
        try:
            draft = self.bridge.tool_prepare_thought(
                self.token, {"authorship": "their_own_words", "thought": THOUGHT,
                             "request_id": "q-1"})
            self.bridge.tool_share_thought(
                self.token, {"draft_id": draft["draft_id"], "confirm": True,
                             "confirmation_token": draft["confirmation_token"],
                             "request_id": "q-2"})
            result = self.call("resonance_my_thoughts")
        finally:
            pictures.render_thought_png = original
        self.assertFalse(result.get("isError"))
        self.assertTrue(result["content"][0]["text"])
        self.assertEqual(len(result["structuredContent"]["sessions"]), 1)


if __name__ == "__main__":
    unittest.main()
