"""Streamable HTTP MCP endpoint over the product service.

Transport only (contract section 7, enforced by test): parse JSON-RPC, map
auth to a subject, call the service/adapter, serialize. MCP protocol
2025-03-26 Streamable HTTP, honestly scoped:

* POST /mcp        -- JSON-RPC request/notification; responses are always
                      `application/json` (the spec permits JSON instead of an
                      SSE stream); sessions via `Mcp-Session-Id`.
* GET  /mcp        -- 405: no server-initiated stream in v0.1 (documented).
* POST /oauth/authorize, /oauth/token -- OAuth 2.1 code+PKCE shape (see
                      auth.py for the demo-grade declaration).

Rich results per the maintainer scope update: `discover_resonance` returns
`structuredContent` (the full R8 DTO) + text JSON + an EmbeddedResource SVG
map derived from consented data only. Clients without image rendering still
get the complete structured/text payload.
"""

from __future__ import annotations

import json
import secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

from src.engine import EngineIntegrityError
from src.discovery.mcp import TOOLS as DISCOVERY_TOOLS
from src.mcp.server import (INTERNAL_ERROR, INVALID_PARAMS, INVALID_REQUEST,
                            METHOD_NOT_FOUND, PARSE_ERROR)

from .auth import AuthStore
from .service import AuthorizationError, ProductService
from .visual import map_svg

PROTOCOL_VERSION = "2025-03-26"
REMOTE_VERSION = "resonance-remote-mcp/0.1"

# Remote v0.1 exposes the read/product path. Write/admin tools
# (index_thought, save/load_snapshot) stay local-stdio until #89's
# authorization semantics land -- documented in README interop notes.
REMOTE_TOOL_NAMES = ("ingest_thought", "discover_resonance",
                     "compare_thoughts", "get_thought")
TOOLS = [dict(t) for t in DISCOVERY_TOOLS if t["name"] in REMOTE_TOOL_NAMES]


class RemoteMCP:
    """Protocol core, transport-framing-free (unit-testable without HTTP)."""

    def __init__(self, service: ProductService, auth: AuthStore):
        self.service = service
        self.auth = auth
        self.sessions: set[str] = set()

    # -- JSON-RPC ------------------------------------------------------------
    def handle(self, message: dict[str, Any], subject: str | None,
               session_id: str | None) -> tuple[dict[str, Any] | None, str | None]:
        if message.get("jsonrpc") != "2.0" or "method" not in message:
            return self._err(message.get("id"), INVALID_REQUEST, "invalid request"), session_id
        method, msg_id = message["method"], message.get("id")
        params = message.get("params") or {}
        if method == "initialize":
            new_session = secrets.token_urlsafe(16)
            self.sessions.add(new_session)
            return ({"jsonrpc": "2.0", "id": msg_id, "result": {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "resonance-remote",
                               "version": REMOTE_VERSION}}}, new_session)
        if method in ("notifications/initialized",):
            return None, session_id
        if msg_id is None:
            return None, session_id
        if session_id not in self.sessions:
            return self._err(msg_id, INVALID_REQUEST, "unknown or missing Mcp-Session-Id"), session_id
        if method == "ping":
            return {"jsonrpc": "2.0", "id": msg_id, "result": {}}, session_id
        if method == "tools/list":
            return {"jsonrpc": "2.0", "id": msg_id, "result": {"tools": TOOLS}}, session_id
        if method == "tools/call":
            return self._call(msg_id, params, subject), session_id
        return self._err(msg_id, METHOD_NOT_FOUND, f"unknown method: {method}"), session_id

    def _call(self, msg_id: Any, params: dict[str, Any],
              subject: str | None) -> dict[str, Any]:
        name = params.get("name")
        arguments = dict(params.get("arguments") or {})
        try:
            payload, rich = self._dispatch(name, arguments, subject)
        except AuthorizationError as exc:
            return self._tool_error(msg_id, "AuthorizationError", str(exc))
        except KeyError as exc:
            return self._err(msg_id, METHOD_NOT_FOUND, str(exc))
        except TypeError as exc:
            return self._err(msg_id, INVALID_PARAMS, f"bad arguments: {exc}")
        except (ValueError, OSError, EngineIntegrityError) as exc:
            return self._tool_error(msg_id, type(exc).__name__, str(exc))
        except Exception as exc:  # noqa: BLE001 -- transport survival
            return self._err(msg_id, INTERNAL_ERROR, f"{type(exc).__name__}: {exc}")
        content = [{"type": "text",
                    "text": json.dumps(payload, ensure_ascii=False, sort_keys=True)}]
        content.extend(rich)
        result: dict[str, Any] = {"content": content, "isError": False}
        if isinstance(payload, dict):
            result["structuredContent"] = payload
        return {"jsonrpc": "2.0", "id": msg_id, "result": result}

    def _dispatch(self, name: str, args: dict[str, Any],
                  subject: str | None):
        rich: list[dict[str, Any]] = []
        if name == "ingest_thought":
            graph = self.service.ingest(subject, args.get("context"),
                                        args.get("source_id"))
            return {"thought": graph.to_dict(),
                    "metadata": self.service.identity(subject)}, rich
        if name == "discover_resonance":
            response = self.service.discover(subject, args["thought"],
                                             mode=args["mode"],
                                             k=int(args.get("k", 8)))
            svg = map_svg(response)
            rich.append({"type": "resource",
                         "resource": {"uri": "resonance://map/latest",
                                      "mimeType": "image/svg+xml",
                                      "text": svg}})
            return response, rich
        if name == "compare_thoughts":
            from src.mcp import wire
            result = self.service.compare(subject, args["a"], args["b"],
                                          mode=args["mode"])
            return {"result": wire.verifier_result(result),
                    "metadata": self.service.identity(subject)}, rich
        if name == "get_thought":
            graph = self.service.get_thought(subject, args["thought_id"])
            return {"thought": graph.to_dict() if graph else None,
                    "metadata": self.service.identity(subject)}, rich
        raise KeyError(f"unknown or remotely-unavailable tool: {name}")

    @staticmethod
    def _err(msg_id: Any, code: int, message: str) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": msg_id,
                "error": {"code": code, "message": message}}

    @staticmethod
    def _tool_error(msg_id: Any, kind: str, message: str) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": msg_id, "result": {
            "content": [{"type": "text",
                         "text": json.dumps({"error": kind, "message": message})}],
            "isError": True}}


