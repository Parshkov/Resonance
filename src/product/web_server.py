"""The production HTTP server: the live product plus the browser write path.

`src/product/server.py` serves the product API and the page; this module adds
the browser WebMCP tools on top of it — prepare, preview, share and consent —
so a person can go from a thought to a discoverable share without leaving the
page.  It is a transport adapter, not a second product state machine: identity,
drafts, consent, discovery results and intro/channel state all live in the
services underneath, and the only state kept here is a small per-process
operation receipt cache so an aborted browser write can be reconciled.

Every read and write requires an authenticated session, and discovery requires
a thought the visitor has explicitly shared.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import threading
from http import HTTPStatus
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import parse_qs

from src.ingestion.identity import (
    INGESTION_DISCARDED,
    INGESTION_PREPARED,
    INGESTION_SHARED,
)
from src.ingestion.service import ShareIntent
from src.product.mcp_bridge import (
    BridgeError, _has_usable_structure, _insufficient_structure_message, _slug,
    _structure_summary, build_thought_dna,
)
from src.identity.models import AuthenticationError
from src.persistence.errors import PersistenceConflictError
from src.product import oauth_mount
from src.product.server import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    UI_DIR,
    ProductHandler,
    ProductRuntime,
    _redact_db,
    _resolve_secret,
    build_runtime,
    startup_purge_demo,
    startup_purge_sessions,
    startup_purge_unsigned,
)

WEBMCP_CONTRACT = "resonance-webmcp/0.1"
REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")
WRITE_OPERATIONS = frozenset({"prepare", "share", "consent"})
CANONICAL_K = 15
CANONICAL_MODE = "analogical"


def _fingerprint(body: Mapping[str, Any]) -> str:
    semantic = {key: value for key, value in body.items() if key != "request_id"}
    raw = json.dumps(semantic, sort_keys=True, separators=(",", ":"),
                     ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


class LiveWebMCPBridge:
    """Translation bookkeeping only; no authoritative product state lives here."""

    def __init__(self) -> None:
        self.lock = threading.RLock()
        self.operations: dict[tuple[str, str, str], dict[str, Any]] = {}

    def operation(self, subject: str, operation: str,
                  request_id: str) -> dict[str, Any] | None:
        with self.lock:
            return self.operations.get((subject, operation, request_id))

    def remember(self, subject: str, operation: str, request_id: str,
                 fingerprint: str, result: Mapping[str, Any]) -> None:
        with self.lock:
            self.operations[(subject, operation, request_id)] = {
                "fingerprint": fingerprint,
                "result": dict(result),
            }


def _latest_prepared_draft(product, token: str) -> str | None:
    actor = product.identity.authenticate(token)
    states: dict[str, tuple[str, str]] = {}
    for event in product.identity.backend.list_identity_events():
        if event.user_id != actor.user_id:
            continue
        draft_id = str(event.payload.get("draft_id", ""))
        if not draft_id:
            continue
        if event.event_type == INGESTION_PREPARED:
            states[draft_id] = ("prepared", event.created_at)
        elif event.event_type == INGESTION_SHARED:
            states[draft_id] = ("shared", event.created_at)
        elif event.event_type == INGESTION_DISCARDED:
            states[draft_id] = ("discarded", event.created_at)
    prepared = [(when, draft) for draft, (status, when) in states.items()
                if status == "prepared"]
    return max(prepared)[1] if prepared else None


def _owned_live_session(product, token: str) -> str | None:
    rows = product.owned_sessions(token)
    discoverable = [row for row in rows if row.get("share_state") == "discoverable"]
    if not discoverable:
        return None
    return str(discoverable[-1].get("session_id") or "") or None


def _has_shared(product, token: str) -> bool:
    return _owned_live_session(product, token) is not None


MAX_CONTEXT_CHARS = 4000


def _presentation_for(thought: Any) -> dict[str, Any]:
    """The durable projection needs exactly {topic, domain, cluster_id}; derive
    them from what the agent supplied (never from the raw text)."""
    topic = (str(thought.get("topic") or "").strip() if isinstance(thought, Mapping) else "") \
        or "Shared thought"
    domain = (str(thought.get("domain") or "").strip() if isinstance(thought, Mapping) else "") \
        or "general"
    return {"topic": topic[:120], "domain": domain[:60],
            "cluster_id": (_slug(topic) or "shared")[:48]}


def _live_context(product, token: str) -> dict[str, Any] | None:
    session_id = _owned_live_session(product, token)
    if not session_id:
        return None
    session = product.identity.backend.get_session(session_id)
    if session is None:
        return None
    thought = dict(getattr(session, "thought_dna", {}) or {})
    presentation = dict(getattr(session, "presentation", {}) or {})
    location = dict(getattr(session, "location", {}) or {})
    consent = product.identity.policy_source.session_consent(session_id)
    context: dict[str, Any] = {
        "contract_version": "resonance-ui-context/0.1",
        "active_thought": {
            "thought_id": thought.get("thought_id", ""),
            "source": thought.get("source", {"text": "", "sha256": ""}),
            "nodes": [
                {"id": n.get("id"), "label": n.get("label"), "role": n.get("role")}
                for n in thought.get("nodes", [])
            ],
            "relations": [
                {"id": r.get("id"), "source": r.get("source"),
                 "target": r.get("target"), "type": r.get("type")}
                for r in thought.get("relations", [])
            ],
        },
        "consent": {"shared_with_resonance": True},
        "pinned_request": {"mode": CANONICAL_MODE, "k": CANONICAL_K},
    }
    if consent.get("share_display_profile"):
        context["presentation"] = {
            "topic": presentation.get("topic", "Shared thought"),
            "domain": presentation.get("domain", ""),
        }
    if consent.get("share_coarse_location") and location:
        context["location"] = location
    return context


def _discovery_view(live: Mapping[str, Any]) -> dict[str, Any]:
    """The shape the page reads; rank/score/evidence are not recomputed."""
    return {
        "contract_version": live.get("discovery_contract") or "resonance-discovery/0.1",
        "query": live.get("query", {}),
        "matches": list(live.get("matches", [])),
        "rejected": list(live.get("rejected", [])),
    }


class WebHandler(ProductHandler):
    bridge: LiveWebMCPBridge

    def _subject(self, token: str) -> str:
        return self.runtime.product.identity.authenticate(token).user_id

    def _request_id(self, body: Mapping[str, Any]) -> str:
        request_id = body.get("request_id")
        if not isinstance(request_id, str) or not REQUEST_ID_RE.fullmatch(request_id):
            raise ValueError("request_id must be 1-128 characters from A-Z a-z 0-9 _ . : -")
        return request_id

    def _operation_start(self, token: str, operation: str,
                         body: Mapping[str, Any]):
        request_id = self._request_id(body)
        subject = self._subject(token)
        fingerprint = _fingerprint(body)
        existing = self.bridge.operation(subject, operation, request_id)
        if existing is not None:
            if existing["fingerprint"] != fingerprint:
                raise PersistenceConflictError(
                    "request_id was already used with different input")
            return subject, request_id, fingerprint, dict(existing["result"])
        return subject, request_id, fingerprint, None

    def _operation_finish(self, subject: str, operation: str, request_id: str,
                          fingerprint: str, result: Mapping[str, Any]) -> None:
        self.bridge.remember(subject, operation, request_id, fingerprint, result)
        self._send_json(dict(result))

    def _send_share_required(self) -> None:
        # A visitor who has not shared a thought is a product state, not a
        # server fault: the WebMCP discover tool used to raise an unmapped
        # PermissionError here and surface as a 500 "unexpected product error"
        # on the very first read anyone makes (same mapping the /api/discover
        # view already uses).
        self._send_json(
            {"error": "share_required",
             "message": "discovery needs a shared thought first: run "
                        "resonance_prepare_thought → resonance_get_share_preview → "
                        "resonance_share_prepared_thought (explicit confirm), then "
                        "resonance_discover again."},
            HTTPStatus.CONFLICT)

    def _visitor_token(self) -> str | None:
        """The visitor's bearer, or None when this browser has no session yet.

        A first load has no session cookie: `webmcp_live.mjs` creates the guest
        session, and the page's own boot fetches race it. "No session" and "no
        shared thought" are the same fact to a reader — nothing of theirs is
        discoverable — so the read routes answer with the same product state
        instead of an authentication fault. Any other identity error still
        propagates.
        """
        try:
            return self._token()
        except AuthenticationError:
            return None

    def _initial_app_state(self, params: Mapping[str, list[str]]) -> str:
        """Serve the state the page will settle in, so it is painted once.

        A visitor with no session cookie has certainly shared nothing, which is
        the common case and costs no lookup at all. With a cookie, one indexed
        read answers it.
        """
        token = self._visitor_token()
        if token is None:
            return "unshared"
        try:
            return "loading" if _owned_live_session(self.runtime.product, token) else "unshared"
        except Exception:                      # never fail a page load over this
            return "loading"

    def _route_get(self, path: str, params: dict[str, list[str]]) -> None:
        product = self.runtime.product

        # These two routes translate the page's presentation contract to the
        # live product without any shadow DB.
        if path == "/api/context":
            context = None
            token = self._visitor_token()
            if token is not None:
                try:
                    context = _live_context(product, token)
                except Exception:
                    context = None
            if context is None:
                # A visitor who has shared nothing has no active thought. Fail
                # closed with the same product state the discovery routes use,
                # rather than showing them somebody else's thought as if it
                # were their own.
                self._send_share_required()
                return
            self._send_json(context)
            return
        if path == "/api/discover":
            token = self._visitor_token()
            session_id = _owned_live_session(product, token) if token else None
            if not session_id:
                # Not an error in the product: the visitor simply has not shared
                # a thought yet. PermissionError was unmapped and surfaced as a
                # 500 "unexpected product error" in the page's view.
                self._send_json(
                    {"error": "share_required",
                     "message": "discovery needs a shared thought first: run "
                                "resonance_prepare_thought → resonance_get_share_preview → "
                                "resonance_share_prepared_thought (or use the Collaboration "
                                "panel)."},
                    HTTPStatus.CONFLICT)
                return
            live = product.discover(token, session_id, mode=CANONICAL_MODE, k=CANONICAL_K)
            self._send_json(_discovery_view(live))
            return

        # The browser tools are the live implementation of the same tool names
        # the standalone demo server under demo/ui/ registers from webmcp.mjs.
        if path == "/webmcp.mjs":
            self._send_bytes((UI_DIR / "webmcp_live.mjs").read_bytes(),
                             "text/javascript; charset=utf-8")
            return

        if path == "/api/webmcp/state":
            try:
                token = self._token()
                product.identity.authenticate(token)
            except Exception:
                self._send_json({
                    "contract_version": WEBMCP_CONTRACT,
                    "draft_ready": False, "draft_id": None, "shared": False,
                    "authenticated": False,
                })
                return
            draft_id = _latest_prepared_draft(product, token)
            self._send_json({
                "contract_version": WEBMCP_CONTRACT,
                "draft_ready": draft_id is not None,
                "draft_id": draft_id,
                "shared": _has_shared(product, token),
                "authenticated": True,
                "freshness": product.freshness(),
            })
            return

        if path == "/api/webmcp/operation":
            token = self._token()
            subject = self._subject(token)
            operation = (params.get("operation") or [""])[0]
            request_id = (params.get("request_id") or [""])[0]
            if operation not in WRITE_OPERATIONS or not REQUEST_ID_RE.fullmatch(request_id):
                raise ValueError("valid operation and request_id are required")
            record = self.bridge.operation(subject, operation, request_id)
            if record is None:
                self._send_json({
                    "error": "operation_not_committed",
                    "message": "no committed result exists for this operation key",
                    "retryable": True,
                }, HTTPStatus.NOT_FOUND)
                return
            self._send_json({
                "contract_version": WEBMCP_CONTRACT,
                "operation": operation,
                "request_id": request_id,
                "committed": True,
                "result": record["result"],
            })
            return

        if path == "/api/webmcp/preview":
            token = self._token()
            draft_id = _latest_prepared_draft(product, token)
            if not draft_id:
                raise PersistenceConflictError("no prepared private draft exists")
            preview = product.preview(token, draft_id, client_id="live-browser-webmcp")
            self._send_json({
                "contract_version": WEBMCP_CONTRACT,
                "draft_id": draft_id,
                "confirmation_token": preview["confirmation_token"],
                "will_become_discoverable": {
                    "thought": preview.get("thought_dna"),
                    "presentation": preview.get("presentation"),
                    "location": preview.get("coarse_location"),
                },
                "currently_shared": _has_shared(product, token),
                "requires_explicit_confirmation": True,
                "source_retention": preview.get("source_retention", "not_retained"),
            })
            return

        if path == "/api/webmcp/discover":
            token = self._token()
            session_id = _owned_live_session(product, token)
            if not session_id:
                self._send_share_required()
                return
            live = product.discover(token, session_id, mode=CANONICAL_MODE, k=CANONICAL_K,
                                    client_id="live-browser-webmcp")
            self._send_json({
                "contract_version": WEBMCP_CONTRACT,
                "result_id": live["result_id"],
                "source": "live",
                "discovery_contract": live.get("discovery_contract"),
                "query": live.get("query", {}),
                "matches_in_backend_order": list(live.get("matches", [])),
                "aggregation": live.get("aggregation", {}),
                "freshness": live.get("freshness", {}),
                "location_note": live.get("location_note", ""),
            })
            return

        if path == "/api/webmcp/match":
            result_id = (params.get("result_id") or [""])[0]
            session_id = (params.get("session_id") or [""])[0]
            token = self._token()
            result = product.get_match(token, result_id, session_id)
            self._send_json({"contract_version": WEBMCP_CONTRACT,
                             "result_id": result_id, "source": "live",
                             "freshness": result.get("freshness"),
                             "match": result["match"]})
            return

        super()._route_get(path, params)

    def _route_post(self, path: str) -> None:
        if path not in {"/api/webmcp/prepare", "/api/webmcp/share",
                        "/api/webmcp/consent"}:
            super()._route_post(path)
            return

        product = self.runtime.product
        token = self._token()
        body = self._body()
        operation = path.rsplit("/", 1)[-1]
        subject, request_id, fingerprint, committed = self._operation_start(
            token, operation, body)
        if committed is not None:
            self._send_json(committed)
            return
        security = self._security_kwargs()
        security["client_id"] = "live-browser-webmcp"

        if operation == "prepare":
            intent = ShareIntent(
                share_display_profile=True,
                share_coarse_location=False,
                receive_intro_requests=True,
            )
            thought = body.get("thought")
            context = body.get("context")
            if thought is not None and context:
                raise ValueError("provide either thought or context, not both")
            if thought is None and not context:
                # There is no stand-in content to fall back on. A prepare with
                # nothing in it used to clone a fixture thought, which made the
                # visitor's first durable row a thought they never had.
                raise ValueError("provide the person's own reasoning as either "
                                 "thought (a labelled causal graph) or context (their text)")
            # The agent hands over the person's REAL reasoning: a labelled
            # causal graph it extracted (preferred) or raw text for the cue
            # extractor. Same contract as remote MCP; the text is never
            # retained.
            presentation = _presentation_for(thought)
            if thought is not None:
                candidate = build_thought_dna(thought, human_id=subject)
                result = product.prepare_structured(
                    token, candidate, presentation=presentation,
                    coarse_location=None, intent=intent, **security)
            else:
                if not isinstance(context, str) or len(context) > MAX_CONTEXT_CHARS:
                    raise ValueError(f"context must be text of at most {MAX_CONTEXT_CHARS} characters")
                # Per-prepare namespace: the extracted id must not collide
                # with a reserved/revoked id for the same sentences.
                result = product.prepare_raw_text(
                    token, context, source_id=f"{subject}:{request_id}",
                    presentation=presentation, coarse_location=None,
                    intent=intent, **security)
                preview = product.preview(token, str(result["draft_id"]),
                                          client_id="live-browser-webmcp")
                structure = _structure_summary(preview.get("thought_dna"))
                if not _has_usable_structure(structure):
                    # Empty graphs must not become shareable drafts (the
                    # extractor abstains on implicit prose).
                    try:
                        product.discard(token, str(result["draft_id"]), confirmed=True, **security)
                    except Exception:  # noqa: BLE001 - best effort clean-up
                        pass
                    raise ValueError(_insufficient_structure_message(
                        structure, result.get("abstentions", [])))
            wire = {
                "contract_version": WEBMCP_CONTRACT,
                "draft_id": result["draft_id"],
                "session_id": result.get("session_id"),
                "discoverable": False,
                "source_retention": result.get("source_retention", "not_retained"),
                "input_kind": result.get("input_kind"),
                "next_step": "Preview exactly what will be shared, then confirm.",
            }
            self._operation_finish(subject, operation, request_id, fingerprint, wire)
            return

        if operation == "share":
            if body.get("confirm") is not True:
                raise ValueError("confirm=true is required after preview")
            draft_id = _latest_prepared_draft(product, token)
            if not draft_id:
                raise PersistenceConflictError("no prepared private draft exists")
            result = product.share_prepared(
                token, draft_id,
                confirmation_token=str(body.get("confirmation_token", "")),
                confirmed=True, **security,
            )
            wire = {
                "contract_version": WEBMCP_CONTRACT,
                "draft_id": draft_id,
                "session_id": result.get("session_id"),
                "shared": True,
                "discoverable": True,
            }
            self._operation_finish(subject, operation, request_id, fingerprint, wire)
            return

        # The consent tool is intentionally revoke-only unless already shared.
        shared = body.get("shared") is True
        session_id = _owned_live_session(product, token)
        if shared:
            if not session_id:
                raise PersistenceConflictError(
                    "restoring sharing requires prepare, preview, and explicit share")
            wire = {"contract_version": WEBMCP_CONTRACT,
                    "session_id": session_id, "shared": True,
                    "revoked": False, "discoverable": True}
        else:
            if session_id:
                product.revoke_session(token, session_id, confirmed=True, **security)
            wire = {"contract_version": WEBMCP_CONTRACT,
                    "session_id": session_id, "shared": False,
                    "revoked": True, "discoverable": False}
        self._operation_finish(subject, operation, request_id, fingerprint, wire)


def serve(host: str, port: int, *, runtime: ProductRuntime) -> ThreadingHTTPServer:
    bridge = LiveWebMCPBridge()
    handler = type("BoundWebHandler", (WebHandler,),
                   {"runtime": runtime, "bridge": bridge})
    return ThreadingHTTPServer((host, port), handler)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Resonance: live product + browser WebMCP")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--db", default="live-product.sqlite3")
    parser.add_argument("--origin", action="append", default=None)
    parser.add_argument("--secret-file", default=None)
    parser.add_argument("--seed-demo", action="store_true",
                        help="seed the R7 demo corpus into this database (RESONANCE_SEED_DEMO=1 "
                             "has the same effect); persistent databases are never seeded by default")
    args = parser.parse_args(argv)
    seed = True if args.db == ":memory:" else (
        args.seed_demo or os.environ.get("RESONANCE_SEED_DEMO", "").strip().lower() in ("1", "true", "yes", "on"))
    origins = frozenset(args.origin or [f"http://{args.host}:{args.port}"])
    try:
        secret = _resolve_secret(args.secret_file, os.environ, args.db)
    except ValueError as exc:
        parser.error(str(exc))
    runtime = build_runtime(args.db, allowed_origins=origins,
                            confirmation_secret=secret,
                            seed=seed)
    startup_purge_demo(runtime)
    startup_purge_sessions(runtime)
    startup_purge_unsigned(runtime)
    # R15C (#136): canonical OAuth for hosted MCP clients on this same origin.
    # Per request the issuer is re-derived from the host actually addressed
    # (`ProductHandler._issuer`), so every allowed origin serves its own
    # metadata. This value only labels the startup log, and `public_issuer()`
    # would pick the alphabetically first https origin — which stops being the
    # canonical one the moment a custom domain is added alongside the platform
    # host. The FIRST declared --origin is the canonical one, so say that.
    oauth_mount.attach_core(
        runtime, issuer=oauth_mount.canonical_origin(args.origin, origins))
    server = serve(args.host, args.port, runtime=runtime)
    print(f"resonance on http://{args.host}:{args.port} "
          f"(origins: {sorted(origins)}; db: {_redact_db(args.db)}; mode: LIVE+WebMCP)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    main()
