"""Authenticated Streamable HTTP MCP endpoint over the live product (R15).

Transport only: parse JSON-RPC, resolve the bearer token to an authenticated
subject, bind the MCP protocol session to that subject+client, dispatch to the
`LiveProductService`, serialize. MCP protocol 2025-03-26 Streamable HTTP.

Closes the recorded #93 blockers:
* live durable subject-scoped state (no R7 fixture) — via `RemoteProductService`;
* the MCP protocol session is bound to the authenticated subject/client, and a
  token whose subject no longer matches is rejected immediately;
* OAuth 2.1 code+PKCE is tied to the accepted R12 identity (login/guest), not a
  caller-selected demo identity;
* strict request-body bound before dispatch;
* full write surface (prepare/preview/share/revoke, intro/message, workspace)
  plus discover with R13B structuredContent + EmbeddedResource SVG.
"""

from __future__ import annotations

import json
import secrets
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

from src.mcp.server import (INTERNAL_ERROR, INVALID_PARAMS, INVALID_REQUEST,
                            METHOD_NOT_FOUND, PARSE_ERROR)

from .service import RemoteProductService, TOOL_ERRORS

PROTOCOL_VERSION = "2025-03-26"
REMOTE_VERSION = "resonance-remote-mcp/0.2"
MAX_BODY_BYTES = 128 * 1024


def _tool(name, description, schema, *, read_only=False, untrusted=False):
    ann: dict[str, Any] = {}
    if read_only:
        ann["readOnlyHint"] = True
    if untrusted:
        ann["untrustedContentHint"] = True
    return {"name": name, "description": description, "inputSchema": schema,
            "annotations": ann}


_OBJ = {"type": "object"}
TOOLS = [
    _tool("resonance_whoami", "Return the authenticated subject and owned sessions.",
          {"type": "object", "properties": {}, "additionalProperties": False},
          read_only=True),
    _tool("resonance_prepare_thought",
          "Prepare a private Thought DNA draft from a structured candidate or raw context. Exactly one of candidate or context.",
          {"type": "object", "properties": {
              "candidate": _OBJ, "context": {"type": "string"},
              "presentation": _OBJ, "coarse_location": _OBJ, "intent": _OBJ}}),
    _tool("resonance_get_share_preview",
          "Read the exact fields that would become discoverable and the one-time confirmation token.",
          {"type": "object", "required": ["draft_id"],
           "properties": {"draft_id": {"type": "string"}}}, untrusted=True),
    _tool("resonance_share_thought",
          "Explicitly share a prepared draft. Requires confirm=true and the preview confirmation_token.",
          {"type": "object", "required": ["draft_id", "confirmation_token", "confirm"],
           "properties": {"draft_id": {"type": "string"},
                          "confirmation_token": {"type": "string"},
                          "confirm": {"type": "boolean"}}}),
    _tool("resonance_update_consent",
          "Change consent for an owned session (revoke discovery or adjust sharing). Requires confirm=true.",
          {"type": "object", "required": ["session_id", "confirm"],
           "properties": {"session_id": {"type": "string"}, "choices": _OBJ,
                          "confirm": {"type": "boolean"}}}),
    _tool("resonance_discover",
          "Run structural discovery from an owned session. Returns structuredContent plus a consent-safe map image.",
          {"type": "object", "required": ["session_id"],
           "properties": {"session_id": {"type": "string"},
                          "mode": {"type": "string"},
                          "k": {"type": "integer"}}}, untrusted=True),
    _tool("resonance_get_match",
          "Return backend evidence for one match bound to the exact discovery result_id.",
          {"type": "object", "required": ["result_id", "session_id"],
           "properties": {"result_id": {"type": "string"},
                          "session_id": {"type": "string"}}}, untrusted=True),
    _tool("resonance_request_intro",
          "Request a consent-gated introduction to a discovered session owner. Requires confirm=true.",
          {"type": "object",
           "required": ["from_session_id", "target_session_id", "message", "confirm"],
           "properties": {"from_session_id": {"type": "string"},
                          "target_session_id": {"type": "string"},
                          "message": {"type": "string"},
                          "request_id": {"type": "string"},
                          "confirm": {"type": "boolean"}}}),
    _tool("resonance_list_requests", "List incoming/outgoing introduction requests.",
          {"type": "object", "properties": {}, "additionalProperties": False},
          read_only=True, untrusted=True),
    _tool("resonance_respond_intro",
          "Accept or decline a pending incoming introduction. Requires confirm=true.",
          {"type": "object", "required": ["intro_id", "accept", "confirm"],
           "properties": {"intro_id": {"type": "string"}, "accept": {"type": "boolean"},
                          "request_id": {"type": "string"}, "confirm": {"type": "boolean"}}}),
    _tool("resonance_send_message",
          "Send a relay message in an accepted channel. Requires confirm=true.",
          {"type": "object", "required": ["channel_id", "body", "confirm"],
           "properties": {"channel_id": {"type": "string"}, "body": {"type": "string"},
                          "request_id": {"type": "string"}, "confirm": {"type": "boolean"}}}),
    _tool("resonance_read_messages", "Read the message thread of an accepted channel.",
          {"type": "object", "required": ["channel_id"],
           "properties": {"channel_id": {"type": "string"}}}, untrusted=True),
    _tool("resonance_create_workspace",
          "Create an idea workspace from an accepted introduction. Requires title.",
          {"type": "object", "required": ["intro_id", "title"],
           "properties": {"intro_id": {"type": "string"}, "title": {"type": "string"},
                          "brief": {"type": "string"}}}),
    _tool("resonance_get_workspace", "Read a workspace you are an active member of.",
          {"type": "object", "required": ["workspace_id"],
           "properties": {"workspace_id": {"type": "string"}}}, untrusted=True),
    _tool("resonance_list_workspaces", "List the workspaces you belong to.",
          {"type": "object", "properties": {}, "additionalProperties": False},
          read_only=True, untrusted=True),
]
_TOOL_NAMES = {t["name"] for t in TOOLS}


