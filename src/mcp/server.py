"""Dependency-free MCP stdio server for Resonance."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any, TextIO

from src.engine import EngineIntegrityError

from .adapter import ADAPTER_VERSION, ResonanceMCPAdapter, UnknownToolError

JSONRPC_VERSION = "2.0"
LATEST_PROTOCOL = "2025-11-25"
SUPPORTED_PROTOCOLS = (
    LATEST_PROTOCOL,
    "2025-06-18",
    "2025-03-26",
    "2024-11-05",
)


def _error(request_id: Any, code: int, message: str, data: Any = None) -> dict[str, Any]:
    error: dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    return {"jsonrpc": JSONRPC_VERSION, "id": request_id, "error": error}


def _result(request_id: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": JSONRPC_VERSION, "id": request_id, "result": result}


def _valid_request_id(value: Any) -> bool:
    return not isinstance(value, bool) and isinstance(value, (str, int))


class ResonanceMCPServer:
    """Small JSON-RPC lifecycle and tools dispatcher around the adapter."""

    def __init__(self, adapter: ResonanceMCPAdapter) -> None:
        self.adapter = adapter
        self.initialized = False
        self.ready = False
        self.protocol_version: str | None = None

    def _initialize(self, request_id: Any, params: Any) -> dict[str, Any]:
        if self.initialized:
            return _error(request_id, -32600, "server is already initialized")
        if not isinstance(params, Mapping):
            return _error(request_id, -32602, "initialize params must be an object")
        required = {"protocolVersion", "capabilities", "clientInfo"}
        missing = sorted(required - set(params))
        if missing:
            return _error(
                request_id,
                -32602,
                "missing initialize params: " + ", ".join(missing),
            )
        requested = params.get("protocolVersion")
        if not isinstance(requested, str) or not requested:
            return _error(request_id, -32602, "protocolVersion must be a non-empty string")
        if not isinstance(params.get("capabilities"), Mapping):
            return _error(request_id, -32602, "capabilities must be an object")
        client_info = params.get("clientInfo")
        if not isinstance(client_info, Mapping):
            return _error(request_id, -32602, "clientInfo must be an object")
        if not isinstance(client_info.get("name"), str) or not isinstance(
            client_info.get("version"), str
        ):
            return _error(request_id, -32602, "clientInfo.name and version must be strings")

        negotiated = requested if requested in SUPPORTED_PROTOCOLS else LATEST_PROTOCOL
        self.initialized = True
        self.protocol_version = negotiated
        return _result(
            request_id,
            {
                "protocolVersion": negotiated,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {
                    "name": "resonance",
                    "title": "Resonance Thought Graph Matcher",
                    "version": ADAPTER_VERSION,
                    "description": "Thin MCP transport over the accepted Resonance EngineFacade.",
                },
                "instructions": (
                    "Ingest or supply Thought DNA, index corpus thoughts, then use find/compare. "
                    "Structured mappings and score components are authoritative."
                ),
            },
        )

    def handle_message(self, message: Any) -> dict[str, Any] | None:
        if not isinstance(message, Mapping):
            return _error(None, -32600, "Invalid Request")
        request = dict(message)
        request_id = request.get("id")
        has_id = "id" in request
        if request.get("jsonrpc") != JSONRPC_VERSION:
            return _error(request_id if _valid_request_id(request_id) else None, -32600, "Invalid Request")
        if has_id and not _valid_request_id(request_id):
            return _error(None, -32600, "request id must be a string or integer")
        method = request.get("method")
        if not isinstance(method, str) or not method:
            return _error(request_id if has_id else None, -32600, "method must be a non-empty string")
        params = request.get("params", {})

        if method == "initialize":
            if not has_id:
                return None
            return self._initialize(request_id, params)

        if method == "ping":
            return _result(request_id, {}) if has_id else None

        if method == "notifications/initialized":
            if has_id:
                return _error(request_id, -32600, "notifications/initialized must not have an id")
            if self.initialized:
                self.ready = True
            return None

        if not self.ready:
            return _error(request_id, -32002, "server is not initialized") if has_id else None

        if method == "tools/list":
            if not has_id:
                return None
            if not isinstance(params, Mapping):
                return _error(request_id, -32602, "tools/list params must be an object")
            cursor = params.get("cursor")
            if cursor is not None:
                return _error(request_id, -32602, "tool pagination cursors are not supported")
            unknown = sorted(set(params) - {"cursor"})
            if unknown:
                return _error(
                    request_id,
                    -32602,
                    "unknown tools/list params: " + ", ".join(unknown),
                )
            return _result(request_id, {"tools": self.adapter.tools()})

        if method == "tools/call":
            if not has_id:
                return None
            if not isinstance(params, Mapping):
                return _error(request_id, -32602, "tools/call params must be an object")
            unknown = sorted(set(params) - {"name", "arguments"})
            if unknown:
                return _error(
                    request_id,
                    -32602,
                    "unknown tools/call params: " + ", ".join(unknown),
                )
            name = params.get("name")
            if not isinstance(name, str) or not name:
                return _error(request_id, -32602, "tools/call name must be a non-empty string")
            arguments = params.get("arguments", {})
            try:
                result = self.adapter.call_tool(name, arguments)
            except UnknownToolError as exc:
                return _error(request_id, -32602, str(exc))
            return _result(request_id, result)

        if not has_id:
            return None
        return _error(request_id, -32601, "Method not found", {"method": method})


def serve_stdio(adapter: ResonanceMCPAdapter, input_stream: TextIO, output_stream: TextIO) -> None:
    """Serve one newline-delimited JSON-RPC message per line until stdin closes."""
    server = ResonanceMCPServer(adapter)
    for raw_line in input_stream:
        try:
            message = json.loads(raw_line)
        except json.JSONDecodeError as exc:
            response = _error(None, -32700, "Parse error", {"line": exc.lineno, "column": exc.colno})
        else:
            try:
                response = server.handle_message(message)
            except Exception as exc:
                request_id = message.get("id") if isinstance(message, Mapping) else None
                response = _error(
                    request_id if _valid_request_id(request_id) else None,
                    -32603,
                    "Internal error",
                    {"type": type(exc).__name__},
                )
        if response is not None:
            output_stream.write(json.dumps(response, sort_keys=True, separators=(",", ":")) + "\n")
            output_stream.flush()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Resonance MCP stdio server")
    parser.add_argument(
        "--data-dir",
        type=Path,
        help=(
            "Manifest-verified engine snapshot directory. When omitted, state is memory-only; "
            "when set, successful index_thought calls autosave."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        adapter = ResonanceMCPAdapter(data_dir=args.data_dir)
    except (EngineIntegrityError, OSError, ValueError) as exc:
        print(f"resonance MCP startup failed: {exc}", file=sys.stderr)
        return 2
    serve_stdio(adapter, sys.stdin, sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

