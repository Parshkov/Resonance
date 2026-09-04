"""Black-box smoke for the canonical hosted-client onboarding (R15C, #136).

Starts from NOTHING but the resource URL a normal user receives
(`https://<origin>/mcp`) and walks exactly what a hosted MCP client does:

  1. POST /mcp without credentials            -> 401 + WWW-Authenticate resource_metadata
  2. GET  protected-resource metadata          -> authorization_servers[0]
  3. GET  authorization-server metadata        -> authorize / token / register endpoints
  4. POST register (RFC 7591) if advertised    -> client_id
  5. build the authorize URL (PKCE S256 + state + resource)
     - `--auto-consent`: submit the consent form like a browser would (local
       smoke against a test server); otherwise print the URL for a human and
       read the redirected `code` back from stdin
  6. POST token (authorization_code + PKCE)    -> access_token (+ refresh_token)
  7. POST /mcp initialize / tools/list / resonance_whoami with the bearer
  8. negatives: wrong verifier, replayed code, wrong redirect_uri
  9. refresh (if issued) and reconnect

Prints PASS/FAIL per step and never prints tokens, codes or secrets. stdlib only.

    python3 ops/oauth_smoke.py https://resonance-production-cfe3.up.railway.app/mcp
    python3 ops/oauth_smoke.py http://127.0.0.1:8788/mcp --auto-consent
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import secrets
import sys
from html.parser import HTMLParser
from http.cookiejar import CookieJar
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit
from urllib.request import HTTPCookieProcessor, HTTPRedirectHandler, Request, build_opener

REDIRECT_URI = "http://127.0.0.1:8765/callback"  # loopback, never contacted


class _Headers(dict):
    """Case-insensitive header view: an HTTP/2 edge (Railway) lowercases every
    header name, while Python's http.server keeps canonical case."""

    def __init__(self, raw) -> None:
        super().__init__((k.lower(), v) for k, v in raw.items())

    def get(self, key, default=None):  # noqa: D401
        return super().get(str(key).lower(), default)


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D401
        return None


class _FormParser(HTMLParser):
    """Collect the first <form> action/method and its input fields."""

    def __init__(self) -> None:
        super().__init__()
        self.action: str | None = None
        self.method = "post"
        self.fields: dict[str, str] = {}
        self.choices: dict[str, list[str]] = {}
        self._in_form = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "form" and self.action is None:
            self._in_form = True
            self.action = a.get("action") or ""
            self.method = (a.get("method") or "post").lower()
        if self._in_form and tag in {"input", "button"} and a.get("name"):
            kind = (a.get("type") or "text").lower()
            if kind in {"submit", "radio", "button"}:
                self.choices.setdefault(a["name"], []).append(a.get("value") or "")
                if kind == "radio" and "checked" in a:
                    self.fields[a["name"]] = a.get("value") or ""
            elif kind == "checkbox":
                if "checked" in a:
                    self.fields[a["name"]] = a.get("value") or "on"
            else:
                self.fields[a["name"]] = a.get("value") or ""

    def handle_endtag(self, tag):
        if tag == "form":
            self._in_form = False


