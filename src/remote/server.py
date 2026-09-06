"""Remote MCP entry point (thin factory over the product server).

Resonance exposes ONE remote MCP tool vocabulary: the `resonance_*` tools of
`src.product.mcp_bridge`, served by `src.product.server.ProductHandler` at
`/mcp` together with the canonical OAuth 2.1 core (`src.remote.oauth`).

Earlier versions carried a second, divergent Streamable-HTTP server with its
own 15-tool vocabulary here; it was never deployed and confused clients and
agents about which tools exist. `build_httpd` now returns the product server
with the OAuth core attached, so OAuth and onboarding tests exercise the same
code path that production runs.
"""

from __future__ import annotations

from http.server import ThreadingHTTPServer


def build_httpd(host: str = "127.0.0.1", port: int = 8899, *, runtime=None, issuer: str | None = None) -> ThreadingHTTPServer:
    from src.product import oauth_mount
    from src.product.server import build_runtime, serve

    if runtime is None:
        runtime = build_runtime(":ephemeral:", allowed_origins=frozenset({f"http://{host}:{port}"}))
    if getattr(runtime, "oauth_core", None) is None:
        oauth_mount.attach_core(runtime, issuer=issuer or oauth_mount.public_issuer(runtime.allowed_origins))
    return serve(host, port, runtime=runtime)


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8899)
    parser.add_argument("--issuer", default=None,
                        help="absolute public origin for discovery URLs (e.g. behind a proxy)")
    args = parser.parse_args()
    httpd = build_httpd(args.host, args.port, issuer=args.issuer)
    print(f"remote MCP (product server) on http://{args.host}:{args.port}/mcp")
    httpd.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
