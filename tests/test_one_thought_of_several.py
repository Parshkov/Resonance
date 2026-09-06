"""A person with more than one thought here, and what the page says to them.

Three defects, none of which an empty instance can show, because each needs
two thoughts from one person:

1. Which thought the page was "about" was a coin toss. `owned_sessions` comes
   back in the store's order -- by session id, which is random hex -- and the
   page took the last row. So did the chat's `resonance_discover` without a
   `session_id`. Both now mean the thought most recently made discoverable,
   by one rule in one place.

2. Withdraw one of two, and the page kept drawing the withdrawn one under
   "What others can see": it only re-read when sharing flipped between
   something and nothing. Now it re-reads when what is discoverable changes.

3. "Private · nothing of yours is discoverable" was said to a person whose
   thought was withdrawn, not private. The line is now built from the three
   counts the chat's whoami reports, and "nothing of yours is discoverable"
   is only ever said of a person for whom it is true.

These fail against the code before the change and pass after it; the ones
that reach the browser modules run them under node, without a document.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from src.product.mcp_bridge import RemoteMCPBridge, current_shared_session
from src.product.phrasing import say
from src.product.server import UI_DIR
from src.product.web_server import _owned_live_session

import threading
from http.cookies import SimpleCookie
from urllib.request import Request, urlopen

from src.product.server import build_runtime
from src.product.web_server import serve


def thought(topic: str, labels: list[str]) -> dict:
    return {
        "topic": topic, "domain": "operations",
        "nodes": [{"id": f"n{i}", "label": label, "role": role}
                  for i, (label, role) in enumerate(zip(labels, ("problem", "mechanism", "outcome")))],
        "relations": [{"source": "n0", "target": "n1", "type": "causes"},
                      {"source": "n1", "target": "n2", "type": "causes"}],
    }


class Person:
    """One person at a browser: a cookie session and its CSRF token."""

    def __init__(self, base: str):
        self.base = base
        self.cookie = None
        self.token = None
        self.csrf = None
        self.counter = 0

    def request(self, method: str, path: str, body=None, *, cookie=True):
        headers = {"Content-Type": "application/json", "Origin": self.base}
        if cookie and self.cookie:
            headers["Cookie"] = self.cookie
        if self.csrf:
            headers["X-Resonance-CSRF"] = self.csrf
        data = json.dumps(body).encode() if body is not None else None
        req = Request(self.base + path, data=data, headers=headers, method=method)
        with urlopen(req, timeout=15) as response:
            set_cookie = response.headers.get("Set-Cookie")
            if set_cookie:
                morsel = SimpleCookie(set_cookie).get("resonance_token")
                if morsel is not None:
                    self.token = morsel.value
                    self.cookie = f"resonance_token={morsel.value}"
            return response.status, json.loads(response.read().decode())

    def arrive(self):
        _, payload = self.request("POST", "/api/product/guest", {})
        self.csrf = payload["csrf_token"]
        return payload

    def prepare(self, what: dict) -> str:
        self.counter += 1
        _, prepared = self.request("POST", "/api/webmcp/prepare", {
            "request_id": f"prep-{self.counter}", "authorship": "their_own_words",
            "thought": what})
        return prepared["session_id"]

    def share(self, what: dict) -> str:
        session_id = self.prepare(what)
        _, preview = self.request("GET", "/api/webmcp/preview")
        self.counter += 1
        _, shared = self.request("POST", "/api/webmcp/share", {
            "request_id": f"share-{self.counter}", "confirm": True,
            "confirmation_token": preview["confirmation_token"]})
        assert shared["discoverable"], shared
        assert shared["session_id"] == session_id
        return session_id

    def mine(self) -> dict:
        _, payload = self.request("GET", "/api/product/mine")
        return payload


def _live_server():
    pending = build_runtime(":memory:", allowed_origins=frozenset({"pending"}), seed=False)
    server = serve("127.0.0.1", 0, runtime=pending)
    host, port = server.server_address[:2]
    base = f"http://{host}:{port}"
    runtime = build_runtime(":memory:", allowed_origins=frozenset({base}), seed=False)
    server.RequestHandlerClass.runtime = runtime
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, base, runtime

REPO = Path(__file__).resolve().parents[1]
NODE = shutil.which("node")


# ---- 1. the thought this page is about ------------------------------------

class _Event:
    def __init__(self, user_id, session_id, event_type, created_at, payload=None):
        self.user_id, self.session_id = user_id, session_id
        self.event_type, self.created_at = event_type, created_at
        self.payload = payload or {}


class _Actor:
    user_id = "person-1"


class _FakeProduct:
    """Just enough of the product to hand `current_shared_session` its inputs,
    with the store's order under our control."""

    def __init__(self, rows, events):
        self.rows, self.events = rows, events
        self.identity = self

    def owned_sessions(self, token):
        return list(self.rows)

    def authenticate(self, token):
        return _Actor()

    @property
    def backend(self):
        return self

    def list_identity_events(self):
        return list(self.events)


