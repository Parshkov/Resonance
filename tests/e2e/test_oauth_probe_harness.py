"""R15B harness self-test: the black-box probe must (a) pass completely against
a minimal standards-shaped reference server written here, so a later FAIL
against the R15A head is a finding and not a harness bug; (b) fail loudly
against a server that skips the consent page or leaks the code to an
attacker's redirect; (c) import nothing from `src/`."""

from __future__ import annotations

import ast
import base64
import hashlib
import hmac
import json
import secrets
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

from tests.e2e import oauth_probe as op

REPO = Path(__file__).resolve().parents[2]


# --------------------------------------------------------------------------
# reference server (deliberately tiny; NOT the product, NOT R15A)
# --------------------------------------------------------------------------

def _s256(v: str) -> str:
    return base64.urlsafe_b64encode(hashlib.sha256(v.encode()).digest()).rstrip(b"=").decode()


class RefState:
    def __init__(self, *, skip_consent=False, open_redirect=False):
        self.clients: dict[str, list[str]] = {}
        self.pending: dict[str, dict] = {}      # consent txn id -> authorize params
        self.codes: dict[str, dict] = {}
        self.tokens: dict[str, dict] = {}       # access -> {sub, resource}
        self.refresh: dict[str, str] = {}       # refresh -> sub
        self.sessions: dict[str, str] = {}      # mcp session -> access
        self.skip_consent = skip_consent
        self.open_redirect = open_redirect


