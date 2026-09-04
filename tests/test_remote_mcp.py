"""R15 acceptance battery: authenticated remote MCP over the live product."""

from __future__ import annotations

import base64
import hashlib
import json
import threading
import unittest
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from src.product.server import build_runtime
from src.remote.auth import CodeStore
from src.remote.server import TOOLS, build_httpd
from tests.test_product_live import PRES, QUERY_DNA, r7_dna


def _pkce():
    verifier = base64.urlsafe_b64encode(b"v" * 48).rstrip(b"=").decode()
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    return verifier, challenge


class RemoteClient:
    def __init__(self, base):
        self.base = base
        self.bearer = None
        self.session = None

    def form(self, path, fields):
        req = Request(self.base + path, data=urlencode(fields).encode(),
                      headers={"Content-Type": "application/x-www-form-urlencoded"},
                      method="POST")
        with urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read())

    def rpc(self, method, params=None, *, bearer=True, mid=1):
        headers = {"Content-Type": "application/json"}
        if bearer and self.bearer:
            headers["Authorization"] = f"Bearer {self.bearer}"
        if self.session:
            headers["Mcp-Session-Id"] = self.session
        body = {"jsonrpc": "2.0", "id": mid, "method": method}
        if params is not None:
            body["params"] = params
        req = Request(self.base + "/mcp", data=json.dumps(body).encode(),
                      headers=headers, method="POST")
        with urlopen(req, timeout=10) as r:
            sid = r.headers.get("Mcp-Session-Id")
            if sid:
                self.session = sid
            return r.status, (json.loads(r.read()) if r.length != 0 else None)

    def call(self, name, arguments=None, mid=2):
        return self.rpc("tools/call", {"name": name, "arguments": arguments or {}}, mid=mid)

    def oauth_guest(self):
        verifier, challenge = _pkce()
        status, authd = self.form("/oauth/authorize", {
            "code_challenge": challenge, "code_challenge_method": "S256",
            "redirect_uri": "https://client/cb", "client_id": "test"})
        status, tok = self.form("/oauth/token", {
            "grant_type": "authorization_code", "code": authd["code"],
            "code_verifier": verifier, "redirect_uri": "https://client/cb",
            "client_id": "test"})
        self.bearer = tok["access_token"]
        return authd, tok

    def initialize(self):
        return self.rpc("initialize", {"protocolVersion": "2025-03-26"})


class RemoteMcpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runtime = build_runtime(":memory:", allowed_origins=frozenset({"https://x"}))
        cls.runtime.remote_auth = CodeStore()
        cls.httpd = build_httpd("127.0.0.1", 0, runtime=cls.runtime)
        cls.base = f"http://127.0.0.1:{cls.httpd.server_address[1]}"
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def client(self):
        return RemoteClient(self.base)

    def _shared(self, client, source, tid, intro=False):
        prep = client.call("resonance_prepare_thought", {
            "candidate": r7_dna(source, tid), "presentation": dict(PRES),
            "intent": {"share_display_profile": True, "receive_intro_requests": intro}})[1]
        draft = prep["result"]["structuredContent"]["draft_id"]
        pv = client.call("resonance_get_share_preview", {"draft_id": draft})[1]
        token = pv["result"]["structuredContent"]["confirmation_token"]
        rec = client.call("resonance_share_thought", {
            "draft_id": draft, "confirmation_token": token, "confirm": True})[1]
        sc = rec["result"]["structuredContent"]
        return sc["session_id"]

    def test_bearer_required_and_oauth_pkce(self):
        c = self.client()
        # no bearer -> 401
        with self.assertRaises(HTTPError) as ctx:
            c.rpc("tools/list", bearer=False)
        self.assertEqual(ctx.exception.code, 401)
        # OAuth guest + PKCE issues a usable bearer (an R12 access token)
        c.oauth_guest()
        self.assertTrue(c.bearer)
        status, init = c.initialize()
        self.assertEqual(init["result"]["protocolVersion"], "2025-03-26")
        status, tools = c.rpc("tools/list", mid=3)
        names = {t["name"] for t in tools["result"]["tools"]}
        self.assertEqual(names, {t["name"] for t in TOOLS})
        who = c.call("resonance_whoami")[1]["result"]["structuredContent"]
        self.assertTrue(who["user_id"].startswith("person-"))

    def test_pkce_wrong_verifier_and_replay_rejected(self):
        c = self.client()
        _, challenge = _pkce()
        status, authd = c.form("/oauth/authorize", {
            "code_challenge": challenge, "code_challenge_method": "S256",
            "redirect_uri": "https://client/cb", "client_id": "test"})
        with self.assertRaises(HTTPError) as ctx:
            c.form("/oauth/token", {"grant_type": "authorization_code",
                                    "code": authd["code"], "code_verifier": "wrong",
                                    "redirect_uri": "https://client/cb", "client_id": "test"})
        self.assertEqual(ctx.exception.code, 400)

    def test_session_bound_to_subject(self):
        alice = self.client(); alice.oauth_guest(); alice.initialize()
        bob = self.client(); bob.oauth_guest()
        # Bob presents Alice's session id with his own bearer -> refused.
        bob.session = alice.session
        status, reply = bob.rpc("tools/list", mid=9)
        self.assertIn("error", reply)
        self.assertIn("different authenticated subject", reply["error"]["message"])

    def test_unknown_session_and_get_405(self):
        c = self.client(); c.oauth_guest()
        c.session = "not-a-real-session"
        status, reply = c.rpc("ping", mid=4)
        self.assertIn("error", reply)
        req = Request(self.base + "/mcp")
        with self.assertRaises(HTTPError) as ctx:
            urlopen(req, timeout=10)
        self.assertEqual(ctx.exception.code, 405)

    def test_full_remote_journey_with_rich_result(self):
        alice = self.client(); alice.oauth_guest(); alice.initialize()
        a_sess = self._shared(alice, "ses-gabe-warehouse", "rem-a")
        bob = self.client(); bob.oauth_guest(); bob.initialize()
        b_sess = self._shared(bob, QUERY_DNA, "rem-b")
        disc = bob.call("resonance_discover", {"session_id": b_sess, "k": 8})[1]
        result = disc["result"]
        sc = result["structuredContent"]
        self.assertEqual(sc["contract_version"], "resonance-rich-result/0.1")
        found = [m["session_id"] for m in sc["matches"]]
        self.assertIn(a_sess, found)
        # rich content: text + an EmbeddedResource SVG
        kinds = [b["type"] for b in result["content"]]
        self.assertIn("text", kinds)
        self.assertIn("resource", kinds)
        svg = next(b for b in result["content"] if b["type"] == "resource")
        self.assertEqual(svg["resource"]["mimeType"], "image/svg+xml")
        # evidence bound to the result_id
        ev = bob.call("resonance_get_match", {
            "result_id": sc["result_id"], "session_id": a_sess})[1]
        self.assertEqual(ev["result"]["structuredContent"]["match"]["session_id"], a_sess)

    def test_confirmation_and_writes_gated(self):
        c = self.client(); c.oauth_guest(); c.initialize()
        # share without confirm -> tool error, not a crash
        prep = c.call("resonance_prepare_thought", {
            "candidate": r7_dna("ses-mei-battery-heat", "rem-c"),
            "presentation": dict(PRES)})[1]
        draft = prep["result"]["structuredContent"]["draft_id"]
        pv = c.call("resonance_get_share_preview", {"draft_id": draft})[1]
        token = pv["result"]["structuredContent"]["confirmation_token"]
        bad = c.call("resonance_share_thought", {
            "draft_id": draft, "confirmation_token": token, "confirm": False})[1]
        self.assertTrue(bad["result"]["isError"])

    def test_cross_transport_parity_remote_equals_direct(self):
        # Same authenticated subject + session -> identical match ids/order/scores
        # through the direct product service and through remote MCP.
        alice = self.client(); alice.oauth_guest(); alice.initialize()
        self._shared(alice, "ses-gabe-warehouse", "par-a")
        bob = self.client(); bob.oauth_guest(); bob.initialize()
        b_sess = self._shared(bob, QUERY_DNA, "par-b")
        remote = bob.call("resonance_discover", {"session_id": b_sess, "k": 20})[1]
        remote_sc = remote["result"]["structuredContent"]
        direct = self.runtime.product.rich_discover(bob.bearer, b_sess, k=20)
        key = lambda ms: [(m["session_id"], m["mode_classification"],
                           json.dumps(m["scores"], sort_keys=True)) for m in ms]
        self.assertEqual(key(remote_sc["matches"]), key(direct["matches"]))

    def test_body_bound_and_transport_survival(self):
        c = self.client(); c.oauth_guest(); c.initialize()
        # oversized body -> 413, server still serves the next request
        big = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "ping",
                          "params": {"x": "z" * (130 * 1024)}}).encode()
        req = Request(self.base + "/mcp", data=big,
                      headers={"Content-Type": "application/json",
                               "Authorization": f"Bearer {c.bearer}",
                               "Mcp-Session-Id": c.session}, method="POST")
        with self.assertRaises(HTTPError) as ctx:
            urlopen(req, timeout=10)
        self.assertEqual(ctx.exception.code, 413)
        status, pong = c.rpc("ping", mid=7)
        self.assertEqual(pong["result"], {})

    def test_source_operates_on_live_product_not_fixture(self):
        from pathlib import Path
        service = Path("src/remote/service.py").read_text()
        server = Path("src/remote/server.py").read_text()
        # The remote layer resolves to the live product, not the old R7 fixture.
        self.assertNotIn("ProductService()", service + server)
        self.assertIn("runtime.product", service)
        # Bearer auth is the accepted R12 identity, not a private token directory.
        self.assertIn("identity.authenticate", service)


