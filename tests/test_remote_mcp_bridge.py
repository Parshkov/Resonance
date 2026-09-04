"""R17 remote MCP bridge: a real chat client (Streamable HTTP, bearer key) drives
the SAME live product as the browser — real content, two-step consent, discovery
between two different people, intro relay — without cookies or CSRF."""

from __future__ import annotations

import json
import threading
import unittest
from http.cookies import SimpleCookie
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from src.product.mcp_bridge import BRIDGE_CONTRACT, TOOLS, build_thought_dna
from src.product.server import build_runtime, serve
from src.graph.model import ThoughtGraph


def _post(url: str, body, headers=None):
    data = json.dumps(body).encode() if body is not None else b""
    req = Request(url, data=data, method="POST",
                  headers={"Content-Type": "application/json", **(headers or {})})
    with urlopen(req, timeout=15) as response:
        raw = response.read()
        return response.status, (json.loads(raw) if raw else None), dict(response.headers)


class Browser:
    """Minimal cookie+CSRF client standing in for the Collaboration panel."""

    def __init__(self, base: str):
        self.base = base
        self.cookie = None
        self.csrf = None

    def request(self, method: str, path: str, body=None):
        headers = {"Content-Type": "application/json", "Origin": self.base}
        if self.cookie:
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
                    self.cookie = f"resonance_token={morsel.value}"
            return response.status, json.loads(response.read().decode())

    def register(self, label: str):
        _, payload = self.request("POST", "/api/product/register", {"display_label": label})
        self.csrf = payload["csrf_token"]
        return payload

    def mcp_key(self):
        _, payload = self.request("POST", "/api/product/mcp_key", {})
        return payload


class Chat:
    """A chat client's MCP side: JSON-RPC over POST /mcp with a bearer key."""

    def __init__(self, base: str, key: str, *, in_path: bool = False):
        self.url = f"{base}/mcp/{key}" if in_path else f"{base}/mcp"
        self.headers = {} if in_path else {"Authorization": f"Bearer {key}"}
        self.counter = 0

    def rpc(self, method: str, params=None):
        self.counter += 1
        status, payload, _ = _post(self.url, {"jsonrpc": "2.0", "id": self.counter,
                                              "method": method, "params": params or {}},
                                   self.headers)
        assert status == 200, status
        return payload

    def call(self, name: str, arguments=None):
        payload = self.rpc("tools/call", {"name": name, "arguments": arguments or {}})
        assert "result" in payload, payload
        result = payload["result"]
        return result["isError"], result["structuredContent"]


THOUGHT_A = {
    "topic": "retry storms after a partial outage",
    "domain": "distributed-systems",
    "nodes": [
        {"id": "n0", "label": "partial upstream outage", "role": "problem"},
        {"id": "n1", "label": "synchronized client retries", "role": "mechanism"},
        {"id": "n2", "label": "request amplification", "role": "state"},
        {"id": "n3", "label": "cascading saturation", "role": "outcome"},
        {"id": "n4", "label": "fixed retry budget", "role": "constraint"},
        {"id": "n5", "label": "jittered exponential backoff", "role": "method"},
    ],
    "relations": [
        {"source": "n0", "target": "n1", "type": "causes"},
        {"source": "n1", "target": "n2", "type": "causes"},
        {"source": "n2", "target": "n3", "type": "causes"},
        {"source": "n4", "target": "n1", "type": "constrains"},
        {"source": "n5", "target": "n3", "type": "prevents"},
    ],
}

THOUGHT_B = {
    "topic": "panic buying after a supply rumour",
    "domain": "retail-logistics",
    "nodes": [
        {"label": "supply shortage rumour", "role": "problem"},
        {"label": "synchronized bulk purchases", "role": "mechanism"},
        {"label": "demand amplification", "role": "state"},
        {"label": "empty shelves", "role": "outcome"},
        {"label": "per-customer purchase cap", "role": "constraint"},
        {"label": "staggered restocking", "role": "method"},
    ],
    "relations": [
        {"source": "supply shortage rumour", "target": "synchronized bulk purchases", "type": "causes"},
        {"source": "synchronized bulk purchases", "target": "demand amplification", "type": "causes"},
        {"source": "demand amplification", "target": "empty shelves", "type": "causes"},
        {"source": "per-customer purchase cap", "target": "synchronized bulk purchases", "type": "constrains"},
        {"source": "staggered restocking", "target": "empty shelves", "type": "prevents"},
    ],
}


