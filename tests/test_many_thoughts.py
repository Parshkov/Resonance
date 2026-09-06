"""Having several thoughts must not lock you out (2026-09-05).

`owned_sessions` authorised every row it returned, and each authorisation
spends a rate-limit token. The limiter holds ten and gives one back a second,
and an ordinary page load makes several of those calls -- so someone with five
thoughts here opened the site and was told discovery could not be read, beside
an empty map. Nothing was wrong except that they had used the product more
than once.

session:read_private is an owner action: the check for each row asks exactly
what the ownership filter has already answered. The limiter exists to make
enumerating OTHER people expensive, and this list can only ever contain your
own, so the act is authorised once.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from src.product.mcp_bridge import RemoteMCPBridge  # noqa: E402
from src.product.server import build_runtime  # noqa: E402


def thought(index: int) -> dict:
    return {"topic": f"pressure {index}", "domain": "general",
            "nodes": [{"id": "n0", "label": f"pressure {index}", "role": "problem"},
                      {"id": "n1", "label": f"shortcut {index}", "role": "mechanism"},
                      {"id": "n2", "label": f"rework {index}", "role": "outcome"}],
            "relations": [{"source": "n0", "target": "n1", "type": "causes"},
                          {"source": "n1", "target": "n2", "type": "causes"}]}


class ManyThoughtsTests(unittest.TestCase):
    def setUp(self):
        self.runtime = build_runtime(":memory:",
                                     allowed_origins=frozenset({"http://127.0.0.1"}),
                                     seed=False)
        self.bridge = RemoteMCPBridge(self.runtime.product)
        self.token = self.runtime.product.register_guest().access_token

    def share(self, index: int) -> None:
        draft = self.bridge.tool_prepare_thought(
            self.token, {"authorship": "their_own_words", "thought": thought(index),
                         "request_id": f"m{index}-1"})
        self.bridge.tool_share_thought(
            self.token, {"draft_id": draft["draft_id"], "confirm": True,
                         "confirmation_token": draft["confirmation_token"],
                         "request_id": f"m{index}-2"})

    def test_a_page_load_still_works_with_several_thoughts(self):
        """Eight thoughts, then the reads a page makes, back to back."""
        for index in range(8):
            self.share(index)
        product = self.runtime.product
        for attempt in range(6):
            with self.subTest(read=attempt):
                owned = product.owned_sessions(self.token)
                self.assertEqual(len(owned), 8)

    def test_reading_your_own_record_costs_one_token_not_one_per_thought(self):
        for index in range(5):
            self.share(index)
        limiter = self.runtime.product.identity.security_policy.limiter
        subject = self.runtime.product.identity.authenticate(self.token).user_id
        key = (subject, "session:read_private")
        before = limiter._state.get(key, (float(limiter.capacity), 0.0))[0]
        self.runtime.product.owned_sessions(self.token)
        after = limiter._state.get(key, (float(limiter.capacity), 0.0))[0]
        self.assertLessEqual(before - after, 1.0,
                             "one read of your own record spent more than one token")

    def test_it_is_still_only_your_own(self):
        """The saving must come from not re-asking the same question, never
        from skipping the ownership filter."""
        self.share(0)
        stranger = self.runtime.product.register_guest().access_token
        self.share(1)
        mine = {row["session_id"] for row in self.runtime.product.owned_sessions(self.token)}
        theirs = {row["session_id"] for row in self.runtime.product.owned_sessions(stranger)}
        self.assertEqual(len(mine), 2)
        self.assertEqual(theirs, set())
        self.assertFalse(mine & theirs)


if __name__ == "__main__":
    unittest.main()
