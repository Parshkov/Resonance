"""R15A focused OAuth protocol tests: the canonical hosted-client authorization
core over the accepted R12 identity model.

Covers the #134 acceptance sequence 1-16 directly (implementer-side, stdlib
urllib), separate from the independent black-box probe. Drives the real browser
handshake: consent page, approve POST, follow the redirect for code+state, then
token exchange — no manual key, bearer, capability URL, or custom header."""

from __future__ import annotations

import base64
import hashlib
import json
import re
import secrets
import threading
import unittest
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

from src.product.server import build_runtime
from src.remote.server import build_httpd

REDIRECT = "https://client.example/callback"


def _pkce(seed: bytes = b"verifier-seed-0123456789-abcdefgh"):
    verifier = base64.urlsafe_b64encode(seed + secrets.token_bytes(16)).rstrip(b"=").decode()
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    return verifier, challenge


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Client:
    def __init__(self, base):
        self.base = base
        self.opener = build_opener(_NoRedirect())

    def _open(self, req):
        try:
            with self.opener.open(req, timeout=10) as r:
                return r.status, dict(r.headers), r.read()
        except HTTPError as e:
            return e.code, dict(e.headers), e.read()

    def get(self, path, headers=None):
        return self._open(Request(self.base + path, method="GET", headers=headers or {}))

    def post_form(self, path, fields, headers=None):
        h = {"Content-Type": "application/x-www-form-urlencoded", **(headers or {})}
        return self._open(Request(self.base + path, data=urlencode(fields).encode(),
                                  method="POST", headers=h))

    def rpc(self, token, method, params=None, session=None, mid=1):
        h = {"Content-Type": "application/json"}
        if token:
            h["Authorization"] = f"Bearer {token}"
        if session:
            h["Mcp-Session-Id"] = session
        msg = {"jsonrpc": "2.0", "id": mid, "method": method}
        if params is not None:
            msg["params"] = params
        status, headers, body = self._open(
            Request(self.base + "/mcp", data=json.dumps(msg).encode(), method="POST", headers=h))
        doc = json.loads(body) if body else None
        return status, headers.get("Mcp-Session-Id"), doc

    # -- flow helpers ---------------------------------------------------
    def authorize(self, *, challenge, state, client_id="cid", redirect_uri=REDIRECT,
                  resource=None, scope="resonance", identity="guest", decision="approve",
                  cookie=None, user_id=None, recovery_secret=None):
        params = {"response_type": "code", "client_id": client_id,
                  "redirect_uri": redirect_uri, "code_challenge": challenge,
                  "code_challenge_method": "S256", "state": state, "scope": scope}
        if resource is not None:
            params["resource"] = resource
        get_headers = {"Cookie": cookie} if cookie else {}
        gstatus, _, gbody = self.get("/oauth/authorize?" + urlencode(params), get_headers)
        fields = dict(params, decision=decision, identity=identity)
        if user_id:
            fields["user_id"] = user_id
        if recovery_secret:
            fields["recovery_secret"] = recovery_secret
        pstatus, pheaders, _ = self.post_form("/oauth/authorize", fields, get_headers)
        loc = pheaders.get("Location", "")
        q = {k: v[0] for k, v in parse_qs(urlparse(loc).query).items()} if loc else {}
        return {"get_status": gstatus, "get_body": gbody.decode(errors="replace"),
                "status": pstatus, "location": loc, "query": q}

    def token(self, fields):
        return self.post_form("/oauth/token", fields)


class OAuthCoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runtime = build_runtime(":memory:", allowed_origins=frozenset({"http://127.0.0.1"}))
        cls.httpd = build_httpd("127.0.0.1", 0, runtime=cls.runtime)
        cls.base = f"http://127.0.0.1:{cls.httpd.server_address[1]}"
        cls.issuer = cls.base
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def c(self):
        return Client(self.base)

    def register_client(self, redirect_uris=(REDIRECT,)):
        c = self.c()
        status, _, body = c.post_form("/oauth/register", {})  # will 400 (form, no json)
        # registration expects JSON:
        req = Request(self.base + "/oauth/register",
                      data=json.dumps({"redirect_uris": list(redirect_uris),
                                       "client_name": "Test"}).encode(),
                      headers={"Content-Type": "application/json"}, method="POST")
        status, _, body = c._open(req)
        self.assertEqual(status, 201, body)
        return json.loads(body)["client_id"]

    # -- 1-3 discovery --------------------------------------------------
    def test_unauthenticated_mcp_challenges_with_resource_metadata(self):
        c = self.c()
        status, headers, _ = c._open(Request(
            self.base + "/mcp",
            data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                             "params": {"protocolVersion": "2025-03-26"}}).encode(),
            headers={"Content-Type": "application/json"}, method="POST"))
        self.assertEqual(status, 401)
        wa = headers.get("WWW-Authenticate", "")
        self.assertIn("Bearer", wa)
        self.assertIn(f'resource_metadata="{self.issuer}/.well-known/oauth-protected-resource"', wa)

    def test_protected_resource_metadata(self):
        _, _, body = self.c().get("/.well-known/oauth-protected-resource")
        doc = json.loads(body)
        self.assertEqual(doc["resource"], f"{self.issuer}/mcp")
        self.assertEqual(doc["authorization_servers"], [self.issuer])
        self.assertIn("resonance", doc["scopes_supported"])

    def test_authorization_server_metadata(self):
        _, _, body = self.c().get("/.well-known/oauth-authorization-server")
        doc = json.loads(body)
        self.assertEqual(doc["issuer"], self.issuer)
        self.assertEqual(doc["authorization_endpoint"], f"{self.issuer}/oauth/authorize")
        self.assertEqual(doc["token_endpoint"], f"{self.issuer}/oauth/token")
        self.assertIn("S256", doc["code_challenge_methods_supported"])
        self.assertIn("authorization_code", doc["grant_types_supported"])
        self.assertIn("refresh_token", doc["grant_types_supported"])
        self.assertTrue(doc["resource_indicators_supported"])

    def test_issuer_is_never_taken_from_an_unlisted_forwarded_host(self):
        # A caller-controlled forwarded host must not become the issuer of the
        # discovery documents (metadata poisoning); the allowlist decides.
        _, _, body = self.c().get("/.well-known/oauth-authorization-server",
                                  {"X-Forwarded-Proto": "https",
                                   "X-Forwarded-Host": "resonance.example"})
        self.assertNotEqual(json.loads(body)["issuer"], "https://resonance.example")

    # -- 4-10 happy path ------------------------------------------------
    def _full_connect(self, client_id, *, scope="resonance"):
        c = self.c()
        verifier, challenge = _pkce()
        state = secrets.token_urlsafe(9)
        authd = c.authorize(challenge=challenge, state=state, client_id=client_id, scope=scope)
        self.assertEqual(authd["get_status"], 200)
        self.assertIn("Authorize access to Resonance", authd["get_body"])
        self.assertEqual(authd["status"], 302)
        self.assertTrue(authd["location"].startswith(REDIRECT))
        self.assertEqual(authd["query"]["state"], state)
        code = authd["query"]["code"]
        status, headers, body = c.token({
            "grant_type": "authorization_code", "code": code, "code_verifier": verifier,
            "redirect_uri": REDIRECT, "client_id": client_id})
        self.assertEqual(status, 200, body)
        self.assertEqual(headers.get("Cache-Control"), "no-store")
        tok = json.loads(body)
        self.assertEqual(tok["token_type"], "Bearer")
        return c, tok, verifier, code

    def test_registration_and_full_journey(self):
        cid = self.register_client()
        c, tok, _, _ = self._full_connect(cid)
        access = tok["access_token"]
        istatus, sid, init = c.rpc(access, "initialize", {"protocolVersion": "2025-03-26"})
        self.assertEqual(istatus, 200)
        self.assertEqual(init["result"]["protocolVersion"], "2025-03-26")
        _, _, tools = c.rpc(access, "tools/list", session=sid, mid=2)
        names = {t["name"] for t in tools["result"]["tools"]}
        self.assertIn("resonance_whoami", names)
        _, _, who = c.rpc(access, "tools/call",
                          {"name": "resonance_whoami", "arguments": {}}, session=sid, mid=3)
        self.assertFalse(who["result"]["isError"])
        self.assertTrue(who["result"]["structuredContent"]["user_id"].startswith("person-"))

    def test_ephemeral_client_without_registration_connects(self):
        # A hosted client that did not register still works with an exact redirect_uri.
        c, tok, _, _ = self._full_connect("unregistered-client-xyz")
        self.assertTrue(tok["access_token"])

    # -- 11-15 negatives ------------------------------------------------
    def test_wrong_verifier_rejected_and_code_consumed(self):
        c = self.c()
        verifier, challenge = _pkce()
        authd = c.authorize(challenge=challenge, state="s")
        code = authd["query"]["code"]
        status, _, body = c.token({"grant_type": "authorization_code", "code": code,
                                   "code_verifier": "not-the-verifier",
                                   "redirect_uri": REDIRECT, "client_id": "cid"})
        self.assertEqual(status, 400)
        self.assertEqual(json.loads(body)["error"], "invalid_grant")
        # correct verifier now fails too: the code was consumed on the first try
        status, _, _ = c.token({"grant_type": "authorization_code", "code": code,
                                "code_verifier": verifier,
                                "redirect_uri": REDIRECT, "client_id": "cid"})
        self.assertEqual(status, 400)

    def test_open_redirect_prevented_at_authorize(self):
        c = self.c()
        _, challenge = _pkce()
        # unregistered client + non-loopback http redirect is an invalid shape -> on-page 400,
        # never a 302 to the attacker.
        authd = c.authorize(challenge=challenge, state="s", redirect_uri="http://attacker.example/x")
        self.assertNotEqual(authd["status"], 302)
        self.assertEqual(authd["query"], {})

    def test_registered_client_rejects_unknown_redirect(self):
        cid = self.register_client(redirect_uris=(REDIRECT,))
        c = self.c()
        _, challenge = _pkce()
        authd = c.authorize(challenge=challenge, state="s", client_id=cid,
                            redirect_uri="https://evil.example/cb")
        # redirect_uri not registered -> on-page error, no redirect to evil
        self.assertNotEqual(authd["status"], 302)
        self.assertNotIn("evil.example", authd["location"])

    def test_token_redirect_uri_mismatch_rejected(self):
        c = self.c()
        verifier, challenge = _pkce()
        authd = c.authorize(challenge=challenge, state="s")
        status, _, body = c.token({"grant_type": "authorization_code",
                                   "code": authd["query"]["code"], "code_verifier": verifier,
                                   "redirect_uri": REDIRECT + "-tampered", "client_id": "cid"})
        self.assertEqual(status, 400)
        self.assertEqual(json.loads(body)["error"], "invalid_grant")

    def test_state_and_pkce_required(self):
        c = self.c()
        _, challenge = _pkce()
        # missing state
        params = {"response_type": "code", "client_id": "cid", "redirect_uri": REDIRECT,
                  "code_challenge": challenge, "code_challenge_method": "S256"}
        status, headers, _ = c._open(Request(
            self.base + "/oauth/authorize?" + urlencode(params), method="GET"))
        # redirect_uri is valid, so this becomes a redirect error carrying error=invalid_request
        self.assertIn(status, (302, 400))
        # plain (non-S256) PKCE method rejected
        params2 = dict(params, state="s", code_challenge_method="plain")
        status2, _, _ = c._open(Request(
            self.base + "/oauth/authorize?" + urlencode(params2), method="GET"))
        self.assertIn(status2, (302, 400))

    def test_wrong_resource_rejected(self):
        c = self.c()
        _, challenge = _pkce()
        authd = c.authorize(challenge=challenge, state="s",
                            resource="https://other.example/mcp")
        # invalid_target is returned as a redirect error (redirect_uri already validated)
        self.assertEqual(authd["query"].get("error"), "invalid_target")
        self.assertNotIn("code", authd["query"])

    def test_consent_denial_redirects_access_denied(self):
        c = self.c()
        _, challenge = _pkce()
        authd = c.authorize(challenge=challenge, state="s", decision="deny")
        self.assertEqual(authd["query"].get("error"), "access_denied")
        self.assertEqual(authd["query"].get("state"), "s")

    def test_revoke_then_reuse_fails(self):
        c, tok, _, _ = self._full_connect("cid")
        access = tok["access_token"]
        istatus, sid, _ = c.rpc(access, "initialize", {"protocolVersion": "2025-03-26"})
        self.assertEqual(istatus, 200)
        status, _, _ = c.post_form("/oauth/revoke",
                                   {"token": access, "token_type_hint": "access_token"})
        self.assertEqual(status, 200)
        rstatus, _, _ = c.rpc(access, "tools/list", session=sid, mid=2)
        self.assertEqual(rstatus, 401)

    # -- 16 refresh / reconnect -----------------------------------------
    def test_refresh_rotation_and_reconnect(self):
        c, tok, _, _ = self._full_connect("cid", scope="resonance offline_access")
        self.assertIn("refresh_token", tok)
        first_refresh = tok["refresh_token"]
        status, _, body = c.token({"grant_type": "refresh_token",
                                   "refresh_token": first_refresh, "client_id": "cid"})
        self.assertEqual(status, 200, body)
        refreshed = json.loads(body)
        self.assertTrue(refreshed["access_token"])
        self.assertNotEqual(refreshed.get("refresh_token"), first_refresh)  # rotated
        # the old refresh token is single-use
        status2, _, _ = c.token({"grant_type": "refresh_token",
                                 "refresh_token": first_refresh, "client_id": "cid"})
        self.assertEqual(status2, 400)
        # the refreshed access token initializes a working MCP session
        istatus, sid, _ = c.rpc(refreshed["access_token"], "initialize",
                                {"protocolVersion": "2025-03-26"})
        self.assertEqual(istatus, 200)

    def test_revoking_refresh_token_cascades_to_its_access_token(self):
        # RFC 7009 §2.1: a client that disconnects hands back its refresh token;
        # the access token issued with it must stop working too (found on the
        # public origin during R17 acceptance: it kept authenticating).
        c, tok, _, _ = self._full_connect("cid", scope="resonance offline_access")
        access, refresh = tok["access_token"], tok["refresh_token"]
        istatus, sid, _ = c.rpc(access, "initialize", {"protocolVersion": "2025-03-26"})
        self.assertEqual(istatus, 200)
        status, _, _ = c.post_form("/oauth/revoke",
                                   {"token": refresh, "token_type_hint": "refresh_token"})
        self.assertEqual(status, 200)
        rstatus, _, _ = c.token({"grant_type": "refresh_token",
                                 "refresh_token": refresh, "client_id": "cid"})
        self.assertEqual(rstatus, 400)
        astatus, _, _ = c.rpc(access, "tools/list", session=sid, mid=2)
        self.assertEqual(astatus, 401)

    def test_no_refresh_without_offline_access(self):
        _, tok, _, _ = self._full_connect("cid", scope="resonance")
        self.assertNotIn("refresh_token", tok)

    # -- login path binds to an existing R12 account --------------------
    def test_login_binds_access_token_to_existing_account(self):
        creds = self.runtime.identity.register("Existing Person")
        c = self.c()
        verifier, challenge = _pkce()
        authd = c.authorize(challenge=challenge, state="s", identity="login",
                            user_id=creds.user_id, recovery_secret=creds.recovery_secret)
        code = authd["query"]["code"]
        status, _, body = c.token({"grant_type": "authorization_code", "code": code,
                                   "code_verifier": verifier, "redirect_uri": REDIRECT,
                                   "client_id": "cid"})
        access = json.loads(body)["access_token"]
        _, sid, _ = c.rpc(access, "initialize", {"protocolVersion": "2025-03-26"})
        _, _, who = c.rpc(access, "tools/call",
                          {"name": "resonance_whoami", "arguments": {}}, session=sid, mid=2)
        self.assertEqual(who["result"]["structuredContent"]["user_id"], creds.user_id)

    def test_bad_recovery_secret_denied(self):
        creds = self.runtime.identity.register("Another Person")
        c = self.c()
        _, challenge = _pkce()
        authd = c.authorize(challenge=challenge, state="s", identity="login",
                            user_id=creds.user_id, recovery_secret="wrong-secret")
        self.assertEqual(authd["query"].get("error"), "access_denied")

    # -- no secret in the consent page ----------------------------------
    def test_consent_page_names_the_client_and_is_styled_without_inline_css(self):
        client_id = self.register_client()
        c = self.c()
        _, challenge = _pkce(b"consent-style-seed-000000000000000001")
        auth = c.authorize(challenge=challenge, state="st", client_id=client_id,
                           resource=self.base + "/mcp", decision="deny")
        page = auth["get_body"]
        self.assertIn("<strong>Test</strong>", page)          # registered client_name
        self.assertIn('href="/oauth/consent.css"', page)
        self.assertNotIn("<style", page)
        # Nothing inline: the page is served under default-src 'self' with no
        # unsafe-inline, so an inline style or script would silently not run.
        # A same-origin src is exactly what that policy allows, and the theme
        # script has to be one -- the person's Light/Dark choice, made on the
        # site, must reach the screen where they decide whether to trust a
        # client. Without it this page follows the OS and contradicts them.
        self.assertNotIn("<script>", page)
        self.assertIn('<script src="/theme.mjs"></script>', page)
        for tag in re.findall(r"<script[^>]*>", page):
            self.assertRegex(tag, r'^<script src="/[^"]+">$', tag)
        status, headers, body = c.get("/oauth/consent.css")
        self.assertEqual(status, 200)
        self.assertTrue(headers.get("Content-Type", "").startswith("text/css"))
        self.assertIn("main.consent", body.decode())
        # A cached sheet with no validator once outlived a fix to it by an
        # hour, and the browser had no way to ask whether it had changed.
        self.assertEqual(headers.get("Cache-Control"), "no-cache")
        etag = headers.get("ETag")
        self.assertTrue(etag and etag.startswith('"'), etag)
        status, headers, body = c.get("/oauth/consent.css",
                                      headers={"If-None-Match": etag})
        self.assertEqual(status, 304)
        self.assertEqual(body, b"")

    def test_consent_page_carries_no_token(self):
        c = self.c()
        _, challenge = _pkce()
        authd = c.authorize(challenge=challenge, state="unique-state-token",
                            decision="deny")  # deny so nothing is issued
        # the rendered consent page must not leak an access token; it only carries
        # the OAuth request parameters back as hidden fields.
        self.assertIn("unique-state-token", authd["get_body"])
        self.assertNotIn("access_token", authd["get_body"])


