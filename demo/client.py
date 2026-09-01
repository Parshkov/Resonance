"""Clean MCP stdio client: JSON-RPC 2.0, newline-delimited, stdlib only.

This module must not import Resonance engine/MCP implementation packages.
It speaks to `python3 -m src.mcp.server` over stdin/stdout.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any


def classify_reply(reply: dict[str, Any]) -> dict[str, Any]:
    """Split transport JSON-RPC errors from engine-stage tool errors."""
    if "error" in reply:
        err = reply["error"]
        return {
            "ok": False,
            "stage": "transport",
            "code": err.get("code"),
            "message": err.get("message", ""),
            "reply": reply,
        }
    result = reply.get("result") or {}
    content = result.get("content") or []
    payload: Any = None
    if content and isinstance(content[0], dict) and "text" in content[0]:
        try:
            payload = json.loads(content[0]["text"])
        except json.JSONDecodeError:
            payload = {"raw": content[0]["text"]}
    if result.get("isError"):
        message = ""
        if isinstance(payload, dict):
            message = str(payload.get("message") or payload.get("error") or "")
        return {
            "ok": False,
            "stage": "engine",
            "code": None,
            "message": message,
            "error_type": (payload or {}).get("error") if isinstance(payload, dict) else None,
            "payload": payload,
            "reply": reply,
        }
    return {"ok": True, "stage": "ok", "payload": payload, "reply": reply}


class MCPClient:
    def __init__(self, proc: subprocess.Popen[str]) -> None:
        self.proc = proc
        self._next_id = 1
        self.transcript: list[dict[str, Any]] = []

    def request(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        msg_id = self._next_id
        self._next_id += 1
        message: dict[str, Any] = {"jsonrpc": "2.0", "id": msg_id, "method": method}
        if params is not None:
            message["params"] = params
        assert self.proc.stdin is not None and self.proc.stdout is not None
        self.proc.stdin.write(json.dumps(message, ensure_ascii=False) + "\n")
        self.proc.stdin.flush()
        line = self.proc.stdout.readline()
        if not line:
            raise RuntimeError("MCP server closed stdout")
        reply = json.loads(line)
        self.transcript.append({"request": message, "reply": reply})
        return reply

    def notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        message: dict[str, Any] = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            message["params"] = params
        assert self.proc.stdin is not None
        self.proc.stdin.write(json.dumps(message, ensure_ascii=False) + "\n")
        self.proc.stdin.flush()
        self.transcript.append({"request": message, "reply": None})

    def initialize(self) -> dict[str, Any]:
        reply = self.request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "resonance-demo-client", "version": "0.1"},
            },
        )
        self.notify("notifications/initialized")
        return reply

    def ping(self) -> dict[str, Any]:
        return self.request("ping")

    def list_tools(self) -> dict[str, Any]:
        return self.request("tools/list")

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        reply = self.request("tools/call", {"name": name, "arguments": arguments})
        classified = classify_reply(reply)
        classified["tool"] = name
        return classified


def start_server(repo: Path, *, snapshot: Path | None = None) -> subprocess.Popen[str]:
    cmd = [sys.executable, "-u", "-m", "src.mcp.server"]
    if snapshot is not None:
        cmd.extend(["--snapshot", str(snapshot)])
    return subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        cwd=str(repo),
        text=True,
        bufsize=1,
    )


def stop_server(proc: subprocess.Popen[str]) -> None:
    if proc.stdin is not None:
        proc.stdin.close()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)
