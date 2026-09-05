"""The half of Resonance that waits (2026-09-04).

Discovery only ever answered "who resonates with me *now*". The common case it
left unserved is the one the product exists for: you share a thought, nobody
matches it yet, and the person who would have matched arrives next week. These
tests hold that second person's arrival — and, above all, that the FIRST person
is told about it, since that is the news that could not reach them any other
way.
"""

from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from demo.corpus.discovery import load_sessions  # noqa: E402
from src.identity import IdentityService, R11IdentityBackend  # noqa: E402
from src.identity.models import ConsentChoices  # noqa: E402
from src.persistence import LiveCorpusService, SQLiteRepository  # noqa: E402
from src.product.service import LiveProductService  # noqa: E402
from src.product.standing import ALERT_KIND, StandingSearch  # noqa: E402

ORIGIN = "https://app.resonance.example"
SECRET = b"standing-search-secret-32-bytes!!"
PRES = {"domain": "engineering", "topic": "thermal", "cluster_id": "c1"}

_R7 = {s["session_id"]: s for s in load_sessions()}
QUERY = "ses-aria-plasma-lens"
RESONANT = "ses-gabe-warehouse"


def dna(source_session: str, thought_id: str) -> dict:
    graph = copy.deepcopy(dict(_R7[source_session]["thought_dna"]))
    graph["thought_id"] = thought_id
    return graph


def build_stack():
    repo = SQLiteRepository(":memory:")
    repo.migrate()
    live = LiveCorpusService(repo)
    identity = IdentityService(R11IdentityBackend(live),
                               allowed_origins=frozenset({ORIGIN}))
    return live, identity, LiveProductService(identity, confirmation_secret=SECRET)


def share(product, creds, thought, presentation=None):
    security = {"csrf_token": creds.csrf_token, "cookie_authenticated": True,
                "origin": ORIGIN, "client_id": "manual-ui"}
    prepared = product.prepare_structured(
        creds.access_token, thought,
        presentation=dict(presentation or PRES), **security)
    preview = product.preview(creds.access_token, prepared["draft_id"],
                              client_id="manual-ui")
    product.share_prepared(
        creds.access_token, prepared["draft_id"],
        confirmation_token=preview["confirmation_token"], confirmed=True,
        **security)
    return prepared["session_id"]


class WaitingTests(unittest.TestCase):
    def setUp(self):
        self.live, self.identity, self.product = build_stack()
        self.alice = self.product.register("Alice")
        self.bob = self.product.register("Bob")

    def test_the_first_person_is_told_when_the_second_arrives(self):
        """The whole point. Alice shares into an empty world and is told
        nothing; Bob arrives later and Alice learns about him without having
        to come back and look."""
        share(self.product, self.alice, dna(QUERY, "th-alice"))
        first = self.product.pending_resonances(self.alice.access_token)
        self.assertTrue(first["available"])
        self.assertEqual(first["alerts"], [], "nobody had arrived yet")

        share(self.product, self.bob, dna(RESONANT, "th-bob"))

        after = self.product.pending_resonances(self.alice.access_token)
        self.assertEqual(len(after["alerts"]), 1)
        alert = after["alerts"][0]
        self.assertEqual(alert["reason"], "they_arrived")
        self.assertIsNone(alert["seen_at"])
        self.assertEqual(after["unseen_count"], 1)
        self.assertGreater(alert["scores_at_detection"].get("structural", 0), 0)

    def test_the_arriving_person_is_told_who_was_already_waiting(self):
        share(self.product, self.alice, dna(QUERY, "th-alice"))
        share(self.product, self.bob, dna(RESONANT, "th-bob"))
        bobs = self.product.pending_resonances(self.bob.access_token)
        self.assertEqual(len(bobs["alerts"]), 1)
        self.assertEqual(bobs["alerts"][0]["reason"], "you_shared")

    def test_nobody_is_told_twice_about_the_same_person(self):
        alice_session = share(self.product, self.alice, dna(QUERY, "th-alice"))
        share(self.product, self.bob, dna(RESONANT, "th-bob"))
        # A second sweep over the same pair, however it is triggered.
        self.product.standing.sweep_for_session(alice_session)
        self.assertEqual(len(self.product.pending_resonances(
            self.alice.access_token)["alerts"]), 1)

    def test_your_own_two_thoughts_resonating_is_not_an_introduction(self):
        share(self.product, self.alice, dna(QUERY, "th-alice-1"))
        share(self.product, self.alice, dna(RESONANT, "th-alice-2"))
        self.assertEqual(self.product.pending_resonances(
            self.alice.access_token)["alerts"], [])

    def test_seen_stops_it_counting_as_news_without_removing_it(self):
        share(self.product, self.alice, dna(QUERY, "th-alice"))
        share(self.product, self.bob, dna(RESONANT, "th-bob"))
        key = self.product.pending_resonances(
            self.alice.access_token)["alerts"][0]["alert_key"]
        marked = self.product.mark_resonances_seen(self.alice.access_token, [key])
        self.assertEqual(marked["marked"], 1)
        after = self.product.pending_resonances(self.alice.access_token)
        self.assertEqual(after["alerts"], [])
        self.assertEqual(after["unseen_count"], 0)
        with_seen = self.product.pending_resonances(self.alice.access_token,
                                                    include_seen=True)
        self.assertEqual(len(with_seen["alerts"]), 1)
        self.assertIsNotNone(with_seen["alerts"][0]["seen_at"])

    def test_marking_someone_else_s_alert_seen_does_nothing(self):
        share(self.product, self.alice, dna(QUERY, "th-alice"))
        share(self.product, self.bob, dna(RESONANT, "th-bob"))
        key = self.product.pending_resonances(
            self.alice.access_token)["alerts"][0]["alert_key"]
        self.assertEqual(self.product.mark_resonances_seen(
            self.bob.access_token, [key])["marked"], 0)
        self.assertEqual(len(self.product.pending_resonances(
            self.alice.access_token)["alerts"]), 1)

    def test_a_person_can_dismiss_an_alert_for_good(self):
        share(self.product, self.alice, dna(QUERY, "th-alice"))
        share(self.product, self.bob, dna(RESONANT, "th-bob"))
        key = self.product.pending_resonances(
            self.alice.access_token)["alerts"][0]["alert_key"]
        self.assertTrue(self.product.dismiss_resonance(
            self.alice.access_token, key)["dismissed"])
        self.assertEqual(self.product.pending_resonances(
            self.alice.access_token, include_seen=True)["alerts"], [])


