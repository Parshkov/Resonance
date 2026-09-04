# Remote MCP (R15) — one vocabulary, one server

The hosted MCP endpoint is the **product server** (`src/product/server.py`,
`ProductHandler`) serving `POST /mcp` through `src/product/mcp_bridge.py`
(the `resonance_*` tools) with the canonical OAuth 2.1 core in
`src/remote/oauth.py` mounted by `src/product/oauth_mount.py`.

`src/remote/server.py` is only a factory (`build_httpd`) that builds that same
server with the OAuth core attached, so tests and local runs exercise exactly
what production serves:

```bash
python3 -m src.remote.server --host 127.0.0.1 --port 8899   # /mcp + OAuth
```

The earlier second Streamable-HTTP server with its own 15-tool vocabulary was
removed (it was never deployed and made the tool surface ambiguous).

## OAuth core (R15A)

A hosted MCP client is handed only `https://<origin>/mcp` and connects through
standard authorization: RFC 9728 protected-resource metadata, RFC 8414 AS
metadata, RFC 7591 dynamic registration, PKCE S256, RFC 8707 resource
indicators. The issuer is derived from the configured allowed origins, never
from a caller-controlled `Host` header (see `oauth_mount.public_issuer`).
Access tokens are audience-bound: `resolve_bearer` rejects a token issued for
another resource. Grants are durable when the runtime carries a repository
(migration 0005).
