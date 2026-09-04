"""Authenticated HTTP server for the live product.

Manual UI, browser WebMCP tools, and plain HTTP clients converge on one
`LiveProductService`. The server owns only transport concerns: cookie session
issuance, CSRF header relay, Origin relay, body bounds, security headers, and
JSON shaping. All authorization, consent, freshness, and discovery semantics
stay in the accepted layers underneath.

The accepted R10 browser tool surface (`demo/ui/webmcp.mjs`) is served as-is
and its `/api/webmcp/*` wire contract is exposed here backed by the live
service, so the exact accepted tools operate on real authenticated state.
"""

from __future__ import annotations

import argparse
import os
import json
import secrets
from dataclasses import dataclass
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import parse_qs, urlparse

from src.identity import IdentityService, R11IdentityBackend
from src.identity.models import (
    AuthenticationError,
    AuthorizationError,
    ConfirmationRequiredError,
    ConsentChoices,
    CsrfError,
    IdentityValidationError,
)
from src.ingestion.service import (
    ConfirmationError,
    DraftNotFound,
    IngestionError,
    ShareIntent,
)
from src.persistence import LiveCorpusService, SQLiteRepository
from src.persistence.errors import (
    PersistenceConflictError,
    PersistenceStaleIndexError,
    PersistenceStateError,
    PersistenceValidationError,
)
from src.persistence.seed import seed_r7
from src.collaboration import CollaborationError
from src.workspaces import WorkspaceError
from src.security.models import ConfirmationRequired as PolicyConfirmationRequired
from src.product.service import LiveProductService, ProductError, StaleResultError

REPO = Path(__file__).resolve().parents[2]
UI_DIR = REPO / "demo" / "ui"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8788
MAX_BODY_BYTES = 96 * 1024
COOKIE_NAME = "resonance_token"

STATIC = {
    "/styles.css": ("styles.css", "text/css; charset=utf-8"),
    "/app.mjs": ("app.mjs", "text/javascript; charset=utf-8"),
    "/webmcp.mjs": ("webmcp.mjs", "text/javascript; charset=utf-8"),
    "/deeplink.mjs": ("deeplink.mjs", "text/javascript; charset=utf-8"),
    "/collab.mjs": ("collab.mjs", "text/javascript; charset=utf-8"),
    "/session.mjs": ("session.mjs", "text/javascript; charset=utf-8"),
    "/collab_ui.mjs": ("collab_ui.mjs", "text/javascript; charset=utf-8"),
    "/workspaces.mjs": ("workspaces.mjs", "text/javascript; charset=utf-8"),
}


@dataclass
class ProductRuntime:
    live: LiveCorpusService
    identity: IdentityService
    product: LiveProductService
    allowed_origins: frozenset[str]


def build_runtime(
    db_path: str = ":memory:",
    *,
    allowed_origins: frozenset[str],
    confirmation_secret: bytes | None = None,
    seed: bool = True,
) -> ProductRuntime:
    live = LiveCorpusService(SQLiteRepository(db_path))
    if seed:
        seed_r7(live)
    identity = IdentityService(
        R11IdentityBackend(live), allowed_origins=allowed_origins
    )
    if confirmation_secret is None:
        # Ephemeral runtime only; persistent DBs are gated at the CLI boundary.
        confirmation_secret = secrets.token_bytes(32)
    elif not confirmation_secret:
        raise ValueError(
            "confirmation_secret must be non-empty; an empty secret would "
            "silently fall back to a per-process value and orphan drafts"
        )
    product = LiveProductService(identity, confirmation_secret=confirmation_secret)
    return ProductRuntime(live=live, identity=identity, product=product,
                          allowed_origins=allowed_origins)


