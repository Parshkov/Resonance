"""Drawings in the chat (2026-09-05).

`src/product/rich.py` has rendered the map of where consented matches are, and
the node-for-node mapping behind one match, since R14 — and the remote bridge
never sent either. A person talking to Resonance through Claude or ChatGPT got
prose about a spatial thing.

They now ride beside the JSON as MCP content blocks. These tests hold the two
rules that matter: a drawing never carries more than the JSON already did, and
a drawing is never sent when there is nothing on it.
"""

from __future__ import annotations

import base64
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from src.product.mcp_bridge import RemoteMCPBridge, ToolOutput  # noqa: E402
from src.product.server import build_runtime  # noqa: E402

LOCATION = {"kind": "synthetic_coarse", "region": "R", "city": "city-R",
            "lat": 55.8, "lon": 37.6, "precision": "city"}
ALICE = ([{"id": "n0", "label": "pressure", "role": "problem"},
          {"id": "n1", "label": "skipped review", "role": "mechanism"},
          {"id": "n2", "label": "rework", "role": "outcome"}],
         [{"source": "n0", "target": "n1", "type": "causes"},
          {"source": "n1", "target": "n2", "type": "causes"}])
BOB = ([{"id": "m0", "label": "yield pressure", "role": "problem"},
        {"id": "m1", "label": "salt", "role": "mechanism"},
        {"id": "m2", "label": "root damage", "role": "outcome"}],
       [{"source": "m0", "target": "m1", "type": "causes"},
        {"source": "m1", "target": "m2", "type": "causes"}])


class VisualsTests(unittest.TestCase):
    def setUp(self):
        self.runtime = build_runtime(":memory:",
                                     allowed_origins=frozenset({"http://127.0.0.1"}),
                                     seed=False)
        self.bridge = RemoteMCPBridge(self.runtime.product)

    def _share(self, tag, shape, location=None):
        creds = self.runtime.product.register_guest()
        nodes, relations = shape
        prepared = self.bridge.tool_prepare_thought(creds.access_token, {
            "authorship": "their_own_words",
            "thought": {"topic": tag, "domain": "d", "nodes": nodes,
                        "relations": relations},
            "coarse_location": location, "request_id": f"{tag}-1"})
        self.bridge.tool_share_thought(creds.access_token, {
            "confirm": True, "request_id": f"{tag}-2",
            "draft_id": prepared["draft_id"],
            "confirmation_token": prepared["confirmation_token"]})
        return creds, prepared["session_id"]

    def _call(self, token, name, arguments=None):
        return self.bridge.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                                   "params": {"name": name,
                                              "arguments": arguments or {}}},
                                  token)["result"]

    def test_the_map_reaches_the_chat_when_someone_consented_to_a_location(self):
        alice, _ = self._share("alice", ALICE)
        self._share("bob", BOB, LOCATION)
        result = self._call(alice.access_token, "resonance_discover")
        kinds = [block["type"] for block in result["content"]]
        self.assertEqual(kinds[0], "text", "the text block must come first")
        self.assertIn("image", kinds)
        drawing = next(b for b in result["content"] if b["type"] == "image")
        # PNG, because that is what a chat client renders. It used to be an
        # SVG resource, which no client drew and which Claude printed into the
        # transcript as markup beside the picture.
        self.assertEqual(drawing["mimeType"], "image/png")
        self.assertTrue(base64.b64decode(drawing["data"]).startswith(b"\x89PNG"))

    def test_no_map_is_sent_when_there_is_nothing_on_it(self):
        """An empty map is worse than no map: it says "nobody is anywhere"
        when the truth is that nobody consented to say where they are."""
        alice, _ = self._share("alice", ALICE)
        self._share("bob", BOB)                      # no location consented
        result = self._call(alice.access_token, "resonance_discover")
        # No drawing. The reply carries two text blocks by design -- one in
        # words for the person, one serialized for the client -- so what this
        # asserts is the absence of an image, not a block count.
        self.assertNotIn("image", [b["type"] for b in result["content"]])

    def test_the_structure_drawing_rides_with_the_evidence(self):
        alice, _ = self._share("alice", ALICE)
        self._share("bob", BOB)
        found = self._call(alice.access_token, "resonance_discover")["structuredContent"]
        match = found["matches_in_backend_order"][0]
        result = self._call(alice.access_token, "resonance_explain_match",
                            {"result_id": found["result_id"],
                             "session_id": match["session_id"]})
        drawing = next(b for b in result["content"] if b["type"] == "image")
        self.assertEqual(drawing["mimeType"], "image/png")
        self.assertTrue(base64.b64decode(drawing["data"]).startswith(b"\x89PNG"))

    def test_the_json_is_unchanged_by_the_drawing(self):
        """A client that renders nothing must lose nothing."""
        alice, _ = self._share("alice", ALICE)
        self._share("bob", BOB, LOCATION)
        result = self._call(alice.access_token, "resonance_discover")
        structured = result["structuredContent"]
        for field in ("result_id", "matches_in_backend_order", "rejected",
                      "aggregation", "location_note", "freshness"):
            self.assertIn(field, structured)
        self.assertNotIn("content", structured)

    def test_a_drawing_never_names_anyone_the_json_did_not(self):
        alice, _ = self._share("alice", ALICE)
        bob, bob_session = self._share("bob", BOB, LOCATION)
        result = self._call(alice.access_token, "resonance_discover")
        # Nothing in the bytes, and nothing in the words beside them.
        drawn = base64.b64decode(next(b for b in result["content"]
                                      if b["type"] == "image")["data"])
        said = result["content"][0]["text"]
        for secret in (bob.user_id, bob_session):
            self.assertNotIn(secret.encode(), drawn)
            self.assertNotIn(secret, said)

    def test_a_failed_drawing_never_fails_the_search(self):
        alice, _ = self._share("alice", ALICE)
        self._share("bob", BOB, LOCATION)
        from src.product import pictures
        broken = pictures.render_map_png

        def explode(*_a, **_k):
            raise RuntimeError("renderer is down")

        pictures.render_map_png = explode
        try:
            result = self._call(alice.access_token, "resonance_discover")
        finally:
            pictures.render_map_png = broken
        self.assertFalse(result["isError"])
        self.assertTrue(result["structuredContent"]["matches_in_backend_order"])
        self.assertNotIn("image", [b["type"] for b in result["content"]])

    def test_a_plain_tool_still_returns_plain_json(self):
        creds = self.runtime.product.register_guest()
        result = self._call(creds.access_token, "resonance_whoami")
        self.assertNotIn("image", [b["type"] for b in result["content"]])
        self.assertIn("user_id", result["structuredContent"])


if __name__ == "__main__":
    unittest.main()
