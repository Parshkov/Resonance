"""Minimal MCP stdio server (JSON-RPC 2.0, newline-delimited, protocol
2024-11-05) over the ResonanceAdapter. Transport only: framing, handshake,
tools/list, tools/call, ping, JSON-RPC errors. stdlib-only.

Run:  python3 -m src.mcp.server [--snapshot DIR]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, TextIO

from src.engine import EngineIntegrityError, ResonanceEngine
from .adapter import MCP_ADAPTER_VERSION, TOOLS, ResonanceAdapter

PROTOCOL_VERSION = "2024-11-05"

PARSE_ERROR, INVALID_REQUEST = -32700, -32600
METHOD_NOT_FOUND, INVALID_PARAMS, INTERNAL_ERROR = -32601, -32602, -32603


class MCPServer:
    def __init__(self, adapter: ResonanceAdapter | None = None) -> None:
        self.adapter = adapter or ResonanceAdapter()
        self.initialized = False

    # -- protocol ------------------------------------------------------------
    def handle(self, message: dict[str, Any]) -> dict[str, Any] | None:
        if message.get("jsonrpc") != "2.0" or "method" not in message:
            return self._error(message.get("id"), INVALID_REQUEST, "invalid request")
        method = message["method"]
        msg_id = message.get("id")
        params = message.get("params") or {}
        if not isinstance(params, dict):
            return self._error(msg_id, INVALID_PARAMS, "params must be an object")
        if method == "initialize":
            self.initialized = True
            return self._result(msg_id, {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "resonance", "version": MCP_ADAPTER_VERSION}})
        if method == "notifications/initialized":
            return None                                  # notification: no reply
        if msg_id is None:
            return None                                  # ignore other notifications
        if not self.initialized:
            return self._error(msg_id, INVALID_REQUEST, "initialize first")
        if method == "ping":
            return self._result(msg_id, {})
        if method == "tools/list":
            return self._result(msg_id, {"tools": TOOLS})
        if method == "tools/call":
            return self._tool_call(msg_id, params)
        return self._error(msg_id, METHOD_NOT_FOUND, f"unknown method: {method}")

    def _tool_call(self, msg_id: Any, params: dict[str, Any]) -> dict[str, Any]:
        name = params.get("name")
        arguments = params.get("arguments") or {}
        if not isinstance(arguments, dict):
            return self._error(msg_id, INVALID_PARAMS, "arguments must be an object")
        try:
            payload = self.adapter.dispatch(name, arguments)
        except KeyError as exc:
            return self._error(msg_id, METHOD_NOT_FOUND, str(exc))
        except TypeError as exc:
            return self._error(msg_id, INVALID_PARAMS, f"bad arguments: {exc}")
        except (ValueError, EngineIntegrityError, OSError) as exc:
            # Engine-declared failures plus filesystem failures from snapshot
            # loading/saving are tool errors, not transport failures. Keep the
            # stdio session alive so the client can issue another request.
            return self._result(msg_id, {
                "content": [{"type": "text",
                             "text": json.dumps({"error": type(exc).__name__,
                                                 "message": str(exc)})}],
                "isError": True})
        except Exception as exc:  # defensive transport boundary
            return self._error(msg_id, INTERNAL_ERROR,
                               f"internal error: {type(exc).__name__}: {exc}")
        return self._result(msg_id, {
            "content": [{"type": "text",
                         "text": json.dumps(payload, ensure_ascii=False, sort_keys=True)}],
            "isError": False})

    @staticmethod
    def _result(msg_id: Any, result: dict[str, Any]) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": msg_id, "result": result}

    @staticmethod
    def _error(msg_id: Any, code: int, message: str) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": msg_id,
                "error": {"code": code, "message": message}}

    # -- stdio loop ----------------------------------------------------------
    def serve(self, stdin: TextIO, stdout: TextIO) -> None:
        for line in stdin:
            line = line.strip()
            if not line:
                continue
            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                reply = self._error(None, PARSE_ERROR, "parse error")
            else:
                if not isinstance(message, dict):
                    reply = self._error(None, INVALID_REQUEST, "invalid request")
                else:
                    try:
                        reply = self.handle(message)
                    except Exception as exc:  # never let one frame kill stdio
                        reply = self._error(message.get("id"), INTERNAL_ERROR,
                                            f"internal error: {type(exc).__name__}: {exc}")
            if reply is not None:
                stdout.write(json.dumps(reply, ensure_ascii=False) + "\n")
                stdout.flush()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path,
                        help="load the engine from a manifest-verified snapshot")
    args = parser.parse_args()
    engine = ResonanceEngine.load(args.snapshot) if args.snapshot else ResonanceEngine()
    MCPServer(ResonanceAdapter(engine)).serve(sys.stdin, sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
