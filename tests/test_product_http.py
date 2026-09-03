"""Real-HTTP tests for the R13 live product server."""

from __future__ import annotations

import json
import threading
import unittest
from http.cookies import SimpleCookie
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from src.product.server import build_runtime, serve
from tests.test_product_live import PRES, QUERY_DNA, location, r7_dna

ORIGIN = "http://127.0.0.1:0"  # rewritten per-test with the bound port


class HttpClient:
    def __init__(self, base: str, origin: str):
        self.base = base
        self.origin = origin
        self.cookie: str | None = None
        self.csrf: str | None = None

    def request(self, method: str, path: str, body=None, *,
                origin=True, csrf=True, raw_body: bytes | None = None):
        headers = {"Content-Type": "application/json"}
        if origin:
            headers["Origin"] = self.origin
        if self.cookie:
            headers["Cookie"] = self.cookie
        if csrf and self.csrf:
            headers["X-Resonance-CSRF"] = self.csrf
        data = raw_body if raw_body is not None else (
            json.dumps(body).encode("utf-8") if body is not None else None)
        request = Request(self.base + path, data=data, headers=headers,
                          method=method)
        with urlopen(request, timeout=10) as response:
            set_cookie = response.headers.get("Set-Cookie")
            if set_cookie:
                morsel = SimpleCookie(set_cookie).get("resonance_token")
                if morsel is not None:
                    self.cookie = f"resonance_token={morsel.value}"
            payload = json.loads(response.read().decode("utf-8"))
            return response.status, payload, dict(response.headers)

    def guest(self):
        status, payload, _ = self.request("POST", "/api/product/guest", {})
        self.csrf = payload["csrf_token"]
        return payload


class ProductHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        runtime = build_runtime(":memory:",
                                allowed_origins=frozenset({"pending"}))
        server = serve("127.0.0.1", 0, runtime=runtime)
        host, port = server.server_address[:2]
        cls.origin = f"http://{host}:{port}"
        # rebuild runtime with the real bound origin in the allowlist
        cls.runtime = build_runtime(":memory:",
                                    allowed_origins=frozenset({cls.origin}))
        server.RequestHandlerClass.runtime = cls.runtime
        cls.server = server
        cls.thread = threading.Thread(target=server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = cls.origin

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def client(self) -> HttpClient:
        return HttpClient(self.base, self.origin)

    def _shared_session(self, client: HttpClient, source: str, thought_id: str,
                        loc=None):
        status, prepared, _ = client.request("POST", "/api/product/prepare", {
            "candidate": r7_dna(source, thought_id),
            "presentation": dict(PRES),
            "coarse_location": dict(loc) if loc else None,
            "share_intent": {"share_display_profile": True,
                             "share_coarse_location": bool(loc)},
        })
        self.assertEqual(prepared["status"], "prepared_private")
        status, preview, _ = client.request(
            "GET", f"/api/product/preview?draft_id={prepared['draft_id']}")
        status, receipt, _ = client.request("POST", "/api/product/share", {
            "draft_id": prepared["draft_id"],
            "confirmation_token": preview["confirmation_token"],
            "confirmed": True,
        })
        self.assertTrue(receipt["discoverable"])
        return prepared["session_id"]

    def test_guest_cookie_flow_and_state(self):
        client = self.client()
        payload = client.guest()
        self.assertTrue(payload["user_id"].startswith("person-"))
        self.assertTrue(client.cookie)
        status, state, headers = client.request("GET", "/api/product/state")
        self.assertEqual(state["mode"], "live")
        self.assertIn("index_current", state["freshness"])
        self.assertEqual(headers.get("Permissions-Policy"), "tools=(self)")
        self.assertIn("default-src 'self'", headers.get("Content-Security-Policy", ""))

    def test_unauthenticated_mutation_is_401(self):
        client = self.client()
        with self.assertRaises(HTTPError) as ctx:
            client.request("POST", "/api/product/prepare",
                           {"context": "Because A causes B, C follows."})
        self.assertEqual(ctx.exception.code, 401)

    def test_cross_origin_and_missing_csrf_are_403(self):
        client = self.client()
        client.guest()
        original = client.origin
        client.origin = "https://evil.example"
        with self.assertRaises(HTTPError) as ctx:
            client.request("POST", "/api/product/prepare",
                           {"context": "Because A causes B, C follows."})
        self.assertEqual(ctx.exception.code, 403)
        client.origin = original
        saved = client.csrf
        client.csrf = "wrong-token"
        with self.assertRaises(HTTPError) as ctx:
            client.request("POST", "/api/product/prepare",
                           {"context": "Because A causes B, C follows."})
        self.assertEqual(ctx.exception.code, 403)
        client.csrf = saved

    def test_full_journey_discover_match_and_r10_compat_shape(self):
        alice = self.client(); alice.guest()
        a_session = self._shared_session(alice, "ses-gabe-warehouse",
                                         "thought-http-alice", loc=location("R"))
        bob = self.client(); bob.guest()
        b_session = self._shared_session(bob, QUERY_DNA, "thought-http-bob",
                                         loc=location("R", lat=55.9, lon=37.7))
        status, response, _ = bob.request(
            "GET", f"/api/product/discover?session_id={b_session}&k=8")
        found = [m["session_id"] for m in response["matches"]]
        self.assertIn(a_session, found)
        self.assertEqual(response["source"], "live")
        self.assertTrue(response["freshness"]["index_current"])
        row = next(m for m in response["matches"] if m["session_id"] == a_session)
        self.assertIn("distance_context", row["display"])

        status, evidence, _ = bob.request(
            "GET", f"/api/product/match?result_id={response['result_id']}"
                   f"&session_id={a_session}")
        self.assertEqual(evidence["match"]["session_id"], a_session)

        status, compat, _ = bob.request(
            "GET", f"/api/webmcp/discover?session_id={b_session}&k=8")
        self.assertIn("matches_in_backend_order", compat)
        self.assertEqual([m["session_id"] for m in compat["matches_in_backend_order"]],
                         found)

    def test_revoke_removes_and_stale_result_is_conflict(self):
        alice = self.client(); alice.guest()
        a_session = self._shared_session(alice, "ses-mei-battery-heat",
                                         "thought-http-a2")
        bob = self.client(); bob.guest()
        b_session = self._shared_session(bob, QUERY_DNA, "thought-http-b2")
        status, response, _ = bob.request(
            "GET", f"/api/product/discover?session_id={b_session}&k=8")
        rid = response["result_id"]
        self.assertIn(a_session, [m["session_id"] for m in response["matches"]])
        status, revoked, _ = alice.request("POST", "/api/product/revoke", {
            "session_id": a_session, "confirmed": True})
        self.assertTrue(revoked["revoked"])
        with self.assertRaises(HTTPError) as ctx:
            bob.request("GET", f"/api/product/match?result_id={rid}"
                               f"&session_id={a_session}")
        self.assertEqual(ctx.exception.code, 409)
        status, fresh, _ = bob.request(
            "GET", f"/api/product/discover?session_id={b_session}&k=8")
        self.assertNotIn(a_session, [m["session_id"] for m in fresh["matches"]])

    def test_oversized_body_is_400(self):
        client = self.client()
        client.guest()
        with self.assertRaises(HTTPError) as ctx:
            client.request("POST", "/api/product/prepare",
                           raw_body=b"x" * (97 * 1024))
        self.assertEqual(ctx.exception.code, 400)

    def test_login_with_recovery_after_logout(self):
        client = self.client()
        payload = client.guest()
        client.request("POST", "/api/product/logout", {})
        client.cookie = None
        client.csrf = None
        status, relog, _ = client.request("POST", "/api/product/login", {
            "user_id": payload["user_id"],
            "recovery_secret": payload["recovery_secret"]}, csrf=False)
        self.assertEqual(relog["user_id"], payload["user_id"])
        client.csrf = relog["csrf_token"]
        status, state, _ = client.request("GET", "/api/product/state")
        self.assertEqual(state["mode"], "live")

    def test_rich_discover_and_authorized_visuals_over_http(self):
        alice = self.client(); alice.guest()
        a_session = self._shared_session(alice, "ses-gabe-warehouse",
                                         "thought-rich-alice", loc=location("R"))
        bob = self.client(); bob.guest()
        b_session = self._shared_session(bob, QUERY_DNA, "thought-rich-bob",
                                         loc=location("R", lat=55.9, lon=37.7))
        status, rich, _ = bob.request(
            "GET", f"/api/product/rich_discover?session_id={b_session}&k=8")
        self.assertEqual(rich["contract_version"], "resonance-rich-result/0.1")
        row = next(m for m in rich["matches"] if m["session_id"] == a_session)
        self.assertIn(row["intro_state"], {"available", "unavailable"})
        self.assertTrue(row["ui_ref"].startswith("/#match="))

        request = Request(
            self.base + f"/api/product/visual/map?result_id={rich['result_id']}",
            headers={"Origin": self.origin, "Cookie": bob.cookie})
        with urlopen(request, timeout=10) as response:
            self.assertEqual(response.headers.get("Content-Type"),
                             "image/svg+xml; charset=utf-8")
            self.assertEqual(response.headers.get("Cache-Control"),
                             "private, no-store")
            svg = response.read().decode("utf-8")
        self.assertTrue(svg.startswith("<svg"))
        self.assertNotIn("ses-", svg)

        # visuals are viewer-bound: Alice cannot reuse Bob's result_id
        with self.assertRaises(HTTPError) as ctx:
            alice.request("GET",
                          f"/api/product/visual/map?result_id={rich['result_id']}")
        self.assertEqual(ctx.exception.code, 400)

        status, evidence, _ = bob.request(
            "GET", f"/api/product/match?result_id={rich['result_id']}"
                   f"&session_id={a_session}")
        request = Request(
            self.base + f"/api/product/visual/structure"
                        f"?result_id={rich['result_id']}&session_id={a_session}",
            headers={"Origin": self.origin, "Cookie": bob.cookie})
        with urlopen(request, timeout=10) as response:
            structure = response.read().decode("utf-8")
        self.assertIn("preserved relations", structure)

    def test_ui_is_served_with_live_injection(self):
        request = Request(self.base + "/", headers={"Origin": self.origin})
        with urlopen(request, timeout=10) as response:
            html = response.read().decode("utf-8")
        self.assertIn('window.RESONANCE_MODE = "live"', html)
        self.assertIn('src="/webmcp.mjs"', html)


if __name__ == "__main__":
    unittest.main()
