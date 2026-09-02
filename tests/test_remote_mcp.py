"""R15 transport tests: real HTTP round trips, auth (bearer + PKCE), sessions,
rich results, service convergence, rate limits, and boundary discipline."""

import json
import secrets
import sys
import threading
import unittest
import urllib.request
import urllib.error
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from src.remote import AuthStore, ProductService, RateLimiter, build_httpd
from src.remote.auth import _s256
from src.discovery.fixtures.r7_corpus import build as build_corpus, flagship_query


def _post(url, payload, headers=None, form=False):
    if form:
        data = "&".join(f"{k}={v}" for k, v in payload.items()).encode()
        content_type = "application/x-www-form-urlencoded"
    else:
        data = json.dumps(payload).encode()
        content_type = "application/json"
    request = urllib.request.Request(url, data=data, method="POST",
                                     headers={"Content-Type": content_type,
                                              **(headers or {})})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read()
            return response.status, dict(response.headers), (
                json.loads(body) if body else None)
    except urllib.error.HTTPError as error:
        body = error.read()
        return error.code, dict(error.headers), (
            json.loads(body) if body else None)


class RemoteMCPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        engine, registry, by_session = build_corpus()
        from src.discovery.service import DiscoveryService
        cls.flagship = flagship_query(by_session)
        cls.auth = AuthStore()
        cls.token = cls.auth.issue_token("user-demo")
        service = ProductService(DiscoveryService(engine, registry),
                                 limiter=RateLimiter(capacity=1000))
        cls.httpd = build_httpd(port=0, service=service, auth=cls.auth)
        cls.port = cls.httpd.server_address[1]
        cls.base = f"http://127.0.0.1:{cls.port}"
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()

    # -- helpers -------------------------------------------------------------
    def _init_session(self, token=None):
        status, headers, reply = _post(
            f"{self.base}/mcp",
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            {"Authorization": f"Bearer {token or self.token}"})
        self.assertEqual(status, 200)
        return headers["Mcp-Session-Id"], reply

    def _call(self, session, name, arguments, token=None, msg_id=7):
        return _post(
            f"{self.base}/mcp",
            {"jsonrpc": "2.0", "id": msg_id, "method": "tools/call",
             "params": {"name": name, "arguments": arguments}},
            {"Authorization": f"Bearer {token or self.token}",
             "Mcp-Session-Id": session})

    # -- auth ---------------------------------------------------------------
    def test_unauthenticated_request_is_401_with_www_authenticate(self):
        status, headers, _ = _post(
            f"{self.base}/mcp",
            {"jsonrpc": "2.0", "id": 1, "method": "initialize"})
        self.assertEqual(status, 401)
        self.assertIn("WWW-Authenticate", headers)

    def test_wrong_token_is_401(self):
        status, _, _ = _post(
            f"{self.base}/mcp",
            {"jsonrpc": "2.0", "id": 1, "method": "initialize"},
            {"Authorization": "Bearer nope"})
        self.assertEqual(status, 401)

    def test_oauth_pkce_flow_yields_working_token(self):
        verifier = secrets.token_urlsafe(32)
        status, _, reply = _post(f"{self.base}/oauth/authorize",
                                 {"user": "demo", "client_id": "c1",
                                  "redirect_uri": "http://cb",
                                  "code_challenge": _s256(verifier),
                                  "code_challenge_method": "S256"}, form=True)
        self.assertEqual(status, 200)
        status, _, token_reply = _post(f"{self.base}/oauth/token",
                                       {"grant_type": "authorization_code",
                                        "code": reply["code"],
                                        "code_verifier": verifier,
                                        "client_id": "c1",
                                        "redirect_uri": "http://cb"}, form=True)
        self.assertEqual(status, 200)
        session, init = self._init_session(token=token_reply["access_token"])
        self.assertEqual(init["result"]["protocolVersion"], "2025-03-26")

    def test_pkce_wrong_verifier_rejected(self):
        verifier = secrets.token_urlsafe(32)
        _, _, reply = _post(f"{self.base}/oauth/authorize",
                            {"user": "demo", "client_id": "c1",
                             "redirect_uri": "http://cb",
                             "code_challenge": _s256(verifier),
                             "code_challenge_method": "S256"}, form=True)
        status, _, err = _post(f"{self.base}/oauth/token",
                               {"grant_type": "authorization_code",
                                "code": reply["code"],
                                "code_verifier": "wrong",
                                "client_id": "c1",
                                "redirect_uri": "http://cb"}, form=True)
        self.assertEqual(status, 400)
        self.assertEqual(err["error"], "invalid_grant")

    # -- protocol ------------------------------------------------------------
    def test_session_required_after_initialize(self):
        session, _ = self._init_session()
        status, _, reply = _post(
            f"{self.base}/mcp",
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            {"Authorization": f"Bearer {self.token}"})
        self.assertEqual(reply["error"]["code"], -32600)
        status, _, reply = _post(
            f"{self.base}/mcp",
            {"jsonrpc": "2.0", "id": 3, "method": "tools/list"},
            {"Authorization": f"Bearer {self.token}",
             "Mcp-Session-Id": session})
        names = [t["name"] for t in reply["result"]["tools"]]
        self.assertEqual(sorted(names), ["compare_thoughts", "discover_resonance",
                                         "get_thought", "ingest_thought"])

    def test_get_mcp_is_405_documented(self):
        request = urllib.request.Request(f"{self.base}/mcp")
        try:
            urllib.request.urlopen(request, timeout=10)
            self.fail("expected 405")
        except urllib.error.HTTPError as error:
            self.assertEqual(error.code, 405)

    # -- rich results --------------------------------------------------------
    def test_discover_returns_structured_content_plus_svg_resource(self):
        session, _ = self._init_session()
        status, _, reply = self._call(session, "discover_resonance",
                                      {"thought": self.flagship.to_dict(),
                                       "mode": "analogical", "k": 15})
        result = reply["result"]
        self.assertFalse(result["isError"])
        structured = result["structuredContent"]
        self.assertEqual(structured["contract_version"], "resonance-discovery/0.1")
        self.assertGreaterEqual(len(structured["matches"]), 4)
        kinds = [c["type"] for c in result["content"]]
        self.assertIn("text", kinds)
        self.assertIn("resource", kinds)
        resource = next(c for c in result["content"] if c["type"] == "resource")
        self.assertEqual(resource["resource"]["mimeType"], "image/svg+xml")
        self.assertIn("<svg", resource["resource"]["text"])
        self.assertNotIn("ravi", json.dumps(structured).lower())

    def test_remote_equals_local_service_result(self):
        """Convergence: the remote wire result equals a direct service call."""
        session, _ = self._init_session()
        _, _, reply = self._call(session, "discover_resonance",
                                 {"thought": self.flagship.to_dict(),
                                  "mode": "analogical", "k": 15})
        remote = reply["result"]["structuredContent"]
        local = self.httpd.RequestHandlerClass.core.service.discover(
            "user-demo", self.flagship, mode="analogical", k=15)
        self.assertEqual(json.dumps(remote, sort_keys=True),
                         json.dumps(local, sort_keys=True))

    # -- guardrails ----------------------------------------------------------
    def test_write_and_admin_tools_are_not_remotely_exposed(self):
        session, _ = self._init_session()
        for name in ("index_thought", "save_snapshot", "load_snapshot",
                     "explain_resonance"):
            _, _, reply = self._call(session, name, {})
            self.assertEqual(reply["error"]["code"], -32601, name)

    def test_oversized_context_is_rejected_as_tool_error(self):
        session, _ = self._init_session()
        _, _, reply = self._call(session, "ingest_thought",
                                 {"context": "x" * 30001})
        result = reply["result"]
        self.assertTrue(result["isError"])
        self.assertIn("size cap", result["content"][0]["text"])

    def test_rate_limit_surfaces_as_tool_error(self):
        engine, registry, _ = build_corpus()
        from src.discovery.service import DiscoveryService
        clock = [0.0]
        limiter = RateLimiter(capacity=2, refill_per_second=0.0,
                              clock=lambda: clock[0])
        service = ProductService(DiscoveryService(engine, registry), limiter)
        auth = AuthStore()
        token = auth.issue_token("user-demo")
        httpd = build_httpd(port=0, service=service, auth=auth)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            base = f"http://127.0.0.1:{httpd.server_address[1]}"
            _, headers, _ = _post(base + "/mcp",
                                  {"jsonrpc": "2.0", "id": 1,
                                   "method": "initialize", "params": {}},
                                  {"Authorization": f"Bearer {token}"})
            session = headers["Mcp-Session-Id"]
            for i in range(2):
                _post(base + "/mcp",
                      {"jsonrpc": "2.0", "id": 10 + i, "method": "tools/call",
                       "params": {"name": "get_thought",
                                  "arguments": {"thought_id": "x"}}},
                      {"Authorization": f"Bearer {token}",
                       "Mcp-Session-Id": session})
            _, _, reply = _post(base + "/mcp",
                                {"jsonrpc": "2.0", "id": 99, "method": "tools/call",
                                 "params": {"name": "get_thought",
                                            "arguments": {"thought_id": "x"}}},
                                {"Authorization": f"Bearer {token}",
                                 "Mcp-Session-Id": session})
            self.assertTrue(reply["result"]["isError"])
            self.assertIn("rate limit", reply["result"]["content"][0]["text"])
        finally:
            httpd.shutdown()
            httpd.server_close()

    def test_transport_sources_contain_no_business_logic(self):
        for module in ("server.py", "auth.py", "visual.py"):
            text = (REPO / "src" / "remote" / module).read_text()
            for forbidden in ("src.alignment", "src.index.store", "src.fingerprint",
                              "src.scoring", "solve_fgw", "adjudicate(",
                              "sorted(match", "reverse=True"):
                self.assertNotIn(forbidden, text, module)


if __name__ == "__main__":
    unittest.main()
