"""Refusing to meet someone has to be a decision (2026-09-05).

`accept=bool(body.get("accept", False))`. A renamed key, a typo, or a
half-built client sent a response the server did not understand, and the
answer it filled in was "no" -- an introduction request from a stranger,
declined on this person's behalf, by nobody.

Found by sending {"decision": "accept"} instead of {"accept": true} against a
running server and watching the introduction come back declined. In a service
whose entire purpose is introducing two people, the default that costs nothing
to get wrong is the one that quietly undoes the product.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from src.product.mcp_bridge import BridgeError, RemoteMCPBridge  # noqa: E402
from src.product.server import build_runtime  # noqa: E402

SHAPE = {"topic": "pressure", "domain": "organisations",
         "nodes": [{"id": "n0", "label": "delivery pressure", "role": "problem"},
                   {"id": "n1", "label": "skipped review", "role": "mechanism"},
                   {"id": "n2", "label": "rework", "role": "outcome"}],
         "relations": [{"source": "n0", "target": "n1", "type": "causes"},
                       {"source": "n1", "target": "n2", "type": "causes"}]}
OTHER = {"topic": "soil", "domain": "agriculture",
         "nodes": [{"id": "m0", "label": "yield pressure", "role": "problem"},
                   {"id": "m1", "label": "salt accumulation", "role": "mechanism"},
                   {"id": "m2", "label": "root damage", "role": "outcome"}],
         "relations": [{"source": "m0", "target": "m1", "type": "causes"},
                       {"source": "m1", "target": "m2", "type": "causes"}]}


class NeverDeclinedByDefaultTests(unittest.TestCase):
    def setUp(self):
        self.runtime = build_runtime(":memory:",
                                     allowed_origins=frozenset({"http://127.0.0.1"}),
                                     seed=False)
        self.bridge = RemoteMCPBridge(self.runtime.product)
        self.asker = self.runtime.product.register_guest().access_token
        self.asked = self.runtime.product.register_guest().access_token

    def share(self, token, what, tag):
        draft = self.bridge.tool_prepare_thought(
            token, {"authorship": "their_own_words", "thought": what,
                    "request_id": tag + "-1"})
        return self.bridge.tool_share_thought(
            token, {"draft_id": draft["draft_id"], "confirm": True,
                    "confirmation_token": draft["confirmation_token"],
                    "request_id": tag + "-2"})

    def pending_intro(self):
        mine = self.share(self.asker, SHAPE, "mine")
        self.share(self.asked, OTHER, "theirs")
        found = self.bridge.tool_discover(self.asker, {})
        payload = found.result if hasattr(found, "result") else found
        rows = payload.get("matches_in_backend_order") or []
        self.assertTrue(rows, "no match to ask about")
        self.bridge.tool_request_intro(
            self.asker, {"from_session_id": mine["session_id"],
                         "target_session_id": rows[0]["session_id"],
                         "confirm": True, "request_id": "ask-1",
                         "message": "your soil is my delivery"})
        incoming = self.bridge.tool_list_intros(self.asked, {})["incoming"]
        self.assertEqual(len(incoming), 1, incoming)
        return incoming[0]["intro_id"]

    def test_an_unreadable_answer_is_refused_not_taken_as_no(self):
        intro_id = self.pending_intro()
        for arguments, why in (
            ({"intro_id": intro_id, "confirm": True, "request_id": "r1"}, "omitted"),
            ({"intro_id": intro_id, "confirm": True, "request_id": "r2",
              "accept": "accept"}, "a string, as a client might send"),
            ({"intro_id": intro_id, "confirm": True, "request_id": "r3",
              "accept": None}, "null"),
        ):
            with self.subTest(why):
                with self.assertRaises(BridgeError) as caught:
                    self.bridge.tool_respond_intro(self.asked, arguments)
                self.assertEqual(caught.exception.code, "validation_failed")
        # And nothing was decided while those were being refused.
        still = self.bridge.tool_list_intros(self.asked, {})["incoming"]
        self.assertEqual(still[0]["state"], "requested", still)

    def test_a_real_decision_is_still_carried_out(self):
        intro_id = self.pending_intro()
        answered = self.bridge.tool_respond_intro(
            self.asked, {"intro_id": intro_id, "accept": True, "confirm": True,
                         "request_id": "yes-1"})
        self.assertNotEqual(answered.get("state"), "declined", answered)

    def test_declining_on_purpose_still_declines(self):
        intro_id = self.pending_intro()
        answered = self.bridge.tool_respond_intro(
            self.asked, {"intro_id": intro_id, "accept": False, "confirm": True,
                         "request_id": "no-1"})
        self.assertEqual(answered.get("state"), "declined", answered)


if __name__ == "__main__":
    unittest.main()
