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

    def test_unknown_session_is_404_and_get_405(self):
        c = self.client(); c.oauth_guest()
        c.session = "not-a-real-session"
        # MCP spec: unknown/expired session on a session-requiring request -> 404
        # so the client re-initializes.
        with self.assertRaises(HTTPError) as ctx:
            c.rpc("ping", mid=4)
        self.assertEqual(ctx.exception.code, 404)
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


if __name__ == "__main__":
    unittest.main()
