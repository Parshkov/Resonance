#!/usr/bin/env python3
"""R15D hosted-client onboarding acceptance harness (black-box, client-side).

Simulates exactly what a hosted MCP client (ChatGPT custom app, Claude custom
connector) does when a tester supplies **only** the canonical resource URL:

    https://resonance-production-cfe3.up.railway.app/mcp

and nothing else — no key, no bearer, no capability URL, no custom header.

The probe is *discovery-driven*: it learns every endpoint from server metadata,
never from hard-coded paths, so it proves the same flow a real client walks:

    unauthenticated /mcp  -> 401 + WWW-Authenticate: resource_metadata=...
      -> RFC 9728 protected-resource metadata (canonical resource + AS)
      -> RFC 8414 authorization-server metadata (endpoints, PKCE, scopes)
      -> [optional] dynamic client registration
      -> authorize: GET consent page, approve (login or guest) -> 302 code+state
      -> token: authorization_code + PKCE S256 -> access token (+ refresh)
      -> MCP initialize (Bearer) -> Mcp-Session-Id
      -> tools/list -> resonance_whoami
      -> [optional] prepare -> preview -> share -> discover smoke
      -> [optional] refresh rotation, revoke-then-reuse

This lane (#137 R15D) owns acceptance tooling only. The probe imports nothing
from the OAuth core (#134) or the product — it speaks HTTP to a running origin,
so it can be validated locally against a conformant server and then pointed at
production unchanged with `--base`.

Usage:
    python3 ops/hosted_onboarding_probe.py --base https://<origin> [--smoke]
    python3 ops/hosted_onboarding_probe.py --base http://127.0.0.1:8899 --smoke --refresh --revoke

Exit code 0 iff every *required* step passed; nonzero otherwise. `--json`
emits the full structured report (the #137 failure-report schema) for evidence.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import secrets
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import parse_qs, urlencode, urljoin, urlparse

# A hosted client always supplies its own callback. We never follow it (the
# client's server would); we read the 302 Location to extract code + state.
DEFAULT_REDIRECT = "https://client.example/callback"

# Cue-laden sample chat so the optional smoke's extractor yields a real graph
# (the accepted CueExtractor builds edges only from explicit lexical cues).
SAMPLE_CHAT = (
    "We keep missing the deadline because code review is a bottleneck. "
    "The bottleneck causes idle branches, and idle branches lead to merge "
    "conflicts, so throughput drops. Adding a second reviewer prevents the "
    "pile-up and supports faster merges."
)


def _pkce() -> tuple[str, str]:
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(48)).rstrip(b"=").decode("ascii")
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode("ascii")).digest()).rstrip(b"=").decode("ascii")
    return verifier, challenge


@dataclass
class Step:
    name: str
    ok: bool
    required: bool
    detail: str = ""
    http_status: int | None = None
    data: dict[str, Any] = field(default_factory=dict)

    def as_row(self) -> dict[str, Any]:
        return {"step": self.name, "ok": self.ok, "required": self.required,
                "http_status": self.http_status, "detail": self.detail, **self.data}


class ProbeFailure(Exception):
    """A required step failed; abort the sequence with the partial report."""


class OnboardingProbe:
    def __init__(self, base: str, *, redirect_uri: str = DEFAULT_REDIRECT,
                 verbose: bool = True, timeout: float = 20.0):
        self.base = base.rstrip("/")
        # canonical MCP resource the tester is given
        self.mcp_url = self.base if self.base.endswith("/mcp") else self.base + "/mcp"
        self.origin = f"{urlparse(self.mcp_url).scheme}://{urlparse(self.mcp_url).netloc}"
        self.redirect_uri = redirect_uri
        self.verbose = verbose
        self.timeout = timeout
        self.steps: list[Step] = []
        # discovered / issued state
        self.resource: str | None = None
        self.endpoints: dict[str, Any] = {}
        self.client_id = "resonance-probe"
        self.access_token: str | None = None
        self.refresh_token: str | None = None
        self.session_id: str | None = None
        self._mid = 0

    # -- low-level HTTP ---------------------------------------------------
    def _http(self, method: str, url: str, *, headers=None, body=None,
              follow_redirects=True):
        req = urllib.request.Request(url, method=method, data=body,
                                     headers=headers or {})
        opener = (urllib.request.build_opener()
                  if follow_redirects else urllib.request.build_opener(_NoRedirect))
        try:
            with opener.open(req, timeout=self.timeout) as r:
                return r.status, dict(r.headers), r.read()
        except urllib.error.HTTPError as e:
            return e.code, dict(e.headers), e.read()

    def _record(self, step: Step) -> Step:
        self.steps.append(step)
        if self.verbose:
            mark = "PASS" if step.ok else ("FAIL" if step.required else "warn")
            line = f"  [{mark}] {step.name}"
            if step.http_status is not None:
                line += f" (HTTP {step.http_status})"
            if step.detail:
                line += f" — {step.detail}"
            print(line, file=sys.stderr)
        if step.required and not step.ok:
            raise ProbeFailure(step.name)
        return step

    def _next_id(self) -> int:
        self._mid += 1
        return self._mid

    # -- 1. unauthenticated /mcp -> challenge -----------------------------
    def unauth_challenge(self) -> Step:
        body = json.dumps({"jsonrpc": "2.0", "id": self._next_id(),
                           "method": "initialize",
                           "params": {"protocolVersion": "2025-03-26"}}).encode()
        status, headers, _ = self._http("POST", self.mcp_url,
                                        headers={"Content-Type": "application/json"},
                                        body=body)
        www = headers.get("WWW-Authenticate", "") or headers.get("Www-Authenticate", "")
        meta_url = None
        for part in www.split(","):
            part = part.strip()
            if part.lower().startswith("bearer") and "resource_metadata=" in part:
                meta_url = part.split("resource_metadata=", 1)[1].strip().strip('"')
        ok = status == 401 and bool(meta_url)
        detail = ("401 with resource_metadata pointer" if ok
                  else f"expected 401 + WWW-Authenticate resource_metadata; got {status} / {www!r}")
        return self._record(Step("unauthenticated /mcp challenge", ok, True, detail,
                                 status, {"www_authenticate": www,
                                          "resource_metadata": meta_url}))

    # -- 2. discovery (RFC 9728 + RFC 8414) -------------------------------
    def discover(self, resource_metadata_url: str) -> Step:
        url = urljoin(self.origin + "/", resource_metadata_url)
        status, _, raw = self._http("GET", url)
        try:
            prm = json.loads(raw)
        except (ValueError, json.JSONDecodeError):
            return self._record(Step("protected-resource metadata", False, True,
                                     "not JSON", status))
        self.resource = prm.get("resource")
        servers = prm.get("authorization_servers") or []
        ok_prm = status == 200 and bool(self.resource) and bool(servers)
        self._record(Step("protected-resource metadata (RFC 9728)", ok_prm, True,
                          f"resource={self.resource}", status,
                          {"authorization_servers": servers}))
        # resource SHOULD be the canonical /mcp we were handed
        self._record(Step("resource == canonical /mcp", bool(self.resource
                     and self.resource.rstrip('/') == self.mcp_url.rstrip('/')), False,
                     f"advertised {self.resource} vs given {self.mcp_url}"))
        as_base = servers[0].rstrip("/")
        as_url = as_base + "/.well-known/oauth-authorization-server"
        status, _, raw = self._http("GET", as_url)
        try:
            asm = json.loads(raw)
        except (ValueError, json.JSONDecodeError):
            return self._record(Step("authorization-server metadata", False, True,
                                     "not JSON", status))
        self.endpoints = asm
        methods = asm.get("code_challenge_methods_supported") or []
        ok_as = (status == 200 and asm.get("authorization_endpoint")
                 and asm.get("token_endpoint") and "S256" in methods)
        return self._record(Step("authorization-server metadata (RFC 8414)", bool(ok_as),
                                 True, f"S256={'S256' in methods}", status,
                                 {"authorization_endpoint": asm.get("authorization_endpoint"),
                                  "token_endpoint": asm.get("token_endpoint"),
                                  "registration_endpoint": asm.get("registration_endpoint"),
                                  "scopes_supported": asm.get("scopes_supported")}))

    # -- 3. optional dynamic client registration --------------------------
    def register(self) -> Step | None:
        reg = self.endpoints.get("registration_endpoint")
        if not reg:
            return None
        body = json.dumps({"redirect_uris": [self.redirect_uri],
                           "client_name": "Resonance onboarding probe",
                           "token_endpoint_auth_method": "none"}).encode()
        status, _, raw = self._http("POST", reg,
                                    headers={"Content-Type": "application/json"}, body=body)
        try:
            doc = json.loads(raw)
        except (ValueError, json.JSONDecodeError):
            doc = {}
        cid = doc.get("client_id")
        if status in (200, 201) and cid:
            self.client_id = cid
        return self._record(Step("dynamic client registration (RFC 7591)",
                                 status in (200, 201) and bool(cid), False,
                                 f"client_id={cid}", status))

    # -- 4. authorize: consent page + approve -> code + state -------------
    def authorize(self, *, user_id: str | None = None, recovery: str | None = None,
                  scope: str = "resonance.read resonance.write offline_access") -> Step:
        verifier, challenge = _pkce()
        self._verifier = verifier
        state = secrets.token_urlsafe(16)
        self._state = state
        authz = self.endpoints["authorization_endpoint"]
        params = {"response_type": "code", "client_id": self.client_id,
                  "redirect_uri": self.redirect_uri, "code_challenge": challenge,
                  "code_challenge_method": "S256", "state": state, "scope": scope}
        if self.resource:
            params["resource"] = self.resource
        # (a) GET the consent page a human would see
        status, headers, raw = self._http("GET", authz + "?" + urlencode(params))
        is_html = "text/html" in (headers.get("Content-Type", "").lower())
        self._record(Step("authorize consent page (GET)", status == 200 and is_html, True,
                          "human consent screen rendered", status))
        # (b) approve — guest continuation unless a real account was supplied
        form = dict(params, decision="approve")
        if user_id and recovery:
            form["user_id"] = user_id
            form["recovery_secret"] = recovery
        status, headers, _ = self._http("POST", authz,
                                        headers={"Content-Type": "application/x-www-form-urlencoded"},
                                        body=urlencode(form).encode(), follow_redirects=False)
        loc = headers.get("Location", "")
        q = parse_qs(urlparse(loc).query)
        code = (q.get("code") or [None])[0]
        got_state = (q.get("state") or [None])[0]
        ok = status == 302 and bool(code) and got_state == state
        detail = ("302 to redirect_uri with code + exact state" if ok
                  else f"status={status} loc={loc!r} state_match={got_state == state}")
        self._code = code
        return self._record(Step("authorize approve -> code + state", ok, True, detail,
                                 status, {"state_round_trip": got_state == state}))

    # -- 5. token exchange ------------------------------------------------
    def token(self) -> Step:
        form = {"grant_type": "authorization_code", "code": self._code,
                "code_verifier": self._verifier, "redirect_uri": self.redirect_uri,
                "client_id": self.client_id}
        if self.resource:
            form["resource"] = self.resource
        status, _, raw = self._http("POST", self.endpoints["token_endpoint"],
                                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                                    body=urlencode(form).encode())
        try:
            tok = json.loads(raw)
        except (ValueError, json.JSONDecodeError):
            tok = {}
        self.access_token = tok.get("access_token")
        self.refresh_token = tok.get("refresh_token")
        ok = status == 200 and bool(self.access_token)
        aud = tok.get("aud")
        return self._record(Step("token exchange (authorization_code + PKCE)", ok, True,
                                 f"aud={aud} refresh={'yes' if self.refresh_token else 'no'}",
                                 status, {"aud": aud, "scope": tok.get("scope")}))

    # -- 6-8. MCP initialize / tools / whoami -----------------------------
    def _rpc(self, method: str, params: dict | None = None, *, mid: int | None = None):
        headers = {"Content-Type": "application/json",
                   "Authorization": f"Bearer {self.access_token}"}
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id
        payload = {"jsonrpc": "2.0", "id": mid if mid is not None else self._next_id(),
                   "method": method}
        if params is not None:
            payload["params"] = params
        status, resp_headers, raw = self._http("POST", self.mcp_url,
                                               headers=headers, body=json.dumps(payload).encode())
        sid = resp_headers.get("Mcp-Session-Id")
        if sid:
            self.session_id = sid
        try:
            doc = json.loads(raw) if raw else None
        except (ValueError, json.JSONDecodeError):
            doc = None
        return status, doc

    def initialize(self) -> Step:
        status, doc = self._rpc("initialize", {"protocolVersion": "2025-03-26"})
        proto = (((doc or {}).get("result") or {}).get("protocolVersion"))
        ok = status == 200 and proto == "2025-03-26" and bool(self.session_id)
        return self._record(Step("MCP initialize (Bearer)", ok, True,
                                 f"session={'issued' if self.session_id else 'missing'}",
                                 status))

    def tools_list(self) -> Step:
        status, doc = self._rpc("tools/list")
        tools = (((doc or {}).get("result") or {}).get("tools")) or []
        names = [t.get("name") for t in tools]
        ok = status == 200 and any(n and n.startswith("resonance_") for n in names)
        return self._record(Step("tools/list", ok, True, f"{len(names)} tools", status,
                                 {"tool_names": names}))

    def whoami(self) -> Step:
        status, doc = self._rpc("tools/call",
                                {"name": "resonance_whoami", "arguments": {}})
        sc = ((((doc or {}).get("result") or {}).get("structuredContent")) or {})
        uid = sc.get("user_id")
        ok = status == 200 and isinstance(uid, str) and uid.startswith("person-")
        return self._record(Step("resonance_whoami", ok, True, f"user_id={uid}", status))

    # -- optional smoke: prepare -> preview -> share -> discover ----------
    def _call(self, name: str, arguments: dict):
        status, doc = self._rpc("tools/call", {"name": name, "arguments": arguments})
        result = ((doc or {}).get("result") or {})
        return status, result, (result.get("structuredContent") or {})

    def smoke(self) -> Step:
        try:
            _, res, sc = self._call("resonance_prepare_thought",
                                    {"context": SAMPLE_CHAT,
                                     "presentation": {"domain": "engineering",
                                                      "topic": "process",
                                                      "cluster_id": "c1"},
                                     "intent": {"share_display_profile": True}})
            if res.get("isError") or not sc.get("draft_id"):
                return self._record(Step("post-connect smoke", False, False,
                                         f"prepare produced no draft ({sc})"))
            draft = sc["draft_id"]
            _, res, sc = self._call("resonance_get_share_preview", {"draft_id": draft})
            token = sc.get("confirmation_token")
            _, res, sc = self._call("resonance_share_thought",
                                    {"draft_id": draft, "confirmation_token": token,
                                     "confirm": True})
            if res.get("isError") or not sc.get("session_id"):
                return self._record(Step("post-connect smoke", False, False,
                                         f"share failed ({sc})"))
            session_id = sc["session_id"]
            _, res, sc = self._call("resonance_discover", {"session_id": session_id, "k": 5})
            ok = not res.get("isError")
            n = len(sc.get("matches", []))
            return self._record(Step("post-connect smoke (prepare→preview→share→discover)",
                                     ok, False, f"shared {session_id}, discover ok ({n} matches)"))
        except Exception as exc:  # noqa: BLE001
            return self._record(Step("post-connect smoke", False, False, f"exception: {exc}"))

    def refresh(self) -> Step | None:
        if not self.refresh_token:
            return self._record(Step("refresh rotation", False, False,
                                     "no refresh_token issued (offline_access?)"))
        old = self.refresh_token
        form = {"grant_type": "refresh_token", "refresh_token": old,
                "client_id": self.client_id}
        status, _, raw = self._http("POST", self.endpoints["token_endpoint"],
                                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                                    body=urlencode(form).encode())
        try:
            tok = json.loads(raw)
        except (ValueError, json.JSONDecodeError):
            tok = {}
        new_access = tok.get("access_token")
        new_refresh = tok.get("refresh_token")
        rotated = bool(new_refresh) and new_refresh != old
        if new_access:
            self.access_token = new_access
        if new_refresh:
            self.refresh_token = new_refresh
        self._record(Step("refresh grant -> new access token", status == 200 and bool(new_access),
                          False, f"rotated={rotated}", status))
        # reuse of the OLD refresh token must now fail (rotation/reuse detection)
        status2, _, _ = self._http("POST", self.endpoints["token_endpoint"],
                                   headers={"Content-Type": "application/x-www-form-urlencoded"},
                                   body=urlencode({"grant_type": "refresh_token",
                                                   "refresh_token": old,
                                                   "client_id": self.client_id}).encode())
        return self._record(Step("old refresh token reuse rejected", status2 >= 400, False,
                                 f"reuse returned {status2}", status2))

    def revoke_then_reuse(self) -> Step:
        # /oauth/revoke is not always in metadata; derive from AS base if absent.
        revoke = self.endpoints.get("revocation_endpoint")
        if not revoke:
            servers = (self.steps and None)
            revoke = self.origin + "/oauth/revoke"
        status, _, _ = self._http("POST", revoke,
                                  headers={"Authorization": f"Bearer {self.access_token}"},
                                  body=b"")
        self._record(Step("revoke (disconnect)", status == 200, False,
                          "subject grants revoked", status))
        # after revoke, the refresh token must no longer mint access
        if self.refresh_token:
            status2, _, _ = self._http("POST", self.endpoints["token_endpoint"],
                                       headers={"Content-Type": "application/x-www-form-urlencoded"},
                                       body=urlencode({"grant_type": "refresh_token",
                                                       "refresh_token": self.refresh_token,
                                                       "client_id": self.client_id}).encode())
            return self._record(Step("refresh after revoke rejected", status2 >= 400, False,
                                     f"returned {status2}", status2))
        return self.steps[-1]

    # -- orchestration ----------------------------------------------------
    def run(self, *, smoke: bool = False, refresh: bool = False,
            revoke: bool = False, user_id: str | None = None,
            recovery: str | None = None) -> dict[str, Any]:
        try:
            challenge = self.unauth_challenge()
            self.discover(challenge.data["resource_metadata"])
            self.register()
            self.authorize(user_id=user_id, recovery=recovery)
            self.token()
            self.initialize()
            self.tools_list()
            self.whoami()
            if smoke:
                self.smoke()
            if refresh:
                self.refresh()
            if revoke:
                self.revoke_then_reuse()
        except ProbeFailure:
            pass  # required step failed; report reflects it
        required = [s for s in self.steps if s.required]
        passed = all(s.ok for s in required)
        return {
            "base": self.base,
            "canonical_mcp": self.mcp_url,
            "required_all_passed": passed,
            "required_passed": sum(s.ok for s in required),
            "required_total": len(required),
            "steps": [s.as_row() for s in self.steps],
        }


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):  # noqa: D401
        return None  # capture 302 instead of following it


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", required=True,
                    help="origin or canonical /mcp URL, e.g. https://host or https://host/mcp")
    ap.add_argument("--redirect-uri", default=DEFAULT_REDIRECT)
    ap.add_argument("--smoke", action="store_true", help="run prepare→preview→share→discover")
    ap.add_argument("--refresh", action="store_true", help="exercise refresh rotation + reuse-reject")
    ap.add_argument("--revoke", action="store_true", help="exercise revoke then reuse-reject")
    ap.add_argument("--user-id", default=None, help="existing account (else guest continuation)")
    ap.add_argument("--recovery", default=None)
    ap.add_argument("--json", action="store_true", help="emit the full JSON report to stdout")
    args = ap.parse_args(argv)

    probe = OnboardingProbe(args.base, redirect_uri=args.redirect_uri)
    print(f"Resonance hosted-client onboarding probe -> {probe.mcp_url}", file=sys.stderr)
    report = probe.run(smoke=args.smoke, refresh=args.refresh, revoke=args.revoke,
                       user_id=args.user_id, recovery=args.recovery)
    if args.json:
        print(json.dumps(report, indent=2))
    verdict = "ONBOARDING PASS" if report["required_all_passed"] else "ONBOARDING FAIL"
    print(f"\n{verdict}: {report['required_passed']}/{report['required_total']} "
          f"required steps passed", file=sys.stderr)
    return 0 if report["required_all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
