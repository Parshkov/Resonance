"""R14 acceptance battery: consent-safe intro state machine + relay messaging."""

from __future__ import annotations

import unittest

from src.collaboration import CollaborationError
from src.ingestion.service import ShareIntent
from src.persistence.errors import PersistenceConflictError
from src.security.models import ConfirmationRequired
from tests.test_product_live import (
    ORIGIN,
    QUERY_DNA,
    build_stack,
    location,
    r7_dna,
    share_thought,
)


def two_user_world():
    """A shares a resonant, intro-allowing session; B discovers it."""
    live, identity, product = build_stack()
    alice = product.register("Alice")
    a_session, _ = share_thought(
        product, alice, r7_dna("ses-gabe-warehouse", "thought-alice"),
        loc=location("R"),
        intent=ShareIntent(share_display_profile=True,
                           share_coarse_location=True,
                           receive_intro_requests=True))
    bob = product.register("Bob")
    b_session, _ = share_thought(
        product, bob, r7_dna(QUERY_DNA, "thought-bob-query"))
    discovery = product.discover(bob.access_token, b_session, k=20)
    assert a_session in [m["session_id"] for m in discovery["matches"]]
    return live, identity, product, alice, a_session, bob, b_session


def request(product, bob, b_session, a_session, **kw):
    defaults = dict(from_session_id=b_session, target_session_id=a_session,
                    message="Your warehouse congestion structure mirrors my plasma bloom — compare mitigations?",
                    request_id="req-1", confirmed=True)
    defaults.update(kw)
    return product.request_intro(bob.access_token, **defaults)