class RemoteMCP:
    """Protocol core, transport-framing-free (unit-testable without HTTP).

    A protocol session (Mcp-Session-Id) is bound to the subject that created it;
    a later request whose bearer resolves to a different subject is refused.
    """

    def __init__(self, service: RemoteProductService):
        self.service = service
        # session_id -> {subject, created_at}
        self.sessions: dict[str, dict[str, Any]] = {}

    def handle(self, message, subject, session_id):
        if message.get("jsonrpc") != "2.0" or "method" not in message:
            return self._err(message.get("id"), INVALID_REQUEST, "invalid request"), session_id
        method, msg_id = message["method"], message.get("id")
        params = message.get("params") or {}
        if method == "initialize":
            new_session = secrets.token_urlsafe(16)
            self.sessions[new_session] = {"subject": subject}
            return ({"jsonrpc": "2.0", "id": msg_id, "result": {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "resonance-remote", "version": REMOTE_VERSION}}},
                new_session)
        if method == "notifications/initialized":
            return None, session_id
        if msg_id is None:
            return None, session_id
        bound = self.sessions.get(session_id)
        if bound is None:
            return self._err(msg_id, INVALID_REQUEST, "unknown or missing Mcp-Session-Id"), session_id
        # Subject binding: the session belongs to exactly one subject. A token
        # that now resolves to a different subject (or none) cannot use it.
        if subject is None or bound["subject"] != subject:
            return self._err(msg_id, INVALID_REQUEST,
                             "session is bound to a different authenticated subject"), session_id
        if method == "ping":
            return {"jsonrpc": "2.0", "id": msg_id, "result": {}}, session_id
        if method == "tools/list":
            return {"jsonrpc": "2.0", "id": msg_id, "result": {"tools": TOOLS}}, session_id
        if method == "tools/call":
            return self._call(msg_id, params, bound["bearer"]), session_id
        return self._err(msg_id, METHOD_NOT_FOUND, f"unknown method: {method}"), session_id

    def _call(self, msg_id, params, bearer):
        name = params.get("name")
        if name not in _TOOL_NAMES:
            return self._err(msg_id, METHOD_NOT_FOUND, f"unknown tool: {name}")
        args = dict(params.get("arguments") or {})
        try:
            payload, rich = self._dispatch(name, args, bearer)
        except TOOL_ERRORS as exc:
            return self._tool_error(msg_id, type(exc).__name__, str(exc))
        except KeyError as exc:
            return self._err(msg_id, INVALID_PARAMS, f"missing argument: {exc}")
        except TypeError as exc:
            return self._err(msg_id, INVALID_PARAMS, f"bad arguments: {exc}")
        except Exception as exc:  # noqa: BLE001 -- transport survival
            return self._err(msg_id, INTERNAL_ERROR, f"{type(exc).__name__}: {exc}")
        content = [{"type": "text",
                    "text": json.dumps(payload, ensure_ascii=False, sort_keys=True)}]
        content.extend(rich)
        result: dict[str, Any] = {"content": content, "isError": False}
        if isinstance(payload, dict):
            result["structuredContent"] = payload
        return {"jsonrpc": "2.0", "id": msg_id, "result": result}

    def _dispatch(self, name, a, bearer):
        s = self.service
        rich: list[dict[str, Any]] = []
        if name == "resonance_whoami":
            return s.whoami(bearer), rich
        if name == "resonance_prepare_thought":
            return s.prepare(bearer, candidate=a.get("candidate"),
                             context=a.get("context"), presentation=a.get("presentation"),
                             coarse_location=a.get("coarse_location"),
                             intent=a.get("intent")), rich
        if name == "resonance_get_share_preview":
            return s.preview(bearer, a["draft_id"]), rich
        if name == "resonance_share_thought":
            return s.share(bearer, a["draft_id"], a["confirmation_token"],
                          bool(a.get("confirm", False))), rich
        if name == "resonance_update_consent":
            return s.set_consent(bearer, a["session_id"], a.get("choices") or {},
                                bool(a.get("confirm", False))), rich
        if name == "resonance_discover":
            packaged = s.discover(bearer, a["session_id"],
                                  mode=a.get("mode", "analogical"),
                                  k=int(a.get("k", 8)))
            # packaged already has content blocks incl. the SVG resource; unwrap
            # so the outer envelope carries structuredContent + those blocks.
            rich.extend(b for b in packaged.get("content", []) if b.get("type") != "text")
            return packaged["structuredContent"], rich
        if name == "resonance_get_match":
            return s.get_match(bearer, a["result_id"], a["session_id"]), rich
        if name == "resonance_request_intro":
            return s.request_intro(bearer, from_session_id=a["from_session_id"],
                                  target_session_id=a["target_session_id"],
                                  message=a["message"], request_id=a.get("request_id"),
                                  confirmed=bool(a.get("confirm", False))), rich
        if name == "resonance_list_requests":
            return s.list_requests(bearer), rich
        if name == "resonance_respond_intro":
            return s.respond_intro(bearer, a["intro_id"], accept=bool(a["accept"]),
                                  request_id=a.get("request_id"),
                                  confirmed=bool(a.get("confirm", False))), rich
        if name == "resonance_send_message":
            return s.send_message(bearer, a["channel_id"], a["body"],
                                 request_id=a.get("request_id"),
                                 confirmed=bool(a.get("confirm", False))), rich
        if name == "resonance_read_messages":
            return s.read_messages(bearer, a["channel_id"]), rich
        if name == "resonance_create_workspace":
            return s.create_workspace(bearer, a["intro_id"], title=a["title"],
                                     brief=a.get("brief", "")), rich
        if name == "resonance_get_workspace":
            return s.get_workspace(bearer, a["workspace_id"]), rich
        if name == "resonance_list_workspaces":
            return s.list_workspaces(bearer), rich
        raise KeyError(name)

    @staticmethod
    def _err(msg_id, code, message):
        return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}}

    @staticmethod
    def _tool_error(msg_id, kind, message):
        return {"jsonrpc": "2.0", "id": msg_id, "result": {
            "content": [{"type": "text",
                         "text": json.dumps({"error": kind, "message": message})}],
            "isError": True}}


