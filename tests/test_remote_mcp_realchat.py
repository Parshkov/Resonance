"""R15 real-chat acceptance (maintainer delta on #87, 2026-09-04 04:25 UTC):
two people ingest independently written raw conversation context through two
separate authenticated remote MCP sessions; discovery from persisted live state
returns the other person on structure, not vocabulary. No fixture helper
(`r7_dna`, `QUERY_DNA`, replay/seed query) builds A or B."""

from __future__ import annotations

import base64
import hashlib
import inspect
import json
import threading
import unittest
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from src.product.server import build_runtime
from src.remote.auth import CodeStore
from src.remote.server import build_httpd

# Written by hand for this test: three "conversations" a person might have
# with their assistant. A and B share causal SHAPE across unrelated domains;
# C reuses A's vocabulary with the causal arrows scrambled.
CHAT_A = (
    "A partial upstream outage causes synchronized client retries. "
    "Synchronized client retries cause request amplification. "
    "Request amplification leads to cascading saturation. "
    "A fixed retry budget constrains synchronized client retries. "
    "Jittered exponential backoff prevents cascading saturation."
)
CHAT_B = (
    "A supply shortage rumour causes synchronized bulk purchases. "
    "Synchronized bulk purchases cause demand amplification. "
    "Demand amplification leads to empty shelves. "
    "A per-customer purchase cap constrains synchronized bulk purchases. "
    "Staggered restocking prevents empty shelves."
)
CHAT_C_WRONG_STRUCTURE = (
    "Cascading saturation causes a partial upstream outage. "
    "Request amplification prevents synchronized client retries. "
    "Jittered exponential backoff causes request amplification. "
    "A fixed retry budget leads to cascading saturation."
)


class Chat:
    """One person's assistant: its own OAuth/PKCE bearer and MCP session."""

    def __init__(self, base: str):
        self.base = base
        verifier = base64.urlsafe_b64encode(b"v" * 48).rstrip(b"=").decode()
        challenge = base64.urlsafe_b64encode(
            hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
        authd = self.form("/oauth/authorize", {
            "code_challenge": challenge, "code_challenge_method": "S256",
            "redirect_uri": "https://client/cb", "client_id": "realchat"})
        tok = self.form("/oauth/token", {
            "grant_type": "authorization_code", "code": authd["code"],
            "code_verifier": verifier, "redirect_uri": "https://client/cb",
            "client_id": "realchat"})
        self.bearer = tok["access_token"]
        self.session = None
        self.rpc("initialize", {"protocolVersion": "2025-03-26"})

    def form(self, path, fields):
        req = Request(self.base + path, data=urlencode(fields).encode(),
                      headers={"Content-Type": "application/x-www-form-urlencoded"},
                      method="POST")
        with urlopen(req, timeout=10) as r:
            return json.loads(r.read())

    def rpc(self, method, params=None, mid=1):
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {self.bearer}"}
        if self.session:
            headers["Mcp-Session-Id"] = self.session
        req = Request(self.base + "/mcp", method="POST", headers=headers,
                      data=json.dumps({"jsonrpc": "2.0", "id": mid, "method": method,
                                       "params": params or {}}).encode())
        with urlopen(req, timeout=10) as r:
            sid = r.headers.get("Mcp-Session-Id")
            if sid:
                self.session = sid
            return json.loads(r.read())

    def call(self, name, arguments):
        return self.rpc("tools/call", {"name": name, "arguments": arguments}, mid=2)["result"]

    def share_context(self, context: str):
        prepared = self.call("resonance_prepare_thought", {"context": context})
        assert not prepared["isError"], prepared
        sc = prepared["structuredContent"]
        preview = self.call("resonance_get_share_preview", {"draft_id": sc["draft_id"]})["structuredContent"]
        shared = self.call("resonance_share_thought", {
            "draft_id": sc["draft_id"], "confirmation_token": preview["confirmation_token"],
            "confirm": True})
        assert not shared["isError"], shared
        return sc, preview, shared["structuredContent"]


class RealChatRemoteMcpTests(unittest.TestCase):
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

    def test_no_fixture_helper_builds_the_chats(self):
        # The chats are literal strings in this module; no fixture import or
        # helper call constructs them.
        source = inspect.getsource(inspect.getmodule(self))
        self.assertNotIn("from tests.test_product_live", source)
        self.assertNotIn("from src.product.competition_server", source)
        for call in ("r7_dna(", "QUERY_DNA[", "_flagship_session(", "seed_r7("):
            self.assertNotIn(call, source)

    def test_two_independent_chats_discover_each_other_on_structure(self):
        alice, bob, carol = Chat(self.base), Chat(self.base), Chat(self.base)

        prepared_a, preview_a, shared_a = alice.share_context(CHAT_A)
        # Raw context is extracted, grounded and NOT retained.
        self.assertEqual(prepared_a["input_kind"], "raw_text_fallback")
        self.assertEqual(prepared_a["source_retention"], "not_retained")
        self.assertGreaterEqual(len(preview_a["thought_dna"]["relations"]), 4)
        self.assertNotIn("partial upstream outage causes", json.dumps(preview_a))
        # Without a caller presentation the share still lands (review delta).
        self.assertTrue(shared_a["discoverable"])
        session_a = shared_a["session_id"]

        _, _, shared_b = bob.share_context(CHAT_B)
        _, _, shared_c = carol.share_context(CHAT_C_WRONG_STRUCTURE)
        session_b, session_c = shared_b["session_id"], shared_c["session_id"]

        # Persisted live state, not the per-request memory: a fresh Chat for Bob
        # (new bearer, new MCP session) still sees his shared thought.
        bob_again = Chat(self.base)
        bob_again.bearer = bob.bearer
        bob_again.session = None
        bob_again.rpc("initialize", {"protocolVersion": "2025-03-26"})
        who = bob_again.call("resonance_whoami", {})["structuredContent"]
        self.assertIn(session_b, [s["session_id"] for s in who["owned_sessions"]])

        disc = bob_again.call("resonance_discover", {"session_id": session_b, "k": 15})
        self.assertFalse(disc["isError"], disc)
        sc = disc["structuredContent"]
        self.assertRegex(sc["result_id"], r"^result-[0-9a-f]{24}$")
        order = [m["session_id"] for m in sc["matches"]]
        self.assertIn(session_a, order)
        self.assertNotIn(session_b, order)  # never your own thought
        by_id = {m["session_id"]: m for m in sc["matches"]}
        a_row = by_id[session_a]
        # Structure, not keywords: Alice (different words, same shape) ranks
        # above Carol (same words, scrambled arrows) on the backend's own order
        # and evidence.
        self.assertEqual(order[0], session_a)
        self.assertEqual(a_row["evidence"]["preserved_relation_count"], 5)
        if session_c in by_id:
            c_row = by_id[session_c]
            self.assertLess(order.index(session_a), order.index(session_c))
            self.assertGreater(a_row["scores"]["structural"], c_row["scores"]["structural"])
            self.assertGreater(a_row["evidence"]["preserved_relation_count"],
                               c_row["evidence"]["preserved_relation_count"])
        # Evidence is bound to this result and readable by the discovering subject.
        ev = bob_again.call("resonance_get_match", {"result_id": sc["result_id"],
                                                   "session_id": session_a})
        self.assertFalse(ev["isError"], ev)
        # Alice's chat cannot read Bob's result (subject isolation).
        stolen = alice.call("resonance_get_match", {"result_id": sc["result_id"],
                                                   "session_id": session_a})
        self.assertTrue(stolen["isError"])


if __name__ == "__main__":
    unittest.main()