def make_ref_handler(state: RefState, base_holder: dict):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):  # quiet
            pass

        # helpers
        def _json(self, status, doc, headers=None):
            body = json.dumps(doc).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            for k, v in (headers or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body)

        def _html(self, html):
            body = html.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _redirect(self, url):
            self.send_response(302)
            self.send_header("Location", url)
            self.send_header("Content-Length", "0")
            self.end_headers()

        def _body(self):
            n = int(self.headers.get("Content-Length") or 0)
            return self.rfile.read(n) if n else b""

        @property
        def base(self):
            return base_holder["base"]

        def _issue_code_redirect(self, p):
            code = secrets.token_urlsafe(24)
            state.codes[code] = dict(p, used=False)
            self._redirect(p["redirect_uri"] + "?" + urlencode({"code": code, "state": p["state"]}))

        def do_GET(self):
            u = urlparse(self.path)
            if u.path == "/.well-known/oauth-protected-resource/mcp":
                return self._json(200, {"resource": f"{self.base}/mcp",
                                        "authorization_servers": [self.base],
                                        "scopes_supported": ["resonance"],
                                        "bearer_methods_supported": ["header"]})
            if u.path == "/.well-known/oauth-authorization-server":
                return self._json(200, {
                    "issuer": self.base,
                    "authorization_endpoint": f"{self.base}/oauth/authorize",
                    "token_endpoint": f"{self.base}/oauth/token",
                    "registration_endpoint": f"{self.base}/oauth/register",
                    "revocation_endpoint": f"{self.base}/oauth/revoke",
                    "response_types_supported": ["code"],
                    "grant_types_supported": ["authorization_code", "refresh_token"],
                    "code_challenge_methods_supported": ["S256"],
                    "token_endpoint_auth_methods_supported": ["none"],
                    "scopes_supported": ["resonance"]})
            if u.path == "/oauth/authorize":
                q = {k: v[0] for k, v in parse_qs(u.query).items()}
                allowed = state.clients.get(q.get("client_id", ""))
                if allowed is None:
                    return self._json(400, {"error": "invalid_client"})
                if q.get("redirect_uri") not in allowed and not state.open_redirect:
                    return self._json(400, {"error": "invalid_request",
                                            "error_description": "redirect_uri not registered"})
                if q.get("code_challenge_method") != "S256" or not q.get("code_challenge") or not q.get("state"):
                    return self._json(400, {"error": "invalid_request"})
                if q.get("resource") and q["resource"] != f"{self.base}/mcp":
                    return self._redirect(q["redirect_uri"] + "?" + urlencode(
                        {"error": "invalid_target", "state": q["state"]}))
                if state.skip_consent:
                    return self._issue_code_redirect(q)
                txn = secrets.token_urlsafe(12)
                state.pending[txn] = q
                return self._html(f"""<html><body><h1>Authorize probe client?</h1>
<form method="post" action="/oauth/authorize">
<input type="hidden" name="txn" value="{txn}">
<label><input type="radio" name="identity" value="login"> Sign in</label>
<input type="text" name="user_id"><input type="password" name="recovery_secret">
<label><input type="radio" name="identity" value="guest" checked> Continue as guest</label>
<button type="submit" name="decision" value="deny">Cancel</button>
<button type="submit" name="decision" value="approve">Allow access</button>
</form></body></html>""")
            if u.path == "/mcp":
                return self._json(405, {"error": "use POST"})
            return self._json(404, {"error": "not_found"})

        def do_POST(self):
            u = urlparse(self.path)
            raw = self._body()
            if u.path == "/oauth/register":
                doc = json.loads(raw)
                cid = "cli_" + secrets.token_hex(6)
                state.clients[cid] = list(doc["redirect_uris"])
                return self._json(201, {"client_id": cid, "redirect_uris": doc["redirect_uris"],
                                        "token_endpoint_auth_method": "none"})
            if u.path == "/oauth/authorize":
                f = {k: v[0] for k, v in parse_qs(raw.decode()).items()}
                p = state.pending.pop(f.get("txn", ""), None)
                if p is None:
                    return self._json(400, {"error": "invalid_request"})
                if f.get("decision") != "approve":
                    return self._redirect(p["redirect_uri"] + "?" + urlencode(
                        {"error": "access_denied", "state": p["state"]}))
                p["sub"] = "guest-" + secrets.token_hex(3) if f.get("identity") == "guest" else "user"
                return self._issue_code_redirect(p)
            if u.path == "/oauth/token":
                f = {k: v[0] for k, v in parse_qs(raw.decode()).items()}
                if f.get("grant_type") == "refresh_token":
                    sub = state.refresh.pop(f.get("refresh_token", ""), None)
                    if sub is None:
                        return self._json(400, {"error": "invalid_grant"})
                    return self._issue_tokens(sub)
                if f.get("grant_type") != "authorization_code":
                    return self._json(400, {"error": "unsupported_grant_type"})
                rec = state.codes.pop(f.get("code", ""), None)   # single use, even on failure
                if rec is None:
                    return self._json(400, {"error": "invalid_grant"})
                if rec["redirect_uri"] != f.get("redirect_uri") or rec["client_id"] != f.get("client_id"):
                    return self._json(400, {"error": "invalid_grant", "error_description": "redirect/client"})
                if f.get("resource") and f["resource"] != f"{self.base}/mcp":
                    return self._json(400, {"error": "invalid_target"})
                if not hmac.compare_digest(rec["code_challenge"], _s256(f.get("code_verifier", ""))):
                    return self._json(400, {"error": "invalid_grant", "error_description": "pkce"})
                return self._issue_tokens(rec.get("sub", "guest"))
            if u.path == "/oauth/revoke":
                f = {k: v[0] for k, v in parse_qs(raw.decode()).items()}
                state.tokens.pop(f.get("token", ""), None)
                return self._json(200, {})
            if u.path == "/mcp":
                return self._mcp(raw)
            return self._json(404, {"error": "not_found"})

        def _issue_tokens(self, sub):
            access, refresh = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
            state.tokens[access] = {"sub": sub}
            state.refresh[refresh] = sub
            return self._json(200, {"access_token": access, "token_type": "Bearer",
                                    "expires_in": 3600, "refresh_token": refresh, "scope": "resonance"})

        def _mcp(self, raw):
            auth = self.headers.get("Authorization") or ""
            tok = auth[7:] if auth.startswith("Bearer ") else ""
            if tok not in state.tokens:
                return self._json(401, {"error": "invalid_token"}, {
                    "WWW-Authenticate": f'Bearer realm="ref", error="invalid_token", '
                                        f'resource_metadata="{self.base}/.well-known/oauth-protected-resource/mcp"'})
            msg = json.loads(raw)
            mid, method = msg.get("id"), msg.get("method")
            if method == "initialize":
                sid = secrets.token_urlsafe(16)
                state.sessions[sid] = tok
                return self._json(200, {"jsonrpc": "2.0", "id": mid, "result": {
                    "protocolVersion": "2025-06-18", "capabilities": {"tools": {}},
                    "serverInfo": {"name": "ref", "version": "0"}}}, {"Mcp-Session-Id": sid})
            if mid is None:
                self.send_response(202); self.send_header("Content-Length", "0"); self.end_headers()
                return
            sid = self.headers.get("Mcp-Session-Id")
            if state.sessions.get(sid) != tok:      # session bound to its token
                return self._json(404, {"jsonrpc": "2.0", "id": mid,
                                        "error": {"code": -32600, "message": "unknown session"}})
            if method == "tools/list":
                return self._json(200, {"jsonrpc": "2.0", "id": mid, "result": {"tools": [
                    {"name": "resonance_whoami", "inputSchema": {"type": "object"}}]}})
            if method == "tools/call" and msg["params"]["name"] == "resonance_whoami":
                sub = state.tokens[tok]["sub"]
                doc = {"user_id": sub, "actor_type": "agent"}
                return self._json(200, {"jsonrpc": "2.0", "id": mid, "result": {
                    "content": [{"type": "text", "text": json.dumps(doc)}],
                    "structuredContent": doc, "isError": False}})
            return self._json(200, {"jsonrpc": "2.0", "id": mid,
                                    "error": {"code": -32601, "message": "no"}})
    return H


def start_ref(**kw):
    state = RefState(**kw)
    holder: dict = {}
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), make_ref_handler(state, holder))
    holder["base"] = f"http://127.0.0.1:{httpd.server_address[1]}"
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, holder["base"], state