class StreamableHTTPHandler(BaseHTTPRequestHandler):
    core: RemoteMCP
    service: RemoteProductService
    server_version = "resonance-remote/0.2"

    def log_message(self, fmt, *args):
        pass

    def _body(self) -> bytes:
        length = int(self.headers.get("Content-Length") or 0)
        if length < 0 or length > MAX_BODY_BYTES:
            raise ValueError("request body exceeds bound")
        return self.rfile.read(length) if length else b""

    def _send(self, status, payload, extra_headers=None):
        data = json.dumps(payload, ensure_ascii=False).encode() if payload is not None else b""
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("X-Content-Type-Options", "nosniff")
        for k, v in (extra_headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if data:
            self.wfile.write(data)

    def _bearer(self) -> str | None:
        header = self.headers.get("Authorization") or ""
        if header.startswith("Bearer "):
            return header[len("Bearer "):].strip()
        return None

    def do_GET(self):  # noqa: N802
        if urlparse(self.path).path == "/mcp":
            self._send(405, {"error": "server-initiated streaming not supported in v0.2; POST JSON-RPC"})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):  # noqa: N802
        route = urlparse(self.path).path
        if route == "/oauth/authorize":
            return self._authorize()
        if route == "/oauth/token":
            return self._token()
        if route != "/mcp":
            return self._send(404, {"error": "not found"})
        bearer = self._bearer()
        subject = self.service.subject_for(bearer)
        if subject is None:
            return self._send(401, {"error": "valid bearer token required"},
                              {"WWW-Authenticate": "Bearer"})
        try:
            raw = self._body()
        except ValueError as exc:
            return self._send(413, {"error": str(exc)})
        try:
            message = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return self._send(400, {"jsonrpc": "2.0", "id": None,
                                    "error": {"code": PARSE_ERROR, "message": "parse error"}})
        session_id = self.headers.get("Mcp-Session-Id")
        # Stash the bearer on the session at initialize time so tool dispatch can
        # authenticate live-product calls with the exact token.
        reply, new_session = self.core.handle(message, subject, session_id)
        if new_session and new_session in self.core.sessions:
            self.core.sessions[new_session]["bearer"] = bearer
        headers = {}
        if new_session and new_session != session_id:
            headers["Mcp-Session-Id"] = new_session
        # MCP spec: an unknown/expired session on a session-requiring request is
        # HTTP 404 so the client re-initializes (sessions are in-memory and a
        # redeploy invalidates them). Subject-mismatch on a *known* session stays
        # a JSON-RPC error over 200.
        method = message.get("method")
        needs_session = method not in ("initialize", "notifications/initialized")
        if (needs_session and message.get("id") is not None
                and session_id not in self.core.sessions):
            self._send(404, reply, headers)
            return
        self._send(202 if reply is None else 200, reply, headers)

    # -- OAuth 2.1 code + PKCE tied to the accepted R12 identity ----------
    def _authorize(self):
        form = parse_qs(self._body().decode("utf-8"))
        g = lambda k: (form.get(k) or [""])[0]
        if g("code_challenge_method") != "S256":
            return self._send(400, {"error": "invalid_request",
                                    "error_description": "PKCE S256 required"})
        # Authenticate through R12: an existing user (user_id + recovery_secret)
        # or a fresh guest. Identity is never caller-asserted beyond the proof.
        try:
            if g("user_id") and g("recovery_secret"):
                creds = self.service.identity.login(g("user_id"), g("recovery_secret"),
                                                   actor_type="agent")
            else:
                creds = self.service.identity.register_guest(actor_type="agent")
        except Exception as exc:  # noqa: BLE001
            return self._send(400, {"error": "access_denied",
                                    "error_description": type(exc).__name__})
        try:
            code = self.service.runtime.remote_auth.issue_code(
                creds.access_token, g("code_challenge"), g("redirect_uri"), g("client_id"))
        except ValueError as exc:
            return self._send(400, {"error": "invalid_request",
                                    "error_description": str(exc)})
        body = {"code": code}
        if getattr(creds, "recovery_secret", None):
            body["recovery_secret"] = creds.recovery_secret
            body["user_id"] = creds.user_id
        self._send(200, body)

    def _token(self):
        form = parse_qs(self._body().decode("utf-8"))
        g = lambda k: (form.get(k) or [""])[0]
        if g("grant_type") != "authorization_code":
            return self._send(400, {"error": "unsupported_grant_type"})
        try:
            access_token = self.service.runtime.remote_auth.exchange_code(
                g("code"), g("code_verifier"), g("redirect_uri"), g("client_id"))
        except ValueError as exc:
            return self._send(400, {"error": "invalid_grant",
                                    "error_description": str(exc)})
        self._send(200, {"access_token": access_token, "token_type": "Bearer"})


def build_httpd(host="127.0.0.1", port=8899, *, runtime=None):
    from src.product.server import build_runtime
    from .auth import CodeStore
    if runtime is None:
        runtime = build_runtime(":memory:", allowed_origins=frozenset({f"http://{host}:{port}"}))
    if not hasattr(runtime, "remote_auth"):
        runtime.remote_auth = CodeStore()
    service = RemoteProductService(runtime)
    handler = type("BoundHandler", (StreamableHTTPHandler,),
                   {"core": RemoteMCP(service), "service": service})
    return ThreadingHTTPServer((host, port), handler)


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8899)
    args = parser.parse_args()
    httpd = build_httpd(args.host, args.port)
    print(f"remote MCP on http://{args.host}:{args.port}/mcp")
    httpd.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
