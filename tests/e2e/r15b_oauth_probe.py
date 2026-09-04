"""R15B independent black-box OAuth / MCP onboarding probe (#135).

External-style probe: it knows ONLY a base URL (the origin that serves the
canonical ``/mcp`` resource) and drives the hosted-client onboarding sequence
purely through standards discovery, exactly the way a hosted MCP client does:

  1. unauthenticated ``POST /mcp``            -> 401 + ``WWW-Authenticate`` challenge
  2. RFC 9728 protected-resource metadata      (URL taken from the challenge)
  3. RFC 8414 authorization-server metadata    (issuer taken from step 2)
  3b. RFC 7591 dynamic client registration     (when advertised)
  4. browser ``GET`` authorize + consent form  (PKCE S256, state, resource)
  5. token exchange
  6. MCP initialize / tools/list / resonance_whoami with the bearer
  7. negatives: wrong verifier, replayed code, wrong redirect, wrong resource,
     revoke-then-reuse, reconnect / stale session, PKCE required, caller-
     selected identity ignored, no secret leakage in error responses.

Design constraints that keep this an *independent* oracle:

* stdlib only; nothing is imported from ``src/``;
* no implementer test helper is reused; the consent page is driven by parsing
  the served HTML form generically (hidden fields + a guest/approve control);
* the probe never follows a redirect to the client callback -- it captures the
  ``Location`` header and checks it, like a real client would;
* secrets (codes, verifiers, access/refresh tokens, recovery secrets) are
  registered with a redactor; the report never contains them and every
  negative-path response is scanned for their presence.

Run against any origin::

    python3 -m tests.e2e.r15b_oauth_probe --base https://host [--report out.json]
        [--client-id ID] [--redirect-uri URI] [--consent name=value ...]

Exit status is 1 when any step FAILs. Output is a JSON report with one row per
step (PASS / FAIL / SKIP / INFO) and a redacted detail string.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import http.cookiejar
import json
import secrets
import sys
import time
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit
from urllib.request import (HTTPCookieProcessor, HTTPRedirectHandler, Request,
                            build_opener)

PROBE_VERSION = "r15b-oauth-probe/0.1"
MCP_PROTOCOL = "2025-03-26"
WHOAMI_TOOL = "resonance_whoami"

# Consent-form control heuristics (lower-cased substring match on
# name + value + visible text).  Overridable from the CLI with --consent.
_APPROVE_WORDS = ("guest", "continue", "approve", "allow", "consent",
                  "authorize", "authorise", "grant", "accept", "yes")
_DENY_WORDS = ("deny", "cancel", "reject", "decline", "sign in", "login",
               "log in", "recover")


# --------------------------------------------------------------------------
# HTTP plumbing: cookies kept, redirects never followed automatically.
# --------------------------------------------------------------------------
class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D401
        return None


@dataclass
class Response:
    status: int
    headers: dict[str, str]
    body: bytes
    url: str

    def header(self, name: str) -> str | None:
        return self.headers.get(name.lower())

    @property
    def text(self) -> str:
        return self.body.decode("utf-8", "replace")

    def json(self) -> Any:
        return json.loads(self.body.decode("utf-8"))

    @property
    def content_type(self) -> str:
        return (self.header("content-type") or "").split(";")[0].strip().lower()


class Http:
    def __init__(self, timeout: float = 15.0):
        self.jar = http.cookiejar.CookieJar()
        self.opener = build_opener(_NoRedirect(), HTTPCookieProcessor(self.jar))
        self.timeout = timeout

    def request(self, method: str, url: str, *, headers: dict[str, str] | None = None,
                body: bytes | None = None) -> Response:
        req = Request(url, data=body, method=method, headers=headers or {})
        req.add_header("User-Agent", PROBE_VERSION)
        try:
            with self.opener.open(req, timeout=self.timeout) as r:
                return Response(r.status, {k.lower(): v for k, v in r.headers.items()},
                                r.read(), r.geturl())
        except HTTPError as e:  # any non-2xx (and 3xx, because we never follow)
            return Response(e.code, {k.lower(): v for k, v in e.headers.items()},
                            e.read() or b"", url)

    def get(self, url: str, **kw) -> Response:
        return self.request("GET", url, **kw)

    def post_form(self, url: str, fields: dict[str, str], *, headers=None) -> Response:
        h = {"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json, text/html"}
        h.update(headers or {})
        return self.request("POST", url, headers=h, body=urlencode(fields).encode())

    def post_json(self, url: str, payload: Any, *, headers=None) -> Response:
        h = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
        h.update(headers or {})
        return self.request("POST", url, headers=h, body=json.dumps(payload).encode())


# --------------------------------------------------------------------------
# Generic HTML form extraction for the consent page.
# --------------------------------------------------------------------------
@dataclass
class Form:
    action: str
    method: str
    fields: list[dict[str, str]] = field(default_factory=list)   # input/textarea/select
    submits: list[dict[str, str]] = field(default_factory=list)  # buttons / submit inputs


class _FormParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.forms: list[Form] = []
        self._cur: Form | None = None
        self._button: dict[str, str] | None = None
        self.inline_script = False
        self.inline_style = False
        self._in_script = False
        self._select_name: str | None = None
        self._select_first_value: str | None = None
        self.text_chunks: list[str] = []

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag == "script":
            self._in_script = True
            if not a.get("src"):
                self.inline_script = True
        elif tag == "style":
            self.inline_style = True
        elif tag == "form":
            self._cur = Form(action=a.get("action", ""), method=a.get("method", "get").lower())
            self.forms.append(self._cur)
        elif self._cur is not None:
            if tag == "input":
                itype = a.get("type", "text").lower()
                rec = {"name": a.get("name", ""), "value": a.get("value", ""), "type": itype,
                       "checked": "checked" in a, "text": ""}
                if itype in ("submit", "image"):
                    self._cur.submits.append(rec)
                elif itype != "button":
                    self._cur.fields.append(rec)
            elif tag == "button":
                btype = a.get("type", "submit").lower()
                self._button = {"name": a.get("name", ""), "value": a.get("value", ""),
                                "type": btype, "checked": False, "text": ""}
                if btype == "submit":
                    self._cur.submits.append(self._button)
            elif tag == "textarea":
                self._cur.fields.append({"name": a.get("name", ""), "value": "",
                                         "type": "textarea", "checked": False, "text": ""})
            elif tag == "select":
                self._select_name = a.get("name", "")
                self._select_first_value = None
            elif tag == "option" and self._select_name is not None:
                if self._select_first_value is None or "selected" in a:
                    self._select_first_value = a.get("value", "")

    def handle_endtag(self, tag):
        if tag == "script":
            self._in_script = False
        elif tag == "form":
            self._cur = None
        elif tag == "button":
            self._button = None
        elif tag == "select" and self._cur is not None and self._select_name is not None:
            self._cur.fields.append({"name": self._select_name,
                                     "value": self._select_first_value or "",
                                     "type": "select", "checked": False, "text": ""})
            self._select_name = None

    def handle_data(self, data):
        if self._in_script:
            return
        if self._button is not None:
            self._button["text"] += data
        self.text_chunks.append(data)


def parse_forms(html: str) -> _FormParser:
    p = _FormParser()
    p.feed(html)
    return p


def choose_consent_submission(form: Form, overrides: dict[str, str]) -> dict[str, str]:
    """Hidden fields + a ticked consent checkbox/radio + one approving control."""
    out: dict[str, str] = {}
    for f in form.fields:
        if not f["name"]:
            continue
        t = f["type"]
        if t == "hidden":
            out[f["name"]] = f["value"]
        elif t == "checkbox":
            label = (f["name"] + " " + f["value"]).lower()
            if f["checked"] or any(w in label for w in _APPROVE_WORDS + ("agree", "ok")):
                out[f["name"]] = f["value"] or "on"
        elif t == "radio":
            label = (f["name"] + " " + f["value"]).lower()
            if f["name"] not in out and (f["checked"] or "guest" in label):
                out[f["name"]] = f["value"]
        elif t == "select":
            out[f["name"]] = f["value"]
        # text/password/textarea intentionally left out: a guest continuation
        # must not need a typed secret.
    chosen = None
    for s in form.submits:
        label = (s["name"] + " " + s["value"] + " " + s["text"]).lower()
        if any(w in label for w in _DENY_WORDS):
            continue
        if any(w in label for w in _APPROVE_WORDS):
            chosen = s
            break
    if chosen is None and form.submits:
        for s in form.submits:  # last resort: first non-deny control
            label = (s["name"] + " " + s["value"] + " " + s["text"]).lower()
            if not any(w in label for w in _DENY_WORDS):
                chosen = s
                break
    if chosen is not None and chosen["name"]:
        out[chosen["name"]] = chosen["value"]
    out.update(overrides)
    return out


# --------------------------------------------------------------------------
# Secret redaction / leak detection.
# --------------------------------------------------------------------------
class Redactor:
    def __init__(self):
        self._secrets: list[tuple[str, str]] = []  # (value, kind)

    def add(self, value: Any, kind: str) -> None:
        if isinstance(value, str) and len(value) >= 8:
            self._secrets.append((value, kind))

    def redact(self, text: str) -> str:
        for value, kind in sorted(self._secrets, key=lambda p: -len(p[0])):
            text = text.replace(value, f"<redacted:{kind}>")
        return text

    def leaks(self, text: str) -> list[str]:
        return sorted({kind for value, kind in self._secrets if value in text})


# --------------------------------------------------------------------------
# PKCE / URL helpers.
# --------------------------------------------------------------------------
def pkce_pair() -> tuple[str, str]:
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(48)).rstrip(b"=").decode()
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode("ascii")).digest()).rstrip(b"=").decode()
    return verifier, challenge


def origin_of(url: str) -> str:
    s = urlsplit(url)
    return f"{s.scheme}://{s.netloc}"


def rfc8414_url(issuer: str, suffix: str = "oauth-authorization-server") -> str:
    s = urlsplit(issuer)
    path = s.path.rstrip("/")
    return f"{s.scheme}://{s.netloc}/.well-known/{suffix}{path}"


def rfc9728_url(resource: str) -> str:
    s = urlsplit(resource)
    path = s.path.rstrip("/")
    return f"{s.scheme}://{s.netloc}/.well-known/oauth-protected-resource{path}"


def parse_www_authenticate(value: str) -> dict[str, str]:
    """Minimal RFC 9110 auth-param parser for a single Bearer challenge."""
    out: dict[str, str] = {}
    v = value.strip()
    if v.lower().startswith("bearer"):
        v = v[len("bearer"):].strip()
    i, n = 0, len(v)
    while i < n:
        while i < n and v[i] in " ,":
            i += 1
        j = i
        while j < n and v[j] not in "=":
            j += 1
        key = v[i:j].strip().lower()
        i = j + 1
        if i >= n:
            break
        if v[i] == '"':
            i += 1
            buf = []
            while i < n and v[i] != '"':
                if v[i] == "\\" and i + 1 < n:
                    i += 1
                buf.append(v[i])
                i += 1
            i += 1
            out[key] = "".join(buf)
        else:
            j = i
            while j < n and v[j] != ",":
                j += 1
            out[key] = v[i:j].strip()
            i = j
    return out


def location_matches(location: str | None, redirect_uri: str) -> bool:
    """Exact match on scheme/host/port/path; query/fragment carry the result."""
    if not location:
        return False
    a, b = urlsplit(location), urlsplit(redirect_uri)
    return (a.scheme, a.netloc, a.path) == (b.scheme, b.netloc, b.path)


# --------------------------------------------------------------------------
# The probe.
# --------------------------------------------------------------------------
@dataclass
class Step:
    id: str
    name: str
    status: str   # PASS | FAIL | SKIP | INFO
    detail: str = ""


class Probe:
    def __init__(self, base: str, *, client_id: str | None = None,
                 redirect_uri: str = "https://r15b-probe.invalid/callback",
                 consent_overrides: dict[str, str] | None = None,
                 timeout: float = 15.0, scope: str | None = "offline_access"):
        self.base = base.rstrip("/")
        self.resource = self.base + "/mcp"
        self.http = Http(timeout)
        self.redact = Redactor()
        self.steps: list[Step] = []
        self.client_id = client_id
        self.client_secret: str | None = None
        self.redirect_uri = redirect_uri
        self.consent_overrides = consent_overrides or {}
        self.scope = scope
        self.prm: dict[str, Any] = {}
        self.asm: dict[str, Any] = {}
        self.issuer: str | None = None
        self.negative_responses: list[tuple[str, Response]] = []
        self.started_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    # -- bookkeeping -------------------------------------------------------
    def _rec(self, sid: str, name: str, ok: bool | None, detail: str = "") -> bool:
        status = "INFO" if ok is None else ("PASS" if ok else "FAIL")
        self.steps.append(Step(sid, name, status, self.redact.redact(detail)))
        return bool(ok)

    def _skip(self, sid: str, name: str, detail: str) -> None:
        self.steps.append(Step(sid, name, "SKIP", self.redact.redact(detail)))

    def _neg(self, tag: str, resp: Response) -> Response:
        self.negative_responses.append((tag, resp))
        return resp

    @staticmethod
    def _short(resp: Response, n: int = 300) -> str:
        return f"HTTP {resp.status} {resp.content_type} {resp.text[:n]!r}"

    # -- step 1 ---------------------------------------------------------------
    def step_unauthenticated_mcp(self) -> dict[str, str]:
        r = self.http.post_json(self.resource, {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                                                "params": {"protocolVersion": MCP_PROTOCOL,
                                                           "capabilities": {},
                                                           "clientInfo": {"name": PROBE_VERSION, "version": "0.1"}}})
        www = r.header("www-authenticate") or ""
        params = parse_www_authenticate(www) if www else {}
        ok = r.status == 401 and www.lower().startswith("bearer")
        self._rec("1", "unauthenticated POST /mcp is 401 with a Bearer challenge", ok,
                  f"HTTP {r.status}; WWW-Authenticate={www!r}")
        self._rec("1b", "challenge carries resource_metadata (RFC 9728 §5.1)",
                  bool(params.get("resource_metadata")), f"params={params}")
        g = self.http.get(self.resource, headers={"Accept": "text/event-stream"})
        self._rec("1c", "unauthenticated GET /mcp does not serve content",
                  None, f"HTTP {g.status} (401/405 both acceptable; informational)")
        return params

    # -- step 2 ---------------------------------------------------------------
    def step_protected_resource_metadata(self, challenge: dict[str, str]) -> bool:
        candidates = []
        if challenge.get("resource_metadata"):
            candidates.append(("challenge", challenge["resource_metadata"]))
        candidates.append(("rfc9728-path", rfc9728_url(self.resource)))
        candidates.append(("rfc9728-root", self.base + "/.well-known/oauth-protected-resource"))
        got: dict[str, Any] | None = None
        used = None
        for tag, url in candidates:
            r = self.http.get(url, headers={"Accept": "application/json"})
            if r.status == 200 and r.content_type == "application/json":
                try:
                    got = r.json()
                    used = (tag, url)
                    break
                except ValueError:
                    continue
        if got is None:
            return self._rec("2", "protected-resource metadata is discoverable", False,
                             f"none of {[u for _, u in candidates]} returned JSON 200")
        self.prm = got
        tag, url = used
        problems = []
        if got.get("resource") != self.resource:
            problems.append(f"resource={got.get('resource')!r} != {self.resource!r}")
        servers = got.get("authorization_servers")
        if not (isinstance(servers, list) and servers and all(isinstance(s, str) for s in servers)):
            problems.append(f"authorization_servers={servers!r}")
        if tag != "challenge":
            problems.append(f"metadata found only via {tag} fallback, challenge URL unusable")
        elif url != rfc9728_url(self.resource) and url != self.base + "/.well-known/oauth-protected-resource":
            problems.append(f"resource_metadata URL {url} is not an RFC 9728 well-known location")
        bm = got.get("bearer_methods_supported")
        if bm is not None and "header" not in bm:
            problems.append(f"bearer_methods_supported={bm!r} lacks 'header'")
        if "https" not in urlsplit(self.resource).scheme and self.base.startswith("https"):
            problems.append("resource is not https")
        ok = self._rec("2", "protected-resource metadata correct and linked from the challenge",
                       not problems, f"via {tag} {url}; " + ("; ".join(problems) or json.dumps(got, sort_keys=True)))
        self._rec("2b", "scopes advertised by the resource", None,
                  f"scopes_supported={got.get('scopes_supported')!r}")
        return ok

    # -- step 3 ---------------------------------------------------------------
    def step_authorization_server_metadata(self) -> bool:
        servers = self.prm.get("authorization_servers") or []
        if not servers:
            return self._rec("3", "authorization-server metadata", False, "no authorization_servers")
        issuer = servers[0]
        self.issuer = issuer
        found = None
        tried = []
        for url in (rfc8414_url(issuer), rfc8414_url(issuer, "openid-configuration"),
                    issuer.rstrip("/") + "/.well-known/oauth-authorization-server"):
            if url in tried:
                continue
            tried.append(url)
            r = self.http.get(url, headers={"Accept": "application/json"})
            if r.status == 200 and r.content_type == "application/json":
                try:
                    found = (url, r.json())
                    break
                except ValueError:
                    pass
        if found is None:
            return self._rec("3", "authorization-server metadata is discoverable", False,
                             f"tried {tried}")
        url, m = found
        self.asm = m
        problems = []
        if m.get("issuer") != issuer:
            problems.append(f"issuer={m.get('issuer')!r} != advertised {issuer!r}")
        for key in ("authorization_endpoint", "token_endpoint"):
            v = m.get(key)
            if not isinstance(v, str) or not v.startswith(("https://", "http://")):
                problems.append(f"{key}={v!r}")
            elif origin_of(v) != origin_of(issuer):
                problems.append(f"{key} origin {origin_of(v)} != issuer origin {origin_of(issuer)}")
        if "S256" not in (m.get("code_challenge_methods_supported") or []):
            problems.append("code_challenge_methods_supported lacks S256")
        if "code" not in (m.get("response_types_supported") or []):
            problems.append("response_types_supported lacks 'code'")
        gts = m.get("grant_types_supported")
        if gts is not None and "authorization_code" not in gts:
            problems.append(f"grant_types_supported={gts!r} lacks authorization_code")
        if url != rfc8414_url(issuer):
            problems.append(f"metadata served at {url}, not the RFC 8414 location for this issuer")
        ok = self._rec("3", "authorization-server metadata correct (RFC 8414)", not problems,
                       f"{url}; " + ("; ".join(problems) or "issuer/endpoints/S256/code all consistent"))
        tam = m.get("token_endpoint_auth_methods_supported")
        self._rec("3b", "public-client token auth ('none') advertised for hosted clients",
                  None if tam is None else ("none" in tam), f"token_endpoint_auth_methods_supported={tam!r}")
        self._rec("3c", "optional endpoints", None,
                  f"registration_endpoint={m.get('registration_endpoint')!r} "
                  f"revocation_endpoint={m.get('revocation_endpoint')!r} "
                  f"scopes_supported={m.get('scopes_supported')!r} "
                  f"resource_indicators_supported={m.get('resource_indicators_supported')!r}")
        return ok

    # -- step 3b: registration -------------------------------------------------
    def step_client_registration(self) -> bool:
        reg = self.asm.get("registration_endpoint")
        if not reg:
            if self.client_id:
                self._skip("3d", "dynamic client registration", f"not advertised; using --client-id")
                return True
            self.client_id = "r15b-probe"
            self._skip("3d", "dynamic client registration",
                       "not advertised and no --client-id given; using client_id 'r15b-probe' "
                       "(hosted clients rely on RFC 7591 or a pre-registered id)")
            return True
        payload = {"client_name": "R15B black-box probe", "redirect_uris": [self.redirect_uri],
                   "grant_types": ["authorization_code", "refresh_token"],
                   "response_types": ["code"], "token_endpoint_auth_method": "none"}
        r = self.http.post_json(reg, payload)
        try:
            body = r.json() if r.body else {}
        except ValueError:
            body = {}
        cid = body.get("client_id") if isinstance(body, dict) else None
        problems = []
        if r.status not in (200, 201):
            problems.append(f"HTTP {r.status}")
        if not cid:
            problems.append("no client_id in response")
        if isinstance(body, dict) and body.get("redirect_uris") not in (None, [self.redirect_uri]):
            problems.append(f"redirect_uris echoed as {body.get('redirect_uris')!r}")
        if cid:
            self.client_id = cid
            if body.get("client_secret"):
                self.client_secret = body["client_secret"]
                self.redact.add(self.client_secret, "client_secret")
        return self._rec("3d", "dynamic client registration (RFC 7591) issues a client_id",
                         not problems, f"HTTP {r.status}; " + ("; ".join(problems) or f"client_id issued; keys={sorted(body)}"))

    # -- authorize + consent helper --------------------------------------------
    def authorize(self, *, redirect_uri: str | None = None, resource: str | None = None,
                  code_challenge: str | None = None, method: str | None = "S256",
                  state: str | None = None, extra: dict[str, str] | None = None,
                  submit_consent: bool = True, tag: str = "authorize") -> tuple[Response, Response | None]:
        """Returns (GET response, final POST response or None)."""
        q: dict[str, str] = {"response_type": "code", "client_id": self.client_id or "",
                             "redirect_uri": redirect_uri if redirect_uri is not None else self.redirect_uri}
        if state is not None:
            q["state"] = state
        if code_challenge is not None:
            q["code_challenge"] = code_challenge
        if method is not None:
            q["code_challenge_method"] = method
        if resource is not None:
            q["resource"] = resource
        if self.scope:
            q["scope"] = self.scope
        if extra:
            q.update(extra)
        url = self.asm["authorization_endpoint"] + ("&" if "?" in self.asm["authorization_endpoint"] else "?") + urlencode(q)
        r = self.http.get(url, headers={"Accept": "text/html,application/xhtml+xml,*/*;q=0.8"})
        # Follow same-origin interstitials (e.g. a login page) but never the client callback.
        hops = 0
        while 300 <= r.status < 400 and hops < 3:
            loc = r.header("location") or ""
            target = urljoin(url, loc)
            if origin_of(target) != origin_of(self.asm["authorization_endpoint"]):
                break
            r = self.http.get(target, headers={"Accept": "text/html"})
            url = target
            hops += 1
        if not submit_consent:
            return r, None
        post = None
        page = r
        page_url = url
        for _ in range(3):
            if not (page.status == 200 and page.content_type.startswith("text/html")):
                break
            parsed = parse_forms(page.text)
            forms = [f for f in parsed.forms if f.method == "post"] or parsed.forms
            if not forms:
                break
            form = next((f for f in forms if "authorize" in f.action or not f.action), forms[0])
            fields = choose_consent_submission(form, self.consent_overrides)
            action = urljoin(page_url, form.action) if form.action else page_url
            post = self.http.post_form(action, fields, headers={"Accept": "text/html", "Origin": origin_of(action),
                                                                "Referer": page_url})
            if 300 <= post.status < 400:
                break
            page, page_url = post, action
        return r, post

    # -- steps 4-6: happy path -----------------------------------------------
    def step_authorize_consent(self) -> tuple[str, str] | None:
        verifier, challenge = pkce_pair()
        state = "st~" + secrets.token_urlsafe(18) + ".-_x"
        self.redact.add(verifier, "code_verifier")
        r, post = self.authorize(code_challenge=challenge, state=state, resource=self.resource)
        html_ok = r.status == 200 and r.content_type.startswith("text/html")
        premature = 300 <= r.status < 400 and location_matches(r.header("location"), self.redirect_uri)
        if premature:
            q = parse_qs(urlsplit(r.header("location") or "").query)
            if "code" in q:
                self._rec("4", "GET authorize renders a consent page (no code without explicit consent)", False,
                          "authorization endpoint redirected with a code before any consent")
                return None
        self._rec("4", "GET authorize renders an explicit consent page", html_ok, self._short(r, 200))
        if html_ok:
            parsed = parse_forms(r.text)
            self._rec("4b", "consent page is CSP-friendly (no inline script/style)", None,
                      f"inline_script={parsed.inline_script} inline_style={parsed.inline_style} "
                      f"forms={len(parsed.forms)}")
            text = " ".join(parsed.text_chunks).lower()
            self._rec("4c", "consent page names the requesting client and what is granted", None,
                      f"mentions client_id={self.client_id.lower() in text if self.client_id else None}; "
                      f"mentions 'guest'={'guest' in text}; mentions 'resonance'={'resonance' in text}")
        if post is None:
            self._rec("5", "login/guest + consent submission", False, "no POST-able consent form found")
            return None
        loc = post.header("location")
        q = parse_qs(urlsplit(loc or "").query)
        code = (q.get("code") or [""])[0]
        got_state = (q.get("state") or [None])[0]
        self.redact.add(code, "authorization_code")   # register BEFORE any detail is recorded
        ok_redirect = 300 <= post.status < 400 and location_matches(loc, self.redirect_uri)
        self._rec("5", "consent POST redirects back to the exact registered redirect_uri", ok_redirect,
                  f"HTTP {post.status} Location={loc!r}" if loc else self._short(post))
        if not ok_redirect:
            return None
        self._rec("6", "redirect carries a code and the exact state", bool(code) and got_state == state,
                  f"code={'present' if code else 'missing'} state_exact={got_state == state} "
                  f"fragment_empty={not urlsplit(loc).fragment}")
        if not code or got_state != state:
            return None
        return code, verifier

    def token_request(self, fields: dict[str, str], tag: str) -> Response:
        f = dict(fields)
        f.setdefault("client_id", self.client_id or "")
        if self.client_secret:
            f.setdefault("client_secret", self.client_secret)
        return self.http.post_form(self.asm["token_endpoint"], f)

    def step_token_exchange(self, code: str, verifier: str) -> dict[str, Any] | None:
        r = self.token_request({"grant_type": "authorization_code", "code": code,
                                "redirect_uri": self.redirect_uri, "code_verifier": verifier,
                                "resource": self.resource}, "token")
        try:
            body = r.json()
        except ValueError:
            body = {}
        tok = body.get("access_token") if isinstance(body, dict) else None
        if tok:
            self.redact.add(tok, "access_token")
        if isinstance(body, dict) and body.get("refresh_token"):
            self.redact.add(body["refresh_token"], "refresh_token")
        problems = []
        if r.status != 200:
            problems.append(f"HTTP {r.status}")
        if not tok:
            problems.append("no access_token")
        if str(body.get("token_type", "")).lower() != "bearer":
            problems.append(f"token_type={body.get('token_type')!r}")
        cc = (r.header("cache-control") or "").lower()
        if "no-store" not in cc:
            problems.append(f"Cache-Control={cc!r} lacks no-store (RFC 6749 §5.1)")
        ok = self._rec("7", "token exchange returns a Bearer access token", not problems,
                       "; ".join(problems) or f"keys={sorted(body)} expires_in={body.get('expires_in')!r} "
                                              f"refresh_token={'yes' if body.get('refresh_token') else 'no'}")
        return body if ok else None

    # -- MCP ------------------------------------------------------------------
    def mcp(self, token: str | None, message: dict[str, Any], session: str | None = None) -> tuple[Response, Any]:
        h = {"MCP-Protocol-Version": MCP_PROTOCOL}
        if token:
            h["Authorization"] = f"Bearer {token}"
        if session:
            h["Mcp-Session-Id"] = session
        r = self.http.post_json(self.resource, message, headers=h)
        parsed: Any = None
        if r.body:
            if r.content_type == "text/event-stream":
                for line in r.text.splitlines():
                    if line.startswith("data:"):
                        try:
                            parsed = json.loads(line[5:].strip())
                        except ValueError:
                            pass
            else:
                try:
                    parsed = r.json()
                except ValueError:
                    parsed = None
        return r, parsed

    def mcp_connect(self, token: str, tag: str) -> tuple[str | None, dict[str, Any] | None]:
        """initialize -> initialized -> tools/list -> whoami. Returns (session, whoami payload)."""
        r, init = self.mcp(token, {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                                   "params": {"protocolVersion": MCP_PROTOCOL, "capabilities": {},
                                              "clientInfo": {"name": PROBE_VERSION, "version": "0.1"}}})
        session = r.header("mcp-session-id")
        ok = r.status == 200 and isinstance(init, dict) and "result" in init and \
            bool((init["result"] or {}).get("protocolVersion"))
        self._rec(f"{tag}.init", "MCP initialize with the OAuth access token", ok,
                  f"HTTP {r.status} session={'yes' if session else 'no'} "
                  f"protocolVersion={(init or {}).get('result', {}).get('protocolVersion') if isinstance(init, dict) else None} "
                  f"serverInfo={(init or {}).get('result', {}).get('serverInfo') if isinstance(init, dict) else None}")
        if not ok:
            return session, None
        r2, _ = self.mcp(token, {"jsonrpc": "2.0", "method": "notifications/initialized"}, session)
        self._rec(f"{tag}.initialized", "notifications/initialized accepted", r2.status in (200, 202, 204),
                  f"HTTP {r2.status}")
        r3, tl = self.mcp(token, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}, session)
        names = [t.get("name") for t in ((tl or {}).get("result") or {}).get("tools", [])] if isinstance(tl, dict) else []
        self._rec(f"{tag}.tools", "tools/list includes resonance_whoami", WHOAMI_TOOL in names,
                  f"HTTP {r3.status} tools={names}")
        r4, who = self.mcp(token, {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                                   "params": {"name": WHOAMI_TOOL, "arguments": {}}}, session)
        payload = None
        if isinstance(who, dict) and isinstance(who.get("result"), dict) and not who["result"].get("isError"):
            res = who["result"]
            payload = res.get("structuredContent")
            if payload is None:
                for block in res.get("content", []):
                    if block.get("type") == "text":
                        try:
                            payload = json.loads(block["text"])
                            break
                        except ValueError:
                            pass
        uid = (payload or {}).get("user_id") if isinstance(payload, dict) else None
        self._rec(f"{tag}.whoami", "resonance_whoami returns the authenticated identity", bool(uid),
                  f"HTTP {r4.status} user_id_prefix={str(uid)[:7] if uid else None} "
                  f"keys={sorted(payload) if isinstance(payload, dict) else None}")
        return session, payload if isinstance(payload, dict) else None

    # -- negatives -----------------------------------------------------------
    def fresh_code(self, tag: str, **kw) -> tuple[str, str] | None:
        verifier, challenge = pkce_pair()
        state = secrets.token_urlsafe(12)
        self.redact.add(verifier, "code_verifier")
        _, post = self.authorize(code_challenge=challenge, state=state, resource=self.resource, tag=tag, **kw)
        if post is None or not (300 <= post.status < 400) or not location_matches(post.header("location"), self.redirect_uri):
            return None
        q = parse_qs(urlsplit(post.header("location") or "").query)
        code = (q.get("code") or [""])[0]
        if not code or (q.get("state") or [None])[0] != state:
            return None
        self.redact.add(code, "authorization_code")
        return code, verifier

    @staticmethod
    def _oauth_error(r: Response) -> str | None:
        try:
            b = r.json()
            return b.get("error") if isinstance(b, dict) else None
        except ValueError:
            return None

    def step_wrong_verifier(self) -> None:
        pair = self.fresh_code("wrong-verifier")
        if pair is None:
            return self._rec("8", "wrong PKCE verifier is rejected", False, "could not obtain a fresh code") and None
        code, verifier = pair
        bad = self._neg("wrong_verifier", self.token_request(
            {"grant_type": "authorization_code", "code": code, "redirect_uri": self.redirect_uri,
             "code_verifier": verifier[:-4] + "XXXX", "resource": self.resource}, "wrong-verifier"))
        try:
            leaked = "access_token" in (bad.json() or {})
        except ValueError:
            leaked = False
        self._rec("8", "wrong PKCE verifier is rejected (400 invalid_grant, no token)",
                  bad.status == 400 and not leaked, f"HTTP {bad.status} error={self._oauth_error(bad)!r}")
        again = self._neg("verifier_retry", self.token_request(
            {"grant_type": "authorization_code", "code": code, "redirect_uri": self.redirect_uri,
             "code_verifier": verifier, "resource": self.resource}, "verifier-retry"))
        self._rec("8b", "code is burned after a failed exchange attempt (OAuth 2.1 §4.1.2 SHOULD)",
                  None if again.status == 200 else True,
                  f"HTTP {again.status} error={self._oauth_error(again)!r}"
                  + (" -- code still redeemable after a failed PKCE attempt (allowed but weaker)" if again.status == 200 else ""))

    def step_replay(self, used_code: str, verifier: str) -> None:
        r = self._neg("replay", self.token_request(
            {"grant_type": "authorization_code", "code": used_code, "redirect_uri": self.redirect_uri,
             "code_verifier": verifier, "resource": self.resource}, "replay"))
        self._rec("9", "replayed authorization code is rejected", r.status == 400,
                  f"HTTP {r.status} error={self._oauth_error(r)!r}")

    def step_wrong_redirect(self) -> None:
        s = urlsplit(self.redirect_uri)
        attackers = [f"{s.scheme}://{s.netloc}.attacker.invalid{s.path}",
                     "https://attacker.invalid/callback",
                     f"{s.scheme}://{s.netloc}{s.path}/../stolen",
                     f"{s.scheme}://{s.netloc}{s.path}?x=1"]
        bad_any = []
        for uri in attackers:
            verifier, challenge = pkce_pair()
            r, post = self.authorize(redirect_uri=uri, code_challenge=challenge, state="s1",
                                     resource=self.resource, tag="wrong-redirect")
            for resp in (r, post):
                if resp is None:
                    continue
                self._neg("wrong_redirect", resp)
                loc = resp.header("location") or ""
                if 300 <= resp.status < 400 and (origin_of(urljoin(self.asm["authorization_endpoint"], loc))
                                                  != origin_of(self.asm["authorization_endpoint"])):
                    bad_any.append(f"{uri} -> redirected off-origin to {self.redact.redact(loc)!r}")
                if "code=" in loc:
                    bad_any.append(f"{uri} -> code issued: {self.redact.redact(loc)!r}")
        self._rec("10", "unregistered / mutated redirect_uri never receives a redirect or a code",
                  not bad_any, "; ".join(bad_any) or f"{len(attackers)} variants refused on-origin")
        pair = self.fresh_code("redirect-mismatch")
        if pair is None:
            self._rec("10b", "token exchange with mismatched redirect_uri is rejected", False, "no fresh code")
            return
        code, verifier = pair
        r = self._neg("redirect_mismatch", self.token_request(
            {"grant_type": "authorization_code", "code": code, "redirect_uri": attackers[1],
             "code_verifier": verifier, "resource": self.resource}, "redirect-mismatch"))
        self._rec("10b", "token exchange with mismatched redirect_uri is rejected", r.status == 400,
                  f"HTTP {r.status} error={self._oauth_error(r)!r}")

    def step_wrong_resource(self) -> None:
        evil = "https://attacker.invalid/mcp"
        verifier, challenge = pkce_pair()
        r, post = self.authorize(code_challenge=challenge, state="s2", resource=evil, tag="wrong-resource")
        issued = False
        detail = []
        for resp in (r, post):
            if resp is None:
                continue
            self._neg("wrong_resource_authorize", resp)
            loc = resp.header("location") or ""
            q = parse_qs(urlsplit(loc).query)
            if "code" in q:
                issued = True
            detail.append(f"HTTP {resp.status} error={(q.get('error') or [self._oauth_error(resp)])[0]!r}")
        self._rec("11", "authorize with a foreign resource does not issue a code (RFC 8707 invalid_target)",
                  not issued, "; ".join(detail))
        pair = self.fresh_code("resource-mismatch")
        if pair is None:
            self._rec("11b", "token exchange for a foreign resource is rejected", False, "no fresh code")
            return
        code, verifier = pair
        t = self._neg("wrong_resource_token", self.token_request(
            {"grant_type": "authorization_code", "code": code, "redirect_uri": self.redirect_uri,
             "code_verifier": verifier, "resource": evil}, "resource-mismatch"))
        self._rec("11b", "token exchange for a foreign resource is rejected", t.status == 400,
                  f"HTTP {t.status} error={self._oauth_error(t)!r}")

    def step_pkce_required(self) -> None:
        got_code = []
        for label, kw in (("no code_challenge", {"code_challenge": None, "method": None}),
                          ("method=plain", {"code_challenge": "plainvalueplainvalueplainvalueplainvalue123", "method": "plain"})):
            r, post = self.authorize(state="s3", resource=self.resource, tag="pkce", **kw)
            for resp in (r, post):
                if resp is None:
                    continue
                self._neg("pkce_required", resp)
                if "code=" in (resp.header("location") or ""):
                    got_code.append(label)
        self._rec("E1", "PKCE S256 is mandatory (no challenge / plain method never yields a code)",
                  not got_code, "; ".join(f"code issued with {g}" for g in got_code) or "both variants refused")

    def step_caller_identity_ignored(self, real_uid: str | None) -> None:
        pair = self.fresh_code("identity", extra={"user_id": "person-attacker", "sub": "person-attacker",
                                                   "login_hint": "person-attacker", "actor": "person-attacker"})
        if pair is None:
            self._rec("E2", "caller-supplied identity parameters are ignored", False, "no fresh code with extra params")
            return
        code, verifier = pair
        t = self.token_request({"grant_type": "authorization_code", "code": code, "redirect_uri": self.redirect_uri,
                                "code_verifier": verifier, "resource": self.resource, "user_id": "person-attacker",
                                "sub": "person-attacker"}, "identity")
        try:
            tok = t.json().get("access_token")
        except ValueError:
            tok = None
        if not tok:
            self._rec("E2", "caller-supplied identity parameters are ignored", False, f"token HTTP {t.status}")
            return
        self.redact.add(tok, "access_token")
        _, who = self.mcp_connect(tok, "E2")
        uid = (who or {}).get("user_id")
        self._rec("E2", "caller-supplied identity parameters are ignored (identity is server-assigned)",
                  bool(uid) and uid != "person-attacker" and uid != real_uid,
                  f"user_id_prefix={str(uid)[:7] if uid else None} distinct_from_first_guest={uid != real_uid}")

    def step_revoke_then_reuse(self, token_body: dict[str, Any]) -> None:
        rev = self.asm.get("revocation_endpoint")
        access = token_body.get("access_token")
        refresh = token_body.get("refresh_token")
        if not rev:
            self._rec("12", "revoke then reuse fails", False, "no revocation_endpoint advertised in AS metadata")
            return
        r = self.http.post_form(rev, {"token": access, "token_type_hint": "access_token",
                                      "client_id": self.client_id or ""})
        self._rec("12a", "revocation endpoint accepts the access token (RFC 7009)", r.status == 200,
                  f"HTTP {r.status}")
        m, _ = self.mcp(access, {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                                 "params": {"protocolVersion": MCP_PROTOCOL, "capabilities": {},
                                            "clientInfo": {"name": PROBE_VERSION, "version": "0.1"}}})
        self._neg("revoked_access", m)
        self._rec("12", "revoked access token is refused at /mcp", m.status == 401,
                  f"HTTP {m.status} WWW-Authenticate={m.header('www-authenticate')!r}")
        if refresh:
            t = self._neg("revoked_refresh", self.token_request(
                {"grant_type": "refresh_token", "refresh_token": refresh, "resource": self.resource}, "revoked-refresh"))
            self._rec("12b", "refresh token no longer usable after revocation", t.status == 400,
                      f"HTTP {t.status} error={self._oauth_error(t)!r}")
        else:
            self._skip("12b", "refresh token no longer usable after revocation", "no refresh_token was issued")

    def step_reconnect(self, token_body: dict[str, Any], first_uid: str | None, session: str | None) -> dict[str, Any]:
        """Refresh (if offered) then re-initialize; also probe stale-session behaviour."""
        refresh = token_body.get("refresh_token")
        current = token_body
        if refresh:
            t = self.token_request({"grant_type": "refresh_token", "refresh_token": refresh,
                                    "resource": self.resource}, "refresh")
            try:
                body = t.json()
            except ValueError:
                body = {}
            new_access = body.get("access_token") if isinstance(body, dict) else None
            if new_access:
                self.redact.add(new_access, "access_token")
            if isinstance(body, dict) and body.get("refresh_token"):
                self.redact.add(body["refresh_token"], "refresh_token")
            ok = t.status == 200 and bool(new_access)
            self._rec("13a", "refresh_token grant issues a new access token", ok,
                      f"HTTP {t.status} rotated={'yes' if body.get('refresh_token') and body.get('refresh_token') != refresh else 'no'}"
                      if ok else f"HTTP {t.status} error={self._oauth_error(t)!r}")
            if ok:
                current = body
                old = self._neg("old_refresh", self.token_request(
                    {"grant_type": "refresh_token", "refresh_token": refresh, "resource": self.resource}, "old-refresh"))
                if body.get("refresh_token") and body.get("refresh_token") != refresh:
                    self._rec("13b", "rotated-out refresh token is rejected", old.status == 400,
                              f"HTTP {old.status} error={self._oauth_error(old)!r}")
                else:
                    self._rec("13b", "refresh token rotation", None, "refresh token not rotated (allowed)")
        else:
            self._skip("13a", "refresh_token grant", "no refresh_token issued (offline_access not granted or unsupported)")
        new_session, who = self.mcp_connect(current["access_token"], "13")
        uid = (who or {}).get("user_id")
        self._rec("13c", "reconnect maps to the same Resonance identity", bool(uid) and uid == first_uid,
                  f"same_user={uid == first_uid}")
        # Stale / foreign session id must not be served.
        r, body = self.mcp(current["access_token"], {"jsonrpc": "2.0", "id": 9, "method": "tools/list"},
                           session="stale-" + secrets.token_urlsafe(12))
        served = r.status == 200 and isinstance(body, dict) and "result" in body
        self._rec("13d", "unknown Mcp-Session-Id is not served (404 lets clients reinitialize)",
                  not served, f"HTTP {r.status}" + (" -- stateless endpoint (no session binding)" if served and not new_session else ""))
        return current

    def step_no_leakage(self) -> None:
        leaks = []
        for tag, resp in self.negative_responses:
            found = self.redact.leaks(resp.text + " " + json.dumps(resp.headers))
            if found:
                leaks.append(f"{tag}: {found}")
        self._rec("E5", "no secret material appears in negative-path responses", not leaks,
                  "; ".join(leaks) or f"{len(self.negative_responses)} responses scanned")

    def step_consent_separation(self, who: dict[str, Any] | None) -> None:
        if not who:
            self._skip("E6", "OAuth consent does not share a thought", "no whoami payload")
            return
        owned = who.get("owned_sessions") or who.get("sessions") or []
        self._rec("E6", "OAuth consent grants client access only (no Thought was shared by connecting)",
                  len(owned) == 0, f"owned_sessions={len(owned)}")

    # -- driver ---------------------------------------------------------------
    def run(self) -> dict[str, Any]:
        challenge = self.step_unauthenticated_mcp()
        if self.step_protected_resource_metadata(challenge) and self.step_authorization_server_metadata():
            self.step_client_registration()
            pair = self.step_authorize_consent()
            token_body = self.step_token_exchange(*pair) if pair else None
            if token_body:
                session, who = self.mcp_connect(token_body["access_token"], "8-10")
                first_uid = (who or {}).get("user_id")
                self.step_consent_separation(who)
                self.step_wrong_verifier()
                self.step_replay(*pair)
                self.step_wrong_redirect()
                self.step_wrong_resource()
                self.step_pkce_required()
                self.step_caller_identity_ignored(first_uid)
                current = self.step_reconnect(token_body, first_uid, session)
                self.step_revoke_then_reuse(current)
        self.step_no_leakage()
        return self.report()

    def report(self) -> dict[str, Any]:
        counts = {k: sum(1 for s in self.steps if s.status == k) for k in ("PASS", "FAIL", "SKIP", "INFO")}
        return {"probe": PROBE_VERSION, "target": self.base, "resource": self.resource,
                "started_at": self.started_at, "issuer": self.issuer,
                "client_id_source": "registration" if self.asm.get("registration_endpoint") else "static",
                "steps": [s.__dict__ for s in self.steps], "summary": counts,
                "verdict": "PASS" if counts["FAIL"] == 0 else "FAIL", "redacted": True}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", required=True, help="origin serving /mcp, e.g. https://host")
    ap.add_argument("--client-id", default=None, help="pre-registered client_id (else RFC 7591 registration)")
    ap.add_argument("--redirect-uri", default="https://r15b-probe.invalid/callback")
    ap.add_argument("--consent", action="append", default=[], metavar="NAME=VALUE",
                    help="extra/override form field for the consent POST (repeatable)")
    ap.add_argument("--scope", default="offline_access")
    ap.add_argument("--timeout", type=float, default=15.0)
    ap.add_argument("--report", default=None, help="write the JSON report here (also printed)")
    a = ap.parse_args(argv)
    overrides = dict(kv.split("=", 1) for kv in a.consent if "=" in kv)
    probe = Probe(a.base, client_id=a.client_id, redirect_uri=a.redirect_uri,
                  consent_overrides=overrides, timeout=a.timeout, scope=a.scope or None)
    try:
        rep = probe.run()
    except URLError as exc:
        rep = probe.report()
        rep["verdict"] = "FAIL"
        rep["transport_error"] = str(exc)
    out = json.dumps(rep, indent=2, sort_keys=True)
    if a.report:
        with open(a.report, "w", encoding="utf-8") as fh:
            fh.write(out + "\n")
    print(out)
    return 0 if rep["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