class ProductHandler(BaseHTTPRequestHandler):
    server_version = "ResonanceLiveProduct/0.1"
    runtime: ProductRuntime  # injected via server factory

    # -- plumbing ----------------------------------------------------------
    def log_message(self, fmt: str, *args: Any) -> None:  # quiet tests
        pass

    def _security_headers(self) -> None:
        self.send_header("Content-Security-Policy",
                         "default-src 'self'; frame-ancestors 'none'")
        self.send_header("Cross-Origin-Opener-Policy", "same-origin")
        self.send_header("Permissions-Policy", "tools=(self)")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")

    def _send_json(self, payload: Mapping[str, Any],
                   status: HTTPStatus = HTTPStatus.OK,
                   cookie: str | None = None) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        if cookie is not None:
            self.send_header("Set-Cookie", cookie)
        self._security_headers()
        self.end_headers()
        self.wfile.write(body)

    def _send_error_json(self, status: HTTPStatus, code: str, message: str) -> None:
        self._send_json({"error": code, "message": message}, status)

    def _send_bytes(self, body: bytes, content_type: str) -> None:
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self._security_headers()
        self.end_headers()
        self.wfile.write(body)

    def _body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or 0)
        if length < 0 or length > MAX_BODY_BYTES:
            raise IngestionError("request body exceeds product bound")
        raw = self.rfile.read(length) if length else b"{}"
        try:
            parsed = json.loads(raw.decode("utf-8") or "{}")
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise IngestionError("request body must be a JSON object") from exc
        if not isinstance(parsed, dict):
            raise IngestionError("request body must be a JSON object")
        return parsed

    def _token(self) -> str:
        cookie = SimpleCookie(self.headers.get("Cookie", ""))
        morsel = cookie.get(COOKIE_NAME)
        if morsel is None or not morsel.value:
            raise AuthenticationError("missing session cookie")
        return morsel.value

    def _origin(self) -> str | None:
        return self.headers.get("Origin")

    def _csrf(self) -> str | None:
        return self.headers.get("X-Resonance-CSRF")

    def _cookie_for(self, token: str) -> str:
        return (f"{COOKIE_NAME}={token}; HttpOnly; SameSite=Strict; Path=/")

    def _security_kwargs(self) -> dict[str, Any]:
        return {
            "csrf_token": self._csrf(),
            "origin": self._origin(),
            "cookie_authenticated": True,
            "client_id": "live-product-http",
        }

    # -- routing -----------------------------------------------------------
    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        try:
            self._route_get(parsed.path, parse_qs(parsed.query))
        except Exception as exc:  # noqa: BLE001 - transport boundary
            self._handle_error(exc)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        try:
            self._route_post(parsed.path)
        except Exception as exc:  # noqa: BLE001 - transport boundary
            self._handle_error(exc)

    def _handle_error(self, exc: Exception) -> None:
        mapping = [
            ((AuthenticationError,), HTTPStatus.UNAUTHORIZED, "authentication_failed"),
            ((AuthorizationError, DraftNotFound), HTTPStatus.FORBIDDEN,
             "authorization_failed"),
            ((CsrfError,), HTTPStatus.FORBIDDEN, "csrf_rejected"),
            ((ConfirmationRequiredError, ConfirmationError, PolicyConfirmationRequired), HTTPStatus.CONFLICT,
             "confirmation_required"),
            ((StaleResultError, PersistenceStaleIndexError), HTTPStatus.CONFLICT,
             "stale_result"),
            ((PersistenceConflictError,), HTTPStatus.CONFLICT, "conflict"),
            ((CollaborationError,), HTTPStatus.BAD_REQUEST, "collaboration_unavailable"),
            ((WorkspaceError,), HTTPStatus.BAD_REQUEST, "workspace_unavailable"),
            ((IdentityValidationError, PersistenceValidationError, IngestionError,
              ProductError, ValueError), HTTPStatus.BAD_REQUEST, "validation_failed"),
            ((PersistenceStateError,), HTTPStatus.CONFLICT, "state_conflict"),
        ]
        for types, status, code in mapping:
            if isinstance(exc, types):
                self._send_error_json(status, code, str(exc))
                return
        self._send_error_json(HTTPStatus.INTERNAL_SERVER_ERROR, "internal_error",
                              "unexpected product error")

    # -- GET ---------------------------------------------------------------
    def _route_get(self, path: str, params: dict[str, list[str]]) -> None:
        product = self.runtime.product
        if path in {"/", "/index.html"}:
            html = (UI_DIR / "index.html").read_text(encoding="utf-8")
            injected = html.replace(
                "</body>",
                '  <script>window.RESONANCE_MODE = "live";</script>\n'
                '  <script type="module" src="/webmcp.mjs"></script>\n'
                '  <script type="module" src="/deeplink.mjs"></script>\n'
                '  <script type="module" src="/session.mjs"></script>\n'
                '  <script type="module" src="/collab.mjs"></script>\n'
                '  <script type="module" src="/collab_ui.mjs"></script>\n'
                '  <script type="module" src="/workspaces.mjs"></script>\n</body>',
            )
            self._send_bytes(injected.encode("utf-8"), "text/html; charset=utf-8")
            return
        if path in STATIC:
            filename, content_type = STATIC[path]
            self._send_bytes((UI_DIR / filename).read_bytes(), content_type)
            return
        if path == "/api/product/health":
            health = self.runtime.live.health()
            self._send_json({"ok": health.ok, "mode": "live",
                             "freshness": product.freshness()})
            return
        if path in {"/api/product/state", "/api/webmcp/state"}:
            token = None
            try:
                token = self._token()
            except AuthenticationError:
                pass
            self._send_json(product.state(token))
            return
        if path == "/api/product/sessions":
            self._send_json({"sessions": product.owned_sessions(self._token())})
            return
        if path == "/api/product/intro/list":
            self._send_json(product.list_requests(self._token()))
            return
        if path == "/api/product/channel/messages":
            channel_id = (params.get("channel_id") or [""])[0]
            self._send_json(product.read_messages(self._token(), channel_id))
            return
        if path == "/api/product/workspaces":
            self._send_json(product.list_my_workspaces(self._token()))
            return
        if path == "/api/product/workspace":
            wid = (params.get("workspace_id") or [""])[0]
            self._send_json(product.get_workspace(self._token(), wid))
            return
        if path in {"/api/product/preview", "/api/webmcp/preview"}:
            draft_id = (params.get("draft_id") or [""])[0]
            self._send_json(product.preview(self._token(), draft_id,
                                            client_id="live-product-http"))
            return
        if path in {"/api/product/discover", "/api/webmcp/discover"}:
            session_id = (params.get("session_id") or [""])[0]
            mode = (params.get("mode") or ["analogical"])[0]
            k = int((params.get("k") or ["8"])[0])
            response = product.discover(self._token(), session_id, mode=mode, k=k)
            if path.startswith("/api/webmcp/"):
                response = _webmcp_discover_shape(response)
            self._send_json(response)
            return
        if path in {"/api/product/match", "/api/webmcp/match"}:
            result_id = (params.get("result_id") or [""])[0]
            session_id = (params.get("session_id") or [""])[0]
            self._send_json(product.get_match(self._token(), result_id, session_id))
            return
        if path == "/api/product/rich_discover":
            session_id = (params.get("session_id") or [""])[0]
            mode = (params.get("mode") or ["analogical"])[0]
            k = int((params.get("k") or ["8"])[0])
            self._send_json(product.rich_discover(self._token(), session_id,
                                                  mode=mode, k=k))
            return
        if path == "/api/product/visual/map":
            result_id = (params.get("result_id") or [""])[0]
            svg = product.visual_map(self._token(), result_id)
            self._send_svg(svg)
            return
        if path == "/api/product/visual/structure":
            result_id = (params.get("result_id") or [""])[0]
            session_id = (params.get("session_id") or [""])[0]
            svg = product.visual_structure(self._token(), result_id, session_id)
            self._send_svg(svg)
            return
        self._send_error_json(HTTPStatus.NOT_FOUND, "not_found", "unknown path")

    def _send_svg(self, svg: str) -> None:
        """User-specific visuals: authorized per request, never cached across
        identities, no long-lived URLs (result_id-scoped, staleness-checked)."""
        body = svg.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "image/svg+xml; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "private, no-store")
        self._security_headers()
        self.end_headers()
        self.wfile.write(body)

    # -- POST --------------------------------------------------------------
    def _route_post(self, path: str) -> None:
        product = self.runtime.product
        if path == "/api/product/guest":
            creds = product.register_guest()
            self._send_json(
                {"user_id": creds.user_id, "csrf_token": creds.csrf_token,
                 "expires_at": creds.expires_at,
                 "recovery_secret": creds.recovery_secret},
                cookie=self._cookie_for(creds.access_token))
            return
        if path == "/api/product/register":
            body = self._body()
            creds = product.register(str(body.get("display_label", "")))
            self._send_json(
                {"user_id": creds.user_id, "csrf_token": creds.csrf_token,
                 "expires_at": creds.expires_at,
                 "recovery_secret": creds.recovery_secret},
                cookie=self._cookie_for(creds.access_token))
            return
        if path == "/api/product/login":
            body = self._body()
            creds = product.login(str(body.get("user_id", "")),
                                  str(body.get("recovery_secret", "")))
            self._send_json(
                {"user_id": creds.user_id, "csrf_token": creds.csrf_token,
                 "expires_at": creds.expires_at},
                cookie=self._cookie_for(creds.access_token))
            return
        if path == "/api/product/logout":
            product.logout(self._token())
            self._send_json({"logged_out": True},
                            cookie=f"{COOKIE_NAME}=; Max-Age=0; Path=/")
            return
        if path == "/api/product/rotate":
            creds = product.rotate_session(self._token())
            self._send_json(
                {"user_id": creds.user_id, "csrf_token": creds.csrf_token,
                 "expires_at": creds.expires_at},
                cookie=self._cookie_for(creds.access_token))
            return

        token = self._token()
        body = self._body()
        security = self._security_kwargs()

        if path in {"/api/product/prepare", "/api/webmcp/prepare"}:
            intent_raw = body.get("share_intent") or {}
            intent = ShareIntent(
                share_display_profile=bool(intent_raw.get("share_display_profile", True)),
                share_coarse_location=bool(intent_raw.get("share_coarse_location", False)),
                receive_intro_requests=bool(intent_raw.get("receive_intro_requests", False)),
            )
            common = dict(
                presentation=body.get("presentation") or {},
                coarse_location=body.get("coarse_location"),
                intent=intent, **security,
            )
            if (body.get("candidate") is None) == (body.get("context") is None):
                raise IngestionError("provide exactly one of candidate or context")
            if body.get("candidate") is not None:
                result = product.prepare_structured(token, body["candidate"], **common)
            else:
                result = product.prepare_raw_text(token, str(body["context"]), **common)
            self._send_json(result)
            return
        if path in {"/api/product/share", "/api/webmcp/share"}:
            self._send_json(product.share_prepared(
                token, str(body.get("draft_id", "")),
                confirmation_token=str(body.get("confirmation_token", "")),
                confirmed=bool(body.get("confirmed", False)), **security))
            return
        if path == "/api/product/discard":
            self._send_json(product.discard(
                token, str(body.get("draft_id", "")),
                confirmed=bool(body.get("confirmed", False)), **security))
            return
        if path in {"/api/product/consent", "/api/webmcp/consent"}:
            choices_raw = body.get("choices") or {}
            choices = ConsentChoices(
                share_thought_dna=bool(choices_raw.get("share_thought_dna", False)),
                share_display_profile=bool(choices_raw.get("share_display_profile", False)),
                share_coarse_location=bool(choices_raw.get("share_coarse_location", False)),
                allow_intro_requests=bool(choices_raw.get("allow_intro_requests", False)),
            )
            result = product.set_consent(
                token, str(body.get("session_id", "")), choices,
                confirmed=bool(body.get("confirmed", False)), **security)
            self._send_json({"session_id": body.get("session_id"),
                             "consent": result.to_corpus_consent(),
                             "allow_intro_requests": result.allow_intro_requests})
            return
        if path == "/api/product/metadata":
            stored = product.update_metadata(
                token, str(body.get("session_id", "")),
                location=body.get("location"),
                presentation=body.get("presentation"), **security)
            self._send_json({"session_id": str(body.get("session_id", "")),
                             "version": int(getattr(stored, "version", 0))})
            return
        if path == "/api/product/revoke":
            stored = product.revoke_session(
                token, str(body.get("session_id", "")),
                confirmed=bool(body.get("confirmed", False)), **security)
            self._send_json({"session_id": str(body.get("session_id", "")),
                             "revoked": True,
                             "discoverable": False})
            return
        if path == "/api/product/intro/request":
            self._send_json(product.request_intro(
                token,
                from_session_id=str(body.get("from_session_id", "")),
                target_session_id=str(body.get("target_session_id", "")),
                message=str(body.get("message", "")),
                request_id=body.get("request_id"),
                confirmed=bool(body.get("confirmed", False)), **security))
            return
        if path == "/api/product/intro/respond":
            self._send_json(product.respond_intro(
                token, str(body.get("intro_id", "")),
                accept=bool(body.get("accept", False)),
                request_id=body.get("request_id"),
                confirmed=bool(body.get("confirmed", False)), **security))
            return
        if path == "/api/product/intro/cancel":
            self._send_json(product.cancel_intro(
                token, str(body.get("intro_id", "")),
                request_id=body.get("request_id"),
                confirmed=bool(body.get("confirmed", False)), **security))
            return
        if path == "/api/product/workspace/create":
            self._send_json(product.create_workspace(
                token, str(body.get("intro_id", "")),
                title=str(body.get("title", "")), brief=str(body.get("brief", "")),
                **security))
            return
        if path == "/api/product/workspace/invite":
            self._send_json(product.workspace_invite(
                token, str(body.get("workspace_id", "")),
                str(body.get("invitee_user_id", "")),
                role=str(body.get("role", "member")), **security))
            return
        if path == "/api/product/workspace/respond":
            self._send_json(product.workspace_respond_invite(
                token, str(body.get("workspace_id", "")),
                accept=bool(body.get("accept", False)), **security))
            return
        if path == "/api/product/workspace/remove":
            self._send_json(product.workspace_remove_member(
                token, str(body.get("workspace_id", "")),
                str(body.get("target_user_id", "")), **security))
            return
        if path == "/api/product/workspace/leave":
            self._send_json(product.workspace_leave(
                token, str(body.get("workspace_id", "")), **security))
            return
        if path == "/api/product/workspace/brief":
            self._send_json(product.workspace_update_brief(
                token, str(body.get("workspace_id", "")), str(body.get("brief", "")),
                expected_version=int(body.get("expected_version", 1)), **security))
            return
        if path == "/api/product/workspace/note":
            self._send_json(product.workspace_add_note(
                token, str(body.get("workspace_id", "")), str(body.get("body", "")),
                **security))
            return
        if path == "/api/product/workspace/task":
            self._send_json(product.workspace_add_task(
                token, str(body.get("workspace_id", "")), str(body.get("title", "")),
                **security))
            return
        if path == "/api/product/workspace/task_state":
            self._send_json(product.workspace_set_task_state(
                token, str(body.get("workspace_id", "")), str(body.get("task_id", "")),
                str(body.get("state", "")), **security))
            return
        if path == "/api/product/workspace/link":
            self._send_json(product.workspace_link_match(
                token, str(body.get("workspace_id", "")), str(body.get("session_id", "")),
                str(body.get("why", "")), **security))
            return
        if path == "/api/product/workspace/artifact":
            self._send_json(product.workspace_add_artifact(
                token, str(body.get("workspace_id", "")),
                label=str(body.get("label", "")), kind=str(body.get("kind", "file")),
                sha256=str(body.get("sha256", "")), size_bytes=int(body.get("size_bytes", 0)),
                **security))
            return
        if path == "/api/product/channel/send":
            self._send_json(product.send_message(
                token, str(body.get("channel_id", "")),
                str(body.get("body", "")),
                request_id=body.get("request_id"),
                confirmed=bool(body.get("confirmed", False)), **security))
            return
        if path == "/api/product/delete":
            product.delete_session(
                token, str(body.get("session_id", "")),
                confirmed=bool(body.get("confirmed", False)), **security)
            self._send_json({"session_id": str(body.get("session_id", "")),
                             "deleted": True, "discoverable": False})
            return
        self._send_error_json(HTTPStatus.NOT_FOUND, "not_found", "unknown path")


