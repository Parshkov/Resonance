"""The waiting half and the search must mean the same thing (2026-09-05).

Discovery sets aside a match whose shape many unrelated people carry. The
standing search did not, so it still wrote the alert -- and someone would have
been told, at their next visit or by email, about a person the search itself
declines to show them.

These two have now disagreed five times: about rejected rows, about your own
other thought appearing as a stranger, about what "private" means, about what
is discoverable, and about this. Every single time the half that speaks to
people was the wrong one. So this is pinned as a pair rather than as two
separate behaviours.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from src.product.mcp_bridge import RemoteMCPBridge  # noqa: E402
from src.product.server import build_runtime  # noqa: E402


def habit(words: str) -> dict:
    """One skeleton, different vocabulary -- what a template produces."""
    return {"topic": words, "domain": "general",
            "nodes": [{"id": "n0", "label": f"{words} pressure", "role": "problem"},
                      {"id": "n1", "label": f"skipped {words} step", "role": "mechanism"},
                      {"id": "n2", "label": f"{words} failure", "role": "outcome"},
                      {"id": "n3", "label": f"{words} safeguard", "role": "method"}],
            "relations": [{"source": "n0", "target": "n1", "type": "causes"},
                          {"source": "n1", "target": "n2", "type": "causes"},
                          {"source": "n3", "target": "n2", "type": "prevents"}]}


class BothHalvesAgreeTests(unittest.TestCase):
    def setUp(self):
        self.runtime = build_runtime(":ephemeral:",
                                     allowed_origins=frozenset({"http://127.0.0.1"}),
                                     seed=False)
        self.bridge = RemoteMCPBridge(self.runtime.product)

    def share(self, token, thought, tag):
        draft = self.bridge.tool_prepare_thought(
            token, {"authorship": "their_own_words", "thought": thought,
                    "request_id": tag + "-1"})
        return self.bridge.tool_share_thought(
            token, {"draft_id": draft["draft_id"], "confirm": True,
                    "confirmation_token": draft["confirmation_token"],
                    "request_id": tag + "-2"})

    def rows_for(self, token):
        found = self.bridge.tool_discover(token, {})
        payload = found.result if hasattr(found, "result") else found
        return list(payload.get("matches_in_backend_order") or [])

    def test_nobody_is_told_about_someone_the_search_will_not_show(self):
        words = ["queue", "soil", "triage", "budget", "staffing", "cache",
                 "roster", "intake", "supply", "review", "backlog", "routing",
                 "billing", "onboarding"]
        first = None
        for index, word in enumerate(words):
            token = self.runtime.product.register_guest().access_token
            self.share(token, habit(word), f"h{index}")
            if first is None:
                first = token

        self.assertEqual(self.rows_for(first), [],
                         "the search still offers the habit")
        waiting = self.bridge.tool_pending_resonances(first, {})
        self.assertEqual(waiting.get("alerts") or [], [],
                         "the waiting half would tell someone about a person "
                         "the search declines to show them")

    def test_a_real_match_is_still_both_found_and_waiting(self):
        """The agreement must come from asking the same question, never from
        the waiting half going quiet."""
        mine = self.runtime.product.register_guest().access_token
        theirs = self.runtime.product.register_guest().access_token
        self.share(mine, habit("delivery"), "a")
        self.share(theirs, {
            "topic": "soil", "domain": "agriculture",
            "nodes": [{"id": "m0", "label": "over-fertilising", "role": "problem"},
                      {"id": "m1", "label": "salt accumulation", "role": "mechanism"},
                      {"id": "m2", "label": "root damage", "role": "outcome"}],
            "relations": [{"source": "m0", "target": "m1", "type": "causes"},
                          {"source": "m1", "target": "m2", "type": "causes"}]}, "b")
        self.assertTrue(self.rows_for(mine), "a genuine match was lost")
        waiting = self.bridge.tool_pending_resonances(mine, {})
        self.assertTrue(waiting.get("alerts"), "nobody was recorded as waiting")


if __name__ == "__main__":
    unittest.main()
