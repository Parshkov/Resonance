"""Telling someone while they are not here (2026-09-05).

The product's promise is that it keeps looking after you leave. The standing
search kept that half faithfully -- it recorded the finding, both ways, never
twice -- and then nobody was told. "Told" meant "will see it if they come
back", so someone could wait three weeks with the answer sitting on a page
they had no reason to open.

These hold the part of the fix that can be checked without a mail server, and
the two things that must stay true whatever the transport does: an email says
that something happened and never what, and the way out never requires signing
in.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from src.product import notify  # noqa: E402
from src.product.mcp_bridge import RemoteMCPBridge  # noqa: E402
from src.product.server import build_runtime  # noqa: E402

MINE = {"topic": "pressure", "domain": "organisations",
        "nodes": [{"id": "n0", "label": "delivery pressure", "role": "problem"},
                  {"id": "n1", "label": "skipped review", "role": "mechanism"},
                  {"id": "n2", "label": "rework", "role": "outcome"}],
        "relations": [{"source": "n0", "target": "n1", "type": "causes"},
                      {"source": "n1", "target": "n2", "type": "causes"}]}
THEIRS = {"topic": "soil", "domain": "agriculture",
          "nodes": [{"id": "m0", "label": "yield pressure", "role": "problem"},
                    {"id": "m1", "label": "salt accumulation", "role": "mechanism"},
                    {"id": "m2", "label": "root damage", "role": "outcome"}],
          "relations": [{"source": "m0", "target": "m1", "type": "causes"},
                        {"source": "m1", "target": "m2", "type": "causes"}]}


class Remembering(notify.Sender):
    """A mail server that keeps what it was handed, so a test can read it."""

    def __init__(self):
        self.sent = []

    def send(self, to, subject, body):
        self.sent.append({"to": to, "subject": subject, "body": body})
        return True


class WhatAnEmailSaysTests(unittest.TestCase):
    def setUp(self):
        self.runtime = build_runtime(":memory:",
                                     allowed_origins=frozenset({"http://127.0.0.1"}),
                                     seed=False)
        self.bridge = RemoteMCPBridge(self.runtime.product)
        self.sender = Remembering()
        self.notifier = self.runtime.product.notifier
        self.notifier.sender = self.sender

    def signed_in(self, subject: str, email: str, verified: bool = True):
        return self.runtime.identity.sign_in_federated(
            provider="google", subject=subject, email=email,
            email_verified=verified, display_label="Ada Lovelace")

    def share(self, token, what, tag):
        draft = self.bridge.tool_prepare_thought(
            token, {"authorship": "their_own_words", "thought": what,
                    "request_id": tag + "-1"})
        return self.bridge.tool_share_thought(
            token, {"draft_id": draft["draft_id"], "confirm": True,
                    "confirmation_token": draft["confirmation_token"],
                    "request_id": tag + "-2"})

    def test_someone_who_left_is_actually_told(self):
        waiting = self.signed_in("s1", "waiting@example.test")
        self.share(waiting.access_token, MINE, "mine")
        self.sender.sent.clear()

        arriving = self.signed_in("s2", "arriving@example.test")
        self.share(arriving.access_token, THEIRS, "theirs")

        recipients = {message["to"] for message in self.sender.sent}
        self.assertIn("waiting@example.test", recipients,
                      "the person who had left was not told anything")

    def test_the_email_carries_nothing_about_the_other_person(self):
        """On the page an arrival card names their pseudonym and topic, and
        that is right: they are signed in, on the surface where the match was
        made. An email is forwarded, backed up, and read by whatever assistant
        is pointed at that inbox."""
        waiting = self.signed_in("s1", "waiting@example.test")
        self.share(waiting.access_token, MINE, "mine")
        self.sender.sent.clear()
        arriving = self.signed_in("s2", "arriving@example.test")
        shared = self.share(arriving.access_token, THEIRS, "theirs")

        their_label = self.runtime.identity.backend.get_user(
            arriving.user_id).display_label
        for message in self.sender.sent:
            whole = message["subject"] + message["body"]
            about_them = [their_label, "soil", "agriculture",
                          "salt accumulation", shared["session_id"]]
            if message["to"] != "arriving@example.test":
                # Their own address and account are theirs to see; nobody
                # else's ever appears.
                about_them += [arriving.user_id, "arriving@example.test"]
            for secret in about_them:
                self.assertNotIn(secret, whole, secret)

    def test_an_unverified_address_never_becomes_an_account_at_all(self):
        """An unverified address belongs to whoever claimed it, so telling it a
        resonance appeared would be the first thing this must never do. Sign-in
        refuses one outright, which is why address_for can trust what it finds."""
        with self.assertRaises(Exception):
            self.signed_in("s1", "claimed@example.test", verified=False)
        self.assertIsNone(self.notifier.address_for("person-not-a-real-account"))

    def test_only_one_a_day(self):
        waiting = self.signed_in("s1", "waiting@example.test")
        self.assertEqual(self.notifier.tell(waiting.user_id), "sent")
        self.assertEqual(self.notifier.tell(waiting.user_id), "already_told_today")
        self.assertEqual(len(self.sender.sent), 1)

    def test_the_way_out_needs_no_sign_in(self):
        """"To stop these emails, log in first" is the sentence nobody follows;
        the alternative they choose is marking us as spam."""
        waiting = self.signed_in("s1", "waiting@example.test")
        self.notifier.tell(waiting.user_id)
        body = self.sender.sent[0]["body"]
        self.assertIn("/notifications/stop", body)
        token = body.split("token=")[1].split()[0].strip()
        self.assertTrue(notify.unsubscribe_matches(waiting.user_id, token,
                                                   self.notifier.secret))
        self.assertFalse(notify.unsubscribe_matches("person-someone-else", token,
                                                    self.notifier.secret))

    def test_stopping_stops_it(self):
        waiting = self.signed_in("s1", "waiting@example.test")
        self.notifier.unsubscribe(waiting.user_id)
        self.assertEqual(self.notifier.tell(waiting.user_id), "unsubscribed")
        self.assertEqual(self.sender.sent, [])

    def test_with_no_mail_server_nothing_pretends_to_have_been_sent(self):
        """A queue nobody drains is worse than an empty one: it looks like the
        feature exists."""
        self.notifier.sender = notify.NoTransport()
        waiting = self.signed_in("s1", "waiting@example.test")
        self.assertEqual(self.notifier.tell(waiting.user_id), "no_transport")
        self.assertIsNone(self.notifier._get(notify.SENT_KIND, waiting.user_id))

    def test_a_mail_server_having_a_bad_afternoon_never_breaks_a_share(self):
        class Broken(notify.Sender):
            def send(self, to, subject, body):
                raise RuntimeError("connection refused")

        self.notifier.sender = Broken()
        waiting = self.signed_in("s1", "waiting@example.test")
        self.share(waiting.access_token, MINE, "mine")
        arriving = self.signed_in("s2", "arriving@example.test")
        shared = self.share(arriving.access_token, THEIRS, "theirs")
        self.assertTrue(shared.get("shared"))



class WhereTheLinkPointsTests(unittest.TestCase):
    """An email is useless if it sends someone to a host that no longer exists.

    Production serves two origins: the custom domain people use, and the
    platform host it was first deployed to. `allowed_origins` is a set, so it
    cannot say which is canonical, and picking the alphabetically first https
    one chose the platform host -- which had already been deleted. Every link
    in every notification would have led nowhere.

    The order the operator declared them in is the only thing that says it.
    """

    ORIGINS = frozenset({"https://resonance-production-cfe3.up.railway.app",
                         "https://resonance.parshkov.com"})

    def test_links_use_the_host_people_actually_visit(self):
        runtime = build_runtime(
            ":memory:", allowed_origins=self.ORIGINS, seed=False,
            declared_origins=["https://resonance.parshkov.com",
                              "https://resonance-production-cfe3.up.railway.app"])
        self.assertEqual(runtime.product.notifier.origin,
                         "https://resonance.parshkov.com")

    def test_the_unsubscribe_link_goes_to_the_same_place(self):
        runtime = build_runtime(
            ":memory:", allowed_origins=self.ORIGINS, seed=False,
            declared_origins=["https://resonance.parshkov.com",
                              "https://resonance-production-cfe3.up.railway.app"])
        url = runtime.product.notifier.unsubscribe_url("person-abc")
        self.assertTrue(url.startswith("https://resonance.parshkov.com/notifications/stop"),
                        url)
        self.assertNotIn("person-abc", url,
                         "the account id must travel inside the signed token")

if __name__ == "__main__":
    unittest.main()
