"""Discriminating-power self-test for the R15B black-box probe (#135).

The probe is only a useful independent oracle if (a) a conformant server
passes it with zero FAILs and (b) each protocol defect it is meant to catch
turns exactly the corresponding step red.  This module provides a small,
self-contained *test double* -- an in-memory OAuth 2.1 authorization server
plus a minimal MCP resource -- with injectable defects, and runs the probe
against it.

The double is test scaffolding, deliberately independent of ``src/remote``;
it is NOT a second Resonance OAuth implementation and must never be imported
from product code.
"""

from __future__ import annotations

import base64
import hashlib
import html
import json
import secrets
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlencode, urlsplit

from tests.e2e.r15b_oauth_probe import Probe, parse_www_authenticate

DEFECTS = ("accept_wrong_verifier", "allow_code_replay", "open_redirect",
           "ignore_resource", "revocation_noop", "leak_token_in_error",
           "skip_consent", "state_dropped", "pkce_optional", "no_challenge_link",
           "caller_identity", "stale_session_served", "shares_on_consent")


def _s256(v: str) -> str:
    return base64.urlsafe_b64encode(hashlib.sha256(v.encode()).digest()).rstrip(b"=").decode()


class _State:
    def __init__(self, defects: set[str]):
        self.defects = defects
        self.clients: dict[str, dict] = {}
        self.codes: dict[str, dict] = {}
        self.access: dict[str, dict] = {}    # token -> {user, resource, refresh}
        self.refresh: dict[str, dict] = {}
        self.sessions: dict[str, str] = {}   # mcp session -> user
        self.pending: dict[str, dict] = {}   # consent txn -> authorize params
        self.lock = threading.Lock()