def _webmcp_discover_shape(response: Mapping[str, Any]) -> dict[str, Any]:
    """Adapt the live payload to the accepted R10 tool wire field names."""
    return {
        "contract_version": response["contract_version"],
        "result_id": response["result_id"],
        "source": response["source"],
        "discovery_contract": response.get("discovery_contract"),
        "query": response.get("query", {}),
        "matches_in_backend_order": list(response.get("matches", [])),
        "aggregation": response.get("aggregation", {}),
        "freshness": response.get("freshness", {}),
        "location_note": response.get("location_note", ""),
    }


def serve(
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    *,
    runtime: ProductRuntime,
) -> ThreadingHTTPServer:
    handler = type("BoundProductHandler", (ProductHandler,), {"runtime": runtime})
    return ThreadingHTTPServer((host, port), handler)


def _require_strong(secret: bytes, source: str) -> bytes:
    """An empty or short secret must fail loudly, never fall back to random."""
    if len(secret) < 32:
        raise ValueError(
            f"{source} must hold a stable secret of at least 32 bytes "
            f"(got {len(secret)}); an empty/short secret would silently orphan "
            "prepared drafts on restart"
        )
    return secret


def _resolve_secret(secret_file: str | None, environ: Mapping[str, str],
                    db_path: str) -> bytes | None:
    """Durable-draft HMAC secret policy (R12C seam).

    A persistent DB REQUIRES a stable secret (file or env) or startup fails
    explicitly — a per-process random secret would orphan every prepared
    private draft on restart. Ephemeral in-memory runs may use a random one.
    Plaintext secrets on the CLI are deliberately not accepted.
    """
    if secret_file:
        return _require_strong(Path(secret_file).read_bytes().strip(),
                               f"secret file {secret_file!r}")
    env_secret = environ.get("RESONANCE_CONFIRMATION_SECRET", "").strip()
    if env_secret:
        return _require_strong(env_secret.encode("utf-8"),
                               "RESONANCE_CONFIRMATION_SECRET")
    if db_path != ":memory:":
        raise ValueError(
            "a persistent --db requires a stable confirmation secret: pass "
            "--secret-file or set RESONANCE_CONFIRMATION_SECRET, otherwise "
            "prepared private drafts cannot survive a restart"
        )
    return None


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Resonance live product server")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--db", default="live-product.sqlite3")
    parser.add_argument("--origin", action="append", default=None,
                        help="allowed browser origin (repeatable)")
    parser.add_argument("--secret-file", default=None,
                        help="file holding the stable draft-confirmation secret")
    parser.add_argument("--no-seed", action="store_true",
                        help="start with an empty live corpus (no R7 seed baseline)")
    args = parser.parse_args(argv)
    origins = frozenset(args.origin or [f"http://{args.host}:{args.port}"])
    try:
        secret = _resolve_secret(args.secret_file, os.environ, args.db)
    except ValueError as exc:
        parser.error(str(exc))
    runtime = build_runtime(args.db, allowed_origins=origins,
                            confirmation_secret=secret,
                            seed=not args.no_seed)
    server = serve(args.host, args.port, runtime=runtime)
    print(f"live product on http://{args.host}:{args.port} "
          f"(origins: {sorted(origins)}; db: {args.db}; mode: LIVE)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    main()