class WhichThoughtTests(unittest.TestCase):
    def test_the_most_recently_shared_thought_not_the_last_row(self):
        from src.ingestion.identity import INGESTION_SHARED
        # The store lists "older" last (its ids sort that way); the person
        # shared "newer" more recently. The old rule took the last row.
        rows = [{"session_id": "ses-newer", "share_state": "discoverable", "created_at": "t1"},
                {"session_id": "ses-older", "share_state": "discoverable", "created_at": "t0"}]
        events = [_Event("person-1", "ses-older", INGESTION_SHARED, "2026-09-01T10:00:00"),
                  _Event("person-1", "ses-newer", INGESTION_SHARED, "2026-09-02T10:00:00")]
        self.assertEqual(current_shared_session(_FakeProduct(rows, events), "tok"), "ses-newer")
        # Re-sharing the older one later makes it the current one: sharing is
        # the act that changes what others can see.
        from src.identity.service import CONSENT_SET
        events.append(_Event("person-1", "ses-older", CONSENT_SET, "2026-09-03T10:00:00",
                             {"share_thought_dna": True}))
        self.assertEqual(current_shared_session(_FakeProduct(rows, events), "tok"), "ses-older")
        # A consent event that did NOT make it discoverable is not a share.
        events.append(_Event("person-1", "ses-newer", CONSENT_SET, "2026-09-04T10:00:00",
                             {"share_thought_dna": False}))
        self.assertEqual(current_shared_session(_FakeProduct(rows, events), "tok"), "ses-older")

    def test_only_discoverable_thoughts_count_and_none_is_none(self):
        rows = [{"session_id": "ses-a", "share_state": "revoked", "created_at": "t0"},
                {"session_id": "ses-b", "share_state": "prepared_private", "created_at": "t1"}]
        self.assertIsNone(current_shared_session(_FakeProduct(rows, []), "tok"))

    def test_without_a_consent_log_the_answer_is_still_the_same_every_time(self):
        # Seeded records have no consent event: fall back to when the thought
        # was prepared, then to the id, so a person never sees the page
        # change its mind between two reads.
        rows = [{"session_id": "ses-z", "share_state": "discoverable", "created_at": "t0"},
                {"session_id": "ses-a", "share_state": "discoverable", "created_at": "t1"}]
        self.assertEqual(current_shared_session(_FakeProduct(rows, []), "tok"), "ses-a")
        tied = [{"session_id": "ses-z", "share_state": "discoverable", "created_at": "t0"},
                {"session_id": "ses-a", "share_state": "discoverable", "created_at": "t0"}]
        self.assertEqual(current_shared_session(_FakeProduct(tied, []), "tok"), "ses-z")
        self.assertEqual(current_shared_session(_FakeProduct(list(reversed(tied)), []), "tok"), "ses-z")