class _Double(BaseHTTPRequestHandler):
    state: _State
    issuer: str

    def log_message(self, *a):  # silence
        pass

    # -- helpers ------------------------------------------------------------
    def _send(self, status, body: bytes, ctype="application/json", headers=None):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status, obj, headers=None):
        h = {"Cache-Control": "no-store"}
        h.update(headers or {})
        self._send(status, json.dumps(obj).encode(), headers=h)

    def _body(self) -> bytes:
        return self.rfile.read(int(self.headers.get("Content-Length") or 0))

    def _form(self) -> dict[str, str]:
        return {k: v[0] for k, v in parse_qs(self._body().decode()).items()}

    def _oauth_error(self, code, desc, extra=None):
        body = {"error": code, "error_description": desc}
        if extra:
            body.update(extra)
        self._json(400, body)

    @property
    def resource(self) -> str:
        return self.issuer + "/mcp"

    # -- GET -----------------------------------------------------------------
    def do_GET(self):  # noqa: N802
        u = urlsplit(self.path)
        d = self.state.defects
        if u.path == "/.well-known/oauth-protected-resource/mcp" or u.path == "/.well-known/oauth-protected-resource":
            return self._json(200, {"resource": self.resource, "authorization_servers": [self.issuer],
                                    "bearer_methods_supported": ["header"],
                                    "scopes_supported": ["offline_access"]})
        if u.path == "/.well-known/oauth-authorization-server":
            return self._json(200, {
                "issuer": self.issuer,
                "authorization_endpoint": self.issuer + "/oauth/authorize",
                "token_endpoint": self.issuer + "/oauth/token",
                "registration_endpoint": self.issuer + "/oauth/register",
                "revocation_endpoint": self.issuer + "/oauth/revoke",
                "response_types_supported": ["code"],
                "grant_types_supported": ["authorization_code", "refresh_token"],
                "code_challenge_methods_supported": ["S256"],
                "token_endpoint_auth_methods_supported": ["none"],
                "scopes_supported": ["offline_access"],
                "resource_indicators_supported": True})
        if u.path == "/oauth/authorize":
            return self._authorize_get(parse_qs(u.query))
        if u.path == "/mcp":
            return self._json(405, {"error": "method_not_allowed"})
        self._json(404, {"error": "not_found"})

    def _authorize_get(self, q):
        g = lambda k: (q.get(k) or [""])[0]  # noqa: E731
        d = self.state.defects
        client = self.state.clients.get(g("client_id"))
        redirect = g("redirect_uri")
        if client is None or (redirect not in client["redirect_uris"] and "open_redirect" not in d):
            return self._send(400, b"<html><body><h1>invalid client or redirect_uri</h1></body></html>", "text/html")
        if "open_redirect" in d and client is None:
            return self._send(400, b"<html><body>bad client</body></html>", "text/html")
        errors = []
        if g("response_type") != "code":
            errors.append("unsupported_response_type")
        if "pkce_optional" not in d and (not g("code_challenge") or g("code_challenge_method") != "S256"):
            errors.append("invalid_request")
        if g("resource") and g("resource") != self.resource and "ignore_resource" not in d:
            errors.append("invalid_target")
        if errors:
            loc = redirect + ("&" if "?" in redirect else "?") + urlencode({"error": errors[0], "state": g("state")})
            return self._send(302, b"", headers={"Location": loc})
        txn = secrets.token_urlsafe(12)
        self.state.pending[txn] = {"client_id": g("client_id"), "redirect_uri": redirect,
                                   "state": g("state"), "code_challenge": g("code_challenge"),
                                   "resource": g("resource") or self.resource, "scope": g("scope")}
        if "skip_consent" in d:
            return self._issue_code(txn, "guest")
        page = (f"<html><body><h1>Resonance authorization</h1>"
                f"<p>Client {html.escape(g('client_id'))} asks to use your Resonance identity.</p>"
                f"<form method='post' action='/oauth/authorize'>"
                f"<input type='hidden' name='txn' value='{txn}'>"
                f"<input type='radio' name='mode' value='guest' checked> Continue as guest<br>"
                f"<input type='radio' name='mode' value='login'> Sign in<br>"
                f"<input type='text' name='user_id'><input type='password' name='recovery_secret'>"
                f"<button type='submit' name='decision' value='approve'>Approve</button>"
                f"<button type='submit' name='decision' value='deny'>Deny</button>"
                f"</form></body></html>")
        self._send(200, page.encode(), "text/html; charset=utf-8")

    def _issue_code(self, txn, mode):
        p = self.state.pending.pop(txn)
        user = "person-" + secrets.token_hex(4)
        code = secrets.token_urlsafe(24)
        self.state.codes[code] = {**p, "user": user, "expires": time.time() + 300, "used": False}
        q = {"code": code}
        if "state_dropped" not in self.state.defects and p["state"]:
            q["state"] = p["state"]
        loc = p["redirect_uri"] + ("&" if "?" in p["redirect_uri"] else "?") + urlencode(q)
        self._send(302, b"", headers={"Location": loc})

    # -- POST ----------------------------------------------------------------
    def do_POST(self):  # noqa: N802
        u = urlsplit(self.path)
        if u.path == "/oauth/register":
            return self._register()
        if u.path == "/oauth/authorize":
            f = self._form()
            if f.get("txn") not in self.state.pending or f.get("decision") != "approve":
                self.state.pending.pop(f.get("txn", ""), None)
                return self._send(400, b"<html><body>denied</body></html>", "text/html")
            return self._issue_code(f["txn"], f.get("mode", "guest"))
        if u.path == "/oauth/token":
            return self._token(self._form())
        if u.path == "/oauth/revoke":
            f = self._form()
            if "revocation_noop" not in self.state.defects:
                rec = self.state.access.pop(f.get("token", ""), None)
                if rec and rec.get("refresh"):
                    self.state.refresh.pop(rec["refresh"], None)
                rrec = self.state.refresh.pop(f.get("token", ""), None)
                if rrec:
                    self.state.access.pop(rrec.get("access", ""), None)
            return self._json(200, {})
        if u.path == "/mcp":
            return self._mcp()
        self._json(404, {"error": "not_found"})

    def _register(self):
        body = json.loads(self._body() or b"{}")
        cid = "client-" + secrets.token_hex(6)
        self.state.clients[cid] = {"redirect_uris": list(body.get("redirect_uris") or [])}
        self._json(201, {"client_id": cid, "redirect_uris": self.state.clients[cid]["redirect_uris"],
                         "token_endpoint_auth_method": "none"})

    def _token(self, f):
        d = self.state.defects
        gt = f.get("grant_type")
        if gt == "authorization_code":
            rec = self.state.codes.get(f.get("code", ""))
            if rec is None or rec["expires"] < time.time():
                return self._oauth_error("invalid_grant", "unknown or expired code")
            if rec["used"] and "allow_code_replay" not in d:
                return self._oauth_error("invalid_grant", "code already used")
            if rec["redirect_uri"] != f.get("redirect_uri") or rec["client_id"] != f.get("client_id"):
                return self._oauth_error("invalid_grant", "redirect_uri/client mismatch")
            if f.get("resource") and f["resource"] != rec["resource"] and "ignore_resource" not in d:
                return self._oauth_error("invalid_target", "resource mismatch")
            if "accept_wrong_verifier" not in d and (
                    rec["code_challenge"] and _s256(f.get("code_verifier", "")) != rec["code_challenge"]):
                rec["used"] = True   # burn on failure
                extra = {"debug_code": f.get("code")} if "leak_token_in_error" in d else None
                return self._oauth_error("invalid_grant", "PKCE verification failed", extra)
            rec["used"] = True
            user = f.get("user_id") if "caller_identity" in d and f.get("user_id") else rec["user"]
            return self._json(200, self._mint(user, rec["resource"], "offline_access" in (rec.get("scope") or "")))
        if gt == "refresh_token":
            rrec = self.state.refresh.pop(f.get("refresh_token", ""), None)
            if rrec is None:
                return self._oauth_error("invalid_grant", "unknown refresh token")
            self.state.access.pop(rrec["access"], None)
            return self._json(200, self._mint(rrec["user"], rrec["resource"], True))
        self._oauth_error("unsupported_grant_type", gt or "")

    def _mint(self, user, resource, offline):
        tok = secrets.token_urlsafe(32)
        body = {"access_token": tok, "token_type": "Bearer", "expires_in": 3600}
        rec = {"user": user, "resource": resource, "refresh": None}
        if offline:
            r = secrets.token_urlsafe(32)
            self.state.refresh[r] = {"user": user, "resource": resource, "access": tok}
            rec["refresh"] = r
            body["refresh_token"] = r
        self.state.access[tok] = rec
        return body

    def _mcp(self):
        d = self.state.defects
        auth = self.headers.get("Authorization") or ""
        tok = auth[7:] if auth.lower().startswith("bearer ") else ""
        rec = self.state.access.get(tok)
        if rec is None or rec["resource"] != self.resource:
            link = "" if "no_challenge_link" in d else \
                f', resource_metadata="{self.issuer}/.well-known/oauth-protected-resource/mcp"'
            return self._json(401, {"error": "invalid_token"},
                              headers={"WWW-Authenticate": f'Bearer realm="double"{link}'})
        msg = json.loads(self._body() or b"{}")
        method, mid = msg.get("method"), msg.get("id")
        if method == "initialize":
            sid = secrets.token_urlsafe(12)
            self.state.sessions[sid] = rec["user"]
            return self._json(200, {"jsonrpc": "2.0", "id": mid, "result": {
                "protocolVersion": "2025-03-26", "capabilities": {"tools": {}},
                "serverInfo": {"name": "double", "version": "0"}}}, headers={"Mcp-Session-Id": sid})
        if mid is None:
            return self._send(202, b"")
        sid = self.headers.get("Mcp-Session-Id") or ""
        if sid not in self.state.sessions and "stale_session_served" not in d:
            return self._json(404, {"jsonrpc": "2.0", "id": mid, "error": {"code": -32600, "message": "unknown session"}})
        if method == "tools/list":
            return self._json(200, {"jsonrpc": "2.0", "id": mid, "result": {"tools": [
                {"name": "resonance_whoami", "inputSchema": {"type": "object"}}]}})
        if method == "tools/call" and msg.get("params", {}).get("name") == "resonance_whoami":
            owned = [{"session_id": "s1"}] if "shares_on_consent" in d else []
            payload = {"user_id": rec["user"], "owned_sessions": owned}
            return self._json(200, {"jsonrpc": "2.0", "id": mid, "result": {
                "content": [{"type": "text", "text": json.dumps(payload)}],
                "structuredContent": payload, "isError": False}})
        self._json(200, {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": "unknown"}})


def start_double(defects: set[str] | None = None):
    state = _State(set(defects or ()))
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), type("Bound", (_Double,), {"state": state, "issuer": ""}))
    httpd.RequestHandlerClass.issuer = f"http://127.0.0.1:{httpd.server_address[1]}"
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    return httpd, httpd.RequestHandlerClass.issuer