# --------------------------------------------------------------------------
# tests
# --------------------------------------------------------------------------

class HelperTests(unittest.TestCase):
    def test_www_authenticate_parsing(self):
        p = op.parse_www_authenticate(
            'Bearer realm="resonance", error="invalid_token", '
            'resource_metadata="https://h/.well-known/oauth-protected-resource/mcp", scope=resonance')
        self.assertEqual(p["scheme"], "bearer")
        self.assertEqual(p["resource_metadata"], "https://h/.well-known/oauth-protected-resource/mcp")
        self.assertEqual(p["scope"], "resonance")
        self.assertEqual(op.parse_www_authenticate(None), {})
        self.assertEqual(op.parse_www_authenticate("Bearer")["scheme"], "bearer")

    def test_pkce_pair_is_s256(self):
        v, c = op.pkce_pair()
        self.assertEqual(c, base64.urlsafe_b64encode(hashlib.sha256(v.encode()).digest()).rstrip(b"=").decode())
        self.assertGreaterEqual(len(v), 43)

    def test_form_planning_picks_guest_and_approve_never_deny(self):
        forms = op.parse_forms("""
        <form method="post" action="/a"><input type="hidden" name="t" value="1">
        <input type="radio" name="who" value="login"><input type="radio" name="who" value="guest">
        <input type="text" name="user_id"><input type="password" name="secret">
        <button name="d" value="deny">Cancel</button><button name="d" value="approve">Allow</button></form>""")
        plan = op.plan_form_submission(forms[0], want="guest")
        self.assertEqual(plan["t"], "1")
        self.assertEqual(plan["who"], "guest")
        self.assertEqual(plan["d"], "approve")
        self.assertEqual(plan["user_id"], "")
        self.assertEqual(plan["secret"], "")
        deny_only = op.parse_forms('<form><button name="d" value="cancel">Cancel</button></form>')
        self.assertIsNone(op.plan_form_submission(deny_only[0], want="approve"))

    def test_redaction(self):
        self.assertEqual(op.redact("tok=abcdefghijkl", ["abcdefghijkl"]), "tok=<redacted>")
        self.assertEqual(op.redact("x=short", ["short"]), "x=short")

    def test_probe_imports_nothing_from_src(self):
        tree = ast.parse((REPO / "tests" / "e2e" / "oauth_probe.py").read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    self.assertNotEqual(a.name.split(".")[0], "src")
            elif isinstance(node, ast.ImportFrom) and node.module:
                self.assertNotEqual(node.module.split(".")[0], "src")


class ReferenceServerTests(unittest.TestCase):
    def test_probe_passes_fully_against_compliant_reference(self):
        httpd, base, _ = start_ref()
        try:
            rep = op.Probe(base=base).run()
        finally:
            httpd.shutdown(); httpd.server_close()
        failed = [s for s in rep["steps"] if not s["ok"]]
        self.assertEqual(failed, [], json.dumps(rep, indent=1))
        ids = {s["id"] for s in rep["steps"]}
        for must in ("01_unauth_mcp_401_bearer", "02_protected_resource_metadata",
                     "03_authorization_server_metadata", "04_authorize_shows_explicit_consent_page",
                     "06_state_round_trip_exact", "07_token_exchange", "10_resonance_whoami",
                     "11_wrong_verifier_rejected", "12_wrong_redirect_uri_not_followed",
                     "13_replayed_code_rejected", "14_wrong_resource_rejected",
                     "15_revoke_then_reuse_rejected", "17b_stale_session_rejected_cleanly",
                     "18_no_secret_leak_in_bodies_or_headers"):
            self.assertIn(must, ids)

    def test_probe_report_never_contains_secret_material(self):
        httpd, base, state = start_ref()
        try:
            rep = op.Probe(base=base).run()
        finally:
            httpd.shutdown(); httpd.server_close()
        text = json.dumps(rep)
        for tok in list(state.tokens) + list(state.refresh) + list(state.codes):
            self.assertNotIn(tok, text)

    def test_probe_flags_missing_consent_page(self):
        httpd, base, _ = start_ref(skip_consent=True)
        try:
            rep = op.Probe(base=base).run()
        finally:
            httpd.shutdown(); httpd.server_close()
        by = {s["id"]: s for s in rep["steps"]}
        self.assertFalse(by["04_authorize_shows_explicit_consent_page"]["ok"])
        self.assertFalse(rep["ok"])

    def test_probe_flags_open_redirect(self):
        httpd, base, _ = start_ref(open_redirect=True)
        try:
            rep = op.Probe(base=base).run()
        finally:
            httpd.shutdown(); httpd.server_close()
        by = {s["id"]: s for s in rep["steps"]}
        self.assertFalse(by["12_wrong_redirect_uri_not_followed"]["ok"])
        self.assertIn("redirected_to_attacker=True", by["12_wrong_redirect_uri_not_followed"]["detail"])


if __name__ == "__main__":
    unittest.main()