class OverHttpTests(unittest.TestCase):
    """One person, two thoughts, over the routes the page and the chat use."""

    @classmethod
    def setUpClass(cls):
        cls.server, cls.base, cls.runtime = _live_server()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def context_topic(self, person: Person) -> str:
        _, context = person.request("GET", "/api/context")
        return context["presentation"]["topic"]

    def test_the_page_is_about_the_thought_shared_last_whatever_its_id(self):
        person = Person(self.base)
        person.arrive()
        shared = []
        for i in range(6):
            topic = f"Thought number {i}"
            shared.append((topic, person.share(thought(topic, [f"a{i}", f"b{i}", f"c{i}"]))))
            # The old rule picked the greatest id. Keep sharing until the
            # newest thought is not the one with the greatest id, so that the
            # old rule and the right one disagree, then check the right one.
            if shared[-1][1] != max(session_id for _, session_id in shared):
                break
        newest_topic, newest_id = shared[-1]
        self.assertEqual(self.context_topic(person), newest_topic)
        self.assertEqual(_owned_live_session(self.runtime.product, person.token), newest_id)
        # And the chat means the same thought when it is not told which.
        bridge = RemoteMCPBridge(self.runtime.product)
        self.assertEqual(bridge._default_session(person.token), newest_id)

    def test_stop_sharing_from_the_page_withdraws_that_thought_and_says_so(self):
        person = Person(self.base)
        person.arrive()
        first = person.share(thought("Kept out there", ["deadline", "skipped review", "rework"]))
        second = person.share(thought("Taken back", ["fertiliser", "salt", "root damage"]))
        self.assertEqual(self.context_topic(person), "Taken back")

        # The page's own "Stop sharing" control makes exactly this call.
        _, answer = person.request("POST", "/api/webmcp/consent",
                                   {"request_id": "stop-1", "shared": False, "confirm": True})
        self.assertEqual(answer["session_id"], second)
        self.assertTrue(answer["revoked"])
        self.assertFalse(answer["discoverable"], "the fact about the thought")
        self.assertFalse(answer["shared"], "also about the thought, as the chat tool's is")
        self.assertEqual(answer["still_discoverable"], 1, "the fact about the person")
        # What they are told is true of the thought, then true of them.
        self.assertIn("That thought is not discoverable any more", answer["say"])
        self.assertIn("1 other thought of yours is still discoverable", answer["say"])
        self.assertNotIn("Nothing of yours", answer["say"])

        # The page now draws the one that is still out there.
        self.assertEqual(self.context_topic(person), "Kept out there")
        self.assertEqual(_owned_live_session(self.runtime.product, person.token), first)

        # And the chat says the same three things about this person.
        theirs = RemoteMCPBridge(self.runtime.product).tool_whoami(person.token, {})
        self.assertEqual(theirs["shared_thoughts"], [first])
        self.assertEqual(theirs["withdrawn_thoughts"], [second])
        self.assertEqual(theirs["private_thoughts"], [])
        _, mine = person.request("GET", "/api/product/mine")
        self.assertEqual(mine["counts"], {"discoverable": 1, "private": 0, "withdrawn": 1})

        # Taking back the last one: now, and only now, nothing of theirs is.
        _, answer = person.request("POST", "/api/webmcp/consent",
                                   {"request_id": "stop-2", "shared": False, "confirm": True})
        self.assertEqual(answer["session_id"], first)
        self.assertEqual(answer["still_discoverable"], 0)
        self.assertIn("Nothing of yours is discoverable now", answer["say"])

    def test_the_chat_tool_says_the_same_about_the_person(self):
        person = Person(self.base)
        person.arrive()
        first = person.share(thought("One", ["a", "b", "c"]))
        person.share(thought("Two", ["d", "e", "f"]))
        bridge = RemoteMCPBridge(self.runtime.product)
        result = bridge.tool_stop_sharing(person.token, {"session_id": first, "confirm": True})
        self.assertEqual(result["still_discoverable"], 1)
        self.assertIn("1 other thought of yours is still discoverable",
                      say("resonance_stop_sharing", result))
        # A result without the count (an older client's wire) says only what
        # it knows: the thought, and nothing about the person.
        older = {k: v for k, v in result.items() if k != "still_discoverable"}
        self.assertEqual(say("resonance_stop_sharing", older),
                         "Withdrawn. That thought is not discoverable any more, and it will "
                         "not be reported to anyone as a match.")


# ---- 2 and 3. what the page says --------------------------------------------

class OnThePageTests(unittest.TestCase):
    """The page reads the three states from the store and says each in words."""
    words = (UI_DIR / "strings.mjs").read_text(encoding="utf-8")
    page = (UI_DIR / "main.mjs").read_text(encoding="utf-8")
    store = (UI_DIR / "store.mjs").read_text(encoding="utf-8")

    def test_the_page_reads_the_same_record_the_chat_reports(self):
        # /api/product/overview carries `mine`, the same three-state list
        # `resonance_whoami` sorts with `_in_state`.
        self.assertIn("/api/product/overview", self.store)
        for state in ("discoverable", "private", "withdrawn"):
            self.assertIn(f'"thoughts.state.{state}":', self.words)
            self.assertIn(f'"thoughts.state.{state}.hint":', self.words)

    def test_stopping_asks_once_inline_never_in_a_browser_dialog(self):
        self.assertNotIn("confirm(", self.page)
        self.assertIn("Yes, stop", self.words)
        self.assertIn("Keep sharing", self.words)
        self.assertIn("/api/product/revoke", self.page)

    def test_a_withdrawal_drops_every_cached_result(self):
        # Withdrawing one of two thoughts must not leave the other's people
        # list, or the withdrawn thought's, on the screen from a stale cache.
        revoke = self.page[self.page.index("/api/product/revoke"):]
        self.assertIn("discovery: true", revoke[:200])


if __name__ == "__main__":
    unittest.main()