class Smoke:
    def __init__(self, resource: str, *, auto_consent: bool, verbose: bool) -> None:
        self.resource = resource.rstrip("/")
        self.origin = "{0.scheme}://{0.netloc}".format(urlsplit(self.resource))
        self.auto_consent = auto_consent
        self.verbose = verbose
        self.jar = CookieJar()
        self.opener = build_opener(_NoRedirect(), HTTPCookieProcessor(self.jar))
        self.results: list[tuple[str, bool, str]] = []
        self.meta: dict = {}
        self.client_id: str | None = None
        self.access_token: str | None = None
        self.refresh_token: str | None = None

    # -- plumbing ---------------------------------------------------------
    def _req(self, url: str, *, method="GET", data: bytes | None = None,
             headers: dict | None = None):
        req = Request(url, data=data, method=method, headers=headers or {})
        try:
            with self.opener.open(req, timeout=20) as r:
                return r.status, _Headers(r.headers), r.read()
        except HTTPError as e:
            return e.code, _Headers(e.headers), e.read()

    def _json(self, url, **kw):
        status, headers, body = self._req(url, **kw)
        try:
            payload = json.loads(body) if body else {}
        except json.JSONDecodeError:
            payload = {"_raw": body[:200].decode("utf-8", "replace")}
        return status, headers, payload

    def _rpc(self, method: str, params=None, *, mid: int, bearer: str | None):
        headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
        if bearer:
            headers["Authorization"] = f"Bearer {bearer}"
        body = json.dumps({"jsonrpc": "2.0", "id": mid, "method": method, "params": params or {}}).encode()
        return self._json(self.resource, method="POST", data=body, headers=headers)

    def ok(self, step: str, cond: bool, detail: str = "") -> bool:
        self.results.append((step, bool(cond), detail))
        print(f"[{'PASS' if cond else 'FAIL'}] {step}" + (f" — {detail}" if detail and (self.verbose or not cond) else ""))
        return bool(cond)

    # -- steps -----------------------------------------------------------------
    def run(self) -> int:
        # 1. unauthenticated resource
        status, headers, payload = self._rpc("ping", mid=1, bearer=None)
        www = headers.get("WWW-Authenticate", "")
        m = re.search(r'resource_metadata="([^"]+)"', www)
        self.ok("1 unauthenticated /mcp is 401", status == 401, f"status={status}")
        if not self.ok("1 challenge carries resource_metadata", bool(m), www[:160]):
            return self.finish()
        prm_url = m.group(1)

        # 2. protected-resource metadata
        status, _, prm = self._json(prm_url)
        self.ok("2 protected-resource metadata 200", status == 200, f"status={status}")
        self.ok("2 resource matches /mcp URL", prm.get("resource") == self.resource,
                f"resource={prm.get('resource')!r} expected {self.resource!r}")
        servers = prm.get("authorization_servers") or []
        if not self.ok("2 authorization_servers present", bool(servers), json.dumps(prm)[:200]):
            return self.finish()
        issuer = servers[0].rstrip("/")

        # 3. authorization-server metadata (RFC 8414 path first, OIDC path second)
        asm = None
        for candidate in (f"{issuer}/.well-known/oauth-authorization-server",
                          f"{issuer}/.well-known/openid-configuration"):
            status, _, doc = self._json(candidate)
            if status == 200 and doc.get("authorization_endpoint"):
                asm = doc
                break
        if not self.ok("3 authorization-server metadata discoverable", asm is not None, issuer):
            return self.finish()
        self.meta = asm
        self.ok("3 issuer matches", asm.get("issuer", "").rstrip("/") == issuer,
                f"issuer={asm.get('issuer')!r}")
        self.ok("3 S256 advertised", "S256" in (asm.get("code_challenge_methods_supported") or []),
                str(asm.get("code_challenge_methods_supported")))
        self.ok("3 absolute https endpoints" if issuer.startswith("https") else "3 absolute endpoints",
                all(str(asm.get(k, "")).startswith(issuer) for k in ("authorization_endpoint", "token_endpoint")),
                f"authorize={asm.get('authorization_endpoint')} token={asm.get('token_endpoint')}")

        # 4. dynamic client registration
        reg = asm.get("registration_endpoint")
        if reg:
            status, _, client = self._json(reg, method="POST", headers={"Content-Type": "application/json"},
                                           data=json.dumps({
                                               "client_name": "resonance-oauth-smoke",
                                               "redirect_uris": [REDIRECT_URI],
                                               "grant_types": ["authorization_code", "refresh_token"],
                                               "response_types": ["code"],
                                               "token_endpoint_auth_method": "none",
                                           }).encode())
            self.ok("4 dynamic registration 201/200", status in (200, 201), f"status={status}")
            self.client_id = client.get("client_id")
            self.ok("4 client_id issued", bool(self.client_id))
        else:
            self.client_id = "resonance-oauth-smoke"
            self.ok("4 registration endpoint advertised", False,
                    "none advertised — hosted clients need RFC 7591 or a public client_id policy")

        # 5. authorize (the real code, exchanged first: a conformant server burns
        #    a code on ANY failed exchange attempt, so negatives get their own codes)
        code = self._authorize()
        if not code:
            return self.finish()
        status, _, tok = self._token({"grant_type": "authorization_code", "code": code,
                                      "code_verifier": self._verifier, "redirect_uri": REDIRECT_URI,
                                      "client_id": self.client_id, "resource": self.resource})
        if not self.ok("6 token exchange 200", status == 200 and tok.get("access_token"),
                       f"status={status} error={tok.get('error')} {tok.get('error_description', '')}"):
            return self.finish()
        self.access_token = tok["access_token"]
        self.refresh_token = tok.get("refresh_token")
        self.ok("6 token_type Bearer", str(tok.get("token_type", "")).lower() == "bearer")
        status, _, tok2 = self._token({"grant_type": "authorization_code", "code": code,
                                       "code_verifier": self._verifier, "redirect_uri": REDIRECT_URI,
                                       "client_id": self.client_id, "resource": self.resource})
        self.ok("8 replayed code rejected", status == 400, f"status={status} error={tok2.get('error')}")
        # fresh codes for the remaining negatives (each failed attempt burns its code)
        bad = self._authorize(quiet=True)
        if bad:
            status, _, tok3 = self._token({"grant_type": "authorization_code", "code": bad,
                                           "code_verifier": "wrong-" + self._verifier,
                                           "redirect_uri": REDIRECT_URI, "client_id": self.client_id,
                                           "resource": self.resource})
            self.ok("8 wrong verifier rejected", status == 400 and tok3.get("error") in ("invalid_grant", "invalid_request"),
                    f"status={status} error={tok3.get('error')}")
        bad = self._authorize(quiet=True)
        if bad:
            status, _, tok4 = self._token({"grant_type": "authorization_code", "code": bad,
                                           "code_verifier": self._verifier,
                                           "redirect_uri": "http://evil.example/cb", "client_id": self.client_id,
                                           "resource": self.resource})
            self.ok("8 wrong redirect_uri rejected", status == 400, f"status={status} error={tok4.get('error')}")

        # 7. MCP with the bearer
        status, headers, init = self._rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                                          "clientInfo": {"name": "oauth-smoke", "version": "0"}},
                                          mid=2, bearer=self.access_token)
        self.ok("7 initialize 200", status == 200 and "result" in init, f"status={status} {json.dumps(init)[:120]}")
        status, _, tools = self._rpc("tools/list", mid=3, bearer=self.access_token)
        names = [t.get("name") for t in (tools.get("result") or {}).get("tools", [])]
        self.ok("7 tools/list includes resonance_whoami", "resonance_whoami" in names, ", ".join(names)[:200])
        status, _, who = self._rpc("tools/call", {"name": "resonance_whoami", "arguments": {}}, mid=4,
                                   bearer=self.access_token)
        sc = ((who.get("result") or {}).get("structuredContent") or {})
        self.ok("7 resonance_whoami returns an account", status == 200 and bool(sc.get("user_id")),
                f"user_id={'person-…' if sc.get('user_id') else None} label={sc.get('display_label')}")

        # 9. refresh + reconnect
        if self.refresh_token:
            status, _, ref = self._token({"grant_type": "refresh_token", "refresh_token": self.refresh_token,
                                          "client_id": self.client_id, "resource": self.resource})
            self.ok("9 refresh_token grant 200", status == 200 and ref.get("access_token"),
                    f"status={status} error={ref.get('error')}")
            if ref.get("access_token"):
                status, _, who2 = self._rpc("tools/call", {"name": "resonance_whoami", "arguments": {}}, mid=5,
                                            bearer=ref["access_token"])
                sc2 = ((who2.get("result") or {}).get("structuredContent") or {})
                self.ok("9 refreshed token maps to the same account", sc2.get("user_id") == sc.get("user_id"))
        else:
            self.ok("9 refresh token issued", False, "no refresh_token in token response (offline_access?)")
        return self.finish()

    # -- helpers -----------------------------------------------------------------
    @staticmethod
    def _pkce_pair():
        verifier = base64.urlsafe_b64encode(secrets.token_bytes(48)).rstrip(b"=").decode()
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
        return verifier, challenge

    def _token(self, form: dict):
        return self._json(self.meta["token_endpoint"], method="POST",
                          headers={"Content-Type": "application/x-www-form-urlencoded"},
                          data=urlencode(form).encode())

    def _authorize(self, quiet: bool = False) -> str | None:
        """Run one authorize round-trip and return the code. `quiet` (used for the
        negative cases that need their own fresh code) records nothing."""
        ok = (lambda *a, **k: bool(a[1])) if quiet else self.ok
        self._verifier, challenge = self._pkce_pair()
        state = secrets.token_urlsafe(16)
        scope = "offline_access" if "offline_access" in (self.meta.get("scopes_supported") or []) else ""
        params = {"response_type": "code", "client_id": self.client_id, "redirect_uri": REDIRECT_URI,
                  "code_challenge": challenge, "code_challenge_method": "S256", "state": state,
                  "resource": self.resource}
        if scope:
            params["scope"] = scope
        url = self.meta["authorization_endpoint"] + "?" + urlencode(params)
        status, headers, body = self._req(url)
        ok("5 GET authorize renders a page (200)", status == 200, f"status={status}")
        if status != 200:
            return None
        if not self.auto_consent:
            print("\nOpen this URL in a browser, sign in / continue as guest, consent, then paste the\n"
                  "redirected callback URL (it will fail to load — that is fine):\n  " + url)
            cb = input("callback URL> ").strip()
            q = parse_qs(urlsplit(cb).query)
        else:
            parser = _FormParser()
            parser.feed(body.decode("utf-8", "replace"))
            if not ok("5 consent form present", parser.action is not None):
                return None
            fields = dict(parser.fields)
            # pick an approve/guest-style submit if the form offers choices
            for name, values in parser.choices.items():
                pick = next((v for v in values if re.search(r"allow|approve|guest|continue|consent", v, re.I)), values[0])
                fields[name] = pick
            action = urljoin(url, parser.action or "")
            status, headers, body = self._req(action, method=parser.method.upper(),
                                              data=urlencode(fields).encode(),
                                              headers={"Content-Type": "application/x-www-form-urlencoded",
                                                       "Origin": self.origin, "Referer": url})
            loc = headers.get("Location", "")
            redacted = re.sub(r"code=[^&]+", "code=<redacted>", loc)
            ok("5 consent POST redirects (302/303)", status in (302, 303), f"status={status}")
            ok("5 redirect goes to the exact redirect_uri", loc.startswith(REDIRECT_URI + "?"), redacted[:120])
            q = parse_qs(urlsplit(loc).query)
        code = (q.get("code") or [None])[0]
        ok("5 code returned", bool(code))
        ok("5 exact state round-trip", (q.get("state") or [None])[0] == state)
        return code

    def finish(self) -> int:
        failed = [r for r in self.results if not r[1]]
        print(f"\n{len(self.results) - len(failed)}/{len(self.results)} checks passed"
              + (f"; FAILED: {', '.join(r[0] for r in failed)}" if failed else ""))
        return 1 if failed else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("resource", help="the canonical MCP URL, e.g. https://host/mcp")
    ap.add_argument("--auto-consent", action="store_true",
                    help="submit the consent form automatically (local smoke only)")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()
    return Smoke(args.resource, auto_consent=args.auto_consent, verbose=args.verbose).run()


if __name__ == "__main__":
    sys.exit(main())
