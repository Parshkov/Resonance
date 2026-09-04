"""Canonical user-facing OAuth 2.1 core for the Resonance remote MCP resource.

A hosted MCP client (ChatGPT, Claude, ...) is handed only the ordinary resource
URL — `https://<origin>/mcp` — and must connect through standard authorization,
with no manually created MCP key, bearer token, capability URL, or custom
header. This module implements exactly that surface and nothing else:

* RFC 9728 protected-resource metadata for `/mcp`, and the 401 `WWW-Authenticate`
  challenge that points a client at it;
* RFC 8414 authorization-server metadata;
* the Authorization Code flow with mandatory PKCE (S256 only), strict `state`
  round-trip, and strict `redirect_uri` validation performed BEFORE any redirect
  (no open redirect);
* RFC 7591 dynamic client registration, plus ephemeral public clients so a
  hosted client that does not register can still connect with an exact
  redirect_uri bound per authorization;
* RFC 8707 resource indicators — every grant is audience-bound to `{issuer}/mcp`;
* a browser authorization endpoint (`GET /oauth/authorize`) that renders an
  explicit human consent screen, `POST /oauth/authorize` that authenticates
  through the ACCEPTED R12 identity model (an existing account via recovery
  secret, the current browser cookie account, or a fresh pseudonymous guest) and
  redirects back with a single-use code + the exact `state`;
* `POST /oauth/token` (authorization_code + refresh_token grants; refresh only
  when `offline_access` was granted, with rotation);
* `POST /oauth/revoke` (RFC 7009).

The issued access token IS the accepted R12 access token — there is no parallel
user store and identity is never caller-selected beyond the R12 authentication
proof. The core is transport-neutral: `handle(...)` returns `(status, headers,
body)` and never touches a socket, so the standalone Streamable-HTTP server and
the production `ProductHandler` mount the same object (R15C). The issuer/all
absolute URLs are injected, never read from the `Host` header. No token, code,
verifier, or recovery secret is ever logged or echoed outside the token
response body and the redirect `Location`.

Demo/known limits are declared in the README; this is the client-interop
authorization surface, not a full multi-tenant IdP.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import html
import json
import secrets
import time
from dataclasses import dataclass, field
from http.cookies import SimpleCookie
from typing import Any, Mapping
from urllib.parse import urlencode

# The single resource this authorization server protects, relative to issuer.
RESOURCE_PATH = "/mcp"
COOKIE_NAME = "resonance_token"
DEFAULT_CODE_TTL = 300           # seconds a single-use auth code lives
DEFAULT_TOKEN_TTL = 3600         # advertised access-token lifetime hint
DEFAULT_REFRESH_TTL = 30 * 24 * 3600
SCOPE_OFFLINE = "offline_access"
SUPPORTED_SCOPES = ("resonance", SCOPE_OFFLINE)


def _s256(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("ascii")).hexdigest()


def _json_body(doc: Any) -> bytes:
    return json.dumps(doc, ensure_ascii=False).encode("utf-8")


class OAuthError(Exception):
    """An OAuth-protocol error carrying the RFC error code and HTTP status."""

    def __init__(self, error: str, description: str = "", status: int = 400):
        super().__init__(f"{error}: {description}" if description else error)
        self.error = error
        self.description = description
        self.status = status

    def as_body(self) -> dict[str, str]:
        body = {"error": self.error}
        if self.description:
            body["error_description"] = self.description
        return body


# ---------------------------------------------------------------------------
# grant store (in-memory default; interface so R15C can back it with Postgres)
# ---------------------------------------------------------------------------

CONSENT_CSS = """
:root { color-scheme: dark; --canvas: #0a0a0a; --panel: rgba(255,255,255,.045); --border: rgba(255,255,255,.12);
  --text: #f2eee8; --text-2: #aaa49b; --gold: #c9b8a0; --bright: #e8d5b7; --rust: #b66d58;
  --serif: ui-serif, Georgia, Cambria, "Times New Roman", serif;
  --sans: Inter, ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  --mono: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
* { box-sizing: border-box; }
body { margin: 0; min-height: 100vh; background: radial-gradient(1200px 600px at 20% -10%, rgba(201,184,160,.12), transparent 60%), var(--canvas);
  color: var(--text); font: 16px/1.55 var(--sans); display: flex; align-items: flex-start; justify-content: center; padding: 6vh 16px; }
main.consent { width: min(640px, 100%); background: var(--panel); border: 1px solid var(--border); border-radius: 22px; padding: 32px 34px 28px; }
.brand { display: flex; align-items: center; gap: 10px; margin: 0 0 18px; font: 600 12px/1 var(--sans); letter-spacing: .18em; text-transform: uppercase; color: var(--text-2); }
.mark { width: 18px; height: 18px; border-radius: 50%; border: 2px solid var(--gold); box-shadow: inset 0 0 0 4px var(--canvas), inset 0 0 0 6px var(--gold); }
h1 { font: 500 30px/1.15 var(--serif); margin: 0 0 14px; color: var(--bright); }
p { margin: 0 0 12px; color: var(--text-2); }
p strong, p em { color: var(--text); }
code { font: 13px var(--mono); color: var(--gold); word-break: break-all; }
fieldset { border: 1px solid var(--border); border-radius: 14px; padding: 14px 16px 6px; margin: 18px 0 20px; }
legend { padding: 0 8px; font: 600 12px/1 var(--sans); letter-spacing: .14em; text-transform: uppercase; color: var(--text-2); }
label.opt { display: block; margin: 6px 0 10px; color: var(--text); cursor: pointer; }
fieldset p { margin: 8px 0; }
fieldset p label { display: flex; flex-direction: column; gap: 6px; color: var(--text-2); font-size: 14px; }
input[type=text], input[type=password] { width: 100%; padding: 10px 12px; border-radius: 10px; border: 1px solid var(--border);
  background: rgba(0,0,0,.35); color: var(--text); font: 15px var(--mono); }
input[type=text]:focus, input[type=password]:focus { outline: 2px solid var(--gold); outline-offset: 1px; }
.actions { display: flex; gap: 12px; flex-wrap: wrap; }
button { cursor: pointer; border-radius: 999px; padding: 12px 22px; font: 600 15px var(--sans); border: 1px solid var(--border);
  background: transparent; color: var(--text); }
button.primary { background: var(--bright); color: #14120f; border-color: var(--bright); }
button:hover { filter: brightness(1.08); }
.fine { margin: 18px 0 0; font-size: 13px; color: var(--text-2); }
"""


@dataclass
class GrantStore:
    """Durable-shaped store for auth codes, refresh grants and client records.

    Records are plain JSON-serialisable dicts so a production backend can persist
    them without knowing the OAuth types. The default is process-memory; a
    redeploy therefore invalidates codes/refresh grants, which is documented.
    """

    clock: Any = time.time
    codes: dict[str, dict[str, Any]] = field(default_factory=dict)
    refresh: dict[str, dict[str, Any]] = field(default_factory=dict)
    clients: dict[str, dict[str, Any]] = field(default_factory=dict)

    # -- authorization codes --------------------------------------------
    def put_code(self, code: str, record: Mapping[str, Any]) -> None:
        self.codes[code] = dict(record)

    def take_code(self, code: str) -> dict[str, Any] | None:
        """Single-use: pop so a replay cannot find it, whatever the outcome."""
        record = self.codes.pop(code, None)
        if record is None:
            return None
        if record.get("expires", 0) < self.clock():
            return None
        return record

    # -- refresh grants -------------------------------------------------
    def put_refresh(self, token: str, record: Mapping[str, Any]) -> None:
        self.refresh[_hash(token)] = dict(record)

    def take_refresh(self, token: str) -> dict[str, Any] | None:
        record = self.refresh.pop(_hash(token), None)   # rotation: single use
        if record is None:
            return None
        if record.get("expires", 0) < self.clock():
            return None
        return record

    def revoke_refresh(self, token: str) -> bool:
        return self.refresh.pop(_hash(token), None) is not None

    def pop_refresh(self, token: str) -> dict[str, Any] | None:
        """Revoke a refresh grant and return its record (for the RFC 7009
        cascade onto the sibling access token); None when unknown."""
        return self.refresh.pop(_hash(token), None)

    def revoke_refresh_for_subject(self, user_id: str) -> int:
        gone = [h for h, r in self.refresh.items() if r.get("user_id") == user_id]
        for h in gone:
            self.refresh.pop(h, None)
        return len(gone)

    # -- clients --------------------------------------------------------
    def put_client(self, client_id: str, record: Mapping[str, Any]) -> None:
        self.clients[client_id] = dict(record)

    def get_client(self, client_id: str) -> dict[str, Any] | None:
        return self.clients.get(client_id)


class RepositoryGrantStore(GrantStore):
    """GrantStore backed by the product repository (PostgreSQL/SQLite).

    Same record shapes and single-use semantics as the in-memory store, but
    codes, refresh grants and client registrations survive a redeploy, so a
    hosted MCP client is not forced to re-authorize after every release.
    Secrets (codes, refresh tokens) are stored under their SHA-256 only.
    """

    KIND_CODE = "code"
    KIND_REFRESH = "refresh"
    KIND_CLIENT = "client"

    def __init__(self, repository: Any, *, clock: Any = time.time) -> None:
        super().__init__(clock=clock)
        self.repository = repository

    # -- authorization codes --------------------------------------------
    def put_code(self, code: str, record: Mapping[str, Any]) -> None:
        self.repository.put_grant(self.KIND_CODE, _hash(code), dict(record),
                                  expires_at=record.get("expires"))

    def take_code(self, code: str) -> dict[str, Any] | None:
        record = self.repository.pop_grant(self.KIND_CODE, _hash(code))
        if record is None or record.get("expires", 0) < self.clock():
            return None
        return dict(record)

    # -- refresh grants -------------------------------------------------
    def put_refresh(self, token: str, record: Mapping[str, Any]) -> None:
        self.repository.put_grant(self.KIND_REFRESH, _hash(token), dict(record),
                                  user_id=record.get("user_id"), expires_at=record.get("expires"))

    def take_refresh(self, token: str) -> dict[str, Any] | None:
        record = self.repository.pop_grant(self.KIND_REFRESH, _hash(token))
        if record is None or record.get("expires", 0) < self.clock():
            return None
        return dict(record)

    def revoke_refresh(self, token: str) -> bool:
        return self.repository.pop_grant(self.KIND_REFRESH, _hash(token)) is not None

    def pop_refresh(self, token: str) -> dict[str, Any] | None:
        record = self.repository.pop_grant(self.KIND_REFRESH, _hash(token))
        return dict(record) if record is not None else None

    def revoke_refresh_for_subject(self, user_id: str) -> int:
        return int(self.repository.delete_grants_for_user(self.KIND_REFRESH, user_id))

    # -- clients --------------------------------------------------------
    def put_client(self, client_id: str, record: Mapping[str, Any]) -> None:
        self.repository.put_grant(self.KIND_CLIENT, client_id, dict(record))

    def get_client(self, client_id: str) -> dict[str, Any] | None:
        record = self.repository.get_grant(self.KIND_CLIENT, client_id)
        return dict(record) if record is not None else None


# Backwards-compatible alias: the retired demo PKCE store name still resolves so
# any lingering import does not explode; new code uses GrantStore.
CodeStore = GrantStore


# ---------------------------------------------------------------------------
# the core
# ---------------------------------------------------------------------------

@dataclass
class OAuthResult:
    status: int
    headers: dict[str, str]
    body: bytes


class OAuthCore:
    """Standards-compatible OAuth for the Resonance MCP resource, transport-free.

    `identity` is the accepted R12 `IdentityService`. The bearer token this core
    issues IS an R12 access token; `resolve_bearer` is the single audience check
    the `/mcp` transport calls before dispatch.
    """

    def __init__(self, identity: Any, store: GrantStore | None = None, *,
                 code_ttl: int = DEFAULT_CODE_TTL,
                 refresh_ttl: int = DEFAULT_REFRESH_TTL,
                 clock: Any = time.time) -> None:
        self.identity = identity
        self.store = store or GrantStore(clock=clock)
        self.code_ttl = code_ttl
        self.refresh_ttl = refresh_ttl
        self.clock = clock

    # -- public helpers used by the transport ---------------------------
    def resource_for(self, issuer: str) -> str:
        return issuer.rstrip("/") + RESOURCE_PATH

    def challenge_header(self, issuer: str, *, error: str = "invalid_token") -> str:
        """The `WWW-Authenticate` value for an unauthenticated `/mcp` request."""
        rm = issuer.rstrip("/") + "/.well-known/oauth-protected-resource"
        parts = ['Bearer realm="resonance"']
        if error:
            parts.append(f'error="{error}"')
        parts.append(f'resource_metadata="{rm}"')
        return ", ".join(parts)

    def resolve_bearer(self, token: str | None, *, resource: str) -> str | None:
        """Return the R12 access token to authenticate `/mcp` with, or None.

        None means: no token, unknown/expired/revoked token, or a token bound to
        a different audience. With a single protected resource the audience check
        is structural (every token this AS issues is for `resource`), but the
        method is the one seam R15C wires, and it never raises.
        """
        if not token:
            return None
        try:
            self.identity.authenticate(token)
        except Exception:  # noqa: BLE001 -- any auth failure is "no subject"
            return None
        return token

    # -- routing --------------------------------------------------------
    def handle(self, method: str, path: str, query: Mapping[str, list[str]],
               headers: Mapping[str, str], body: bytes, *, issuer: str) -> OAuthResult:
        issuer = issuer.rstrip("/")
        try:
            if method == "GET" and path == "/.well-known/oauth-protected-resource":
                return self._ok(self._protected_resource_metadata(issuer))
            # RFC 9728 also allows the resource path to be appended.
            if method == "GET" and path == "/.well-known/oauth-protected-resource/mcp":
                return self._ok(self._protected_resource_metadata(issuer))
            if method == "GET" and path == "/.well-known/oauth-authorization-server":
                return self._ok(self._authorization_server_metadata(issuer))
            if method == "GET" and path == "/.well-known/oauth-authorization-server/mcp":
                return self._ok(self._authorization_server_metadata(issuer))
            if path == "/oauth/consent.css" and method == "GET":
                return OAuthResult(200, {"Content-Type": "text/css; charset=utf-8",
                                         "Cache-Control": "public, max-age=3600"},
                                   CONSENT_CSS.encode("utf-8"))
            if path == "/oauth/register" and method == "POST":
                return self._register(body)
            if path == "/oauth/authorize" and method == "GET":
                return self._authorize_get(query, headers, issuer)
            if path == "/oauth/authorize" and method == "POST":
                return self._authorize_post(body, headers, issuer)
            if path == "/oauth/token" and method == "POST":
                return self._token(body, issuer)
            if path == "/oauth/revoke" and method == "POST":
                return self._revoke(body)
            return OAuthResult(404, {"Content-Type": "application/json"},
                               _json_body({"error": "not_found"}))
        except OAuthError as exc:
            return OAuthResult(exc.status, {"Content-Type": "application/json"},
                               _json_body(exc.as_body()))

    # -- metadata -------------------------------------------------------
    def _protected_resource_metadata(self, issuer: str) -> dict[str, Any]:
        return {
            "resource": self.resource_for(issuer),
            "authorization_servers": [issuer],
            "scopes_supported": list(SUPPORTED_SCOPES),
            "bearer_methods_supported": ["header"],
            "resource_documentation": issuer + "/",
        }

    def _authorization_server_metadata(self, issuer: str) -> dict[str, Any]:
        return {
            "issuer": issuer,
            "authorization_endpoint": issuer + "/oauth/authorize",
            "token_endpoint": issuer + "/oauth/token",
            "registration_endpoint": issuer + "/oauth/register",
            "revocation_endpoint": issuer + "/oauth/revoke",
            "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code", "refresh_token"],
            "code_challenge_methods_supported": ["S256"],
            "token_endpoint_auth_methods_supported": ["none"],
            "revocation_endpoint_auth_methods_supported": ["none"],
            "scopes_supported": list(SUPPORTED_SCOPES),
            "resource_indicators_supported": True,
        }

    # -- dynamic client registration (RFC 7591) -------------------------
    def _register(self, body: bytes) -> OAuthResult:
        try:
            doc = json.loads(body.decode("utf-8") or "{}")
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise OAuthError("invalid_client_metadata", "body must be JSON")
        if not isinstance(doc, dict):
            raise OAuthError("invalid_client_metadata", "body must be a JSON object")
        redirects = doc.get("redirect_uris")
        if not isinstance(redirects, list) or not redirects or not all(
                isinstance(u, str) and self._redirect_shape_ok(u) for u in redirects):
            raise OAuthError("invalid_redirect_uri",
                             "redirect_uris must be a non-empty list of absolute https/loopback URIs")
        client_id = "resonance-client-" + secrets.token_hex(8)
        record = {
            "client_id": client_id,
            "redirect_uris": list(redirects),
            "grant_types": doc.get("grant_types") or ["authorization_code", "refresh_token"],
            "response_types": doc.get("response_types") or ["code"],
            "token_endpoint_auth_method": "none",
            "client_name": str(doc.get("client_name", ""))[:200],
            "created_at": int(self.clock()),
        }
        self.store.put_client(client_id, record)
        out = {k: record[k] for k in ("client_id", "redirect_uris", "grant_types",
                                      "response_types", "token_endpoint_auth_method",
                                      "client_name")}
        out["client_id_issued_at"] = record["created_at"]
        return OAuthResult(201, {"Content-Type": "application/json"}, _json_body(out))

    @staticmethod
    def _redirect_shape_ok(uri: str) -> bool:
        # Absolute https, or http only for loopback (native/dev clients). No
        # fragment. This is the shape gate; exact-match is enforced per grant.
        if "#" in uri:
            return False
        if uri.startswith("https://"):
            return True
        if uri.startswith("http://"):
            host = uri[len("http://"):].split("/", 1)[0].split(":", 1)[0]
            return host in ("127.0.0.1", "localhost", "::1")
        # Custom app schemes (e.g. a native client) are allowed if they are absolute.
        return "://" in uri and not uri.startswith("javascript:")

    # -- authorization endpoint -----------------------------------------
    def _authorize_params(self, params: Mapping[str, str], issuer: str) -> dict[str, str]:
        """Validate everything that must be right BEFORE any redirect can be
        emitted. redirect_uri/client_id problems are shown on-page, never
        redirected (an unvalidated redirect_uri is an open redirect)."""
        client_id = params.get("client_id", "")
        redirect_uri = params.get("redirect_uri", "")
        if not client_id:
            raise OAuthError("invalid_request", "client_id required")
        if not redirect_uri or not self._redirect_shape_ok(redirect_uri):
            raise OAuthError("invalid_request", "a valid absolute redirect_uri is required")
        client = self.store.get_client(client_id)
        if client is not None and redirect_uri not in client["redirect_uris"]:
            raise OAuthError("invalid_request", "redirect_uri not registered for this client")
        # Past this point redirect_uri is trusted enough to redirect errors to it.
        resp_type = params.get("response_type", "")
        if resp_type != "code":
            raise OAuthError("unsupported_response_type", "only response_type=code", status=302)
        if params.get("code_challenge_method") != "S256":
            raise OAuthError("invalid_request", "PKCE code_challenge_method=S256 required", status=302)
        if not params.get("code_challenge"):
            raise OAuthError("invalid_request", "code_challenge required", status=302)
        if not params.get("state"):
            raise OAuthError("invalid_request", "state is required", status=302)
        resource = params.get("resource") or self.resource_for(issuer)
        if resource.rstrip("/") != self.resource_for(issuer):
            raise OAuthError("invalid_target", "resource must be this MCP endpoint", status=302)
        scope = params.get("scope", "resonance")
        return {"client_id": client_id, "redirect_uri": redirect_uri,
                "code_challenge": params["code_challenge"],
                "state": params["state"], "resource": self.resource_for(issuer),
                "scope": scope}

    def _flatten(self, query: Mapping[str, list[str]]) -> dict[str, str]:
        return {k: (v[0] if isinstance(v, list) else v) for k, v in query.items()}

    def _authorize_get(self, query: Mapping[str, list[str]], headers: Mapping[str, str],
                       issuer: str) -> OAuthResult:
        params = self._flatten(query)
        try:
            clean = self._authorize_params(params, issuer)
        except OAuthError as exc:
            if exc.status == 302 and params.get("redirect_uri") and self._redirect_shape_ok(
                    params["redirect_uri"]):
                return self._redirect_error(params["redirect_uri"], exc, params.get("state"))
            raise
        current = self._cookie_subject(headers)
        html_page = self._consent_page(clean, current_account=current)
        return OAuthResult(200, {"Content-Type": "text/html; charset=utf-8",
                                 "Cache-Control": "no-store"},
                           html_page.encode("utf-8"))

    def _authorize_post(self, body: bytes, headers: Mapping[str, str],
                        issuer: str) -> OAuthResult:
        form = self._flatten(self._parse_form(body))
        # Re-validate everything; never trust the page. A redirect-eligible error
        # (redirect_uri already proven) is returned TO the client as a redirect,
        # exactly as the spec requires, not as an on-page JSON body.
        try:
            clean = self._authorize_params(form, issuer)
        except OAuthError as exc:
            if exc.status == 302 and form.get("redirect_uri") and \
                    self._redirect_shape_ok(form["redirect_uri"]):
                return self._redirect_error(form["redirect_uri"], exc, form.get("state"))
            raise
        decision = form.get("decision", "")
        if decision != "approve":
            return self._redirect_error(clean["redirect_uri"],
                                        OAuthError("access_denied", "user declined", status=302),
                                        clean["state"])
        try:
            access_token, _issued = self._authenticate_subject(form, headers)
        except OAuthError as exc:
            # Authentication failure (bad recovery secret, no active session) is
            # reported back to the client as access_denied on the redirect.
            return self._redirect_error(clean["redirect_uri"], exc, clean["state"])
        code = secrets.token_urlsafe(24)
        self.store.put_code(code, {
            "access_token": access_token,
            "code_challenge": clean["code_challenge"],
            "redirect_uri": clean["redirect_uri"],
            "client_id": clean["client_id"],
            "resource": clean["resource"],
            "scope": clean["scope"],
            "expires": self.clock() + self.code_ttl,
        })
        location = clean["redirect_uri"] + ("&" if "?" in clean["redirect_uri"] else "?") + \
            urlencode({"code": code, "state": clean["state"]})
        return OAuthResult(302, {"Location": location, "Cache-Control": "no-store"}, b"")

    def _authenticate_subject(self, form: Mapping[str, str],
                              headers: Mapping[str, str]) -> tuple[str, Any]:
        """Resolve the R12 subject the grant binds to. Identity is proven, never
        asserted: an existing account (user_id + recovery secret), the current
        browser cookie account, or a fresh pseudonymous guest. A fresh agent
        session is always minted for the client, never the browser cookie token."""
        identity = self.identity
        choice = form.get("identity", "")
        if choice == "login" or (form.get("user_id") and form.get("recovery_secret")):
            try:
                creds = identity.login(form.get("user_id", ""),
                                       form.get("recovery_secret", ""),
                                       actor_type="agent")
            except Exception as exc:  # noqa: BLE001
                raise OAuthError("access_denied", type(exc).__name__)
            return creds.access_token, creds
        if choice == "current":
            subject = self._cookie_subject(headers)
            if not subject:
                raise OAuthError("access_denied", "no active browser session to continue")
            creds = identity._issue_session(subject, actor_type="agent")  # noqa: SLF001
            return creds.access_token, creds
        # default: guest continuation
        creds = identity.register_guest(actor_type="agent")
        return creds.access_token, creds

    def _cookie_subject(self, headers: Mapping[str, str]) -> str | None:
        raw = headers.get("Cookie") or headers.get("cookie") or ""
        if not raw:
            return None
        jar = SimpleCookie()
        try:
            jar.load(raw)
        except Exception:  # noqa: BLE001
            return None
        morsel = jar.get(COOKIE_NAME)
        if morsel is None or not morsel.value:
            return None
        try:
            return self.identity.authenticate(morsel.value).user_id
        except Exception:  # noqa: BLE001
            return None

    # -- token endpoint -------------------------------------------------
    def _token(self, body: bytes, issuer: str) -> OAuthResult:
        form = self._flatten(self._parse_form(body))
        grant = form.get("grant_type")
        if grant == "authorization_code":
            return self._token_auth_code(form, issuer)
        if grant == "refresh_token":
            return self._token_refresh(form, issuer)
        raise OAuthError("unsupported_grant_type", "authorization_code or refresh_token")

    def _token_auth_code(self, form: Mapping[str, str], issuer: str) -> OAuthResult:
        record = self.store.take_code(form.get("code", ""))
        if record is None:
            raise OAuthError("invalid_grant", "authorization code invalid, used, or expired")
        if record["redirect_uri"] != form.get("redirect_uri") or \
                record["client_id"] != form.get("client_id"):
            raise OAuthError("invalid_grant", "redirect_uri/client_id mismatch")
        requested_resource = form.get("resource")
        if requested_resource and requested_resource.rstrip("/") != record["resource"].rstrip("/"):
            raise OAuthError("invalid_target", "resource does not match the authorization")
        verifier = form.get("code_verifier", "")
        if not verifier or not hmac.compare_digest(record["code_challenge"], _s256(verifier)):
            raise OAuthError("invalid_grant", "PKCE verification failed")
        access_token = record["access_token"]
        return self._token_response(access_token, record["scope"], record["resource"],
                                    record["client_id"])

    def _token_refresh(self, form: Mapping[str, str], issuer: str) -> OAuthResult:
        record = self.store.take_refresh(form.get("refresh_token", ""))
        if record is None:
            raise OAuthError("invalid_grant", "refresh token invalid, used, or expired")
        if record["client_id"] != form.get("client_id"):
            raise OAuthError("invalid_grant", "client_id mismatch")
        requested_resource = form.get("resource")
        if requested_resource and requested_resource.rstrip("/") != record["resource"].rstrip("/"):
            raise OAuthError("invalid_target", "resource does not match the grant")
        try:
            creds = self.identity._issue_session(record["user_id"],  # noqa: SLF001
                                                 actor_type=record.get("actor_type", "agent"))
        except Exception as exc:  # noqa: BLE001
            raise OAuthError("invalid_grant", type(exc).__name__)
        return self._token_response(creds.access_token, record["scope"], record["resource"],
                                    record["client_id"])

    def _token_response(self, access_token: str, scope: str, resource: str,
                        client_id: str) -> OAuthResult:
        body: dict[str, Any] = {
            "access_token": access_token,
            "token_type": "Bearer",
            "expires_in": DEFAULT_TOKEN_TTL,
            "scope": scope,
        }
        if SCOPE_OFFLINE in scope.split():
            actor = self.identity.authenticate(access_token)
            refresh = secrets.token_urlsafe(32)
            self.store.put_refresh(refresh, {
                "user_id": actor.user_id,
                "actor_type": actor.actor_type,
                "resource": resource,
                "client_id": client_id,
                "scope": scope,
                "expires": self.clock() + self.refresh_ttl,
                # RFC 7009 §2.1: revoking the refresh token SHOULD also revoke
                # the access token issued with it; keep it reachable for that.
                "access_token": access_token,
            })
            body["refresh_token"] = refresh
        return OAuthResult(200, {"Content-Type": "application/json",
                                 "Cache-Control": "no-store"}, _json_body(body))

    # -- revocation (RFC 7009) ------------------------------------------
    def _revoke(self, body: bytes) -> OAuthResult:
        form = self._flatten(self._parse_form(body))
        token = form.get("token", "")
        hint = form.get("token_type_hint", "")
        # RFC 7009: always answer 200, whether or not the token was known.
        if token:
            if hint == "refresh_token":
                if not self._revoke_refresh_grant(token):
                    self._revoke_access(token)
            else:
                if not self._revoke_access(token):
                    self._revoke_refresh_grant(token)
        return OAuthResult(200, {"Content-Type": "application/json",
                                 "Cache-Control": "no-store"}, _json_body({}))

    def _revoke_refresh_grant(self, token: str) -> bool:
        """Revoke a refresh grant and cascade onto the access token issued with
        it (RFC 7009 §2.1), so a client that disconnects is really logged out."""
        record = self.store.pop_refresh(token)
        if record is None:
            return False
        sibling = record.get("access_token")
        if sibling:
            try:
                self.identity.logout(sibling)
            except Exception:  # noqa: BLE001 - already expired/logged out
                pass
        return True

    def _revoke_access(self, token: str) -> bool:
        try:
            actor = self.identity.authenticate(token)
        except Exception:  # noqa: BLE001
            return False
        try:
            self.identity.logout(token)
        except Exception:  # noqa: BLE001
            pass
        # Revoking an access token also revokes the subject's refresh grants:
        # a client that lost its access token must re-authorize.
        self.store.revoke_refresh_for_subject(actor.user_id)
        return True

    # -- rendering / helpers --------------------------------------------
    def _consent_page(self, clean: Mapping[str, str], *, current_account: str | None) -> str:
        e = html.escape
        hidden = "".join(
            f'<input type="hidden" name="{e(k)}" value="{e(v)}">'
            for k, v in {
                "response_type": "code",
                "client_id": clean["client_id"],
                "redirect_uri": clean["redirect_uri"],
                "code_challenge": clean["code_challenge"],
                "code_challenge_method": "S256",
                "state": clean["state"],
                "resource": clean["resource"],
                "scope": clean["scope"],
            }.items())
        offline = SCOPE_OFFLINE in clean["scope"].split()
        current_block = ""
        if current_account:
            current_block = (
                '<label class="opt"><input type="radio" name="identity" value="current" checked> '
                f'Continue as your current account (<code>{e(current_account)}</code>)</label>')
        guest_checked = "" if current_account else " checked"
        client = self.store.get_client(clean["client_id"]) or {}
        client_name = str(client.get("client_name") or "").strip()
        who = (f"<strong>{e(client_name)}</strong> (<code>{e(clean['client_id'])}</code>)"
               if client_name else f"A client (<code>{e(clean['client_id'])}</code>)")
        # No inline script/style: the origin serves CSP default-src 'self'. The
        # stylesheet is a same-origin resource served by this core.
        return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Authorize Resonance access</title>
<link rel="stylesheet" href="/oauth/consent.css"></head>
<body>
<main class="consent">
<p class="brand"><span class="mark" aria-hidden="true"></span>Resonance</p>
<h1>Authorize access to Resonance</h1>
<p>{who} is asking to connect to your
Resonance account at <code>{e(clean['resource'])}</code> and act as you through
the Resonance tools.</p>
<p>This authorization lets the client read and share <em>the Thought DNA you
explicitly choose to share</em> and use discovery and introductions on your
behalf. It does <strong>not</strong> by itself make anything discoverable —
every share still needs your separate in-tool confirmation.</p>
{"<p>The client requested offline access (a refresh token so it can reconnect without asking again).</p>" if offline else ""}
<form method="post" action="/oauth/authorize">
{hidden}
<fieldset>
<legend>Sign in to Resonance</legend>
{current_block}
<label class="opt"><input type="radio" name="identity" value="guest"{guest_checked}> Continue as a new pseudonymous guest</label>
<label class="opt"><input type="radio" name="identity" value="login"> Sign in with an existing account</label>
<p><label>Account ID <input type="text" name="user_id" autocomplete="username"></label></p>
<p><label>Recovery secret <input type="password" name="recovery_secret" autocomplete="current-password"></label></p>
</fieldset>
<div class="actions">
<button type="submit" name="decision" value="approve" class="primary">Allow access</button>
<button type="submit" name="decision" value="deny">Cancel</button>
</div>
</form>
<p class="fine">Private by default. Only the structural Thought DNA you explicitly confirm becomes discoverable; conversation text is never stored.</p>
</main>
</body></html>"""

    def _redirect_error(self, redirect_uri: str, exc: OAuthError,
                        state: str | None) -> OAuthResult:
        q = {"error": exc.error}
        if exc.description:
            q["error_description"] = exc.description
        if state:
            q["state"] = state
        location = redirect_uri + ("&" if "?" in redirect_uri else "?") + urlencode(q)
        return OAuthResult(302, {"Location": location, "Cache-Control": "no-store"}, b"")

    @staticmethod
    def _parse_form(body: bytes) -> dict[str, list[str]]:
        from urllib.parse import parse_qs
        try:
            return parse_qs(body.decode("utf-8"), keep_blank_values=True)
        except UnicodeDecodeError:
            raise OAuthError("invalid_request", "form body must be UTF-8")

    def _ok(self, doc: dict[str, Any]) -> OAuthResult:
        return OAuthResult(200, {"Content-Type": "application/json",
                                 "Cache-Control": "no-store"}, _json_body(doc))
