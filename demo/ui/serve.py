#!/usr/bin/env python3
"""Serve the R9 visual demo. Stdlib only.

    python3 -m demo.ui.serve          # replay on http://127.0.0.1:8765
    python3 -m demo.ui.serve --live   # live MCP discover_resonance + same UI
"""

from __future__ import annotations

import argparse
import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

REPO = Path(__file__).resolve().parents[2]
UI = Path(__file__).resolve().parent
STATIC = UI / "static"


def load_replay_payload() -> dict:
    from .contract import FIXTURE_RELATIVE
    return json.loads((REPO / FIXTURE_RELATIVE).read_text(encoding="utf-8"))


def build_view(source: str) -> dict:
    from .view_model import project
    if source == "live":
        from .live import discover_live
        payload = discover_live(REPO)
    else:
        payload = load_replay_payload()
    return project(payload, source=source)


class Handler(SimpleHTTPRequestHandler):
    source = "replay"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC), **kwargs)

    def log_message(self, fmt, *args):
        print("[r9-ui]", fmt % args)

    def do_GET(self):
        path = urlparse(self.path).path
        if path in ("/api/view", "/api/replay", "/api/live"):
            source = "live" if path.endswith("live") or (path == "/api/view" and self.source == "live") else "replay"
            if path == "/api/live":
                source = "live"
            try:
                body = json.dumps(build_view(source), ensure_ascii=False).encode("utf-8")
            except Exception as exc:
                payload = json.dumps({"ok": False, "error": str(exc)}).encode("utf-8")
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if path == "/":
            self.path = "/index.html"
        return super().do_GET()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--dump-view", type=Path, default=None)
    args = parser.parse_args()
    source = "live" if args.live else "replay"
    if args.dump_view is not None:
        view = build_view(source)
        args.dump_view.write_text(json.dumps(view, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(json.dumps({"ok": True, "source": source, "featured": [c["session_id"] for c in view["featured"]]}))
        return 0
    Handler.source = source
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"R9 visual demo ({source}) http://{args.host}:{args.port}/")
    print("Record at 1920x1080. Replay is the canonical offline path.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
