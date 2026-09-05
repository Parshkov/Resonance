"""You are not the person you were looking for (2026-09-05).

Share two thoughts and discovery reported the second one back as a match:
"someone whose reasoning has the same shape as yours", carrying your own
pseudonym, in a service whose entire purpose is introducing you to somebody
else. You could then ask to be introduced to yourself, and the request would
be waiting for you.

The standing search never had this bug — it drops a pair whose two sides have
the same owner (standing.py). So the two halves of the product disagreed
about what a resonance is, and the half that talks to people was the wrong
one. That is the second time these two have disagreed; both tests live here
so the next divergence is caught by the pair, not by one of them.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from src.product.mcp_bridge import RemoteMCPBridge  # noqa: E402
from src.product.server import build_runtime  # noqa: E402


def thought(topic: str, problem: str, mechanism: str, outcome: str) -> dict:
    return {"topic": topic, "domain": "general",
            "nodes": [{"id": "n0", "label": problem, "role": "problem"},
                      {"id": "n1", "label": mechanism, "role": "mechanism"},
                      {"id": "n2", "label": outcome, "role": "outcome"}],
            "relations": [{"source": "n0", "target": "n1", "type": "causes"},
                          {"source": "n1", "target": "n2", "type": "causes"}]}


TEAM = thought("pressure", "delivery pressure", "skipped review", "rework")
SOIL = thought("soil", "yield pressure", "salt accumulation", "root damage")


class NotYourselfTests(unittest.TestCase):
    def setUp(self):
        self.runtime = build_runtime(":memory:",
                                     allowed_origins=frozenset({"http://127.0.0.1"}),
                                     seed=False)
        self.bridge = RemoteMCPBridge(self.runtime.product)
        self.mine = self.runtime.product.register_guest()
        self.theirs = self.runtime.product.register_guest()

    def share(self, credentials, what, tag):
        token = credentials.access_token
        draft = self.bridge.tool_prepare_thought(
            token, {"authorship": "their_own_words", "thought": what,
                    "request_id": tag + "-1"})
        return self.bridge.tool_share_thought(
            token, {"draft_id": draft["draft_id"], "confirm": True,
                    "confirmation_token": draft["confirmation_token"],
                    "request_id": tag + "-2"})

    def rows(self, credentials, session_id):
        result = self.bridge.tool_discover(
            credentials.access_token, {"session_id": session_id})
        payload = result.result if hasattr(result, "result") else result
        return list(payload.get("matches_in_backend_order") or [])

    def test_my_own_other_thought_is_never_reported_as_a_person(self):
        first = self.share(self.mine, TEAM, "first")
        self.share(self.mine, SOIL, "second")
        self.assertEqual(self.rows(self.mine, first["session_id"]), [])

    def test_a_real_other_person_is_still_found(self):
        """The exclusion must be about who owns the row, not about the shape —
        otherwise it would quietly delete the product."""
        first = self.share(self.mine, TEAM, "first")
        self.share(self.mine, SOIL, "second")
        self.share(self.theirs, SOIL, "theirs")
        found = self.rows(self.mine, first["session_id"])
        self.assertEqual(len(found), 1, found)
        owner = self.runtime.product.identity.policy_source.owner_of(
            "session", found[0]["session_id"])
        self.assertEqual(owner, self.theirs.user_id)

    def test_the_two_halves_agree_about_it(self):
        """The standing search always excluded this. Pinning both together is
        the point: they disagreed once about rejected rows and again about
        this, and each time only one half was wrong."""
        first = self.share(self.mine, TEAM, "first")
        self.share(self.mine, SOIL, "second")
        waiting = self.bridge.tool_pending_resonances(self.mine.access_token, {})
        self.assertEqual(waiting.get("alerts") or [], [])
        self.assertEqual(self.rows(self.mine, first["session_id"]), [])


if __name__ == "__main__":
    unittest.main()
