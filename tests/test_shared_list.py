"""Everything a person has here, in the same three states the chat reports.

The page showed the one discoverable thought and nothing else, so nobody
could see what they had shared over time, what was still private, or what
they had taken back. And the two halves disagreed: `resonance_whoami` called a
withdrawn thought "kept private here" while the page showed nothing at all.

These hold the new list to the chat's answer, thought by thought, over real
HTTP as one person: two shares, one withdrawal, one private draft, and one
deletion. They also keep identifiers and raw numbers off the screen.
"""

from __future__ import annotations

import json
import re
import threading
import unittest
from http.cookies import SimpleCookie
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from src.product.mcp_bridge import RemoteMCPBridge
from src.product.phrasing import say
from src.product.server import UI_DIR, build_runtime
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


def _floats(value, path="$"):
    if isinstance(value, float):
        yield path
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from _floats(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _floats(item, f"{path}[{index}]")


def _live_server():
    pending = build_runtime(":memory:", allowed_origins=frozenset({"pending"}), seed=False)
    server = serve("127.0.0.1", 0, runtime=pending)
    host, port = server.server_address[:2]
    base = f"http://{host}:{port}"
    runtime = build_runtime(":memory:", allowed_origins=frozenset({base}), seed=False)
    server.RequestHandlerClass.runtime = runtime
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, base, runtime


class EverythingHereTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server, cls.base, cls.runtime = _live_server()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def whoami(self, person: Person) -> dict:
        # The same account from a chat: the bridge is handed the very session
        # the browser holds, so both halves are asked about one person.
        return RemoteMCPBridge(self.runtime.product).tool_whoami(person.token, {})

    def assertAgrees(self, person: Person, mine: dict):
        theirs = self.whoami(person)
        by_state = {}
        for row in mine["thoughts"]:
            by_state.setdefault(row["state"], set()).add(row["session_id"])
        self.assertEqual(by_state.get("discoverable", set()), set(theirs["shared_thoughts"]))
        self.assertEqual(by_state.get("private", set()), set(theirs["private_thoughts"]))
        self.assertEqual(by_state.get("withdrawn", set()), set(theirs["withdrawn_thoughts"]))
        self.assertEqual(mine["counts"], {
            "discoverable": len(theirs["shared_thoughts"]),
            "private": len(theirs["private_thoughts"]),
            "withdrawn": len(theirs["withdrawn_thoughts"])})
        return theirs

    def test_nothing_yet_is_an_empty_list_on_both_sides(self):
        person = Person(self.base)
        person.arrive()
        mine = person.mine()
        self.assertEqual(mine["thoughts"], [])
        theirs = self.assertAgrees(person, mine)
        self.assertIn("Nothing of yours is discoverable", say("resonance_whoami", theirs))

    def test_three_states_over_http_agree_with_whoami(self):
        person = Person(self.base)
        person.arrive()
        first = person.share(thought("Pressure to ship", ["deadline", "skipped review", "rework"]))
        second = person.share(thought("Salt in the soil", ["fertiliser", "salt", "root damage"]))
        draft = person.prepare(thought("Never shared", ["queue", "retries", "saturation"]))

        # Taking the first one back: the same call the page's own control makes.
        _, withdrawn = person.request("POST", "/api/product/revoke",
                                      {"session_id": first, "confirmed": True})
        self.assertTrue(withdrawn["revoked"])

        mine = person.mine()
        state_of = {row["session_id"]: row for row in mine["thoughts"]}
        self.assertEqual(state_of[second]["state"], "discoverable")
        self.assertEqual(state_of[first]["state"], "withdrawn")
        self.assertEqual(state_of[draft]["state"], "private")
        self.assertEqual(mine["counts"], {"discoverable": 1, "private": 1, "withdrawn": 1})
        theirs = self.assertAgrees(person, mine)

        # The chat says the same three things in words.
        said = say("resonance_whoami", theirs)
        self.assertIn("1 thought of yours is discoverable", said)
        self.assertIn("1 thought is kept private here", said)

        # Each state carries the moment that matters for it.
        self.assertTrue(state_of[second]["shared_at"])
        self.assertIsNone(state_of[second]["withdrawn_at"])
        self.assertTrue(state_of[first]["shared_at"])
        self.assertTrue(state_of[first]["withdrawn_at"])
        self.assertGreaterEqual(state_of[first]["withdrawn_at"], state_of[first]["shared_at"])
        self.assertIsNone(state_of[draft]["shared_at"])
        self.assertIsNone(state_of[draft]["withdrawn_at"])
        for row in mine["thoughts"]:
            self.assertTrue(row["prepared_at"])

        # The structure it carries, as labels a person wrote, not node ids.
        self.assertEqual([n["label"] for n in state_of[first]["nodes"]],
                         ["deadline", "skipped review", "rework"])
        self.assertEqual(state_of[first]["relations"][0],
                         {"from": "deadline", "type": "causes", "to": "skipped review"})
        self.assertEqual(state_of[first]["topic"], "Pressure to ship")

        # Nothing in the payload is a raw number a person would have to read.
        self.assertEqual(list(_floats(mine)), [])
        # And nothing the page could accidentally print as an identifier
        # beyond the one it needs to name a thought to the server.
        for row in mine["thoughts"]:
            self.assertEqual(set(row) - {"session_id"}, {
                "state", "topic", "domain", "nodes", "relations",
                "prepared_at", "shared_at", "withdrawn_at"})

    def test_a_deleted_thought_is_gone_from_both_sides(self):
        person = Person(self.base)
        person.arrive()
        kept = person.share(thought("Kept", ["a", "b", "c"]))
        gone = person.share(thought("Gone", ["d", "e", "f"]))
        person.request("POST", "/api/product/delete", {"session_id": gone, "confirmed": True})
        mine = person.mine()
        self.assertEqual([row["session_id"] for row in mine["thoughts"]], [kept])
        theirs = self.assertAgrees(person, mine)
        self.assertEqual(theirs["withdrawn_thoughts"], [],
                         "a deleted thought is not listed as withdrawn on either side")

    def test_nobody_is_told_they_have_nothing(self):
        person = Person(self.base)
        with self.assertRaises(HTTPError) as ctx:
            person.request("GET", "/api/product/mine", cookie=False)
        self.assertEqual(ctx.exception.code, 401)

    def test_one_person_cannot_list_or_withdraw_anothers(self):
        alice, bob = Person(self.base), Person(self.base)
        alice.arrive(); bob.arrive()
        hers = alice.share(thought("Hers", ["x", "y", "z"]))
        self.assertEqual(bob.mine()["thoughts"], [])
        with self.assertRaises(HTTPError) as ctx:
            bob.request("POST", "/api/product/revoke", {"session_id": hers, "confirmed": True})
        self.assertEqual(ctx.exception.code, 403)
        self.assertEqual(alice.mine()["thoughts"][0]["state"], "discoverable")


class OnThePageTests(unittest.TestCase):
    """What the browser module and its stylesheet are allowed to do."""

    module = (UI_DIR / "shared_list.mjs").read_text(encoding="utf-8")
    stylesheet = (UI_DIR / "shared_list.css").read_text(encoding="utf-8")

    def test_the_list_reads_the_one_route_and_stops_through_the_real_one(self):
        self.assertIn('"/api/product/mine"', self.module)
        self.assertIn('"/api/product/revoke"', self.module)
        # A browser confirm() cannot say what will happen in the page's words.
        self.assertNotIn("confirm(", self.module)
        self.assertIn("Yes, stop", self.module)
        self.assertIn("Keep sharing", self.module)

    def test_no_identifier_can_reach_the_screen(self):
        # The one identifier the server sends is used once, to name the thought
        # to the server, and never put into text or an attribute.
        uses = [line for line in self.module.splitlines() if "session_id" in line]
        self.assertEqual(len(uses), 1, uses)
        self.assertIn("/api/product/revoke", uses[0])
        for forbidden in ("thought_id", "user_id", "innerHTML", "dataset.session", "toFixed("):
            self.assertNotIn(forbidden, self.module)

    def test_three_states_are_three_different_sentences(self):
        for word in ("Discoverable", "Private", "Withdrawn"):
            self.assertIn(word, self.module)
        self.assertIn("never made discoverable", self.module)       # private
        self.assertIn("not discoverable any more", self.module)     # withdrawn
        self.assertIn("can find it", self.module)                   # discoverable

    def test_styling_is_linked_tokens_only_and_works_in_both_schemes(self):
        # CSP default-src 'self': inline styles silently do nothing.
        self.assertNotIn("style=", self.module)
        self.assertNotIn(".style.", self.module)
        self.assertNotIn("<style", self.module)
        self.assertIsNone(re.search(r"#[0-9a-fA-F]{3,8}\b", self.stylesheet), "raw colour")
        self.assertNotIn("rgb(", self.stylesheet)
        self.assertNotIn("rgba(", self.stylesheet)
        tokens = set(re.findall(r"var\(--([a-z0-9-]+)\)", self.stylesheet))
        palette = (UI_DIR / "styles.css").read_text(encoding="utf-8")
        for token in tokens:
            self.assertIn(f"--{token}:", palette, f"--{token} is not a palette token")

    def test_served_and_wired_by_the_live_server(self):
        server, base, _ = _live_server()
        try:
            with urlopen(Request(base + "/"), timeout=10) as response:
                html = response.read().decode("utf-8")
            self.assertIn('href="/shared_list.css"', html)
            self.assertIn('src="/shared_list.mjs"', html)
            with urlopen(Request(base + "/shared_list.mjs"), timeout=10) as response:
                self.assertTrue(response.headers["Content-Type"].startswith("text/javascript"))
                self.assertIn("default-src 'self'", response.headers["Content-Security-Policy"])
            with urlopen(Request(base + "/shared_list.css"), timeout=10) as response:
                self.assertTrue(response.headers["Content-Type"].startswith("text/css"))
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()
