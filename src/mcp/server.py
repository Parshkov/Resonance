"""Minimal MCP stdio server (JSON-RPC 2.0, newline-delimited, protocol
2024-11-05) over the ResonanceAdapter. Transport only: framing, handshake,
tools/list, tools/call, JSON-RPC errors. stdlib-only.

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
        if method == "initialize":
            self.initialized = True
            return self._result(msg_id, {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "resonance", "version": MCP_ADAPTER_VERSION}})
        if method == "notifications/initialized":
            return None                                  # notification: no reply
        if method == "ping":
            return self._result(msg_id, {})              # MCP utilities/ping
        if msg_id is None:
            return None                                  # ignore other notifications
        if not self.initialized:
            return self._error(msg_id, INVALID_REQUEST, "initialize first")
        if method == "tools/list":
            return self._result(msg_id, {"tools": TOOLS})
        if method == "tools/call":
            return self._tool_call(msg_id, params)
        return self._error(msg_id, METHOD_NOT_FOUND, f"unknown method: {method}")

    def _tool_call(self, msg_id: Any, params: dict[str, Any]) -> dict[str, Any]:
        name = params.get("name")
        arguments = params.get("arguments") or {}
        try:
            payload = self.adapter.dispatch(name, arguments)
        except KeyError as exc:
            return self._error(msg_id, METHOD_NOT_FOUND, str(exc))
        except TypeError as exc:
            return self._error(msg_id, INVALID_PARAMS, f"bad arguments: {exc}")
        except (ValueError, OSError, EngineIntegrityError) as exc:
            # engine-declared failures (unknown mode, validation, integrity)
            # and filesystem failures on the persistence tools (missing or
            # unreadable snapshot directory) surface as tool errors with the
            # underlying message; a bad tool ARGUMENT must never terminate
            # the transport.
            return self._result(msg_id, {
                "content": [{"type": "text",
                             "text": json.dumps({"error": type(exc).__name__,
                                                 "message": str(exc)})}],
                "isError": True})
        except Exception as exc:  # noqa: BLE001 -- transport survival:
            # one unexpected handler failure becomes INTERNAL_ERROR and the
            # session continues; serve() must outlive any single tools/call.
            return self._error(msg_id, INTERNAL_ERROR,
                               f"{type(exc).__name__}: {exc}")
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
                reply = self.handle(message)
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
