"""Disconnecting one chat must not sign you out of the others (2026-09-05).

`_revoke_access` ended with `revoke_refresh_for_subject(actor.user_id)`: every
refresh grant that person held, with every client. So revoking one token --
disconnecting Resonance in ChatGPT, say -- silently ended Claude and Grok too,
and the next thing they saw there was "login expired" with nothing to explain
it.

Found by doing it. A throwaway client was revoked after an acceptance run, and
two unrelated chats asked to reconnect. Refresh itself worked fine; what had
happened was that revoking one grant took the others with it.

RFC 7009 §2.1 asks the server to invalidate tokens based on the SAME
authorization grant. The person's other clients are other grants, given
separately, and not withdrawn.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from src.product.server import build_runtime  # noqa: E402
from src.remote.oauth import GrantStore, OAuthCore  # noqa: E402


class OneClientAtATimeTests(unittest.TestCase):
    def setUp(self):
        self.runtime = build_runtime(":memory:",
                                     allowed_origins=frozenset({"http://127.0.0.1"}),
                                     seed=False)
        self.store = GrantStore()
        self.core = OAuthCore(identity=self.runtime.product.identity, store=self.store)
        self.person = self.runtime.product.register_guest()

    def issue(self, client_id: str):
        """One client's pair of tokens for THIS person.

        The same account throughout, which is the whole point: three chats
        connected by one human being. Three separate people would each have
        their own subject, and the bug -- which keyed off the subject -- would
        never show.
        """
        # Each client gets its own session for the same account, which is what
        # the authorize step does when someone connects a second chat.
        credentials = self.runtime.product.identity._issue_session(  # noqa: SLF001
            self.person.user_id, actor_type="agent")
        result = self.core._token_response(
            credentials.access_token, "resonance offline_access",
            "https://example.test/mcp", client_id)
        import json
        body = json.loads(result.body.decode())
        return body["access_token"], body["refresh_token"]

    def test_revoking_one_client_leaves_the_others_signed_in(self):
        first_access, first_refresh = self.issue("client-one")
        _, second_refresh = self.issue("client-two")
        _, third_refresh = self.issue("client-three")

        self.core._revoke_access(first_access)

        self.assertIsNone(self.store.take_refresh(first_refresh),
                          "the revoked client's own grant should be gone")
        for name, token in (("second", second_refresh), ("third", third_refresh)):
            with self.subTest(name):
                self.assertIsNotNone(
                    self.store.take_refresh(token),
                    "another chat was signed out by a revocation it had no part in")

    def test_revoking_a_refresh_grant_still_ends_its_own_access_token(self):
        """The cascade that should happen still happens."""
        access, refresh = self.issue("client-one")
        self.assertTrue(self.core._revoke_refresh_grant(refresh))
        with self.assertRaises(Exception):
            self.runtime.product.identity.authenticate(access)


if __name__ == "__main__":
    unittest.main()