class IntroStateMachineTests(unittest.TestCase):
    def setUp(self):
        (self.live, self.identity, self.product, self.alice, self.a_session,
         self.bob, self.b_session) = two_user_world()

    def test_full_acceptance_scenario_request_accept_message_reply(self):
        generation_before = self.product.freshness()["serving_generation"]
        intro = request(self.product, self.bob, self.b_session, self.a_session)
        self.assertEqual(intro["state"], "requested")
        self.assertEqual(intro["direction"], "outgoing")
        self.assertTrue(intro["untrusted"])

        incoming = self.product.list_requests(self.alice.access_token)["incoming"]
        self.assertEqual(len(incoming), 1)
        self.assertEqual(incoming[0]["counterpart_display"], "Bob")
        self.assertIn("plasma bloom", incoming[0]["message"])

        accepted = self.product.respond_intro(
            self.alice.access_token, incoming[0]["intro_id"],
            accept=True, request_id="resp-1", confirmed=True)
        self.assertEqual(accepted["state"], "accepted")
        channel_id = accepted["channel_id"]

        sent = self.product.send_message(
            self.bob.access_token, channel_id,
            "Here is how we throttle input power.", request_id="msg-1",
            confirmed=True)
        self.assertTrue(sent["delivered"])
        reply = self.product.send_message(
            self.alice.access_token, channel_id,
            "We stage inbound docks the same way!", request_id="msg-2",
            confirmed=True)
        self.assertTrue(reply["delivered"])

        thread = self.product.read_messages(self.alice.access_token, channel_id)
        self.assertEqual([m["author"] for m in thread["messages"]],
                         ["counterpart", "me"])
        self.assertTrue(all(m["untrusted"] for m in thread["messages"]))
        thread_b = self.product.read_messages(self.bob.access_token, channel_id)
        self.assertEqual([m["author_display"] for m in thread_b["messages"]],
                         ["Bob", "Alice"])
        # No contact details anywhere; chat never touches the corpus generation.
        blob = str(thread) + str(incoming) + str(accepted)
        for needle in ("@", "email", "phone"):
            self.assertNotIn(needle, blob)
        self.assertEqual(self.product.freshness()["serving_generation"],
                         generation_before)

    def test_confirmation_and_message_required(self):
        with self.assertRaises(ConfirmationRequired):
            request(self.product, self.bob, self.b_session, self.a_session,
                    confirmed=False)
        with self.assertRaises(CollaborationError):
            request(self.product, self.bob, self.b_session, self.a_session,
                    message="   ")

    def test_duplicate_request_and_idempotent_replay(self):
        first = request(self.product, self.bob, self.b_session, self.a_session)
        replay = request(self.product, self.bob, self.b_session, self.a_session)
        self.assertEqual(first["intro_id"], replay["intro_id"])
        with self.assertRaises(CollaborationError):
            request(self.product, self.bob, self.b_session, self.a_session,
                    request_id="req-2")

    def test_decline_cancel_and_state_conflicts(self):
        intro = request(self.product, self.bob, self.b_session, self.a_session)
        declined = self.product.respond_intro(
            self.alice.access_token, intro["intro_id"],
            accept=False, request_id="resp-d", confirmed=True)
        self.assertEqual(declined["state"], "declined")
        with self.assertRaises(CollaborationError):
            self.product.respond_intro(self.alice.access_token,
                                       intro["intro_id"], accept=True,
                                       request_id="resp-late", confirmed=True)
        # after decline, B may request again; then cancel their own request
        second = request(self.product, self.bob, self.b_session, self.a_session,
                         request_id="req-3")
        cancelled = self.product.cancel_intro(
            self.bob.access_token, second["intro_id"],
            request_id="cxl-1", confirmed=True)
        self.assertEqual(cancelled["state"], "cancelled")
        with self.assertRaises(CollaborationError):
            self.product.respond_intro(self.alice.access_token,
                                       second["intro_id"], accept=True,
                                       request_id="resp-x", confirmed=True)

    def test_participant_only_visibility_uniform_negatives(self):
        intro = request(self.product, self.bob, self.b_session, self.a_session)
        carol = self.product.register("Carol")
        with self.assertRaises(CollaborationError) as ctx_foreign:
            self.product.respond_intro(carol.access_token, intro["intro_id"],
                                       accept=True, request_id="x",
                                       confirmed=True)
        with self.assertRaises(CollaborationError) as ctx_missing:
            self.product.respond_intro(carol.access_token, "intro-" + "0" * 24,
                                       accept=True, request_id="y",
                                       confirmed=True)
        self.assertEqual(str(ctx_foreign.exception), str(ctx_missing.exception))
        self.assertEqual(self.product.list_requests(carol.access_token),
                         {"incoming": [], "outgoing": []})
        # requester cannot accept their own request; target cannot cancel
        with self.assertRaises(CollaborationError):
            self.product.respond_intro(self.bob.access_token, intro["intro_id"],
                                       accept=True, request_id="z",
                                       confirmed=True)
        with self.assertRaises(CollaborationError):
            self.product.cancel_intro(self.alice.access_token,
                                      intro["intro_id"], request_id="w",
                                      confirmed=True)

    def test_no_intro_to_non_consenting_or_blocked_or_missing(self):
        carol = self.product.register("Carol")
        c_session, _ = share_thought(
            self.product, carol, r7_dna("ses-mei-battery-heat", "thought-carol"),
            intent=ShareIntent(share_display_profile=True,
                               receive_intro_requests=False))
        with self.assertRaises(CollaborationError) as no_consent:
            request(self.product, self.bob, self.b_session, c_session,
                    request_id="rc-1")
        with self.assertRaises(CollaborationError) as missing:
            request(self.product, self.bob, self.b_session,
                    "ses-" + "0" * 16, request_id="rc-2")
        self.assertEqual(str(no_consent.exception), str(missing.exception))
        self.identity.policy_source.block(self.bob.user_id, self.alice.user_id)
        with self.assertRaises(CollaborationError) as blocked:
            request(self.product, self.bob, self.b_session, self.a_session,
                    request_id="rc-3")
        self.assertEqual(str(blocked.exception), str(missing.exception))

    def test_messaging_gates(self):
        intro = request(self.product, self.bob, self.b_session, self.a_session)
        with self.assertRaises(CollaborationError):
            self.product.send_message(self.bob.access_token, "chan-" + "0" * 24,
                                      "hi", request_id="m0", confirmed=True)
        accepted = self.product.respond_intro(
            self.alice.access_token, intro["intro_id"], accept=True,
            request_id="ra", confirmed=True)
        channel_id = accepted["channel_id"]
        carol = self.product.register("Carol")
        with self.assertRaises(CollaborationError):
            self.product.read_messages(carol.access_token, channel_id)
        with self.assertRaises(CollaborationError):
            self.product.send_message(carol.access_token, channel_id, "hi",
                                      request_id="m1", confirmed=True)
        with self.assertRaises(ConfirmationRequired):
            self.product.send_message(self.bob.access_token, channel_id, "hi",
                                      request_id="m2", confirmed=False)
        # block after acceptance kills messaging via the kernel path
        self.identity.policy_source.block(self.bob.user_id, self.alice.user_id)
        with self.assertRaises(CollaborationError):
            self.product.send_message(self.bob.access_token, channel_id,
                                      "still there?", request_id="m3",
                                      confirmed=True)

    def test_accept_is_atomic_one_channel_per_intro(self):
        intro = request(self.product, self.bob, self.b_session, self.a_session)
        iid = self.product.list_requests(
            self.alice.access_token)["incoming"][0]["intro_id"]
        first = self.product.respond_intro(
            self.alice.access_token, iid, accept=True, request_id="acc-x",
            confirmed=True)
        # idempotent replay: same channel, no second row
        replay = self.product.respond_intro(
            self.alice.access_token, iid, accept=True, request_id="acc-x",
            confirmed=True)
        self.assertEqual(first["channel_id"], replay["channel_id"])
        # a fresh request_id after already-accepted also cannot mint a channel
        with self.assertRaises(CollaborationError):
            self.product.respond_intro(self.alice.access_token, iid,
                                       accept=True, request_id="acc-y",
                                       confirmed=True)
        self.assertEqual(
            self.live.repo.get_channel_by_intro(iid).channel_id,
            first["channel_id"])
        # channel id is deterministic in the intro id (replay-convergent)
        self.assertTrue(first["channel_id"].startswith("chan-"))

    def test_message_idempotency_is_per_author(self):
        """026B-N2: two different senders reusing the same request_id must NOT
        collide — each author's key namespace is independent."""
        intro = request(self.product, self.bob, self.b_session, self.a_session)
        iid = self.product.list_requests(
            self.alice.access_token)["incoming"][0]["intro_id"]
        acc = self.product.respond_intro(self.alice.access_token, iid,
                                         accept=True, request_id="acc",
                                         confirmed=True)
        ch = acc["channel_id"]
        b_msg = self.product.send_message(self.bob.access_token, ch, "hello",
                                          request_id="shared", confirmed=True)
        a_msg = self.product.send_message(self.alice.access_token, ch, "hello",
                                          request_id="shared", confirmed=True)
        self.assertNotEqual(a_msg["message_id"], b_msg["message_id"])
        thread = self.product.read_messages(self.alice.access_token, ch)["messages"]
        self.assertEqual(len(thread), 2)
        self.assertEqual({m["author_display"] for m in thread}, {"Alice", "Bob"})

    def test_requester_obtains_channel_id_from_list_not_acceptor_response(self):
        """F1 / 026B-N1: the requester (B) never sees A's respond response, so
        the channel id must be reachable from B's own list_requests."""
        request(self.product, self.bob, self.b_session, self.a_session)
        iid = self.product.list_requests(
            self.alice.access_token)["incoming"][0]["intro_id"]
        self.product.respond_intro(self.alice.access_token, iid, accept=True,
                                   request_id="acc", confirmed=True)
        # B only ever calls list_requests — never A's response.
        outgoing = self.product.list_requests(self.bob.access_token)["outgoing"]
        accepted = next(r for r in outgoing if r["state"] == "accepted")
        self.assertIn("channel_id", accepted)
        # and that id actually works for B to send.
        sent = self.product.send_message(self.bob.access_token,
                                         accepted["channel_id"], "reachable",
                                         request_id="b-first", confirmed=True)
        self.assertTrue(sent["delivered"])

    def test_message_idempotent_replay_and_collision(self):
        intro = request(self.product, self.bob, self.b_session, self.a_session)
        accepted = self.product.respond_intro(
            self.alice.access_token, intro["intro_id"], accept=True,
            request_id="ra", confirmed=True)
        channel_id = accepted["channel_id"]
        one = self.product.send_message(self.bob.access_token, channel_id,
                                        "hello", request_id="mk", confirmed=True)
        two = self.product.send_message(self.bob.access_token, channel_id,
                                        "hello", request_id="mk", confirmed=True)
        self.assertEqual(one["message_id"], two["message_id"])
        self.assertEqual(
            len(self.product.read_messages(self.bob.access_token,
                                           channel_id)["messages"]), 1)
        with self.assertRaises(PersistenceConflictError):
            self.product.send_message(self.bob.access_token, channel_id,
                                      "different", request_id="mk",
                                      confirmed=True)