class WithdrawalTests(unittest.TestCase):
    """A withdrawal has to reach the people who were already told."""

    def setUp(self):
        self.live, self.identity, self.product = build_stack()
        self.alice = self.product.register("Alice")
        self.bob = self.product.register("Bob")
        self.alice_session = share(self.product, self.alice, dna(QUERY, "th-alice"))
        self.bob_session = share(self.product, self.bob, dna(RESONANT, "th-bob"))

    def _security(self, creds):
        return {"csrf_token": creds.csrf_token, "cookie_authenticated": True,
                "origin": ORIGIN, "client_id": "manual-ui"}

    def test_revoking_your_thought_withdraws_what_you_were_told_about_it(self):
        self.assertEqual(len(self.product.pending_resonances(
            self.alice.access_token)["alerts"]), 1)
        self.product.revoke_session(self.alice.access_token, self.alice_session,
                                    confirmed=True, **self._security(self.alice))
        self.assertEqual(self.product.pending_resonances(
            self.alice.access_token, include_seen=True)["alerts"], [])

    def test_when_they_withdraw_you_stop_being_told_about_them(self):
        self.assertEqual(len(self.product.pending_resonances(
            self.alice.access_token)["alerts"]), 1)
        self.product.revoke_session(self.bob.access_token, self.bob_session,
                                    confirmed=True, **self._security(self.bob))
        # Alice's own alert survives the sweep-side retraction, so this is the
        # read-time re-check doing its job: the thought it points at is gone.
        self.assertEqual(self.product.pending_resonances(
            self.alice.access_token)["alerts"], [])

    def test_a_withdrawn_alert_is_not_merely_hidden_but_dropped(self):
        self.product.revoke_session(self.bob.access_token, self.bob_session,
                                    confirmed=True, **self._security(self.bob))
        self.product.pending_resonances(self.alice.access_token)
        remaining = self.live.repo.list_grants_for_user(ALERT_KIND, self.alice.user_id)
        self.assertEqual(list(remaining), [])

    def test_turning_sharing_off_stops_the_standing_search(self):
        self.product.set_consent(
            self.alice.access_token, self.alice_session,
            ConsentChoices(share_thought_dna=False), confirmed=True,
            **self._security(self.alice))
        self.assertEqual(self.product.pending_resonances(
            self.alice.access_token, include_seen=True)["alerts"], [])


class BlockTests(unittest.TestCase):
    def setUp(self):
        self.live, self.identity, self.product = build_stack()
        self.alice = self.product.register("Alice")
        self.bob = self.product.register("Bob")

    def test_a_blocked_person_is_never_reported(self):
        share(self.product, self.alice, dna(QUERY, "th-alice"))
        self.identity.block_user(
            self.alice.access_token, self.bob.user_id, confirmed=True,
            csrf_token=self.alice.csrf_token, cookie_authenticated=True,
            origin=ORIGIN, client_id="manual-ui")
        share(self.product, self.bob, dna(RESONANT, "th-bob"))
        self.assertEqual(self.product.pending_resonances(
            self.alice.access_token)["alerts"], [])


class DegradedRuntimeTests(unittest.TestCase):
    def test_a_runtime_without_a_record_store_says_so_rather_than_lying(self):
        """Silence and "nobody matched you" are different answers, and the
        difference matters more here than anywhere else in the product."""
        live, identity, product = build_stack()

        class NoStore:
            def __getattr__(self, name):
                if name == "repo":
                    return None
                raise AttributeError(name)

        standing = StandingSearch(product)
        standing.live = NoStore()
        self.assertFalse(standing.available)
        creds = product.register("Solo")
        answer = standing.pending(creds.access_token)
        self.assertFalse(answer["available"])
        self.assertEqual(answer["alerts"], [])


if __name__ == "__main__":
    unittest.main()
