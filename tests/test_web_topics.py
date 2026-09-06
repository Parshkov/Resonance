"""Shared topics on the website (2026-09-05).

Until now a topic existed only for someone in a chat: the tools could open
one, contribute to one and read the delta, and a person on the site could not
see that any of it existed. These tests drive the page's routes over real HTTP
with real cookies, as three people, and hold what the page depends on:

- one contributes, another reads it once, as a delta, marked as theirs;
- the topic says where the two accounts agree and where they contradict each
  other, in the words the people used and never in an engine identifier;
- an invitation is offered, listed to the invitee, and accepted;
- a retried contribution is one contribution.
"""

from __future__ import annotations

import json
import re
import threading
import unittest
from http.cookies import SimpleCookie
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from src.product.server import build_runtime
from src.product.web_server import serve

ENGINE_ID = re.compile(r"^[nr]\d+$")


def graph(nodes, relations):
    return {"nodes": [{"id": f"n{i}", "label": label, "role": role}
                      for i, (label, role) in enumerate(nodes)],
            "relations": [{"source": f"n{a}", "target": f"n{b}", "type": kind}
                          for a, b, kind in relations]}


PUSHED = graph([("pressure to ship", "problem"), ("skipped review", "mechanism"),
                ("rework", "outcome"), ("slack time", "method")],
               [(0, 1, "causes"), (1, 2, "causes"), (3, 2, "prevents")])
# The same shape with one link the other way round: what the engine reports
# as a contradiction, which is the thing a topic exists to surface.
PUSHED_BACK = graph([("pressure to ship", "problem"), ("skipped review", "mechanism"),
                     ("rework", "outcome"), ("slack time", "method")],
                    [(0, 1, "causes"), (1, 2, "causes"), (3, 2, "causes")])
FED = graph([("over-fertilising", "problem"), ("salt accumulation", "mechanism"),
             ("root damage", "outcome"), ("leaching schedule", "method")],
            [(0, 1, "causes"), (1, 2, "causes"), (3, 2, "prevents")])


class Person:
    """A browser: one cookie jar, one CSRF token, same-origin requests."""

    def __init__(self, base: str):
        self.base = base
        self.cookie = None
        self.csrf = None
        self.pseudonym = ""
        self.session_id = ""

    def request(self, method: str, path: str, body=None):
        headers = {"Content-Type": "application/json", "Origin": self.base}
        if self.cookie:
            headers["Cookie"] = self.cookie
        if self.csrf:
            headers["X-Resonance-CSRF"] = self.csrf
        data = json.dumps(body).encode() if body is not None else None
        with urlopen(Request(self.base + path, data=data, headers=headers, method=method),
                     timeout=15) as response:
            set_cookie = response.headers.get("Set-Cookie")
            if set_cookie:
                morsel = SimpleCookie(set_cookie).get("resonance_token")
                if morsel is not None:
                    self.cookie = f"resonance_token={morsel.value}"
            return response.status, json.loads(response.read().decode())

    def status_of(self, method: str, path: str, body=None) -> int:
        try:
            return self.request(method, path, body)[0]
        except HTTPError as error:
            return error.code

    def arrive(self, tag: str, thought):
        _, creds = self.request("POST", "/api/product/guest", {})
        self.csrf = creds["csrf_token"]
        _, state = self.request("GET", "/api/product/state")
        self.pseudonym = state["account"]["display_label"]
        self.request("POST", "/api/webmcp/prepare", {
            "request_id": f"{tag}-prepare", "authorship": "their_own_words",
            "thought": thought})
        _, preview = self.request("GET", "/api/webmcp/preview")
        _, shared = self.request("POST", "/api/webmcp/share", {
            "request_id": f"{tag}-share", "confirm": True,
            "confirmation_token": preview["confirmation_token"]})
        self.session_id = shared["session_id"]
        return self


class WebTopicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pending = build_runtime(":ephemeral:", allowed_origins=frozenset({"pending"}))
        server = serve("127.0.0.1", 0, runtime=pending)
        host, port = server.server_address[:2]
        cls.base = f"http://{host}:{port}"
        server.RequestHandlerClass.runtime = build_runtime(
            ":ephemeral:", allowed_origins=frozenset({cls.base}), seed=False)
        cls.server = server
        cls.thread = threading.Thread(target=server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)

    def setUp(self):
        self.alice = Person(self.base).arrive("alice", PUSHED)
        self.bob = Person(self.base).arrive("bob", PUSHED_BACK)
        self.carol = Person(self.base).arrive("carol", FED)
        self.bob_intro = self._introduce(self.bob, self.alice, "b")
        self.carol_intro = self._introduce(self.carol, self.alice, "c")
        _, opened = self.alice.request("POST", "/api/product/workspace/create", {
            "intro_id": self.bob_intro, "title": "Pressure that backfires"})
        self.topic = opened["workspace_id"]
        self.bob.request("POST", "/api/product/workspace/respond",
                         {"workspace_id": self.topic, "accept": True})

    def _introduce(self, asker: Person, target: Person, tag: str) -> str:
        asker.request("POST", "/api/product/intro/request", {
            "from_session_id": asker.session_id, "target_session_id": target.session_id,
            "message": "same shape?", "request_id": f"{tag}-ask", "confirmed": True})
        _, listed = target.request("GET", "/api/product/intro/list")
        intro = next(i for i in listed["incoming"]
                     if i["counterpart_display"] == asker.pseudonym)
        target.request("POST", "/api/product/intro/respond", {
            "intro_id": intro["intro_id"], "accept": True,
            "request_id": f"{tag}-accept", "confirmed": True})
        return intro["intro_id"]

    def _contribute(self, who: Person, thought, note: str, request_id: str):
        return who.request("POST", "/api/product/topic/contribute", {
            "workspace_id": self.topic, "thought": thought, "note": note,
            "confirmed": True, "request_id": request_id})[1]

    def _read(self, who: Person, advance: bool = True):
        flag = "1" if advance else "0"
        return who.request("GET", f"/api/product/topic?workspace_id={self.topic}&advance={flag}")[1]

    def _bring_in_carol(self):
        _, invited = self.alice.request("POST", "/api/product/topic/invite", {
            "workspace_id": self.topic, "intro_id": self.carol_intro})
        self.carol.request("POST", "/api/product/workspace/respond",
                           {"workspace_id": self.topic, "accept": True})
        return invited

    # -- the page can see a topic ------------------------------------------
    def test_a_topic_is_listed_with_its_people_and_what_is_waiting(self):
        self._contribute(self.bob, PUSHED_BACK, "Slack time only adds to the rework.", "b1")
        _, listed = self.alice.request("GET", "/api/product/topics")
        self.assertEqual(listed["viewer_pseudonym"], self.alice.pseudonym)
        topic = next(t for t in listed["topics"] if t["workspace_id"] == self.topic)
        self.assertEqual(topic["title"], "Pressure that backfires")
        self.assertEqual(topic["new_for_you"], 1)
        self.assertEqual({m["pseudonym"] for m in topic["members"]},
                         {self.alice.pseudonym, self.bob.pseudonym})
        self.assertEqual([m["you"] for m in topic["members"]].count(True), 1)
        # A glance marks nothing read.
        _, again = self.alice.request("GET", "/api/product/topics")
        self.assertEqual(next(t for t in again["topics"]
                              if t["workspace_id"] == self.topic)["new_for_you"], 1)

    def test_a_person_in_no_topic_gets_an_empty_list_not_an_error(self):
        _, listed = self.carol.request("GET", "/api/product/topics")
        self.assertEqual(listed["topics"], [])
        self.assertEqual(listed["invitations"], [])

    # -- one contributes, another reads the delta --------------------------
    def test_what_one_side_adds_reaches_the_other_once_and_as_theirs(self):
        self._contribute(self.alice, PUSHED, "Slack time is what actually prevents it.", "a1")
        seen = self._read(self.bob)
        self.assertEqual(seen["new_for_you"], 1)
        item = seen["delta"][0]
        self.assertEqual(item["note"], "Slack time is what actually prevents it.")
        self.assertEqual(item["author_pseudonym"], self.alice.pseudonym)
        self.assertTrue(item["untrusted"])
        self.assertEqual([n["label"] for n in item["thought"]["nodes"]][:2],
                         ["pressure to ship", "skipped review"])
        self.assertNotIn("provenance", item["thought"])
        self.assertNotIn("source", item["thought"])
        # Read once: the cursor moved.
        self.assertEqual(self._read(self.bob)["new_for_you"], 0)
        # Before the other side has said anything, the topic says so plainly.
        self.assertFalse(seen["standing"]["available"])
        self.assertIn("contribute your own", seen["standing"]["reason"])

    def test_a_look_without_advancing_leaves_it_new(self):
        self._contribute(self.alice, PUSHED, "first", "a1")
        self.assertEqual(self._read(self.bob, advance=False)["new_for_you"], 1)
        self.assertEqual(self._read(self.bob)["new_for_you"], 1)

    # -- the agreement and the contradiction, in words ----------------------
    def test_the_topic_says_where_they_agree_and_where_they_contradict(self):
        self._contribute(self.alice, PUSHED, "slack prevents rework", "a1")
        self._contribute(self.bob, PUSHED_BACK, "slack only adds rework", "b1")
        standing = self._read(self.bob)["standing"]
        self.assertTrue(standing["available"])
        side = next(s for s in standing["sides"] if s["with_pseudonym"] == self.alice.pseudonym)
        self.assertIn({"yours": "pressure to ship", "theirs": "pressure to ship"},
                      side["agreed_nodes"])
        self.assertGreaterEqual(side["agreed_relations"], 1)
        self.assertEqual(side["contested"], [
            {"kind": "relation_type", "yours": "slack time causes rework",
             "theirs": "slack time prevents rework"}])
        self.assertIsInstance(side["classification"], str)
        self.assertIsInstance(side["confidence"], str)
        # Nothing the engine names by id reaches the page as an id.
        for text in json.dumps(standing).split('"'):
            self.assertIsNone(ENGINE_ID.match(text), text)

    def test_a_contribution_from_text_is_shown_back_as_structure_first(self):
        _, preview = self.alice.request("POST", "/api/product/topic/preview", {
            "context": "Pressure to ship causes skipped review. Skipped review causes "
                       "rework. Slack time prevents rework."})
        labels = [n["label"].lower() for n in preview["thought"]["nodes"]]
        self.assertGreaterEqual(len(labels), 2)
        self.assertGreaterEqual(len(preview["thought"]["relations"]), 1)
        # Looking stored nothing: the share composer's draft is untouched.
        _, state = self.alice.request("GET", "/api/webmcp/state")
        self.assertFalse(state["draft_ready"])
        # And the same structure is accepted as a contribution.
        added = self._contribute(self.alice, preview["thought"], "from my own words", "a-text")
        self.assertEqual(added["nodes"], len(labels))
        self.assertTrue(added["say"].startswith("Added to the shared topic"))

    def test_text_with_no_structure_is_answered_in_plain_words(self):
        with self.assertRaises(HTTPError) as caught:
            self.alice.request("POST", "/api/product/topic/preview", {"context": "hello there"})
        self.assertEqual(caught.exception.code, 400)
        answer = json.loads(caught.exception.read().decode())
        self.assertIn("what causes what", answer["message"])
        self.assertNotIn("`", answer["message"])

    # -- the invitation ------------------------------------------------------
    def test_an_invitation_is_offered_listed_and_accepted(self):
        _, invited = self.alice.request("POST", "/api/product/topic/invite", {
            "workspace_id": self.topic, "intro_id": self.carol_intro})
        self.assertEqual(invited["invited_pseudonym"], self.carol.pseudonym)
        self.assertEqual(invited["state"], "invited")
        self.assertNotIn("user_id", json.dumps(invited))
        _, listed = self.carol.request("GET", "/api/product/topics")
        self.assertEqual(listed["topics"], [])
        invitation = listed["invitations"][0]
        self.assertEqual(invitation["title"], "Pressure that backfires")
        self.assertEqual(invitation["invited_by_pseudonym"], self.alice.pseudonym)
        # Nothing inside is readable before joining.
        self.assertEqual(self.carol.status_of(
            "GET", f"/api/product/topic?workspace_id={self.topic}"), 400)
        self.carol.request("POST", "/api/product/workspace/respond",
                           {"workspace_id": self.topic, "accept": True})
        _, listed = self.carol.request("GET", "/api/product/topics")
        self.assertEqual(listed["invitations"], [])
        self.assertEqual(len(listed["topics"][0]["members"]), 3)

    def test_only_an_accepted_introduction_can_be_invited(self):
        stranger = Person(self.base).arrive("dana", FED)
        stranger.request("POST", "/api/product/intro/request", {
            "from_session_id": stranger.session_id, "target_session_id": self.alice.session_id,
            "message": "?", "request_id": "d-ask", "confirmed": True})
        _, listed = self.alice.request("GET", "/api/product/intro/list")
        pending = next(i for i in listed["incoming"] if i["state"] == "requested")
        self.assertEqual(self.alice.status_of("POST", "/api/product/topic/invite", {
            "workspace_id": self.topic, "intro_id": pending["intro_id"]}), 400)
        # Nor can a member invite through an introduction that is not theirs.
        self.assertEqual(self.bob.status_of("POST", "/api/product/topic/invite", {
            "workspace_id": self.topic, "intro_id": self.carol_intro}), 400)

    # -- three people ----------------------------------------------------------
    def test_three_people_read_each_other_and_the_standing_has_two_sides(self):
        self._bring_in_carol()
        self._contribute(self.alice, PUSHED, "from alice", "a1")
        self._contribute(self.bob, PUSHED_BACK, "from bob", "b1")
        seen = self._read(self.carol)
        self.assertEqual(seen["new_for_you"], 2)
        self.assertEqual({row["author_pseudonym"] for row in seen["delta"]},
                         {self.alice.pseudonym, self.bob.pseudonym})
        self._contribute(self.carol, FED, "from carol", "c1")
        standing = self._read(self.carol)["standing"]
        self.assertEqual({s["with_pseudonym"] for s in standing["sides"]},
                         {self.alice.pseudonym, self.bob.pseudonym})
        _, listed = self.alice.request("GET", "/api/product/topics")
        self.assertEqual(listed["topics"][0]["new_for_you"], 2)

    # -- boundaries and retries ------------------------------------------------
    def test_a_stranger_can_neither_read_nor_contribute(self):
        stranger = Person(self.base).arrive("eve", FED)
        self.assertEqual(stranger.status_of(
            "GET", f"/api/product/topic?workspace_id={self.topic}"), 400)
        self.assertEqual(stranger.status_of("POST", "/api/product/topic/contribute", {
            "workspace_id": self.topic, "thought": FED, "note": "", "confirmed": True,
            "request_id": "e1"}), 400)

    def test_contributing_needs_approval_and_a_csrf_token(self):
        self.assertEqual(self.alice.status_of("POST", "/api/product/topic/contribute", {
            "workspace_id": self.topic, "thought": PUSHED, "note": "", "confirmed": False,
            "request_id": "a-unconfirmed"}), 400)
        token, self.alice.csrf = self.alice.csrf, None
        try:
            self.assertEqual(self.alice.status_of("POST", "/api/product/topic/contribute", {
                "workspace_id": self.topic, "thought": PUSHED, "note": "", "confirmed": True,
                "request_id": "a-nocsrf"}), 403)
        finally:
            self.alice.csrf = token
        self.assertEqual(self._read(self.bob)["contributions_total"], 0)

    def test_a_retried_contribution_is_one_contribution(self):
        body = {"workspace_id": self.topic, "thought": PUSHED, "note": "once",
                "confirmed": True, "request_id": "a-retry"}
        _, first = self.alice.request("POST", "/api/product/topic/contribute", body)
        _, second = self.alice.request("POST", "/api/product/topic/contribute", body)
        self.assertEqual(first["contribution_id"], second["contribution_id"])
        self.assertEqual(self._read(self.bob)["contributions_total"], 1)
        self.assertEqual(self.alice.status_of("POST", "/api/product/topic/contribute",
                                              {**body, "note": "twice"}), 409)
        _, record = self.alice.request(
            "GET", "/api/webmcp/operation?operation=contribute&request_id=a-retry")
        self.assertTrue(record["committed"])

    # -- the page itself ---------------------------------------------------------
    def test_the_page_has_a_groups_screen_over_the_same_routes(self):
        with urlopen(self.base + "/main.mjs", timeout=10) as response:
            source = response.read().decode()
        for route in ("/api/product/topic/preview", "/api/product/topic/contribute",
                      "/api/product/topic/invite", "/api/product/workspace/create",
                      "/api/product/workspace/note", "/api/product/workspace/task"):
            self.assertIn(route, source, route)
        self.assertNotIn("innerHTML", source)
        with urlopen(self.base + "/groups", timeout=10) as response:
            html = response.read().decode()
        self.assertIn('src="/main.mjs"', html)
        with urlopen(self.base + "/app.css", timeout=10) as response:
            css = response.read().decode()
        self.assertNotRegex(css.split(":root")[0], r"#[0-9a-fA-F]{3,8}\b",
                            "raw colours outside the palette blocks")


if __name__ == "__main__":
    unittest.main()