if __name__ == "__main__":
    unittest.main()


class DurableGrantStoreTests(unittest.TestCase):
    """Codes / refresh grants / client registrations survive a process restart
    when the core is built over the product repository (migration 0005)."""

    def test_refresh_grant_and_client_survive_restart(self):
        import tempfile
        from pathlib import Path
        from src.remote.oauth import RepositoryGrantStore

        with tempfile.TemporaryDirectory() as tmp:
            db = str(Path(tmp) / "grants.sqlite3")
            runtime = build_runtime(db, allowed_origins=frozenset({"http://127.0.0.1"}), seed=False)
            runtime.remote_auth = RepositoryGrantStore(runtime.live.repo)
            httpd = build_httpd("127.0.0.1", 0, runtime=runtime)
            base = f"http://127.0.0.1:{httpd.server_address[1]}"
            threading.Thread(target=httpd.serve_forever, daemon=True).start()
            try:
                c = Client(base)
                req = Request(base + "/oauth/register",
                              data=json.dumps({"redirect_uris": [REDIRECT], "client_name": "T"}).encode(),
                              headers={"Content-Type": "application/json"}, method="POST")
                status, _, body = c._open(req)
                self.assertEqual(status, 201, body)
                client_id = json.loads(body)["client_id"]
                verifier, challenge = _pkce(b"durable-grant-verifier-seed-000001")
                auth = c.authorize(challenge=challenge, state="s1", client_id=client_id,
                                   resource=base + "/mcp", scope="resonance offline_access")
                self.assertEqual(auth["status"], 302, auth)
                status, _, body = c.token({"grant_type": "authorization_code", "code": auth["query"]["code"],
                                           "code_verifier": verifier, "redirect_uri": REDIRECT,
                                           "client_id": client_id, "resource": base + "/mcp"})
                self.assertEqual(status, 200, body)
                tok = json.loads(body)
                self.assertIn("refresh_token", tok)
            finally:
                httpd.shutdown(); httpd.server_close()
            runtime.live.repo.close()

            # "redeploy": a brand-new process over the same database
            runtime2 = build_runtime(db, allowed_origins=frozenset({"https://x"}), seed=False)
            runtime2.remote_auth = RepositoryGrantStore(runtime2.live.repo)
            httpd2 = build_httpd("127.0.0.1", 0, runtime=runtime2)
            base2 = f"http://127.0.0.1:{httpd2.server_address[1]}"
            threading.Thread(target=httpd2.serve_forever, daemon=True).start()
            try:
                c2 = Client(base2)
                status, _, body = c2.token({"grant_type": "refresh_token",
                                            "refresh_token": tok["refresh_token"],
                                            "client_id": client_id})
                self.assertEqual(status, 200, body)  # grant survived the restart
                refreshed = json.loads(body)
                self.assertNotEqual(refreshed["refresh_token"], tok["refresh_token"])  # rotated
                status2, _, _ = c2.token({"grant_type": "refresh_token",
                                          "refresh_token": tok["refresh_token"],
                                          "client_id": client_id})
                self.assertEqual(status2, 400)  # single use, even across processes
                # the registered client is known to the new process too
                verifier, challenge = _pkce(b"durable-grant-verifier-seed-000002")
                auth = c2.authorize(challenge=challenge, state="s2", client_id=client_id,
                                    resource=base2 + "/mcp")
                self.assertEqual(auth["status"], 302, auth)
            finally:
                httpd2.shutdown(); httpd2.server_close()
                runtime2.live.repo.close()