class BuildThoughtDnaTests(unittest.TestCase):
    def test_builds_canonical_manual_thought_dna_that_validates(self):
        dna = build_thought_dna(THOUGHT_B, human_id="person-x")
        graph = ThoughtGraph.from_dict(dna)  # validates the accepted schema
        self.assertEqual(len(graph.nodes), 6)
        self.assertEqual(len(graph.relations), 5)
        self.assertEqual(dna["provenance"], {"kind": "manual", "extractor": None, "human_id": "person-x"})
        self.assertEqual(dna["source"]["text"], "")  # conversation text never stored
        # label-addressed relations were resolved to node ids
        self.assertTrue(all(r["source"].startswith("n") for r in dna["relations"]))

    def test_rejects_unknown_vocabulary_with_precise_message(self):
        bad = {"nodes": [{"label": "a", "role": "vibe"}, {"label": "b", "role": "state"}],
               "relations": []}
        with self.assertRaises(Exception) as ctx:
            build_thought_dna(bad, human_id="p")
        self.assertIn("role must be one of", str(ctx.exception))

    def test_tool_table_is_well_formed(self):
        names = [t["name"] for t in TOOLS]
        self.assertEqual(len(names), len(set(names)))
        for tool in TOOLS:
            self.assertEqual(tool["inputSchema"]["type"], "object")
            self.assertIn("readOnlyHint", tool["annotations"])


class RemoteMCPHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pending = build_runtime(":memory:", allowed_origins=frozenset({"pending"}))
        server = serve("127.0.0.1", 0, runtime=pending)
        host, port = server.server_address[:2]
        cls.base = f"http://{host}:{port}"
        runtime = build_runtime(":memory:", allowed_origins=frozenset({cls.base}))
        server.RequestHandlerClass.runtime = runtime
        cls.server = server
        cls.thread = threading.Thread(target=server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)

    def test_unauthenticated_and_bad_key_are_401_get_is_405(self):
        with self.assertRaises(HTTPError) as ctx:
            _post(self.base + "/mcp", {"jsonrpc": "2.0", "id": 1, "method": "ping"})
        self.assertEqual(ctx.exception.code, 401)
        self.assertIn("Bearer", ctx.exception.headers.get("WWW-Authenticate", ""))
        with self.assertRaises(HTTPError) as ctx:
            _post(self.base + "/mcp", {"jsonrpc": "2.0", "id": 1, "method": "ping"},
                  {"Authorization": "Bearer not-a-key"})
        self.assertEqual(ctx.exception.code, 401)
        with self.assertRaises(HTTPError) as ctx:
            urlopen(Request(self.base + "/mcp"), timeout=10)
        self.assertEqual(ctx.exception.code, 405)

    def test_mcp_key_requires_cookie_and_csrf(self):
        with self.assertRaises(HTTPError) as ctx:
            _post(self.base + "/api/product/mcp_key", {})
        self.assertEqual(ctx.exception.code, 401)
        browser = Browser(self.base)
        browser.register("Nika")
        browser.csrf = "wrong"
        with self.assertRaises(HTTPError) as ctx:
            browser.request("POST", "/api/product/mcp_key", {})
        self.assertEqual(ctx.exception.code, 403)

    def test_two_people_two_chats_real_content_discover_and_intro(self):
        # Two different people, each with their own browser account and their
        # own chat client holding a key minted in the Collaboration panel.
        alice_browser, bob_browser = Browser(self.base), Browser(self.base)
        alice_browser.register("Alice")
        bob_browser.register("Bob")
        alice_key = alice_browser.mcp_key()
        bob_key = bob_browser.mcp_key()
        self.assertTrue(alice_key["endpoint"].endswith("/mcp"))
        self.assertTrue(alice_key["endpoint_with_key"].endswith("/mcp/" + alice_key["mcp_key"]))
        alice = Chat(self.base, alice_key["mcp_key"])
        bob = Chat(self.base, bob_key["mcp_key"], in_path=True)  # URL-only client

        # MCP handshake
        init = alice.rpc("initialize", {"protocolVersion": "2025-06-18",
                                        "capabilities": {}, "clientInfo": {"name": "t", "version": "0"}})
        self.assertEqual(init["result"]["protocolVersion"], "2025-06-18")
        self.assertIn("tools", init["result"]["capabilities"])
        status, body, _ = _post(alice.url, {"jsonrpc": "2.0", "method": "notifications/initialized"},
                                alice.headers)
        self.assertEqual((status, body), (202, None))
        tools = alice.rpc("tools/list")["result"]["tools"]
        self.assertEqual({t["name"] for t in tools}, {t["name"] for t in TOOLS})

        # The key maps to the same account the browser sees.
        err, who = alice.call("resonance_whoami")
        self.assertFalse(err)
        self.assertEqual(who["display_label"], "Alice")
        self.assertEqual(who["actor_type"], "agent")
        self.assertEqual(who["shared_thoughts"], [])

        # Discovery before sharing is a clear, actionable tool error, not a crash.
        err, payload = alice.call("resonance_discover")
        self.assertTrue(err)
        self.assertEqual(payload["error"], "share_required")

        # Step 1: prepare real content -> preview + token, nothing discoverable.
        err, prep_a = alice.call("resonance_prepare_thought", {"thought": THOUGHT_A})
        self.assertFalse(err, prep_a)
        self.assertFalse(prep_a["discoverable"])
        self.assertTrue(prep_a["requires_explicit_confirmation"])
        self.assertEqual(prep_a["source_retention"], "not_retained")
        self.assertIn("thought_dna", prep_a["will_become_discoverable"])
        # Sharing without confirm is refused.
        err, refused = alice.call("resonance_share_thought", {
            "draft_id": prep_a["draft_id"], "confirmation_token": prep_a["confirmation_token"],
            "confirm": False, "request_id": "a-share-0"})
        self.assertTrue(err)
        self.assertEqual(refused["error"], "confirmation_required")
        # Step 2: explicit approval.
        err, shared_a = alice.call("resonance_share_thought", {
            "draft_id": prep_a["draft_id"], "confirmation_token": prep_a["confirmation_token"],
            "confirm": True, "request_id": "a-share-1"})
        self.assertFalse(err, shared_a)
        self.assertTrue(shared_a["discoverable"])
        session_a = shared_a["session_id"]

        # Bob shares a structurally analogous thought from a different domain
        # through the URL-only transport.
        err, prep_b = bob.call("resonance_prepare_thought", {"thought": THOUGHT_B})
        self.assertFalse(err, prep_b)
        err, shared_b = bob.call("resonance_share_thought", {
            "draft_id": prep_b["draft_id"], "confirmation_token": prep_b["confirmation_token"],
            "confirm": True, "request_id": "b-share-1"})
        self.assertFalse(err, shared_b)
        session_b = shared_b["session_id"]

        # The browser sees the chat's writes (same account, same record).
        _, sessions = alice_browser.request("GET", "/api/product/sessions")
        self.assertEqual([s["session_id"] for s in sessions["sessions"]
                          if s["share_state"] == "discoverable"], [session_a])

        # Real discovery: Alice finds Bob's analogous structure.
        err, disc = alice.call("resonance_discover", {"k": 15})
        self.assertFalse(err, disc)
        self.assertEqual(disc["contract_version"], BRIDGE_CONTRACT)
        self.assertEqual(disc["query_session_id"], session_a)
        found = [m for m in disc["matches_in_backend_order"] if m["session_id"] == session_b]
        self.assertEqual(len(found), 1, disc["matches_in_backend_order"][:3])
        # Analogical, cross-domain, all five relations preserved; the counterpart
        # is addressed by session and display label only (no user id, no contact).
        self.assertEqual(found[0]["mode_classification"], "analogical")
        self.assertEqual(found[0]["evidence"]["preserved_relation_count"], 5)
        self.assertNotIn("user_id", json.dumps(found[0]))
        self.assertNotIn(bob_key["user_id"], json.dumps(disc))
        err, evidence = alice.call("resonance_explain_match",
                                   {"result_id": disc["result_id"], "session_id": session_b})
        self.assertFalse(err, evidence)

        # Consent-gated intro from Alice's chat, accepted from Bob's chat,
        # then a relayed message both can read.
        err, intro = alice.call("resonance_request_intro", {
            "from_session_id": session_a, "target_session_id": session_b,
            "message": "Your retry-storm structure mirrors my panic-buying model; compare notes?",
            "confirm": True, "request_id": "a-intro-1"})
        self.assertFalse(err, intro)
        err, bob_inbox = bob.call("resonance_list_intros")
        self.assertFalse(err)
        incoming = [r for r in bob_inbox["incoming"] if r["state"] == "requested"]
        self.assertEqual(len(incoming), 1)
        err, accepted = bob.call("resonance_respond_intro", {
            "intro_id": incoming[0]["intro_id"], "accept": True,
            "confirm": True, "request_id": "b-resp-1"})
        self.assertFalse(err, accepted)
        err, alice_list = alice.call("resonance_list_intros")
        accepted_rows = [r for r in alice_list["outgoing"] if r["state"] == "accepted"]
        self.assertEqual(len(accepted_rows), 1)
        channel_id = accepted_rows[0]["channel_id"]
        err, sent = alice.call("resonance_send_message", {
            "channel_id": channel_id, "body": "hello from Alice's chat",
            "confirm": True, "request_id": "a-msg-1"})
        self.assertFalse(err, sent)
        err, thread = bob.call("resonance_read_messages", {"channel_id": channel_id})
        self.assertFalse(err, thread)
        self.assertEqual([m["body"] for m in thread["messages"]], ["hello from Alice's chat"])

        # Stop sharing from the chat; the browser and discovery agree.
        err, revoked = alice.call("resonance_stop_sharing", {"session_id": session_a, "confirm": True})
        self.assertFalse(err, revoked)
        err, who = alice.call("resonance_whoami")
        self.assertEqual(who["shared_thoughts"], [])

    def test_raw_text_fallback_and_unknown_tool(self):
        browser = Browser(self.base)
        browser.register("Cleo")
        chat = Chat(self.base, browser.mcp_key()["mcp_key"])
        err, prep = chat.call("resonance_prepare_thought", {
            "context": "Slow code review causes merge queue pile-up, which leads to release delays. "
                       "A review SLA prevents the pile-up."})
        self.assertFalse(err, prep)
        self.assertEqual(prep["input_kind"], "raw_text_fallback")
        bad = chat.rpc("tools/call", {"name": "resonance_nope", "arguments": {}})
        self.assertEqual(bad["error"]["code"], -32602)
        unknown = chat.rpc("frobnicate")
        self.assertEqual(unknown["error"]["code"], -32601)


if __name__ == "__main__":
    unittest.main()