class RichIntroStateLiveTests(unittest.TestCase):
    def test_intro_state_flips_live_in_rich_results(self):
        (live, identity, product, alice, a_session,
         bob, b_session) = two_user_world()
        rich0 = product.rich_discover(bob.access_token, b_session, k=20)
        row0 = next(m for m in rich0["matches"] if m["session_id"] == a_session)
        self.assertEqual(row0["intro_state"], "available")
        intro = request(product, bob, b_session, a_session)
        rich1 = product.rich_discover(bob.access_token, b_session, k=20)
        row1 = next(m for m in rich1["matches"] if m["session_id"] == a_session)
        self.assertEqual(row1["intro_state"], "requested")
        product.respond_intro(alice.access_token, intro["intro_id"],
                              accept=True, request_id="ra", confirmed=True)
        rich2 = product.rich_discover(bob.access_token, b_session, k=20)
        row2 = next(m for m in rich2["matches"] if m["session_id"] == a_session)
        self.assertEqual(row2["intro_state"], "accepted")
        # counterpart's own rich view mirrors the state through the same seam
        rich_a = product.rich_discover(alice.access_token, a_session, k=20)
        for match in rich_a["matches"]:
            self.assertIn(match["intro_state"],
                          {"available", "unavailable", "requested", "accepted"})

    def test_restart_preserves_connections_and_messages(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            db = ":ephemeral:" + Path(tmp).name
            live, identity, product = build_stack(db)
            alice = product.register("Alice")
            a_session, _ = share_thought(
                product, alice, r7_dna("ses-gabe-warehouse", "thought-alice"),
                intent=ShareIntent(share_display_profile=True,
                                   receive_intro_requests=True))
            bob = product.register("Bob")
            b_session, _ = share_thought(
                product, bob, r7_dna(QUERY_DNA, "thought-bob-query"))
            intro = product.request_intro(
                bob.access_token, from_session_id=b_session,
                target_session_id=a_session, message="connect?",
                request_id="r1", confirmed=True)
            accepted = product.respond_intro(
                alice.access_token, intro["intro_id"], accept=True,
                request_id="a1", confirmed=True)
            product.send_message(bob.access_token, accepted["channel_id"],
                                 "survives restart?", request_id="m1",
                                 confirmed=True)
            live.repo.close()

            live2, identity2, product2 = build_stack(db)
            thread = product2.read_messages(alice.access_token,
                                            accepted["channel_id"])
            self.assertEqual(thread["messages"][0]["body"], "survives restart?")
            outgoing = product2.list_requests(bob.access_token)["outgoing"]
            self.assertEqual(outgoing[0]["state"], "accepted")
            live2.repo.close()


if __name__ == "__main__":
    unittest.main()
