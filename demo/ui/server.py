#!/usr/bin/env python3
"""Offline-first HTTP surface for the R9 Resonance visual demo.

Run from the repository root:

    python3 -m demo.ui.server

The browser receives the accepted R8 DTO from one of two paths:

* REPLAY reads the committed capture without reserializing it.
* LIVE invokes ``discover_resonance`` over the accepted newline-delimited
  stdio MCP server with the canonical request pinned to analogical / k=15.

Only Python's standard library is required.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from .presentation import (
    CANONICAL_K,
    CANONICAL_MODE,
    visible_signature,
)

REPO = Path(__file__).resolve().parents[2]
UI_DIR = Path(__file__).resolve().parent
REPLAY_FIXTURE = REPO / "src" / "discovery" / "fixtures" / "example_response.json"
CORPUS = REPO / "demo" / "corpus" / "sessions.jsonl"
FLAGSHIP_SESSION_ID = "ses-aria-plasma-lens"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765

STATIC_ASSETS = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/styles.css": ("styles.css", "text/css; charset=utf-8"),
    "/app.mjs": ("app.mjs", "text/javascript; charset=utf-8"),
    "/theme.mjs": ("theme.mjs", "text/javascript; charset=utf-8"),
    "/shell.mjs": ("shell.mjs", "text/javascript; charset=utf-8"),
    "/favicon.svg": ("favicon.svg", "image/svg+xml"),
}


def load_replay_bytes() -> bytes:
    """Return the genuine accepted capture byte-for-byte."""
    return REPLAY_FIXTURE.read_bytes()


def load_replay() -> dict[str, Any]:
    return json.loads(load_replay_bytes())


def _flagship_session() -> dict[str, Any]:
    for line in CORPUS.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        session = json.loads(line)
        if session["session_id"] == FLAGSHIP_SESSION_ID:
            return session
    raise RuntimeError(f"missing canonical session: {FLAGSHIP_SESSION_ID}")


def public_context() -> dict[str, Any]:
    """Return only the active session context required by the UI.

    The corpus is never sent to the browser. The active Thought DNA is user
    context, while candidates and all presentational match fields still come
    exclusively from the R8 discovery response.
    """
    session = _flagship_session()
    thought = session["thought_dna"]
    consent = session["consent"]
    context: dict[str, Any] = {
        "contract_version": "resonance-ui-context/0.1",
        "active_thought": {
            "thought_id": thought["thought_id"],
            "source": thought["source"],
            "nodes": [
                {"id": node["id"], "label": node["label"], "role": node["role"]}
                for node in thought["nodes"]
            ],
            "relations": [
                {
                    "id": relation["id"],
                    "source": relation["source"],
                    "target": relation["target"],
                    "type": relation["type"],
                }
                for relation in thought["relations"]
            ],
        },
        "consent": {
            "shared_with_resonance": bool(
                consent["share_enabled"] and consent["share_thought_dna"]
            )
        },
        "pinned_request": {"mode": CANONICAL_MODE, "k": CANONICAL_K},
    }
    if consent["share_display_profile"]:
        context["presentation"] = {
            "topic": session["presentation"]["topic"],
            "domain": session["presentation"]["domain"],
        }
    if consent["share_coarse_location"]:
        context["location"] = {
            "city": session["location"]["city"],
            "region": session["location"]["region"],
            "kind": session["location"]["kind"],
            "precision": session["location"]["precision"],
            "lat": session["location"]["lat"],
            "lon": session["location"]["lon"],
        }
    return context


def call_live_mcp(timeout: float = 120.0) -> dict[str, Any]:
    """Call the accepted R8 MCP tool as a clean stdio client."""
    thought = _flagship_session()["thought_dna"]
    frames = [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {},
        },
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "discover_resonance",
                "arguments": {
                    "thought": thought,
                    "mode": CANONICAL_MODE,
                    "k": CANONICAL_K,
                },
            },
        },
    ]
    wire = "".join(json.dumps(frame, separators=(",", ":")) + "\n"
                   for frame in frames)
    completed = subprocess.run(
        [sys.executable, "-m", "src.discovery.demo_server"],
        cwd=REPO,
        input=wire,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or "discovery MCP exited without a message"
        raise RuntimeError(detail)
    replies = [json.loads(line) for line in completed.stdout.splitlines() if line.strip()]
    if len(replies) != 2:
        raise RuntimeError("discovery MCP returned an unexpected frame count")
    call = replies[1]
    if "error" in call:
        raise RuntimeError(call["error"].get("message", "discovery MCP error"))
    result = call["result"]
    if result.get("isError"):
        raise RuntimeError(result["content"][0]["text"])
    return json.loads(result["content"][0]["text"])


def verify_sources() -> dict[str, Any]:
    """Execute both canonical paths and compare every visible match field."""
    replay = load_replay()
    live = call_live_mcp()
    replay_signature = visible_signature(replay)
    live_signature = visible_signature(live)
    return {
        "contract_version": replay["contract_version"],
        "pinned_request": {"mode": CANONICAL_MODE, "k": CANONICAL_K},
        "fixture_sha256": hashlib.sha256(load_replay_bytes()).hexdigest(),
        "visible_match_count": len(replay_signature),
        "visible_match_ids": [item["match_id"] for item in replay_signature],
        "visible_session_ids": [item["session_id"] for item in replay_signature],
        "live_replay_visible_equal": live_signature == replay_signature,
        "live_corpus_snapshot": live["query"]["provenance"]["corpus_snapshot"],
        "replay_corpus_snapshot": replay["query"]["provenance"]["corpus_snapshot"],
    }


class DemoHandler(BaseHTTPRequestHandler):
    server_version = "ResonanceDemo/0.1"
    default_source = "replay"

    def do_GET(self) -> None:  # noqa: N802 -- BaseHTTPRequestHandler API
        parsed = urlparse(self.path)
        if parsed.path in STATIC_ASSETS:
            filename, content_type = STATIC_ASSETS[parsed.path]
            self._send_bytes((UI_DIR / filename).read_bytes(), content_type)
            return
        if parsed.path == "/api/context":
            self._send_json(public_context())
            return
        if parsed.path == "/api/config":
            self._send_json({"default_source": self.default_source})
            return
        if parsed.path == "/api/discover":
            source = parse_qs(parsed.query).get("source", ["replay"])[0]
            try:
                if source == "replay":
                    self._send_bytes(load_replay_bytes(), "application/json; charset=utf-8")
                elif source == "live":
                    self._send_json(call_live_mcp())
                else:
                    self._send_json(
                        {"error": "source must be replay or live"},
                        status=HTTPStatus.BAD_REQUEST,
                    )
            except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
                self._send_json(
                    {"error": type(exc).__name__, "message": str(exc)},
                    status=HTTPStatus.BAD_GATEWAY,
                )
            return
        if parsed.path == "/api/health":
            self._send_json({"status": "ok"})
            return
        self._send_json({"error": "not found"}, status=HTTPStatus.NOT_FOUND)

    def log_message(self, format: str, *args: object) -> None:
        sys.stderr.write("[resonance-ui] " + format % args + "\n")

    def _send_json(
        self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK
    ) -> None:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
        self._send_bytes(body, "application/json; charset=utf-8", status=status)

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
        self.send_header("Content-Security-Policy", "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(body)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument(
        "--source",
        choices=("replay", "live"),
        default="replay",
        help="initial browser source; both modes remain switchable in the UI",
    )
    parser.add_argument(
        "--verify-sources",
        action="store_true",
        help="run LIVE and REPLAY once, compare visible payload values, then exit",
    )
    args = parser.parse_args(argv)
    if args.verify_sources:
        report = verify_sources()
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0 if report["live_replay_visible_equal"] else 1
    DemoHandler.default_source = args.source
    server = ThreadingHTTPServer((args.host, args.port), DemoHandler)
    print(f"Resonance visual demo ({args.source}): http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