def run_probe(defects=None, **kw):
    httpd, base = start_double(defects)
    try:
        return Probe(base, timeout=10, **kw).run()
    finally:
        httpd.shutdown()
        httpd.server_close()


def failed_ids(report):
    return {s["id"] for s in report["steps"] if s["status"] == "FAIL"}


class ProbeSelfTest(unittest.TestCase):
    def test_conformant_double_passes_with_zero_failures(self):
        rep = run_probe()
        self.assertEqual(rep["verdict"], "PASS", json.dumps(rep, indent=1))
        self.assertEqual(failed_ids(rep), set())
        ids = {s["id"] for s in rep["steps"] if s["status"] == "PASS"}
        for required in ("1", "1b", "2", "3", "3d", "4", "5", "6", "7", "8-10.init", "8-10.tools",
                         "8-10.whoami", "8", "9", "10", "10b", "11", "11b", "12", "12a", "12b",
                         "13a", "13b", "13c", "13d", "E1", "E2", "E5", "E6"):
            self.assertIn(required, ids, required)

    def test_report_never_contains_secret_material(self):
        httpd, base = start_double()
        try:
            probe = Probe(base, timeout=10)
            rep = probe.run()
        finally:
            httpd.shutdown()
            httpd.server_close()
        text = json.dumps(rep)
        for value, kind in probe.redact._secrets:
            self.assertNotIn(value, text, kind)
        self.assertGreaterEqual(len(probe.redact._secrets), 6)

    def test_each_defect_turns_its_step_red(self):
        expectations = {
            "accept_wrong_verifier": {"8"},
            "allow_code_replay": {"9"},
            "open_redirect": {"10"},
            "ignore_resource": {"11", "11b"},
            "revocation_noop": {"12"},
            "leak_token_in_error": {"E5"},
            "skip_consent": {"4"},
            "state_dropped": {"6"},
            "pkce_optional": {"E1"},
            "no_challenge_link": {"1b", "2"},
            "caller_identity": {"E2"},
            "stale_session_served": {"13d"},
            "shares_on_consent": {"E6"},
        }
        for defect, expected in expectations.items():
            with self.subTest(defect=defect):
                rep = run_probe({defect})
                got = failed_ids(rep)
                self.assertTrue(expected <= got, f"{defect}: expected {expected} in failures, got {got}")

    def test_scan_log_flags_leaked_secrets_only(self):
        import os
        import tempfile
        httpd, base = start_double()
        try:
            probe = Probe(base, timeout=10)
            probe.run()
        finally:
            httpd.shutdown()
            httpd.server_close()
        secret = probe.redact._secrets[0][0]
        with tempfile.TemporaryDirectory() as d:
            clean, dirty = os.path.join(d, "clean.log"), os.path.join(d, "dirty.log")
            with open(clean, "w") as fh:
                fh.write("GET /oauth/authorize 200\nPOST /oauth/token 200\n")
            with open(dirty, "w") as fh:
                fh.write(f"DEBUG issued code={secret}\n")
            probe.scan_log(clean)
            probe.scan_log(dirty)
        e7 = [s for s in probe.steps if s.id == "E7"]
        self.assertEqual([s.status for s in e7], ["PASS", "FAIL"])
        self.assertNotIn(secret, json.dumps(probe.report()))

    def test_www_authenticate_parser(self):
        p = parse_www_authenticate('Bearer realm="x", resource_metadata="https://h/.well-known/oauth-protected-resource/mcp", error=invalid_token')
        self.assertEqual(p["resource_metadata"], "https://h/.well-known/oauth-protected-resource/mcp")
        self.assertEqual(p["error"], "invalid_token")
        self.assertEqual(p["realm"], "x")


if __name__ == "__main__":
    unittest.main()