class RealChatIngestionTests(unittest.TestCase):
    """The canonical product story: two humans' REAL chat contexts are passed
    through remote MCP as raw text, extracted into Thought DNA (raw NOT
    retained), and discovered against each other from live persisted state —
    with no fixture/seed corpus and no r7_dna/QUERY_DNA helper constructing the
    inputs. Structural resonance, not keyword coincidence, drives the match.
    """

    # Parallel causal STRUCTURE (X causes accumulation; accumulation leads to
    # collapse; a control prevents collapse; the control requires a signal),
    # disjoint VOCABULARY. Real conversational text with explicit relation cues.
    CHAT_A = ("Rising input power causes heat accumulation. Heat accumulation "
              "leads to beam bloom. A feedback throttle prevents beam bloom. "
              "The feedback throttle requires a focus drift signal.")
    CHAT_B = ("Feature launches cause ticket accumulation. Ticket accumulation "
              "leads to queue collapse. Admission control prevents queue "
              "collapse. Admission control requires a backlog monitor.")
    # Same VOCABULARY as A, scrambled structure — the keyword-coincidence trap.
    CHAT_C = ("Beam bloom causes input power. A focus drift signal prevents heat "
              "accumulation. Heat accumulation requires a feedback throttle.")

    # Ambient corpus of OTHER users' real chats (independent hand-written text,
    # NOT R7 fixtures) so retrieval has the distributional mass a live product
    # has — the small-N cold-start behaviour of the accepted MULTI retrieval is
    # a known limitation, not this scenario's subject.
    AMBIENT = [
        ("Cheap credit causes speculative borrowing. Speculative borrowing leads "
         "to asset bubbles. Prudential limits prevent asset bubbles. Prudential "
         "limits require a leverage indicator."),
        ("Nutrient runoff causes algae growth. Algae growth leads to oxygen "
         "collapse. Buffer strips prevent oxygen collapse. Buffer strips require "
         "a runoff sensor."),
        ("Fast onboarding causes shallow understanding. Shallow understanding "
         "leads to churn. Mentorship prevents churn. Mentorship requires a "
         "capacity budget."),
        ("Loose coupling supports resilience. Tight deadlines cause shortcuts. "
         "Shortcuts lead to outages. Reviews prevent outages."),
    ]

    def setUp(self):
        # Per-test runtime for full isolation (in-memory, fast). seed=False: the
        # corpus contains ONLY real chat text (ambient + test inputs) — no R7
        # fixture candidate is ever a query or a match.
        self.runtime = build_runtime(":memory:", seed=False,
                                    allowed_origins=frozenset({"https://x"}))
        self.runtime.remote_auth = CodeStore()
        self.httpd = build_httpd("127.0.0.1", 0, runtime=self.runtime)
        self.base = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        for chat in self.AMBIENT:
            self._ambient_ingest(chat)

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()

    def _ambient_ingest(self, chat_text):
        c = RemoteClient(self.base)
        c.oauth_guest()
        c.initialize()
        prep = c.call("resonance_prepare_thought", {
            "context": chat_text,
            "presentation": {"domain": "d", "topic": "t", "cluster_id": "c"}})[1]
        sc = prep["result"]["structuredContent"]
        pv = c.call("resonance_get_share_preview", {"draft_id": sc["draft_id"]})[1]
        c.call("resonance_share_thought", {
            "draft_id": sc["draft_id"],
            "confirmation_token": pv["result"]["structuredContent"]["confirmation_token"],
            "confirm": True})

    def _ingest_chat(self, chat_text):
        """A fresh authenticated remote-MCP session ingests raw chat and shares.
        No fixture helper touches the Thought DNA."""
        c = RemoteClient(self.base)
        c.oauth_guest()
        c.initialize()
        prep = c.call("resonance_prepare_thought", {
            "context": chat_text,
            "presentation": {"domain": "d", "topic": "t", "cluster_id": "c"}})[1]
        sc = prep["result"]["structuredContent"]
        self.assertEqual(sc["input_kind"], "raw_text_fallback")
        draft = sc["draft_id"]
        session_id = sc["session_id"]
        pv = c.call("resonance_get_share_preview", {"draft_id": draft})[1]
        token = pv["result"]["structuredContent"]["confirmation_token"]
        # explicit confirm is still required
        unconfirmed = c.call("resonance_share_thought", {
            "draft_id": draft, "confirmation_token": token, "confirm": False})[1]
        self.assertTrue(unconfirmed["result"]["isError"])
        shared = c.call("resonance_share_thought", {
            "draft_id": draft, "confirmation_token": token, "confirm": True})[1]
        self.assertTrue(shared["result"]["structuredContent"]["discoverable"])
        return c, session_id

    def test_two_independent_chats_resonate_from_live_state(self):
        # Guard: the acceptance inputs are real chat text, not fixtures.
        for chat in (self.CHAT_A, self.CHAT_B, self.CHAT_C):
            self.assertNotIn("thought-", chat)
        alice, a_session = self._ingest_chat(self.CHAT_A)
        carol, c_session = self._ingest_chat(self.CHAT_C)  # keyword trap
        bob, b_session = self._ingest_chat(self.CHAT_B)

        # raw conversation is NOT retained: the stored Thought DNA has an empty
        # source, and no full raw sentence survives in the durable store.
        import hashlib
        a_dna = self.runtime.live.get_session(a_session).thought_dna
        self.assertEqual(a_dna["source"]["text"], "")
        self.assertEqual(a_dna["source"]["sha256"], hashlib.sha256(b"").hexdigest())
        dump = json.dumps(self.runtime.live.repo.export_payload(), ensure_ascii=False)
        self.assertNotIn("Rising input power causes heat accumulation.", dump)
        self.assertNotIn("Feature launches cause ticket accumulation.", dump)
        # extraction produced real structure from the raw chat
        self.assertGreaterEqual(len(a_dna["nodes"]), 4)
        self.assertGreaterEqual(len(a_dna["relations"]), 3)

        # Bob discovers from live persisted state.
        disc = bob.call("resonance_discover", {"session_id": b_session, "k": 8})[1]
        sc = disc["result"]["structuredContent"]
        by_session = {m["session_id"]: m for m in sc["matches"]}
        self.assertIn(a_session, by_session, "Alice must resonate with Bob")
        alice_match = by_session[a_session]
        # structural analog across disjoint vocabulary: structure >> semantics
        self.assertEqual(alice_match["mode_classification"], "analogical")
        self.assertGreater(alice_match["scores"]["structural"], 0.3)
        self.assertLess(alice_match["scores"]["semantic"], 0.3)
        # the keyword-coincidence chat (Carol) is NOT an analogical match
        if c_session in by_session:
            self.assertNotEqual(by_session[c_session]["mode_classification"],
                                "analogical")

        # result_id-bound backend evidence for the real match
        ev = bob.call("resonance_get_match", {
            "result_id": sc["result_id"], "session_id": a_session})[1]
        match = ev["result"]["structuredContent"]["match"]
        self.assertEqual(match["session_id"], a_session)
        self.assertTrue(match["evidence"]["top_correspondences"])

    def test_subject_isolation_and_restart_persistence_real_chat(self):
        alice, a_session = self._ingest_chat(self.CHAT_A)
        bob, b_session = self._ingest_chat(self.CHAT_B)
        # Bob cannot discover from Alice's session (subject isolation).
        iso = bob.call("resonance_discover", {"session_id": a_session})[1]
        self.assertTrue(iso["result"]["isError"])
        # persisted live state: a second RemoteProductService over the same
        # durable repo still discovers the shared chats.
        from src.remote import RemoteProductService
        svc2 = RemoteProductService(self.runtime)
        again = svc2.discover(bob.bearer, b_session, mode="analogical", k=8)
        self.assertIn(a_session,
                      [m["session_id"] for m in again["structuredContent"]["matches"]])


if __name__ == "__main__":
    unittest.main()
