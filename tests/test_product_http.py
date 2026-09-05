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


class HeadRequestTests(unittest.TestCase):
    """Link scanners / uptime checkers preflight with HEAD; the stdlib handler
    answered 501 on the public origin. HEAD must mirror GET's headers."""

    @classmethod
    def setUpClass(cls):
        from src.product.server import build_runtime, serve
        pending = build_runtime(":memory:", allowed_origins=frozenset({"pending"}))
        cls.server = serve("127.0.0.1", 0, runtime=pending)
        host, port = cls.server.server_address[:2]
        cls.base = f"http://{host}:{port}"
        cls.server.RequestHandlerClass.runtime = build_runtime(
            ":memory:", allowed_origins=frozenset({cls.base}))
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def test_head_mirrors_get_headers_without_body(self):
        for path in ("/", "/api/product/health", "/webmcp.mjs"):
            with urlopen(Request(self.base + path, method="GET"), timeout=10) as get:
                get_len, get_type = get.headers.get("Content-Length"), get.headers.get("Content-Type")
            with urlopen(Request(self.base + path, method="HEAD"), timeout=10) as head:
                self.assertEqual(head.status, 200, path)
                self.assertEqual(head.headers.get("Content-Length"), get_len, path)
                self.assertEqual(head.headers.get("Content-Type"), get_type, path)
                self.assertEqual(head.headers.get("Permissions-Policy"), "tools=(self)")
                self.assertEqual(head.read(), b"")
        with self.assertRaises(HTTPError) as ctx:
            urlopen(Request(self.base + "/mcp", method="HEAD"), timeout=10)
        self.assertEqual(ctx.exception.code, 405)


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

    def test_collaboration_two_account_flow_over_http(self):
        alice = self.client(); alice.guest()
        a_session = self._shared_session(alice, "ses-gabe-warehouse",
                                         "thought-collab-alice")
        # opt into intro requests
        alice.request("POST", "/api/product/consent", {
            "session_id": a_session,
            "choices": {"share_thought_dna": True, "share_display_profile": True,
                        "share_coarse_location": False, "allow_intro_requests": True},
            "confirmed": True})
        bob = self.client(); bob.guest()
        b_session = self._shared_session(bob, QUERY_DNA, "thought-collab-bob")
        status, disc, _ = bob.request(
            "GET", f"/api/product/discover?session_id={b_session}&k=20")
        self.assertIn(a_session, [m["session_id"] for m in disc["matches"]])

        status, intro, _ = bob.request("POST", "/api/product/intro/request", {
            "from_session_id": b_session, "target_session_id": a_session,
            "message": "compare mitigations?", "request_id": "http-req",
            "confirmed": True})
        self.assertEqual(intro["state"], "requested")
        # confirmation is required
        with self.assertRaises(HTTPError) as ctx:
            bob.request("POST", "/api/product/intro/request", {
                "from_session_id": b_session, "target_session_id": a_session,
                "message": "again", "request_id": "http-req-2", "confirmed": False})
        self.assertEqual(ctx.exception.code, 409)

        status, incoming, _ = alice.request("GET", "/api/product/intro/list")
        self.assertEqual(len(incoming["incoming"]), 1)
        status, accepted, _ = alice.request("POST", "/api/product/intro/respond", {
            "intro_id": incoming["incoming"][0]["intro_id"], "accept": True,
            "request_id": "http-acc", "confirmed": True})
        channel = accepted["channel_id"]
        bob.request("POST", "/api/product/channel/send", {
            "channel_id": channel, "body": "throttle input power",
            "request_id": "http-m1", "confirmed": True})
        alice.request("POST", "/api/product/channel/send", {
            "channel_id": channel, "body": "stage inbound docks",
            "request_id": "http-m2", "confirmed": True})
        status, thread, _ = bob.request(
            "GET", f"/api/product/channel/messages?channel_id={channel}")
        self.assertEqual([m["body"] for m in thread["messages"]],
                         ["throttle input power", "stage inbound docks"])
        self.assertTrue(all(m["untrusted"] for m in thread["messages"]))
        # a third party cannot read the channel
        carol = self.client(); carol.guest()
        with self.assertRaises(HTTPError) as ctx:
            carol.request("GET", f"/api/product/channel/messages?channel_id={channel}")
        self.assertEqual(ctx.exception.code, 400)
        # rich intro_state is now accepted for Bob's view
        status, rich, _ = bob.request(
            "GET", f"/api/product/rich_discover?session_id={b_session}&k=20")
        row = next(m for m in rich["matches"] if m["session_id"] == a_session)
        self.assertEqual(row["intro_state"], "accepted")

    def test_workspace_flow_over_http(self):
        from src.ingestion.service import ShareIntent
        alice = self.client(); alice.guest()
        bob = self.client(); bob.guest()

        def share(client, source, tid, intro=True):
            status, prepared, _ = client.request("POST", "/api/product/prepare", {
                "candidate": r7_dna(source, tid), "presentation": dict(PRES),
                "share_intent": {"share_display_profile": True,
                                 "receive_intro_requests": intro}})
            status, preview, _ = client.request(
                "GET", f"/api/product/preview?draft_id={prepared['draft_id']}")
            client.request("POST", "/api/product/share", {
                "draft_id": prepared["draft_id"],
                "confirmation_token": preview["confirmation_token"], "confirmed": True})
            return prepared["session_id"]

        a_sess = share(alice, "ses-gabe-warehouse", "ws-a")
        b_sess = share(bob, QUERY_DNA, "ws-b")
        status, intro, _ = bob.request("POST", "/api/product/intro/request", {
            "from_session_id": b_sess, "target_session_id": a_sess,
            "message": "connect?", "request_id": "wri", "confirmed": True})
        status, incoming, _ = alice.request("GET", "/api/product/intro/list")
        iid = incoming["incoming"][0]["intro_id"]
        alice.request("POST", "/api/product/intro/respond", {
            "intro_id": iid, "accept": True, "request_id": "wai", "confirmed": True})

        status, ws, _ = alice.request("POST", "/api/product/workspace/create", {
            "intro_id": iid, "title": "Plasma×Warehouse", "brief": "compare"})
        wid = ws["workspace_id"]
        # Bob invited -> cannot read until accept
        with self.assertRaises(HTTPError) as ctx:
            bob.request("GET", f"/api/product/workspace?workspace_id={wid}")
        self.assertEqual(ctx.exception.code, 400)
        bob.request("POST", "/api/product/workspace/respond", {
            "workspace_id": wid, "accept": True})
        bob.request("POST", "/api/product/workspace/note", {
            "workspace_id": wid, "body": "throttle input power"})
        status, full, _ = alice.request("GET", f"/api/product/workspace?workspace_id={wid}")
        self.assertEqual([n["body"] for n in full["notes"]], ["throttle input power"])
        self.assertEqual(len(full["members"]), 2)
        self.assertEqual({m["state"] for m in full["members"]}, {"active"})
        bob_member = next(m for m in full["members"] if m["role"] == "member")
        # remove Bob -> immediate loss
        alice.request("POST", "/api/product/workspace/remove", {
            "workspace_id": wid, "target_user_id": bob_member["user_id"]})
        with self.assertRaises(HTTPError):
            bob.request("GET", f"/api/product/workspace?workspace_id={wid}")

    def test_ui_is_served_with_live_injection(self):
        request = Request(self.base + "/", headers={"Origin": self.origin})
        with urlopen(request, timeout=10) as response:
            html = response.read().decode("utf-8")
        # The former inline `window.RESONANCE_MODE` marker was refused by the
        # page's own CSP (default-src 'self') and had no readers; live mode is
        # now carried by live_shell.mjs as a body data attribute.
        self.assertNotIn("<script>window.RESONANCE_MODE", html)
        self.assertIn('src="/webmcp.mjs"', html)
        self.assertIn('src="/deeplink.mjs"', html)
        self.assertIn('src="/session.mjs"', html)
        self.assertIn('src="/collab.mjs"', html)
        self.assertIn('src="/collab_ui.mjs"', html)
        self.assertIn('src="/workspaces.mjs"', html)
        # R13 live-origin shell state (#88): the module that moves the R9 page
        # off its loading placeholders when /api/config is absent is served and
        # injected after the collaboration panel so it can reorder it.
        self.assertIn('src="/live_shell.mjs"', html)
        self.assertLess(html.index('src="/collab_ui.mjs"'), html.index('src="/live_shell.mjs"'))
        self.assertLess(html.index('src="/workspaces.mjs"'), html.index('src="/live_shell.mjs"'))
        # R16 Chrome audit: the collaboration drawer is styled by a linked
        # stylesheet (CSP default-src 'self' forbids inline styles) and the page
        # ships a favicon, both injected into <head>; served with proper types.
        self.assertIn('href="/live_ui.css"', html)
        self.assertIn('href="/favicon.svg"', html)
        self.assertLess(html.index('href="/live_ui.css"'), html.index("</head>"))
        self.assertLess(html.index("</head>"), html.index('src="/collab_ui.mjs"'))
        with urlopen(Request(self.base + "/live_ui.css"), timeout=10) as response:
            self.assertTrue(response.headers["Content-Type"].startswith("text/css"))
            css = response.read().decode("utf-8")
        self.assertIn(".collab-drawer", css)
        self.assertIn(".collab-toggle", css)
        for icon in ("/favicon.svg", "/favicon.ico"):
            with urlopen(Request(self.base + icon), timeout=10) as response:
                self.assertEqual(response.headers["Content-Type"], "image/svg+xml")
                self.assertIn(b"<svg", response.read())
        with urlopen(Request(self.base + "/live_shell.mjs"), timeout=10) as response:
            shell = response.read().decode("utf-8")
        self.assertIn("markLiveShell", shell)
        self.assertNotIn(".innerHTML", shell)
        # the R9 demo routes stay absent on the live origin — that absence is
        # exactly what the shell module keys on
        with self.assertRaises(HTTPError) as ctx:
            urlopen(Request(self.base + "/api/config"), timeout=10)
        self.assertEqual(ctx.exception.code, 404)
        # the human-UI collaboration module is committed and served
        with urlopen(Request(self.base + "/collab_ui.mjs"), timeout=10) as response:
            ui = response.read().decode("utf-8")
        self.assertIn("Request intro", ui)
        self.assertIn("/api/product/intro/request", ui)
        self.assertIn("textContent", ui)  # UGC displayed, never assigned to innerHTML
        self.assertNotIn(".innerHTML =", ui)
        self.assertNotIn(".innerHTML=", ui)

    def test_session_bootstrap_csrf_survives_reload_without_injection(self):
        # A committed page flow: establish a session, then a "reload" that only
        # carries the cookie must still be able to mint a usable CSRF via
        # /api/product/rotate — no harness secret injection.
        client = self.client()
        first = client.guest()
        original_csrf = first["csrf_token"]
        # F2: an authenticated visitor reports authenticated=true; an anon one
        # false — so the bootstrap never mints a guest for an authenticated user.
        status, state, _ = client.request("GET", "/api/product/state")
        self.assertTrue(state["authenticated"])
        anon = self.client()
        status, anon_state, _ = anon.request("GET", "/api/product/state",
                                             origin=False, csrf=False)
        self.assertFalse(anon_state["authenticated"])
        # simulate reload: same cookie, CSRF value no longer in hand
        rotated_headers = {"Content-Type": "application/json",
                           "Origin": self.origin, "Cookie": client.cookie}
        request = Request(self.base + "/api/product/rotate", data=b"{}",
                          headers=rotated_headers, method="POST")
        with urlopen(request, timeout=10) as response:
            rotated = json.loads(response.read())
            set_cookie = response.headers.get("Set-Cookie")
        self.assertEqual(rotated["user_id"], first["user_id"])
        self.assertTrue(rotated["csrf_token"])
        self.assertNotEqual(rotated["csrf_token"], original_csrf)
        # the rotated csrf actually authorizes a write on the same identity
        new_cookie = SimpleCookie(set_cookie).get("resonance_token")
        client.cookie = f"resonance_token={new_cookie.value}"
        client.csrf = rotated["csrf_token"]
        status, prepared, _ = client.request("POST", "/api/product/prepare", {
            "candidate": r7_dna(QUERY_DNA, "thought-reload"),
            "presentation": dict(PRES)})
        self.assertEqual(prepared["status"], "prepared_private")

    def test_two_concurrent_clients_of_one_subject_selfheal(self):
        """F4: a second client rotating must not permanently strand the first.

        The committed bootstrap shares one token via localStorage and, on a
        csrf_rejected write, re-bootstraps once. This test models the recovery
        contract at the HTTP layer: after a rotate invalidates an old token, a
        client that re-reads the current token can write again; the server
        never accepts the stale token (fail-closed), which is what the
        client-side self-heal keys off.
        """
        client = self.client()
        client.guest()
        # tab-2 rotates the shared subject
        rot_headers = {"Content-Type": "application/json", "Origin": self.origin,
                       "Cookie": client.cookie}
        request = Request(self.base + "/api/product/rotate", data=b"{}",
                          headers=rot_headers, method="POST")
        with urlopen(request, timeout=10) as response:
            rotated = json.loads(response.read())
            new_cookie = SimpleCookie(response.headers.get("Set-Cookie")).get(
                "resonance_token")
        # tab-1 still holding the OLD token+cookie: write fails closed (401,
        # prior auth session revoked) — never silently accepted.
        with self.assertRaises(HTTPError) as ctx:
            client.request("POST", "/api/product/prepare", {
                "candidate": r7_dna("ses-gabe-warehouse", "thought-strand"),
                "presentation": dict(PRES)})
        self.assertIn(ctx.exception.code, (401, 403))
        # self-heal: re-read the shared token+cookie, write succeeds again
        client.cookie = f"resonance_token={new_cookie.value}"
        client.csrf = rotated["csrf_token"]
        status, prepared, _ = client.request("POST", "/api/product/prepare", {
            "candidate": r7_dna("ses-gabe-warehouse", "thought-healed"),
            "presentation": dict(PRES)})
        self.assertEqual(prepared["status"], "prepared_private")

    def test_collab_ui_has_intro_initiation_and_the_page_no_longer_lies(self):
        with urlopen(Request(self.base + "/collab_ui.mjs"), timeout=10) as response:
            ui = response.read().decode("utf-8")
        # human intro initiation exists and drives the live discover+request path
        self.assertIn("Start an introduction", ui)
        self.assertIn("/api/product/rich_discover", ui)
        self.assertIn("querySession", ui)
        # The page used to carry a static "Introductions unavailable — not
        # exposed by the accepted R8 MCP" chip, which stopped being true at
        # R13/R14, and this module hid it at runtime. Hiding a false statement
        # is not the same as not making it: the markup now states the rule that
        # IS true, so both the claim and the workaround are gone.
        with urlopen(Request(self.base + "/"), timeout=10) as response:
            html = response.read().decode("utf-8")
        # match the element, not the phrase: the phrase survives on purpose in
        # the comment that records what the chip used to claim.
        self.assertNotIn('class="intro-unavailable"', html)
        self.assertIn("Introductions need both sides", html)
        self.assertNotIn('querySelector(".intro-unavailable")', ui)

    def test_connect_panel_leads_with_the_url_not_a_key(self):
        # The panel used to lead with "Create MCP key" and hand out
        # `Authorization: Bearer <key>` plus a `…/mcp/<key>` capability URL for
        # "clients that only take a URL". ops/CONNECT_MCP.md calls the key a
        # developer fallback, "debug only, not the normal path", and
        # submission/HUMAN_TEST_CARDS.md tells a tester that being asked for a
        # key is a FAIL. The product's own UI was teaching the failing path.
        with urlopen(Request(self.base + "/collab_ui.mjs"), timeout=10) as response:
            ui = response.read().decode("utf-8")
        # anchor on code, not prose: the phrase "Create MCP key" also appears in
        # the comment explaining why it no longer leads.
        url_block = ui.index("Hand your client this one address")
        key_block = ui.index('actionButton("Create MCP key"')
        self.assertLess(url_block, key_block, "the canonical URL must lead")
        self.assertIn("collab-advanced", ui)
        self.assertIn("Advanced: mint a key (debug only)", ui)
        # kept inside one string literal: the source wraps this sentence
        self.assertIn("You will not be asked to paste a", ui)
        # the capability URL (a secret inside a path) is no longer advertised
        self.assertNotIn("endpoint_with_key", ui)
        # R16 Chrome audit: the panel is a top-bar-toggled drawer (never a 4th
        # item of the 3-column workspace grid), refreshes after any successful
        # write made through session.mjs, and offers the human share path.
        self.assertIn("collab-toggle", ui)
        self.assertIn("collab-drawer", ui)
        self.assertNotIn('getElementById("main-workspace")', ui)
        self.assertIn("resonance:write", ui)
        self.assertIn("/api/webmcp/preview", ui)
        self.assertIn("/api/webmcp/share", ui)
        self.assertNotIn("style.cssText", ui)  # presentation lives in live_ui.css
        with urlopen(Request(self.base + "/session.mjs"), timeout=10) as response:
            self.assertIn("resonance:write", response.read().decode("utf-8"))
        # session bootstrap shares the token across tabs (F4) and self-heals
        with urlopen(Request(self.base + "/session.mjs"), timeout=10) as response:
            session = response.read().decode("utf-8")
        self.assertIn("localStorage", session)
        self.assertIn("csrf_rejected", session)
        with urlopen(Request(self.base + "/deeplink.mjs"), timeout=10) as response:
            script = response.read().decode("utf-8")
        self.assertIn("FRAGMENT_RE", script)
        self.assertIn("hashchange", script)
        self.assertIn("/api/product/match", script)

    def test_ui_ref_deep_link_round_trip_with_fail_closed_rejections(self):
        import re
        alice = self.client(); alice.guest()
        a_session = self._shared_session(alice, "ses-noah-org-overload",
                                         "thought-link-alice")
        bob = self.client(); bob.guest()
        b_session = self._shared_session(bob, QUERY_DNA, "thought-link-bob")
        status, rich, _ = bob.request(
            "GET", f"/api/product/rich_discover?session_id={b_session}&k=20")
        row = next(m for m in rich["matches"] if m["session_id"] == a_session)
        # The emitted ui_ref resolves through the SAME authorized match path
        # the deeplink script calls — full round trip.
        parsed = re.fullmatch(r"/#match=(result-[0-9a-f]{24}):([A-Za-z0-9._-]+)",
                              row["ui_ref"])
        self.assertIsNotNone(parsed)
        result_id, session_id = parsed.group(1), parsed.group(2)
        self.assertEqual(session_id, a_session)
        status, evidence, _ = bob.request(
            "GET", f"/api/product/match?result_id={result_id}"
                   f"&session_id={session_id}")
        self.assertEqual(evidence["match"]["session_id"], a_session)
        # foreign viewer: fail closed
        with self.assertRaises(HTTPError) as ctx:
            alice.request("GET", f"/api/product/match?result_id={result_id}"
                                 f"&session_id={session_id}")
        self.assertEqual(ctx.exception.code, 400)
        # stale after revoke: fail closed
        alice.request("POST", "/api/product/revoke",
                      {"session_id": a_session, "confirmed": True})
        with self.assertRaises(HTTPError) as ctx:
            bob.request("GET", f"/api/product/match?result_id={result_id}"
                               f"&session_id={session_id}")
        self.assertEqual(ctx.exception.code, 409)


if __name__ == "__main__":
    unittest.main()
