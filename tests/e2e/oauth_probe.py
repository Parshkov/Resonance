"""R15B black-box probe: hosted-client-style OAuth + MCP onboarding.

Independent of the R15A implementation and of its tests: this script imports
nothing from `src/` and knows nothing about the server except one base URL.
It behaves like a hosted MCP client that was handed only

    https://<host>/mcp

and must connect through ordinary authorization: unauthenticated challenge →
protected-resource metadata → authorization-server metadata → (dynamic client
registration if advertised) → browser authorize/consent → redirect with
code+state → token exchange → MCP initialize / tools/list / resonance_whoami,
followed by the negative cases the #135 lane requires (wrong verifier, replayed
code, wrong redirect_uri, wrong resource/audience, revoke-then-reuse,
reconnect/stale-session recovery) and a token-leak scan over everything the
server sent back.

Every step records PASS/FAIL with a short redacted detail. Access tokens,
refresh tokens, authorization codes and recovery secrets are never printed.

Usage:

    python3 -m tests.e2e.oauth_probe --base https://host [--json report.json]

Exit status 0 iff every step passed. stdlib only.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import http.cookiejar
import json
import re
import secrets
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Any

PROBE_VERSION = "resonance-oauth-probe/0.1"
DEFAULT_REDIRECT = "https://probe.invalid/oauth/callback"
WRONG_REDIRECT = "https://attacker.invalid/steal"
MCP_PROTOCOL = "2025-06-18"
TIMEOUT = 15

# Heuristics for driving an unknown consent page. A hosted client never sees
# this page (a human does); the probe stands in for the human and must pick
# "continue as guest" and "approve/allow" without knowing the markup.
GUEST_WORDS = ("guest", "continue", "anonymous", "pseudonym", "skip")
APPROVE_WORDS = ("approve", "allow", "authorize", "authorise", "consent", "grant", "accept", "yes")
DENY_WORDS = ("deny", "cancel", "reject", "refuse", "decline", "no", "back", "logout")


# --------------------------------------------------------------------------
# small pure helpers (unit-tested separately)
# --------------------------------------------------------------------------

def pkce_pair() -> tuple[str, str]:
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(48)).rstrip(b"=").decode()
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode("ascii")).digest()).rstrip(b"=").decode()
    return verifier, challenge


def parse_www_authenticate(header: str | None) -> dict[str, str]:
    """`Bearer realm="x", resource_metadata="https://..."` -> params dict.

    Scheme is lower-cased under key `scheme`. Unquoted and quoted values are
    both accepted; malformed input yields whatever parsed."""
    out: dict[str, str] = {}
    if not header:
        return out
    scheme, _, rest = header.strip().partition(" ")
    out["scheme"] = scheme.lower()
    for m in re.finditer(r'([A-Za-z0-9_\-]+)\s*=\s*(?:"([^"]*)"|([^,\s]+))', rest):
        out[m.group(1).lower()] = m.group(2) if m.group(2) is not None else m.group(3)
    return out


class _FormParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.forms: list[dict[str, Any]] = []
        self._cur: dict[str, Any] | None = None
        self._button: dict[str, Any] | None = None

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v if v is not None else "") for k, v in attrs}
        if tag == "form":
            self._cur = {"action": a.get("action", ""), "method": a.get("method", "get").lower(),
                         "fields": [], "submits": []}
            self.forms.append(self._cur)
            return
        if self._cur is None:
            return
        if tag == "input":
            typ = a.get("type", "text").lower()
            item = {"name": a.get("name", ""), "value": a.get("value", ""), "type": typ,
                    "checked": "checked" in a}
            if typ in ("submit", "image"):
                self._cur["submits"].append(item)
            else:
                self._cur["fields"].append(item)
        elif tag == "button":
            typ = a.get("type", "submit").lower()
            self._button = {"name": a.get("name", ""), "value": a.get("value", ""),
                            "type": typ, "text": ""}
            if typ == "submit":
                self._cur["submits"].append(self._button)
        elif tag in ("select", "textarea"):
            self._cur["fields"].append({"name": a.get("name", ""), "value": "",
                                        "type": tag, "checked": False})

    def handle_data(self, data):
        if self._button is not None:
            self._button["text"] += data

    def handle_endtag(self, tag):
        if tag == "form":
            self._cur = None
        elif tag == "button":
            self._button = None


def parse_forms(html: str) -> list[dict[str, Any]]:
    p = _FormParser()
    p.feed(html)
    return p.forms


def _words(*parts: str) -> str:
    return " ".join(p.lower() for p in parts if p)


def plan_form_submission(form: dict[str, Any], *, want: str) -> dict[str, str] | None:
    """Fill an unknown authorize/consent form the way a human clicking
    "continue as guest" / "approve" would. `want` is "guest" or "approve".
    Returns the field dict to POST, or None if the form offers no such action."""
    words = GUEST_WORDS if want == "guest" else APPROVE_WORDS
    data: dict[str, str] = {}
    for f in form["fields"]:
        if not f["name"]:
            continue
        typ = f["type"]
        if typ == "hidden":
            data[f["name"]] = f["value"]
        elif typ in ("radio", "checkbox"):
            label = _words(f["name"], f["value"])
            positive = any(w in label for w in words) or (
                want == "approve" and any(w in label for w in ("consent", "agree", "confirm", "approve")))
            negative = any(w in label for w in DENY_WORDS)
            if positive and not negative:
                data[f["name"]] = f["value"] or "on"
            elif typ == "radio" and f["checked"] and f["name"] not in data:
                data[f["name"]] = f["value"]
        elif typ in ("text", "password", "email", "textarea", "select", "search", "url"):
            # Leave login credentials empty: the probe never asserts an identity.
            data.setdefault(f["name"], "")
    def _label(s):
        return _words(s.get("name", ""), s.get("value", ""), s.get("text", ""))

    def _pick(word_set):
        for s in form["submits"]:
            label = _label(s)
            if any(w in label for w in word_set) and not any(w in label for w in DENY_WORDS):
                return s
        return None

    positive_choice = any(any(w in _words(k, v) for w in words) for k, v in data.items())
    chosen = _pick(words) or _pick(APPROVE_WORDS)
    if chosen is None and (positive_choice or want == "approve"):
        # No labelled button: take the only non-deny submit, if there is exactly one.
        rest = [s for s in form["submits"] if not any(w in _label(s) for w in DENY_WORDS)]
        if len(rest) == 1:
            chosen = rest[0]
    if chosen is None:
        return None
    if chosen.get("name"):
        data[chosen["name"]] = chosen.get("value", "")
    return data


def redact(text: str, secrets_: list[str]) -> str:
    for s in secrets_:
        if s and len(s) >= 8:
            text = text.replace(s, "<redacted>")
    return text


# --------------------------------------------------------------------------
# HTTP plumbing
# --------------------------------------------------------------------------

@dataclass
class Response:
    status: int
    headers: dict[str, str]
    body: bytes
    url: str

    def json(self) -> Any:
        return json.loads(self.body.decode("utf-8"))

    @property
    def text(self) -> str:
        return self.body.decode("utf-8", "replace")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Http:
    """Cookie-aware client that never follows redirects (we must inspect them)
    and records every response for the leak scan."""

    def __init__(self) -> None:
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            _NoRedirect(), urllib.request.HTTPCookieProcessor(self.jar))
        self.observed: list[Response] = []

    def request(self, method: str, url: str, *, headers: dict[str, str] | None = None,
                body: bytes | None = None) -> Response:
        req = urllib.request.Request(url, data=body, method=method, headers=headers or {})
        try:
            with self.opener.open(req, timeout=TIMEOUT) as r:
                resp = Response(r.status, {k.lower(): v for k, v in r.headers.items()},
                                r.read(), r.geturl())
        except urllib.error.HTTPError as e:
            resp = Response(e.code, {k.lower(): v for k, v in e.headers.items()},
                            e.read(), url)
        self.observed.append(resp)
        return resp

    def get(self, url: str, **kw) -> Response:
        return self.request("GET", url, **kw)

    def post_form(self, url: str, fields: dict[str, str], **kw) -> Response:
        headers = {"Content-Type": "application/x-www-form-urlencoded",
                   **(kw.pop("headers", None) or {})}
        return self.request("POST", url, headers=headers,
                            body=urllib.parse.urlencode(fields).encode(), **kw)

    def post_json(self, url: str, payload: Any, **kw) -> Response:
        headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream",
                   **(kw.pop("headers", None) or {})}
        return self.request("POST", url, headers=headers,
                            body=json.dumps(payload).encode(), **kw)


# --------------------------------------------------------------------------
# the probe
# --------------------------------------------------------------------------

@dataclass
class Step:
    id: str
    ok: bool
    detail: str


@dataclass
class Probe:
    base: str
    redirect_uri: str = DEFAULT_REDIRECT
    client_id: str | None = None
    steps: list[Step] = field(default_factory=list)
    secrets_: list[str] = field(default_factory=list)
    http: Http = field(default_factory=Http)
    prm: dict[str, Any] = field(default_factory=dict)
    asm: dict[str, Any] = field(default_factory=dict)
    resource: str = ""
    scope: str = ""

    # -- bookkeeping ---------------------------------------------------
    @property
    def mcp_url(self) -> str:
        return self.base.rstrip("/") + "/mcp"

    def _rec(self, sid: str, ok: bool, detail: str = "") -> bool:
        self.steps.append(Step(sid, bool(ok), redact(detail, self.secrets_)[:400]))
        return bool(ok)

    def _secret(self, value: Any) -> None:
        if isinstance(value, str) and value:
            self.secrets_.append(value)

    # -- step 1: unauthenticated /mcp --------------------------------------
    def step_unauth(self) -> bool:
        r = self.http.post_json(self.mcp_url, {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                                               "params": {"protocolVersion": MCP_PROTOCOL,
                                                          "capabilities": {},
                                                          "clientInfo": {"name": PROBE_VERSION,
                                                                         "version": "0.1"}}})
        wa = parse_www_authenticate(r.headers.get("www-authenticate"))
        ok = r.status == 401 and wa.get("scheme") == "bearer"
        self._rec("01_unauth_mcp_401_bearer", ok, f"status={r.status} www-authenticate={wa}")
        has_rm = bool(wa.get("resource_metadata"))
        self._rec("01b_challenge_has_resource_metadata", has_rm,
                  wa.get("resource_metadata", "<absent>"))
        self._rm_url = wa.get("resource_metadata")
        return ok

    # -- step 2: protected resource metadata --------------------------------
    def step_prm(self) -> bool:
        candidates = []
        if getattr(self, "_rm_url", None):
            candidates.append(self._rm_url)
        b = self.base.rstrip("/")
        candidates += [f"{b}/.well-known/oauth-protected-resource/mcp",
                       f"{b}/.well-known/oauth-protected-resource"]
        for url in candidates:
            r = self.http.get(url, headers={"Accept": "application/json"})
            if r.status == 200:
                try:
                    doc = r.json()
                except Exception:  # noqa: BLE001
                    continue
                self.prm = doc
                self.resource = str(doc.get("resource", ""))
                servers = doc.get("authorization_servers") or []
                ok = (self.resource.rstrip("/") == self.mcp_url.rstrip("/")
                      and isinstance(servers, list) and len(servers) >= 1)
                self._rec("02_protected_resource_metadata", ok,
                          f"url={url} resource={self.resource} authorization_servers={servers}")
                self._rec("02b_prm_from_challenge_url", url == getattr(self, "_rm_url", None),
                          "resource_metadata URL in the challenge resolved" if url == self._rm_url
                          else "fell back to a well-known path; challenge URL missing/unusable")
                return ok
        return self._rec("02_protected_resource_metadata", False,
                         "no protected-resource metadata at challenge URL or well-known paths")

    # -- step 3: authorization server metadata --------------------------------
    def step_asm(self) -> bool:
        servers = self.prm.get("authorization_servers") or [self.base]
        issuer = str(servers[0]).rstrip("/")
        u = urllib.parse.urlparse(issuer)
        candidates = [f"{issuer}/.well-known/oauth-authorization-server"]
        if u.path and u.path != "/":
            candidates.append(f"{u.scheme}://{u.netloc}/.well-known/oauth-authorization-server{u.path}")
        candidates.append(f"{issuer}/.well-known/openid-configuration")
        for url in candidates:
            r = self.http.get(url, headers={"Accept": "application/json"})
            if r.status != 200:
                continue
            try:
                doc = r.json()
            except Exception:  # noqa: BLE001
                continue
            self.asm = doc
            problems = []
            if str(doc.get("issuer", "")).rstrip("/") != issuer:
                problems.append(f"issuer mismatch {doc.get('issuer')!r} != {issuer!r}")
            for k in ("authorization_endpoint", "token_endpoint"):
                if not str(doc.get(k, "")).startswith("http"):
                    problems.append(f"{k} missing")
            if "S256" not in (doc.get("code_challenge_methods_supported") or []):
                problems.append("S256 not advertised")
            if "code" not in (doc.get("response_types_supported") or []):
                problems.append("response_type code not advertised")
            if "authorization_code" not in (doc.get("grant_types_supported") or ["authorization_code", "implicit"]):
                problems.append("authorization_code grant not advertised")
            scopes = doc.get("scopes_supported") or self.prm.get("scopes_supported") or []
            self.scope = " ".join(str(s) for s in scopes)
            self._rec("03_authorization_server_metadata", not problems,
                      f"url={url} " + ("; ".join(problems) if problems else
                                        f"endpoints ok; grants={doc.get('grant_types_supported')} "
                                        f"scopes={scopes} registration="
                                        f"{'yes' if doc.get('registration_endpoint') else 'no'} "
                                        f"revocation={'yes' if doc.get('revocation_endpoint') else 'no'}"))
            return not problems
        return self._rec("03_authorization_server_metadata", False,
                         f"no AS metadata for issuer {issuer}")

    # -- step 3b: client registration (RFC 7591) if advertised ------------------
    def step_register(self) -> bool:
        reg = self.asm.get("registration_endpoint")
        if not reg:
            if self.client_id:
                return self._rec("03b_client_registration", True,
                                 "no registration endpoint; using operator-supplied client_id")
            self.client_id = "resonance-oauth-probe"
            return self._rec("03b_client_registration", True,
                             "no registration endpoint advertised; using an arbitrary public client_id "
                             "(server must then accept unregistered public clients with exact redirect_uri)")
        r = self.http.post_json(reg, {
            "client_name": "Resonance OAuth probe (R15B)",
            "redirect_uris": [self.redirect_uri],
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
            "token_endpoint_auth_method": "none"})
        ok = r.status in (200, 201)
        cid = None
        if ok:
            try:
                doc = r.json()
                cid = doc.get("client_id")
                if doc.get("client_secret"):
                    self._secret(doc["client_secret"])
                ok = bool(cid) and self.redirect_uri in (doc.get("redirect_uris") or [self.redirect_uri])
            except Exception:  # noqa: BLE001
                ok = False
        self.client_id = cid or self.client_id or "resonance-oauth-probe"
        return self._rec("03b_client_registration", ok, f"status={r.status} client_id={'yes' if cid else 'no'}")

    # -- authorize round (browser stand-in) -----------------------------------
    def authorize_round(self, *, redirect_uri: str | None = None, resource: str | None = None,
                        want_error: bool = False, label: str = "") -> dict[str, Any]:
        """Drive GET authorize → consent page → POST until a redirect back to
        the client. Returns dict(code, state, verifier, redirect_uri, resource,
        location, error, status, hops)."""
        redirect_uri = redirect_uri or self.redirect_uri
        resource = self.resource if resource is None else resource
        verifier, challenge = pkce_pair()
        state = secrets.token_urlsafe(24)
        self._secret(verifier)
        params = {"response_type": "code", "client_id": self.client_id or "",
                  "redirect_uri": redirect_uri, "code_challenge": challenge,
                  "code_challenge_method": "S256", "state": state}
        if resource:
            params["resource"] = resource
        if self.scope:
            params["scope"] = self.scope
        url = self.asm["authorization_endpoint"] + "?" + urllib.parse.urlencode(params)
        out: dict[str, Any] = {"verifier": verifier, "state": state, "redirect_uri": redirect_uri,
                               "resource": resource, "code": None, "error": None, "hops": 0,
                               "consent_page_seen": False, "location": None, "status": None}
        r = self.http.get(url, headers={"Accept": "text/html"})
        out["status"] = r.status
        for _ in range(5):
            if r.status in (301, 302, 303, 307):
                loc = r.headers.get("location", "")
                out["location"] = loc
                q = urllib.parse.parse_qs(urllib.parse.urlparse(loc).query)
                if loc.split("?")[0] == redirect_uri.split("?")[0]:
                    out["code"] = (q.get("code") or [None])[0]
                    out["returned_state"] = (q.get("state") or [None])[0]
                    out["error"] = (q.get("error") or [None])[0]
                    self._secret(out["code"])
                    return out
                # server-internal redirect (e.g. to a login page): follow it
                nxt = urllib.parse.urljoin(r.url, loc)
                r = self.http.get(nxt, headers={"Accept": "text/html"})
                out["hops"] += 1
                out["status"] = r.status
                continue
            if r.status != 200:
                try:
                    out["error"] = r.json().get("error") or f"http_{r.status}"
                except Exception:  # noqa: BLE001
                    out["error"] = f"http_{r.status}"
                return out
            out["consent_page_seen"] = True
            forms = parse_forms(r.text)
            plan = None
            for want in ("guest", "approve"):
                for form in forms:
                    data = plan_form_submission(form, want=want)
                    if data is not None:
                        plan = (form, data)
                        break
                if plan:
                    break
            if plan is None:
                out["error"] = "consent_page_not_drivable"
                out["page_excerpt"] = re.sub(r"\s+", " ", r.text)[:300]
                return out
            form, data = plan
            action = urllib.parse.urljoin(r.url, form["action"] or r.url)
            if form["method"] == "get":
                r = self.http.get(action + "?" + urllib.parse.urlencode(data), headers={"Accept": "text/html"})
            else:
                r = self.http.post_form(action, data, headers={"Accept": "text/html",
                                                                 "Origin": self.base.rstrip("/"),
                                                                 "Referer": r.url})
            out["hops"] += 1
            out["status"] = r.status
        out["error"] = out["error"] or "too_many_hops"
        return out

    def token_request(self, fields: dict[str, str]) -> Response:
        return self.http.post_form(self.asm["token_endpoint"], fields,
                                   headers={"Accept": "application/json"})

    def exchange(self, rnd: dict[str, Any], *, verifier: str | None = None,
                 redirect_uri: str | None = None, resource: str | None = None) -> Response:
        fields = {"grant_type": "authorization_code", "code": rnd["code"] or "",
                  "redirect_uri": redirect_uri or rnd["redirect_uri"],
                  "client_id": self.client_id or "",
                  "code_verifier": verifier or rnd["verifier"]}
        res = rnd["resource"] if resource is None else resource
        if res:
            fields["resource"] = res
        r = self.token_request(fields)
        if r.status == 200:
            try:
                doc = r.json()
                self._secret(doc.get("access_token"))
                self._secret(doc.get("refresh_token"))
            except Exception:  # noqa: BLE001
                pass
        return r

    # -- MCP ----------------------------------------------------------------
    def mcp(self, token: str | None, method: str, params: Any = None, *, session: str | None = None,
            mid: int = 1) -> tuple[Response, Any]:
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        if session:
            headers["Mcp-Session-Id"] = session
        msg: dict[str, Any] = {"jsonrpc": "2.0", "id": mid, "method": method}
        if params is not None:
            msg["params"] = params
        r = self.http.post_json(self.mcp_url, msg, headers=headers)
        doc = None
        if r.body:
            try:
                doc = r.json()
            except Exception:  # noqa: BLE001
                doc = None
        return r, doc

    def mcp_initialize(self, token: str) -> tuple[Response, Any, str | None]:
        r, doc = self.mcp(token, "initialize", {"protocolVersion": MCP_PROTOCOL, "capabilities": {},
                                                "clientInfo": {"name": PROBE_VERSION, "version": "0.1"}})
        sid = r.headers.get("mcp-session-id")
        if r.status == 200 and sid:
            # A well-behaved client sends this; servers must tolerate it.
            self.http.post_json(self.mcp_url, {"jsonrpc": "2.0", "method": "notifications/initialized"},
                                headers={"Authorization": f"Bearer {token}", "Mcp-Session-Id": sid})
        return r, doc, sid

    # -- the full sequence ----------------------------------------------------
    def run(self) -> dict[str, Any]:
        self.step_unauth()
        if not self.step_prm():
            return self.report()
        if not self.step_asm():
            return self.report()
        self.step_register()

        # 4-6: authorize with PKCE + state + exact redirect; consent; code+state back
        rnd = self.authorize_round(label="happy")
        self._rec("04_authorize_shows_explicit_consent_page", rnd["consent_page_seen"],
                  f"hops={rnd['hops']} status={rnd['status']} error={rnd['error']}"
                  + (f" excerpt={rnd.get('page_excerpt')}" if rnd.get("page_excerpt") else ""))
        self._rec("05_redirect_back_with_code", bool(rnd["code"]) and not rnd["error"],
                  f"location_host={urllib.parse.urlparse(rnd['location'] or '').netloc} error={rnd['error']}")
        self._rec("06_state_round_trip_exact", bool(rnd["code"]) and rnd.get("returned_state") == rnd["state"],
                  "state echoed exactly" if rnd.get("returned_state") == rnd["state"]
                  else f"state mismatch/missing (returned={'yes' if rnd.get('returned_state') else 'no'})")
        if not rnd["code"]:
            return self.report()

        # 7: exchange
        tr = self.exchange(rnd)
        tok = tr.json() if tr.status == 200 else {}
        access = tok.get("access_token")
        ok = tr.status == 200 and bool(access) and str(tok.get("token_type", "")).lower() == "bearer"
        self._rec("07_token_exchange", ok,
                  f"status={tr.status} token_type={tok.get('token_type')} "
                  f"refresh={'yes' if tok.get('refresh_token') else 'no'} expires_in={tok.get('expires_in')}")
        if not ok:
            return self.report()

        # 8-10: MCP with the access token
        ir, idoc, sid = self.mcp_initialize(access)
        init_ok = ir.status == 200 and isinstance(idoc, dict) and "result" in idoc
        self._rec("08_mcp_initialize_with_access_token", init_ok,
                  f"status={ir.status} protocolVersion={(idoc or {}).get('result', {}).get('protocolVersion') if isinstance(idoc, dict) else None} session={'yes' if sid else 'no'}")
        lr, ldoc = self.mcp(access, "tools/list", {}, session=sid, mid=2)
        names = [t.get("name") for t in ((ldoc or {}).get("result") or {}).get("tools", [])] if isinstance(ldoc, dict) else []
        self._rec("09_tools_list", lr.status == 200 and "resonance_whoami" in names,
                  f"status={lr.status} n_tools={len(names)} whoami={'resonance_whoami' in names}")
        wr, wdoc = self.mcp(access, "tools/call", {"name": "resonance_whoami", "arguments": {}},
                            session=sid, mid=3)
        who = ((wdoc or {}).get("result") or {}) if isinstance(wdoc, dict) else {}
        sc = who.get("structuredContent") or {}
        if not sc and who.get("content"):
            try:
                sc = json.loads(who["content"][0].get("text", "{}"))
            except Exception:  # noqa: BLE001
                sc = {}
        subject = sc.get("user_id")
        self._rec("10_resonance_whoami", wr.status == 200 and not who.get("isError", True) and bool(subject),
                  f"status={wr.status} isError={who.get('isError')} has_user_id={bool(subject)} "
                  f"actor_type={sc.get('actor_type')}")

        # 11: wrong verifier
        r2 = self.authorize_round(label="wrong-verifier")
        if r2["code"]:
            bad = self.exchange(r2, verifier=pkce_pair()[0])
            self._rec("11_wrong_verifier_rejected", bad.status in (400, 401) and b"access_token" not in bad.body,
                      f"status={bad.status} error={self._err(bad)}")
            # the failed attempt must have consumed/invalidated the code
            again = self.exchange(r2)
            self._rec("11b_code_dead_after_failed_verify", again.status in (400, 401),
                      f"status={again.status} error={self._err(again)}")
        else:
            self._rec("11_wrong_verifier_rejected", False, f"could not obtain a second code: {r2['error']}")

        # 12: wrong redirect_uri — at authorize time (no open redirect) and at token time
        r3 = self.authorize_round(redirect_uri=WRONG_REDIRECT, label="wrong-redirect-authorize")
        leaked = bool(r3["location"]) and r3["location"].startswith(WRONG_REDIRECT)
        self._rec("12_wrong_redirect_uri_not_followed", not leaked and not r3["code"],
                  f"status={r3['status']} error={r3['error']} redirected_to_attacker={leaked}")
        r3b = self.authorize_round(label="wrong-redirect-token")
        if r3b["code"]:
            bad = self.exchange(r3b, redirect_uri=self.redirect_uri + "x")
            self._rec("12b_token_redirect_mismatch_rejected", bad.status in (400, 401) and b"access_token" not in bad.body,
                      f"status={bad.status} error={self._err(bad)}")

        # 13: replayed code
        replay = self.exchange(rnd)
        self._rec("13_replayed_code_rejected", replay.status in (400, 401) and b"access_token" not in replay.body,
                  f"status={replay.status} error={self._err(replay)}")

        # 14: wrong resource/audience
        r4 = self.authorize_round(resource="https://other.invalid/mcp", label="wrong-resource")
        got_token_for_other = False
        if r4["code"]:
            bad = self.exchange(r4)
            got_token_for_other = bad.status == 200
        self._rec("14_wrong_resource_rejected", not r4["code"] or not got_token_for_other,
                  f"authorize_error={r4['error']} code_issued={bool(r4['code'])} token_issued={got_token_for_other}")
        if self.resource:
            r4b = self.authorize_round(label="resource-swap-at-token")
            if r4b["code"]:
                bad = self.exchange(r4b, resource="https://other.invalid/mcp")
                self._rec("14b_token_resource_mismatch_rejected", bad.status in (400, 401),
                          f"status={bad.status} error={self._err(bad)}")

        # 15: revoke then reuse
        rev = self.asm.get("revocation_endpoint")
        if rev:
            rr = self.http.post_form(rev, {"token": access, "client_id": self.client_id or "",
                                           "token_type_hint": "access_token"},
                                     headers={"Accept": "application/json"})
            after, adoc = self.mcp(access, "tools/list", {}, session=sid, mid=4)
            self._rec("15_revoke_then_reuse_rejected", rr.status == 200 and after.status == 401,
                      f"revoke_status={rr.status} reuse_status={after.status}")
        else:
            self._rec("15_revoke_then_reuse_rejected", False, "no revocation_endpoint advertised")

        # 16: refresh if issued
        if tok.get("refresh_token"):
            fr = self.token_request({"grant_type": "refresh_token", "refresh_token": tok["refresh_token"],
                                     "client_id": self.client_id or "",
                                     **({"resource": self.resource} if self.resource else {})})
            fdoc = fr.json() if fr.status == 200 else {}
            self._secret(fdoc.get("access_token"))
            self._secret(fdoc.get("refresh_token"))
            if rev:
                # the access token was revoked above; whether the refresh grant survives is a
                # policy choice — record, don't judge, but a NEW token must work if issued.
                detail = f"status={fr.status} new_access={'yes' if fdoc.get('access_token') else 'no'} rotated={'yes' if fdoc.get('refresh_token') and fdoc.get('refresh_token') != tok['refresh_token'] else 'no'}"
                self._rec("16_refresh_after_revoke_observed", True, detail)
            else:
                self._rec("16_refresh_token_grant", fr.status == 200 and bool(fdoc.get("access_token")),
                          f"status={fr.status}")
            if fdoc.get("access_token"):
                ir2, idoc2, sid2 = self.mcp_initialize(fdoc["access_token"])
                self._rec("16b_refreshed_token_initializes", ir2.status == 200, f"status={ir2.status}")
        else:
            self._rec("16_refresh_token_grant", True, "no refresh_token issued (allowed; reconnect re-authorizes)")

        # reconnect: a fresh authorization gives a working session; the old session id is dead
        r5 = self.authorize_round(label="reconnect")
        if r5["code"]:
            t5 = self.exchange(r5)
            if t5.status == 200:
                acc5 = t5.json().get("access_token")
                ir5, _, sid5 = self.mcp_initialize(acc5)
                l5, ldoc5 = self.mcp(acc5, "tools/list", {}, session=sid5, mid=5)
                self._rec("17_reconnect_new_authorization_works", ir5.status == 200 and l5.status == 200,
                          f"init={ir5.status} list={l5.status}")
                if sid:
                    stale, sdoc = self.mcp(acc5, "tools/list", {}, session=sid, mid=6)
                    stale_ok = stale.status in (400, 404) or (isinstance(sdoc, dict) and "error" in sdoc)
                    self._rec("17b_stale_session_rejected_cleanly", stale_ok,
                              f"status={stale.status} jsonrpc_error={'error' in (sdoc or {}) if isinstance(sdoc, dict) else False}")
            else:
                self._rec("17_reconnect_new_authorization_works", False, f"token status={t5.status}")
        else:
            self._rec("17_reconnect_new_authorization_works", False, f"authorize error={r5['error']}")

        # leak scan: no token/code may appear anywhere except the token response
        # bodies and the redirect Location headers.
        self.leak_scan(allowed_urls={self.asm.get("token_endpoint", "")})
        return self.report()

    def leak_scan(self, *, allowed_urls: set[str]) -> None:
        leaks = []
        for resp in self.http.observed:
            if resp.url in allowed_urls:
                continue
            hay = resp.text
            hdrs = {k: v for k, v in resp.headers.items() if k != "location"}
            for s in self.secrets_:
                if not s or len(s) < 16:
                    continue
                if s in hay or any(s in v for v in hdrs.values()):
                    leaks.append(f"{resp.status} {urllib.parse.urlparse(resp.url).path}")
                    break
        self._rec("18_no_secret_leak_in_bodies_or_headers", not leaks,
                  "clean" if not leaks else f"secret material echoed by: {sorted(set(leaks))[:5]}")

    def _err(self, r: Response) -> str:
        try:
            d = r.json()
            return str(d.get("error") or d.get("error_description") or "")[:80]
        except Exception:  # noqa: BLE001
            return redact(r.text[:80], self.secrets_)

    def report(self) -> dict[str, Any]:
        return {"probe": PROBE_VERSION, "base": self.base,
                "ok": all(s.ok for s in self.steps),
                "steps": [{"id": s.id, "ok": s.ok, "detail": s.detail} for s in self.steps]}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", required=True, help="public origin, e.g. https://host (probe uses <base>/mcp)")
    ap.add_argument("--redirect-uri", default=DEFAULT_REDIRECT)
    ap.add_argument("--client-id", default=None, help="only if the server has no registration endpoint")
    ap.add_argument("--json", default=None, help="write the report here as JSON")
    args = ap.parse_args(argv)
    probe = Probe(base=args.base, redirect_uri=args.redirect_uri, client_id=args.client_id)
    rep = probe.run()
    for s in rep["steps"]:
        print(f"{'PASS' if s['ok'] else 'FAIL'}  {s['id']}  {s['detail']}")
    print(f"\n{'ALL PASS' if rep['ok'] else 'FAILURES PRESENT'}: {sum(s['ok'] for s in rep['steps'])}/{len(rep['steps'])}")
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(rep, fh, indent=2)
    return 0 if rep["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
