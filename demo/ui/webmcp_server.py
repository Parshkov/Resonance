#!/usr/bin/env python3
"""Browser WebMCP surface for the accepted Resonance R9 visual client.

This module is a progressive-enhancement transport over the accepted discovery
path. It does not implement matching, reranking, extraction, or scoring.

Run from the repository root:

    python3 -m demo.ui.webmcp_server --source replay

Use HTTPS in hosted/judge environments. Localhost is suitable for local browser
verification because browsers treat it as a potentially trustworthy origin.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import ipaddress
import json
import re
import secrets
import sys
import threading
from http import HTTPStatus
from http.server import ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

from .server import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    DemoHandler,
    UI_DIR,
    call_live_mcp,
    load_replay,
    public_context,
)

WEBMCP_CONTRACT = "resonance-webmcp/0.1"
MAX_BODY_BYTES = 16 * 1024
MAX_DISCOVERY_RESULTS = 8
REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")
RESULT_ID_RE = re.compile(r"^result-[0-9a-f]{24}$")
WRITE_OPERATIONS = frozenset({"prepare", "share", "consent"})


class WebMCPState:
    """Small in-process R10 demo state; R11 owns durable persistence."""

    def __init__(self) -> None:
        self.lock = threading.RLock()
        self.draft: dict[str, Any] | None = None
        self.shared = bool(public_context()["consent"]["shared_with_resonance"])
        self._confirmation_secret = secrets.token_bytes(32)
        self.operations: dict[tuple[str, str], dict[str, Any]] = {}
        self.discovery_results: dict[str, dict[str, Any]] = {}
        self.discovery_order: list[str] = []

    def reset(self) -> None:
        with self.lock:
            self.draft = None
            self.shared = bool(public_context()["consent"]["shared_with_resonance"])
            self._confirmation_secret = secrets.token_bytes(32)
            self.operations = {}
            self.discovery_results = {}
            self.discovery_order = []

    def rotate_confirmation_secret(self) -> None:
        self._confirmation_secret = secrets.token_bytes(32)

    def confirmation_token(self, draft_id: str) -> str:
        return hmac.new(
            self._confirmation_secret,
            draft_id.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def operation_record(self, operation: str, request_id: str) -> dict[str, Any] | None:
        return self.operations.get((operation, request_id))

    def remember_operation(
        self,
        operation: str,
        request_id: str,
        fingerprint: str,
        result: dict[str, Any],
    ) -> None:
        self.operations[(operation, request_id)] = {
            "fingerprint": fingerprint,
            "result": result,
        }

    def remember_discovery(self, source: str, payload: dict[str, Any]) -> str:
        canonical = json.dumps(
            {"source": source, "payload": payload},
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        result_id = "result-" + hashlib.sha256(canonical).hexdigest()[:24]
        self.discovery_results[result_id] = {"source": source, "payload": payload}
        if result_id in self.discovery_order:
            self.discovery_order.remove(result_id)
        self.discovery_order.append(result_id)
        while len(self.discovery_order) > MAX_DISCOVERY_RESULTS:
            expired = self.discovery_order.pop(0)
            self.discovery_results.pop(expired, None)
        return result_id

    def discovery_record(self, result_id: str) -> dict[str, Any] | None:
        return self.discovery_results.get(result_id)

    def clear_discovery_results(self) -> None:
        self.discovery_results = {}
        self.discovery_order = []


STATE = WebMCPState()


def _draft_from_context(note: str = "") -> dict[str, Any]:
    context = public_context()
    payload = {
        "thought": context["active_thought"],
        "presentation": context.get("presentation"),
        "location": context.get("location"),
        "note": note,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    draft_id = "draft-" + hashlib.sha256(canonical).hexdigest()[:16]
    return {
        "draft_id": draft_id,
        "thought": payload["thought"],
        "presentation": payload["presentation"],
        "location": payload["location"],
        "note": note,
        "discoverable": False,
    }


def _safe_match(row: dict[str, Any]) -> dict[str, Any]:
    """Project only the consent-safe accepted discovery fields."""
    return {
        "session_id": row["session_id"],
        "person_pseudonym": row["person_pseudonym"],
        "mode_classification": row["mode_classification"],
        "hard_rejection": row.get("hard_rejection"),
        "confidence": row.get("confidence"),
        "scores": row.get("scores"),
        "display": row.get("display"),
        "evidence": row.get("evidence"),
    }


def _discoverable_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in [*payload.get("matches", []), *payload.get("rejected", [])]:
        session_id = row.get("session_id")
        if not session_id or session_id in seen:
            continue
        if row.get("display", {}).get("share_state") != "discoverable":
            continue
        seen.add(session_id)
        rows.append(row)
    return rows


def _discovery_payload(source: str) -> dict[str, Any]:
    if source == "replay":
        return load_replay()
    if source == "live":
        return call_live_mcp()
    raise ValueError("source must be replay or live")


def _operation_fingerprint(body: dict[str, Any]) -> str:
    semantic = {key: value for key, value in body.items() if key != "request_id"}
    canonical = json.dumps(
        semantic,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


class WebMCPHandler(DemoHandler):
    server_version = "ResonanceWebMCP/0.1"

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path in {"/", "/index.html"}:
            html = (UI_DIR / "index.html").read_text(encoding="utf-8")
            injected = html.replace(
                "</body>",
                '  <script type="module" src="/webmcp.mjs"></script>\n</body>',
            )
            self._send_bytes(injected.encode(), "text/html; charset=utf-8")
            return
        if parsed.path == "/webmcp.mjs":
            self._send_bytes(
                (UI_DIR / "webmcp.mjs").read_bytes(),
                "text/javascript; charset=utf-8",
            )
            return
        if parsed.path == "/api/context":
            context = public_context()
            with STATE.lock:
                context["consent"]["shared_with_resonance"] = STATE.shared
            self._send_json(context)
            return
        if parsed.path == "/api/webmcp/state":
            with STATE.lock:
                self._send_json({
                    "contract_version": WEBMCP_CONTRACT,
                    "draft_ready": STATE.draft is not None,
                    "draft_id": STATE.draft["draft_id"] if STATE.draft else None,
                    "shared": STATE.shared,
                    "discovery_result_count": len(STATE.discovery_results),
                })
            return
        if parsed.path == "/api/webmcp/operation":
            params = parse_qs(parsed.query)
            operation = params.get("operation", [""])[0]
            request_id = params.get("request_id", [""])[0]
            if operation not in WRITE_OPERATIONS or not REQUEST_ID_RE.fullmatch(request_id):
                self._send_error(
                    HTTPStatus.BAD_REQUEST,
                    "validation_failed",
                    "valid operation and request_id are required",
                    retryable=False,
                )
                return
            with STATE.lock:
                record = STATE.operation_record(operation, request_id)
            if record is None:
                self._send_error(
                    HTTPStatus.NOT_FOUND,
                    "operation_not_committed",
                    "no committed result exists for this operation key",
                    retryable=True,
                )
                return
            self._send_json({
                "contract_version": WEBMCP_CONTRACT,
                "operation": operation,
                "request_id": request_id,
                "committed": True,
                "result": record["result"],
            })
            return
        if parsed.path == "/api/webmcp/preview":
            with STATE.lock:
                if STATE.draft is None:
                    self._send_error(
                        HTTPStatus.CONFLICT,
                        "draft_required",
                        "no prepared draft exists",
                        retryable=False,
                    )
                    return
                draft = STATE.draft
                token = STATE.confirmation_token(draft["draft_id"])
                self._send_json({
                    "contract_version": WEBMCP_CONTRACT,
                    "draft_id": draft["draft_id"],
                    "confirmation_token": token,
                    "will_become_discoverable": {
                        "thought": draft["thought"],
                        "presentation": draft["presentation"],
                        "location": draft["location"],
                    },
                    "currently_shared": STATE.shared,
                    "requires_explicit_confirmation": True,
                })
            return
        if parsed.path == "/api/webmcp/discover":
            self._handle_discover(parsed)
            return
        if parsed.path == "/api/webmcp/match":
            self._handle_match(parsed)
            return
        super().do_GET()

    def _handle_discover(self, parsed) -> None:
        with STATE.lock:
            if not STATE.shared:
                self._send_error(
                    HTTPStatus.FORBIDDEN,
                    "authorization_failed",
                    "current thought is private; sharing consent is required",
                    retryable=False,
                )
                return
        source = parse_qs(parsed.query).get("source", ["live"])[0]
        try:
            payload = _discovery_payload(source)
        except ValueError as exc:
            self._send_error(
                HTTPStatus.BAD_REQUEST,
                "validation_failed",
                str(exc),
                retryable=False,
            )
            return
        except (OSError, RuntimeError) as exc:
            self._send_error(
                HTTPStatus.BAD_GATEWAY,
                "upstream_unavailable",
                str(exc),
                retryable=True,
            )
            return
        rows = _discoverable_rows(payload)
        with STATE.lock:
            if not STATE.shared:
                self._send_error(
                    HTTPStatus.FORBIDDEN,
                    "authorization_failed",
                    "sharing was revoked before discovery completed",
                    retryable=False,
                )
                return
            result_id = STATE.remember_discovery(source, payload)
        self._send_json({
            "contract_version": WEBMCP_CONTRACT,
            "result_id": result_id,
            "source": source,
            "discovery_contract": payload.get("contract_version"),
            "query": payload.get("query"),
            "matches_in_backend_order": [_safe_match(row) for row in rows],
        })

    def _handle_match(self, parsed) -> None:
        params = parse_qs(parsed.query)
        result_id = params.get("result_id", [""])[0]
        session_id = params.get("session_id", [""])[0]
        if not RESULT_ID_RE.fullmatch(result_id) or not session_id:
            self._send_error(
                HTTPStatus.BAD_REQUEST,
                "validation_failed",
                "result_id and session_id are required",
                retryable=False,
            )
            return
        with STATE.lock:
            if not STATE.shared:
                self._send_error(
                    HTTPStatus.FORBIDDEN,
                    "authorization_failed",
                    "current thought is private",
                    retryable=False,
                )
                return
            record = STATE.discovery_record(result_id)
            if record is None:
                self._send_error(
                    HTTPStatus.NOT_FOUND,
                    "discovery_result_not_found",
                    "discovery result is unknown, expired, or revoked; run discovery again",
                    retryable=False,
                )
                return
            source = record["source"]
            payload = record["payload"]
        row = next(
            (candidate for candidate in _discoverable_rows(payload)
             if candidate["session_id"] == session_id),
            None,
        )
        if row is None:
            self._send_error(
                HTTPStatus.NOT_FOUND,
                "not_found",
                "match is not present as discoverable in the referenced discovery result",
                retryable=False,
            )
            return
        self._send_json({
            "contract_version": WEBMCP_CONTRACT,
            "result_id": result_id,
            "source": source,
            "match": _safe_match(row),
        })

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        operations = {
            "/api/webmcp/prepare": "prepare",
            "/api/webmcp/share": "share",
            "/api/webmcp/consent": "consent",
        }
        operation = operations.get(parsed.path)
        if operation is None:
            self._send_error(
                HTTPStatus.NOT_FOUND,
                "not_found",
                "endpoint not found",
                retryable=False,
            )
            return
        if not self._same_origin_request():
            self._send_error(
                HTTPStatus.FORBIDDEN,
                "authorization_failed",
                "cross-origin write rejected",
                retryable=False,
            )
            return
        try:
            body = self._read_json_body()
        except (ValueError, json.JSONDecodeError) as exc:
            self._send_error(
                HTTPStatus.BAD_REQUEST,
                "validation_failed",
                str(exc),
                retryable=False,
            )
            return

        request_id = body.get("request_id")
        if not isinstance(request_id, str) or not REQUEST_ID_RE.fullmatch(request_id):
            self._send_error(
                HTTPStatus.BAD_REQUEST,
                "validation_failed",
                "request_id must be 1-128 characters from A-Z a-z 0-9 _ . : -",
                retryable=False,
            )
            return
        fingerprint = _operation_fingerprint(body)

        with STATE.lock:
            existing = STATE.operation_record(operation, request_id)
            if existing is not None:
                if existing["fingerprint"] != fingerprint:
                    result: dict[str, Any] | None = None
                    conflict = True
                else:
                    result = existing["result"]
                    conflict = False
            else:
                result = None
                conflict = False

        if conflict:
            self._send_error(
                HTTPStatus.CONFLICT,
                "idempotency_conflict",
                "request_id was already used with different input",
                retryable=False,
            )
            return
        if result is not None:
            self._send_json(result)
            return

        if operation == "prepare":
            self._prepare(request_id, fingerprint, body)
            return
        if operation == "share":
            self._share(request_id, fingerprint, body)
            return
        self._update_consent(request_id, fingerprint, body)

    def _prepare(
        self,
        request_id: str,
        fingerprint: str,
        body: dict[str, Any],
    ) -> None:
        note = body.get("note", "")
        if not isinstance(note, str) or len(note) > 500:
            self._send_error(
                HTTPStatus.BAD_REQUEST,
                "validation_failed",
                "note must be a string of at most 500 characters",
                retryable=False,
            )
            return
        draft = _draft_from_context(note)
        result = {
            "contract_version": WEBMCP_CONTRACT,
            "request_id": request_id,
            "draft_id": draft["draft_id"],
            "status": "prepared_private",
            "discoverable": False,
            "next_step": "Call resonance_get_share_preview before explicit share confirmation.",
        }
        with STATE.lock:
            existing = STATE.operation_record("prepare", request_id)
            if existing is not None:
                if existing["fingerprint"] == fingerprint:
                    result = existing["result"]
                else:
                    self._send_error(
                        HTTPStatus.CONFLICT,
                        "idempotency_conflict",
                        "request_id was already used with different input",
                        retryable=False,
                    )
                    return
            else:
                STATE.rotate_confirmation_secret()
                STATE.draft = draft
                STATE.remember_operation("prepare", request_id, fingerprint, result)
        self._send_json(result)

    def _share(
        self,
        request_id: str,
        fingerprint: str,
        body: dict[str, Any],
    ) -> None:
        if body.get("confirm") is not True:
            self._send_error(
                HTTPStatus.PRECONDITION_REQUIRED,
                "confirmation_required",
                "explicit confirm=true is required after preview",
                retryable=False,
            )
            return
        token = body.get("confirmation_token")
        if not isinstance(token, str) or not token:
            self._send_error(
                HTTPStatus.PRECONDITION_REQUIRED,
                "confirmation_required",
                "confirmation_token from share preview is required",
                retryable=False,
            )
            return
        with STATE.lock:
            existing = STATE.operation_record("share", request_id)
            if existing is not None:
                if existing["fingerprint"] != fingerprint:
                    self._send_error(
                        HTTPStatus.CONFLICT,
                        "idempotency_conflict",
                        "request_id was already used with different input",
                        retryable=False,
                    )
                    return
                result = existing["result"]
            else:
                if STATE.draft is None:
                    self._send_error(
                        HTTPStatus.CONFLICT,
                        "draft_required",
                        "prepare and preview a draft first",
                        retryable=False,
                    )
                    return
                draft_id = STATE.draft["draft_id"]
                expected = STATE.confirmation_token(draft_id)
                if not hmac.compare_digest(token, expected):
                    self._send_error(
                        HTTPStatus.PRECONDITION_FAILED,
                        "confirmation_failed",
                        "share preview token is invalid or stale",
                        retryable=False,
                    )
                    return
                result = {
                    "contract_version": WEBMCP_CONTRACT,
                    "request_id": request_id,
                    "draft_id": draft_id,
                    "shared": True,
                    "discoverable": True,
                }
                STATE.shared = True
                STATE.draft = None
                STATE.rotate_confirmation_secret()
                STATE.clear_discovery_results()
                STATE.remember_operation("share", request_id, fingerprint, result)
        self._send_json(result)

    def _update_consent(
        self,
        request_id: str,
        fingerprint: str,
        body: dict[str, Any],
    ) -> None:
        shared = body.get("shared")
        if not isinstance(shared, bool):
            self._send_error(
                HTTPStatus.BAD_REQUEST,
                "validation_failed",
                "shared must be boolean",
                retryable=False,
            )
            return
        with STATE.lock:
            existing = STATE.operation_record("consent", request_id)
            if existing is not None:
                if existing["fingerprint"] != fingerprint:
                    self._send_error(
                        HTTPStatus.CONFLICT,
                        "idempotency_conflict",
                        "request_id was already used with different input",
                        retryable=False,
                    )
                    return
                result = existing["result"]
            else:
                if shared and not STATE.shared:
                    self._send_error(
                        HTTPStatus.CONFLICT,
                        "confirmation_required",
                        "restoring sharing requires prepare, preview, and explicit share confirmation",
                        retryable=False,
                    )
                    return
                if not shared:
                    STATE.shared = False
                    STATE.rotate_confirmation_secret()
                    STATE.clear_discovery_results()
                result = {
                    "contract_version": WEBMCP_CONTRACT,
                    "request_id": request_id,
                    "shared": STATE.shared,
                    "discoverable": STATE.shared,
                    "revoked": not STATE.shared,
                }
                STATE.remember_operation("consent", request_id, fingerprint, result)
        self._send_json(result)

    def _read_json_body(self) -> dict[str, Any]:
        raw_length = self.headers.get("Content-Length", "0")
        try:
            length = int(raw_length)
        except ValueError as exc:
            raise ValueError("invalid Content-Length") from exc
        if length < 0 or length > MAX_BODY_BYTES:
            raise ValueError("request body too large")
        raw = self.rfile.read(length)
        payload = json.loads(raw or b"{}")
        if not isinstance(payload, dict):
            raise ValueError("JSON body must be an object")
        return payload

    def _same_origin_request(self) -> bool:
        origin = self.headers.get("Origin")
        if not origin:
            try:
                return ipaddress.ip_address(self.client_address[0]).is_loopback
            except ValueError:
                return False
        parsed = urlparse(origin)
        if parsed.scheme not in {"http", "https"}:
            return False
        if parsed.netloc != self.headers.get("Host"):
            return False
        fetch_site = self.headers.get("Sec-Fetch-Site")
        return fetch_site not in {"cross-site"}

    def _send_error(
        self,
        status: HTTPStatus,
        code: str,
        message: str,
        *,
        retryable: bool,
    ) -> None:
        self._send_json(
            {"error": code, "message": message, "retryable": retryable},
            status=status,
        )

    def _send_bytes(
        self,
        body: bytes,
        content_type: str,
        status: HTTPStatus = HTTPStatus.OK,
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cross-Origin-Opener-Policy", "same-origin")
        self.send_header("Permissions-Policy", "tools=(self)")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data:; style-src 'self'; "
            "script-src 'self'; connect-src 'self'; object-src 'none'; "
            "base-uri 'none'; frame-ancestors 'none'",
        )
        self.end_headers()
        self.wfile.write(body)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--source", choices=("replay", "live"), default="replay")
    args = parser.parse_args(argv)
    WebMCPHandler.default_source = args.source
    server = ThreadingHTTPServer((args.host, args.port), WebMCPHandler)
    print(f"Resonance WebMCP ({args.source}): http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
