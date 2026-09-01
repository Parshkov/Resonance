"""Live discover_resonance call over accepted discovery MCP stdio.

This helper speaks JSON-RPC to `python3 -m src.discovery.demo_server`.
It does not import alignment, retrieval, verifier, or scoring packages.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from .contract import PINNED_K, PINNED_MODE, QUERY_SESSION_ID


def _load_query_thought(repo: Path) -> dict[str, Any]:
    path = repo / "demo" / "corpus" / "sessions.jsonl"
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        if record.get("session_id") == QUERY_SESSION_ID:
            return record["thought_dna"]
    raise FileNotFoundError(f"{QUERY_SESSION_ID} missing from R7 corpus")


def discover_live(repo: Path) -> dict[str, Any]:
    thought = _load_query_thought(repo)
    proc = subprocess.Popen(
        [sys.executable, "-u", "-m", "src.discovery.demo_server"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        cwd=str(repo),
        text=True,
        bufsize=1,
    )
    assert proc.stdin is not None and proc.stdout is not None
    try:
        frames = [
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "resonance-r9-ui", "version": "0.1"},
                },
            },
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "discover_resonance",
                    "arguments": {
                        "thought": thought,
                        "mode": PINNED_MODE,
                        "k": PINNED_K,
                    },
                },
            },
        ]
        for frame in frames:
            proc.stdin.write(json.dumps(frame, ensure_ascii=False) + "\n")
        proc.stdin.flush()
        replies = []
        for _ in frames:
            line = proc.stdout.readline()
            if not line:
                raise RuntimeError("discovery MCP closed stdout early")
            replies.append(json.loads(line))
        body = json.loads(replies[1]["result"]["content"][0]["text"])
        body.pop("metadata", None)
        return body
    finally:
        if proc.stdin is not None:
            proc.stdin.close()
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
