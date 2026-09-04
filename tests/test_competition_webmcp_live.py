"""Competition browser bridge: real R13/R14 product state behind R10 WebMCP UX."""

from __future__ import annotations

import json
import threading
import unittest
from http.cookies import SimpleCookie
from urllib.request import Request, urlopen

from src.product.competition_server import serve
from src.product.server import build_runtime


class Client:
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
            return response.status, json.loads(response.read().decode()), dict(response.headers)

    def guest(self):
        _, payload, _ = self.request("POST", "/api/product/guest", {})
        self.csrf = payload["csrf_token"]
        return payload


class CompetitionWebMCPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pending = build_runtime(":memory:", allowed_origins=frozenset({"pending"}))
        server = serve("127.0.0.1", 0, runtime=pending)
        host, port = server.server_address[:2]
        cls.base = f"http://{host}:{port}"
        runtime = build_runtime(":memory:", allowed_origins=frozenset({cls.base}))
        server.RequestHandlerClass.runtime = runtime
        cls.runtime = runtime
        cls.server = server
        cls.thread = threading.Thread(target=server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)

    def test_root_serves_live_webmcp_transport_but_replay_starts_explicit(self):
        with urlopen(self.base + "/", timeout=10) as response:
            html = response.read().decode()
            self.assertIn('src="/webmcp.mjs"', html)
            self.assertEqual(response.headers.get("Permissions-Policy"), "tools=(self)")
        with urlopen(self.base + "/webmcp.mjs", timeout=10) as response:
            source = response.read().decode()
        self.assertIn("document.modelContext", source)
        self.assertIn('from "/session.mjs"', source)
        self.assertIn("apiFetch", source)
        self.assertNotIn("STATE =", source)
        with urlopen(self.base + "/api/config", timeout=10) as response:
            config = json.loads(response.read())
        self.assertEqual(config["default_source"], "replay")
        self.assertTrue(config["live_product"])

    def test_webmcp_prepare_preview_share_live_discover_updates_same_product(self):
        client = Client(self.base)
        client.guest()

        _, prepared, _ = client.request("POST", "/api/webmcp/prepare", {
            "request_id": "competition-prepare-1", "note": "judge flow",
        })
        self.assertFalse(prepared["discoverable"])
        self.assertTrue(prepared["session_id"].startswith("session-"))

        _, state, _ = client.request("GET", "/api/webmcp/state")
        self.assertTrue(state["draft_ready"])
        self.assertFalse(state["shared"])

        _, preview, _ = client.request("GET", "/api/webmcp/preview")
        self.assertEqual(preview["draft_id"], prepared["draft_id"])
        self.assertTrue(preview["requires_explicit_confirmation"])
        self.assertTrue(preview["confirmation_token"])
        self.assertIn("thought", preview["will_become_discoverable"])

        _, shared, _ = client.request("POST", "/api/webmcp/share", {
            "request_id": "competition-share-1",
            "confirm": True,
            "confirmation_token": preview["confirmation_token"],
        })
        self.assertTrue(shared["shared"])
        self.assertTrue(shared["discoverable"])

        _, state, _ = client.request("GET", "/api/webmcp/state")
        self.assertFalse(state["draft_ready"])
        self.assertTrue(state["shared"])

        _, result, _ = client.request("GET", "/api/webmcp/discover?source=live")
        self.assertEqual(result["source"], "live")
        self.assertRegex(result["result_id"], r"^result-[0-9a-f]{24}$")
        self.assertGreater(len(result["matches_in_backend_order"]), 0)

        session_id = result["matches_in_backend_order"][0]["session_id"]
        _, evidence, _ = client.request(
            "GET", f"/api/webmcp/match?result_id={result['result_id']}"
                   f"&session_id={session_id}")
        self.assertEqual(evidence["source"], "live")
        self.assertEqual(evidence["match"]["session_id"], session_id)

        # The unchanged R9 page source switch reads the SAME live product result
        # contract through its presentation adapter, not legacy stdio shadow state.
        _, visible, _ = client.request("GET", "/api/discover?source=live")
        self.assertEqual(visible["contract_version"], "resonance-discovery/0.1")
        self.assertGreater(len(visible["matches"]), 0)

    def test_webmcp_operation_receipt_reconciles_same_process_retry(self):
        client = Client(self.base)
        client.guest()
        body = {"request_id": "competition-idempotent-prepare", "note": "once"}
        _, first, _ = client.request("POST", "/api/webmcp/prepare", body)
        _, second, _ = client.request("POST", "/api/webmcp/prepare", body)
        self.assertEqual(first, second)
        _, op, _ = client.request(
            "GET", "/api/webmcp/operation?operation=prepare"
                   "&request_id=competition-idempotent-prepare")
        self.assertTrue(op["committed"])
        self.assertEqual(op["result"], first)


if __name__ == "__main__":
    unittest.main()
