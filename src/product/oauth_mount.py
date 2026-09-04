"""Production mount for the canonical MCP OAuth core (R15C, #136).

The OAuth protocol lives in `src/remote/**` (R15A, #134). This module owns only
what production wiring needs so that the SAME public origin that serves `/mcp`
also serves the discovery documents and the authorization endpoints:

- deriving the absolute HTTPS issuer behind Railway's TLS-terminating proxy;
- the `WWW-Authenticate` challenge that points an unauthenticated `/mcp` call
  at the protected-resource metadata;
- dispatching the well-known / `/oauth/*` paths to whatever OAuth core object
  the runtime carries, without any protocol semantics of its own.

Nothing here mints, validates or stores tokens.
"""
from __future__ import annotations

from typing import Any, Mapping
from urllib.parse import urlsplit

PROTECTED_RESOURCE_PATH = "/.well-known/oauth-protected-resource"
AUTH_SERVER_PATH = "/.well-known/oauth-authorization-server"
OAUTH_PREFIX = "/oauth/"
RESOURCE_PATH = "/mcp"


def public_issuer(allowed_origins: frozenset[str] | set[str] | None,
                  headers: Mapping[str, str] | None = None) -> str:
    """Absolute origin browsers and hosted clients see.

    Order: the deployment contract (the single https allowed origin, i.e.
    `PUBLIC_ORIGIN`) wins; behind a proxy the process itself only ever sees
    plain HTTP, so `Host` alone would produce `http://0.0.0.0:8080`. Fallbacks
    use the edge's forwarded headers, then `Host`.
    """
    https = sorted(o.rstrip("/") for o in (allowed_origins or ()) if o.startswith("https://"))
    if len(https) == 1:
        return https[0]
    headers = headers or {}
    host = headers.get("X-Forwarded-Host") or headers.get("Host") or ""
    host = host.split(",", 1)[0].strip()
    if host:
        proto = (headers.get("X-Forwarded-Proto") or "http").split(",", 1)[0].strip()
        return f"{proto}://{host}"
    if len(https) > 1:
        return https[0]
    origins = sorted(o.rstrip("/") for o in (allowed_origins or ()))
    return origins[0] if origins else "http://127.0.0.1"


def resource_url(issuer: str) -> str:
    return issuer.rstrip("/") + RESOURCE_PATH


def resource_metadata_url(issuer: str) -> str:
    return issuer.rstrip("/") + PROTECTED_RESOURCE_PATH


def www_authenticate(issuer: str, *, error: str | None = None) -> str:
    """RFC 9728 challenge: points the client at the protected-resource document."""
    parts = ['realm="resonance"', f'resource_metadata="{resource_metadata_url(issuer)}"']
    if error:
        parts.insert(1, f'error="{error}"')
    return "Bearer " + ", ".join(parts)


def is_oauth_path(path: str) -> bool:
    return path in {PROTECTED_RESOURCE_PATH, AUTH_SERVER_PATH} or path.startswith(OAUTH_PREFIX)


class MountResponse:
    __slots__ = ("status", "headers", "body")

    def __init__(self, status: int, headers: Mapping[str, str] | None, body: bytes) -> None:
        self.status = int(status)
        self.headers = dict(headers or {})
        self.body = body


def dispatch(core: Any, *, method: str, path: str, query: Mapping[str, list[str]],
             headers: Mapping[str, str], body: bytes, issuer: str) -> MountResponse:
    """Hand an OAuth/discovery request to the core.

    The core contract requested on #134: `handle(method, path, query, headers,
    body, *, issuer) -> (status, headers, body)`. A runtime without a core
    answers 404 so the rest of the product is unaffected.
    """
    if core is None or not hasattr(core, "handle"):
        return MountResponse(404, {"Content-Type": "application/json; charset=utf-8"},
                             b'{"error":"not_found","message":"OAuth core is not mounted"}')
    result = core.handle(method, path, dict(query), dict(headers), body, issuer=issuer)
    if isinstance(result, tuple):
        status, out_headers, out_body = result
    else:  # src.remote.oauth.OAuthResult (status / headers / body attributes)
        status, out_headers, out_body = result.status, result.headers, result.body
    if isinstance(out_body, str):
        out_body = out_body.encode("utf-8")
    return MountResponse(status, out_headers, out_body or b"")


def resolve_bearer(core: Any, token: str | None, *, issuer: str) -> str | None:
    """Map a presented bearer to the R12 access token the product understands.

    Without a core the bearer is used as-is (today's behaviour: the bearer IS
    the R12 token). With a core, audience/revocation checks happen there.
    """
    if not token:
        return None
    if core is None or not hasattr(core, "resolve_bearer"):
        return token
    return core.resolve_bearer(token, resource=resource_url(issuer))


def attach_core(runtime: Any, *, issuer: str) -> Any | None:
    """Attach the R15A OAuth core to the runtime at process start.

    Zero-config: the core module is imported lazily; when it is absent (or
    exposes a different factory) production keeps running without the OAuth
    paths (404) and `/mcp` unchanged, and the reason is printed once — never a
    token, never a secret.
    """
    try:
        from src.remote.oauth import GrantStore, OAuthCore, RepositoryGrantStore  # R15A-owned (#134)
    except ImportError as exc:
        print(f"oauth: core not attached ({exc.__class__.__name__}: {exc}); "
              f"/mcp keeps bearer-only access")
        return None
    # The core's bearer IS the R12 access token (durable in the identity event
    # log). Codes / refresh grants / client registrations are durable too when
    # the runtime carries a repository (PostgreSQL/SQLite, migration 0005), so
    # a redeploy no longer forces hosted clients to re-authorize; the
    # in-memory store remains the fallback for runtimes without one.
    repository = getattr(getattr(runtime, "live", None), "repo", None)
    if repository is not None and hasattr(repository, "put_grant"):
        store: Any = RepositoryGrantStore(repository)
        durability = "durable"
    else:
        store = GrantStore()
        durability = "in-memory"
    core = OAuthCore(runtime.identity, store)
    runtime.oauth_core = core
    print(f"oauth: core attached; issuer {issuer}; resource {resource_url(issuer)}; "
          f"grants {durability}")
    return core


def split_origin(url: str) -> tuple[str, str]:
    parts = urlsplit(url)
    return parts.scheme, parts.netloc
