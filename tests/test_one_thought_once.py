"""The same reasoning, shared twice, is one thought.

Seen on production 2026-09-07: a thought was prepared twice four seconds apart
and shared twice thirteen seconds apart. Both landed as separate sessions,
each raised its own standing-search alert against the same person, and the
page honestly showed the duplicate twice -- so the corpus, the alerts and
every count on the home screen were wrong together.

The tempting fix is to derive `thought_id` from the content. It is the wrong
one: the store never rebinds a `thought_id`, even after deletion (v0.1
tombstone policy), so a content-derived id would permanently bar a person from
sharing again anything they had once withdrawn. Duplicates are a product
question, answered against what is live now.
"""

from __future__ import annotations

import unittest

from src.product.mcp_bridge import (BridgeError, RemoteMCPBridge, build_thought_dna,
                                    thought_fingerprint)
from src.product.server import build_runtime

THOUGHT = {
    "topic": "AI dynamically creates antenna form",
    "nodes": [{"label": "changing radio conditions", "role": "problem"},
              {"label": "adaptive antenna topology", "role": "method"}],
    "relations": [{"source": "changing radio conditions",
                   "target": "adaptive antenna topology", "type": "requires"}],
}


class FingerprintTests(unittest.TestCase):
    def test_the_same_reasoning_has_the_same_fingerprint(self):
        a = build_thought_dna(THOUGHT, human_id="person-a")
        b = build_thought_dna(THOUGHT, human_id="person-a")
        self.assertNotEqual(a["thought_id"], b["thought_id"], "ids stay unique per attempt")
        self.assertEqual(thought_fingerprint(a), thought_fingerprint(b))

    def test_the_order_the_nodes_arrive_in_is_not_the_reasoning(self):
        shuffled = dict(THOUGHT, nodes=list(reversed(THOUGHT["nodes"])))
        self.assertEqual(thought_fingerprint(build_thought_dna(THOUGHT, human_id="p")),
                         thought_fingerprint(build_thought_dna(shuffled, human_id="p")))

    def test_different_reasoning_differs(self):
        other = dict(THOUGHT, nodes=[{"label": "a quiet anchorage", "role": "problem"},
                                     {"label": "a second anchor", "role": "method"}],
                     relations=[{"source": "a quiet anchorage", "target": "a second anchor",
                                 "type": "requires"}])
        self.assertNotEqual(thought_fingerprint(build_thought_dna(THOUGHT, human_id="p")),
                            thought_fingerprint(build_thought_dna(other, human_id="p")))


class OneThoughtOnceTests(unittest.TestCase):
    def setUp(self):
        self.runtime = build_runtime(":ephemeral:",
                                     allowed_origins=frozenset({"http://127.0.0.1"}),
                                     seed=False)
        self.bridge = RemoteMCPBridge(self.runtime.product, origin="http://127.0.0.1")
        self.token = self.runtime.product.register_guest().access_token
        self.n = 0

    def share(self, thought=THOUGHT):
        self.n += 1
        prepared = self.bridge.tool_prepare_thought(
            self.token, {"authorship": "their_own_words", "thought": thought})
        return self.bridge.tool_share_thought(self.token, {
            "draft_id": prepared["draft_id"],
            "confirmation_token": prepared["confirmation_token"],
            "confirm": True, "request_id": f"share-{self.n}"})

    def test_sharing_the_same_reasoning_twice_is_refused(self):
        first = self.share()
        with self.assertRaises(BridgeError) as caught:
            self.share()
        said = str(caught.exception)
        self.assertIn(first["session_id"], said, "it names the one already here")
        self.assertIn("Nothing was duplicated", said)

    def test_a_different_thought_is_untouched(self):
        self.share()
        other = dict(THOUGHT, topic="Anchoring",
                     nodes=[{"label": "a quiet anchorage", "role": "problem"},
                            {"label": "a second anchor", "role": "method"}],
                     relations=[{"source": "a quiet anchorage", "target": "a second anchor",
                                 "type": "requires"}])
        self.assertTrue(self.share(other).get("session_id"))

    def test_the_same_reasoning_can_be_shared_again_after_withdrawing_it(self):
        """The reason the id must NOT be derived from the content."""
        first = self.share()
        self.bridge.tool_stop_sharing(self.token, {
            "session_id": first["session_id"], "confirm": True, "request_id": "stop"})
        again = self.share()
        self.assertNotEqual(again["session_id"], first["session_id"])

    def test_another_person_may_reason_the_same_way(self):
        self.share()
        other_token = self.runtime.product.register_guest().access_token
        prepared = self.bridge.tool_prepare_thought(
            other_token, {"authorship": "their_own_words", "thought": THOUGHT})
        self.assertTrue(prepared.get("draft_id"))


if __name__ == "__main__":
    unittest.main()