class StreamableHTTPHandler(BaseHTTPRequestHandler):
    """HTTP framing only. Class attributes `core` and `auth` are injected by
    build_httpd()."""

    core: RemoteMCP
    auth: AuthStore
    server_version = "resonance-remote/0.1"

    def log_message(self, fmt: str, *args: object) -> None:  # noqa: A003
        pass

    # -- helpers -------------------------------------------------------------
    def _body(self) -> bytes:
        length = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(length) if length else b""

    def _send(self, status: int, payload: dict[str, Any] | None,
              extra_headers: dict[str, str] | None = None) -> None:
        data = (json.dumps(payload, ensure_ascii=False).encode()
                if payload is not None else b"")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        for key, value in (extra_headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        if data:
            self.wfile.write(data)

    def _subject(self) -> str | None:
        header = self.headers.get("Authorization") or ""
        if header.startswith("Bearer "):
            return self.auth.subject_for_token(header[len("Bearer "):].strip())
        return None

    # -- routes --------------------------------------------------------------
    def do_GET(self) -> None:  # noqa: N802
        if urlparse(self.path).path == "/mcp":
            self._send(405, {"error": "server-initiated streaming not "
                                      "supported in v0.1; POST JSON-RPC"})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        route = urlparse(self.path).path
        if route == "/oauth/authorize":
            self._authorize()
            return
        if route == "/oauth/token":
            self._token()
            return
        if route != "/mcp":
            self._send(404, {"error": "not found"})
            return
        subject = self._subject()
        if subject is None:
            self._send(401, {"error": "bearer token required"},
                       {"WWW-Authenticate": "Bearer"})
            return
        try:
            message = json.loads(self._body().decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._send(400, {"jsonrpc": "2.0", "id": None,
                             "error": {"code": PARSE_ERROR,
                                       "message": "parse error"}})
            return
        session_id = self.headers.get("Mcp-Session-Id")
        reply, new_session = self.core.handle(message, subject, session_id)
        headers = {}
        if new_session and new_session != session_id:
            headers["Mcp-Session-Id"] = new_session
        if reply is None:
            self._send(202, None, headers)
        else:
            self._send(200, reply, headers)

    # -- OAuth 2.1 code+PKCE shape ------------------------------------------
    def _authorize(self) -> None:
        form = parse_qs(self._body().decode("utf-8"))
        get1 = lambda key: (form.get(key) or [""])[0]
        try:
            code = self.auth.issue_code(get1("user"), get1("code_challenge"),
                                        get1("redirect_uri"), get1("client_id"))
        except ValueError as exc:
            self._send(400, {"error": "invalid_request",
                             "error_description": str(exc)})
            return
        if get1("code_challenge_method") not in ("S256",):
            self._send(400, {"error": "invalid_request",
                             "error_description": "PKCE S256 required"})
            return
        self._send(200, {"code": code})

    def _token(self) -> None:
        form = parse_qs(self._body().decode("utf-8"))
        get1 = lambda key: (form.get(key) or [""])[0]
        if get1("grant_type") != "authorization_code":
            self._send(400, {"error": "unsupported_grant_type"})
            return
        try:
            token = self.auth.exchange_code(get1("code"), get1("code_verifier"),
                                            get1("redirect_uri"), get1("client_id"))
        except ValueError as exc:
            self._send(400, {"error": "invalid_grant",
                             "error_description": str(exc)})
            return
        self._send(200, {"access_token": token, "token_type": "Bearer"})


def build_httpd(host: str = "127.0.0.1", port: int = 8899,
                service: ProductService | None = None,
                auth: AuthStore | None = None) -> ThreadingHTTPServer:
    service = service or ProductService()
    auth = auth or AuthStore()
    handler = type("BoundHandler", (StreamableHTTPHandler,),
                   {"core": RemoteMCP(service, auth), "auth": auth})
    return ThreadingHTTPServer((host, port), handler)


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8899)
    parser.add_argument("--issue-test-token", action="store_true",
                        help="print a bearer token for the demo subject")
    args = parser.parse_args()
    auth = AuthStore()
    if args.issue_test_token:
        print(json.dumps({"bearer": auth.issue_token("user-demo")}))
    httpd = build_httpd(args.host, args.port, auth=auth)
    httpd.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
