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
from urllib.parse import quote, urlencode

from .cimd import ClientMetadataCache, CimdError, looks_like_cimd

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
:root { color-scheme: light dark;
  --paper: #f4f1eb; --paper-2: #fbfaf7; --paper-3: #ece7de; --ink: #1d1a16; --ink-2: #57524a; --ink-3: #857f75;
  --line: rgba(29,26,22,.14); --line-soft: rgba(29,26,22,.08);
  --accent: #8a5a2b; --accent-ink: #6f4620; --accent-soft: rgba(138,90,43,.10); --accent-line: rgba(138,90,43,.35);
  --serif: ui-serif, Georgia, Cambria, "Times New Roman", serif;
  --sans: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  --mono: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
@media (prefers-color-scheme: dark) { :root {
  --paper: #16140f; --paper-2: #1e1b16; --paper-3: #26221c; --ink: #ede8df; --ink-2: #b7b0a4; --ink-3: #8c8579;
  --line: rgba(237,232,223,.16); --line-soft: rgba(237,232,223,.09);
  --accent: #d3a66f; --accent-ink: #e2bc8a; --accent-soft: rgba(211,166,111,.12); --accent-line: rgba(211,166,111,.4); } }
* { box-sizing: border-box; }
body { margin: 0; min-height: 100vh; background: var(--paper); color: var(--ink); font: 15px/1.55 var(--sans);
  display: flex; align-items: flex-start; justify-content: center; padding: clamp(16px, 6vh, 64px) 16px; }
main.consent { width: min(600px, 100%); background: var(--paper-2); border: 1px solid var(--line); border-radius: 12px; padding: clamp(20px, 4vw, 34px); }
.brand { display: flex; align-items: center; gap: 10px; margin: 0 0 20px; font: 500 20px/1 var(--serif); color: var(--ink); }
.mark { width: 20px; height: 20px; border-radius: 50%; border: 2px solid var(--accent); box-shadow: inset 0 0 0 4px var(--paper-2), inset 0 0 0 6px var(--accent); }
h1 { font: 500 clamp(26px, 4vw, 32px)/1.15 var(--serif); letter-spacing: -.01em; margin: 0 0 14px; }
p { margin: 0 0 12px; color: var(--ink-2); }
p strong { color: var(--ink); font-weight: 600; }
p em { color: var(--ink); font-style: italic; }
code { font: 13px var(--mono); color: var(--accent-ink); overflow-wrap: anywhere; }
fieldset { border: 1px solid var(--line); border-radius: 10px; padding: 8px 14px 12px; margin: 22px 0 18px; }
legend { padding: 0 8px; font: 600 11px/1 var(--sans); letter-spacing: .12em; text-transform: uppercase; color: var(--ink-3); }
label.opt { display: flex; align-items: flex-start; gap: 10px; padding: 10px 4px; border-bottom: 1px solid var(--line-soft); color: var(--ink); cursor: pointer; }
label.opt:last-of-type { border-bottom: 0; }
label.opt input { margin: 4px 0 0; accent-color: var(--accent); }
fieldset p { margin: 6px 0 0 30px; }
fieldset p label { display: flex; flex-direction: column; gap: 4px; color: var(--ink-2); font-size: 13.5px; }
input[type=text], input[type=password] { width: 100%; padding: 9px 12px; border-radius: 8px; border: 1px solid var(--line);
  background: var(--paper); color: var(--ink); font: 14px var(--mono); }
input[type=text]:focus, input[type=password]:focus { outline: 2px solid var(--ink); outline-offset: 1px; }
.actions { display: flex; gap: 10px; flex-wrap: wrap; }
button { cursor: pointer; min-height: 42px; border-radius: 999px; padding: 0 22px; font: 500 15px var(--sans); border: 1px solid var(--line);
  background: var(--paper-2); color: var(--ink); }
button.primary { background: var(--ink); color: var(--paper); border-color: var(--ink); }
button:hover { border-color: var(--ink-3); }
button.primary:hover { background: var(--accent-ink); border-color: var(--accent-ink); }
.fine { margin: 20px 0 0; padding-top: 14px; border-top: 1px solid var(--line-soft); font-size: 13px; color: var(--ink-3); }
.who { margin: 10px 4px 4px; font-size: 14px; }
.who-id { font-size: 12.5px; color: var(--ink-3); }
a.primary-link { display: inline-flex; align-items: center; min-height: 42px; margin: 4px 4px 8px; padding: 0 22px; border-radius: 999px;
  background: var(--ink); color: var(--paper); border: 1px solid var(--ink); font: 500 15px var(--sans); text-decoration: none; }
a.primary-link:hover { background: var(--accent-ink); border-color: var(--accent-ink); }
a.primary-link:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
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
    access: dict[str, dict[str, Any]] = field(default_factory=dict)

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

    # -- access-token audience records -----------------------------------
    def put_access(self, token: str, record: Mapping[str, Any]) -> None:
        """Remember which resource an access token was issued for (RFC 8707)."""
        self.access[_hash(token)] = dict(record)

    def get_access(self, token: str) -> dict[str, Any] | None:
        record = self.access.get(_hash(token))
        return dict(record) if record is not None else None

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
    KIND_ACCESS = "access"

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

    # -- access-token audience records -----------------------------------
    def put_access(self, token: str, record: Mapping[str, Any]) -> None:
        """Remember which resource an access token was issued for (RFC 8707)."""
        self.repository.put_grant(self.KIND_ACCESS, _hash(token), dict(record),
                                  user_id=record.get("user_id"), expires_at=record.get("expires"))

    def get_access(self, token: str) -> dict[str, Any] | None:
        record = self.repository.get_grant(self.KIND_ACCESS, _hash(token))
        return dict(record) if record is not None else None

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

def _account_line(account: Mapping[str, str] | str, e: Any) -> str:
    """The "you are signed in as" line, in the plainest terms available.

    A name the person recognises first, the address that proves which account
    it is second, and the identifier last for the case where a provider gave
    neither.
    """
    if not isinstance(account, Mapping):
        return f'<p class="who">Signed in as <code>{e(account)}</code>.</p>'
    label = (account.get("label") or "").strip()
    email = (account.get("email") or "").strip()
    user_id = account.get("user_id") or ""
    if label and email:
        headline = f"Signed in as <strong>{e(label)}</strong> ({e(email)})."
    elif label:
        headline = f"Signed in as <strong>{e(label)}</strong>."
    elif email:
        headline = f"Signed in as <strong>{e(email)}</strong>."
    else:
        headline = f"Signed in as <code>{e(user_id)}</code>."
    lines = [f'<p class="who">{headline}</p>']
    if label or email:
        lines.append('<p class="who who-id">Account <code>'
                     f'{e(user_id)}</code> — this is what other people see, '
                     'never your name or address.</p>')
    return "".join(lines)


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
                 clock: Any = time.time,
                 sign_in_required: Any = None) -> None:
        self.identity = identity
        self.store = store or GrantStore(clock=clock)
        self.code_ttl = code_ttl
        self.refresh_ttl = refresh_ttl
        self.clock = clock
        # Callable answering whether this deployment offers a real sign-in.
        # Where it does, a connector authorization must bind to the account the
        # person signed into — a connection that minted a fresh anonymous
        # account would make the same person a stranger on every surface, and
        # leave no one to notify when a match appears.
        self._sign_in_required = sign_in_required or (lambda: False)
        # Client ID Metadata Documents: a client identified by an https URL
        # rather than by a stored registration. Fetched documents are cached
        # briefly so a busy directory costs one fetch, not one per person.
        self.client_metadata = ClientMetadataCache()

    def sign_in_required(self) -> bool:
        try:
            return bool(self._sign_in_required())
        except Exception:  # noqa: BLE001 - never fail an authorization on this
            return False

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
        record = self.store.get_access(token) if hasattr(self.store, "get_access") else None
        if record is not None and record.get("resource", "").rstrip("/") != resource.rstrip("/"):
            return None                      # token bound to another audience
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
            if path == "/oauth/userinfo" and method in ("GET", "POST"):
                return self._userinfo(headers, issuer)
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
            "userinfo_endpoint": issuer + "/oauth/userinfo",
            "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code", "refresh_token"],
            "code_challenge_methods_supported": ["S256"],
            "token_endpoint_auth_methods_supported": ["none"],
            # Selected over dynamic registration when a host sees both this and
            # the "none" auth method above.
            "client_id_metadata_document_supported": True,
            "revocation_endpoint_auth_methods_supported": ["none"],
            "scopes_supported": list(SUPPORTED_SCOPES),
            "resource_indicators_supported": True,
        }

    # -- userinfo -------------------------------------------------------
    def _userinfo(self, headers: Mapping[str, str], issuer: str) -> OAuthResult:
        """Who the presented bearer belongs to.

        Hosted clients use this to show whose account they connected, and to
        confirm that two of their surfaces reached the same person. Only the
        account identifier and the sign-in address are returned; nothing about
        what the person has thought or shared is reachable here.
        """
        raw = (headers.get("Authorization") or headers.get("authorization") or "")
        token = raw[7:].strip() if raw[:7].lower() == "bearer " else ""
        subject = self.resolve_bearer(token or None, resource=self.resource_for(issuer))
        if not subject:
            return OAuthResult(401, {
                "Content-Type": "application/json",
                "WWW-Authenticate": self.challenge_header(issuer),
            }, _json_body({"error": "invalid_token"}))
        try:
            actor = self.identity.authenticate(subject)
        except Exception:  # noqa: BLE001
            return OAuthResult(401, {
                "Content-Type": "application/json",
                "WWW-Authenticate": self.challenge_header(issuer),
            }, _json_body({"error": "invalid_token"}))
        doc: dict[str, Any] = {"sub": actor.user_id}
        claims = {}
        if hasattr(self.identity, "identity_claims"):
            try:
                claims = self.identity.identity_claims(actor.user_id) or {}
            except Exception:  # noqa: BLE001
                claims = {}
        if claims.get("email"):
            doc["email"] = claims["email"]
            doc["email_verified"] = bool(claims.get("email_verified"))
        user = self.identity.backend.get_user(actor.user_id)
        label = getattr(user, "display_label", None) if user is not None else None
        if label:
            doc["name"] = str(label)
        return self._ok(doc)

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
        if looks_like_cimd(client_id):
            # The client_id is its own metadata document. Its redirect_uris are
            # authoritative, so an unknown redirect_uri is refused here rather
            # than tolerated the way an unregistered client_id is.
            try:
                metadata = self.client_metadata.get(client_id)
            except CimdError as exc:
                raise OAuthError("invalid_client", str(exc))
            if not metadata.allows(redirect_uri):
                raise OAuthError("invalid_request",
                                 "redirect_uri is not listed in the client metadata document")
        else:
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
        current = self._cookie_account(headers)
        html_page = self._consent_page(clean, current_account=current,
                                       return_to="/oauth/authorize?" + urlencode(
                                           {k: v for k, v in params.items() if v}))
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
        if self.sign_in_required():
            # Reached only when the consent form was replayed without a signed-in
            # browser session; the page itself offers no guest option.
            raise OAuthError("access_denied", "sign in to Resonance before connecting a client")
        # default: guest continuation (deployments with no sign-in provider)
        creds = identity.register_guest(actor_type="agent")
        return creds.access_token, creds

    def _cookie_account(self, headers: Mapping[str, str]) -> dict[str, str] | None:
        """Who the browser is signed in as, in terms a person can check.

        This page asks someone to confirm that a client may act as them, and
        they may have just chosen between several accounts at their provider.
        An opaque `person-…` identifier gives them nothing to check against, so
        the name and address they signed in with are shown, with the identifier
        kept as the precise thing underneath. All three are the viewer's own —
        nothing here is another participant's.
        """
        user_id = self._cookie_subject(headers)
        if not user_id:
            return None
        account = {"user_id": user_id, "label": "", "email": ""}
        try:
            user = self.identity.backend.get_user(user_id)
            account["label"] = str(getattr(user, "display_label", "") or "")
        except Exception:  # noqa: BLE001 - the identifier alone still works
            pass
        try:
            claims = self.identity.identity_claims(user_id) or {}
            account["email"] = str(claims.get("email") or "")
        except Exception:  # noqa: BLE001
            pass
        return account

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
        if hasattr(self.store, "put_access"):
            try:
                owner = self.identity.authenticate(access_token)
                self.store.put_access(access_token, {
                    "user_id": owner.user_id, "resource": resource, "client_id": client_id,
                    "expires": self.clock() + DEFAULT_TOKEN_TTL,
                })
            except Exception as exc:  # noqa: BLE001 -- transport returns an OAuth error
                # Never return an OAuth-issued token unless its audience record
                # was committed.  Otherwise a transient grant-store failure
                # would silently downgrade RFC 8707 enforcement to the legacy
                # unbound manual-key path.
                try:
                    self.identity.logout(access_token)
                except Exception:  # noqa: BLE001 -- best-effort cleanup only
                    pass
                raise OAuthError(
                    "server_error", "could not bind access token to the requested resource", 500
                ) from exc
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
    def _consent_page(self, clean: Mapping[str, str], *,
                      current_account: Mapping[str, str] | str | None,
                      return_to: str = "/") -> str:
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
        # Where a real sign-in exists it is the only way in, and the choice on
        # this page collapses to one: connect this client to the account you
        # signed into. Anonymous connections are what made the same person a
        # stranger on every surface, so they are not offered.
        if self.sign_in_required():
            if current_account:
                who_line = _account_line(current_account, e)
                identity_block = (
                    '<input type="hidden" name="identity" value="current">'
                    '<fieldset><legend>Your Resonance account</legend>'
                    f'{who_line}'
                    '</fieldset>')
                actions = (
                    '<div class="actions">'
                    '<button type="submit" name="decision" value="approve" class="primary">'
                    'Allow access</button>'
                    '<button type="submit" name="decision" value="deny">Cancel</button>'
                    '</div>')
            else:
                identity_block = (
                    '<fieldset><legend>Sign in to Resonance</legend>'
                    '<p class="who">Resonance introduces people whose reasoning has the '
                    'same shape, so a connection has to belong to a person it can come '
                    'back to. Sign in, and this client connects to that account.</p>'
                    '<p><a class="primary-link" '
                    # URL-encoded, not merely HTML-escaped: the authorize URL
                    # carries its own query, and an unencoded `&` would split
                    # `next` into separate parameters of the sign-in page and
                    # lose the way back to this consent screen.
                    f'href="/auth/sign-in?next={e(quote(return_to, safe=""))}">'
                    'Sign in to continue</a></p></fieldset>')
                actions = ('<div class="actions">'
                           '<button type="submit" name="decision" value="deny">Cancel</button>'
                           '</div>')
        else:
            current_block = ""
            if current_account:
                current_id = (current_account["user_id"]
                              if isinstance(current_account, Mapping) else current_account)
                current_block = (
                    '<label class="opt"><input type="radio" name="identity" value="current" checked> '
                    f'Continue as your current account (<code>{e(current_id)}</code>)</label>')
            guest_checked = "" if current_account else " checked"
            identity_block = (
                '<fieldset><legend>Sign in to Resonance</legend>'
                f'{current_block}'
                f'<label class="opt"><input type="radio" name="identity" value="guest"{guest_checked}> '
                'Continue as a new pseudonymous guest</label>'
                '<label class="opt"><input type="radio" name="identity" value="login"> '
                'Sign in with an existing account</label>'
                '<p><label>Account ID <input type="text" name="user_id" autocomplete="username"></label></p>'
                '<p><label>Recovery secret <input type="password" name="recovery_secret" '
                'autocomplete="current-password"></label></p>'
                '</fieldset>')
            actions = ('<div class="actions">'
                       '<button type="submit" name="decision" value="approve" class="primary">'
                       'Allow access</button>'
                       '<button type="submit" name="decision" value="deny">Cancel</button>'
                       '</div>')
        client_name = ""
        if looks_like_cimd(clean["client_id"]):
            try:
                client_name = self.client_metadata.get(clean["client_id"]).client_name
            except CimdError:
                client_name = ""
        else:
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
{identity_block}
{actions}
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
