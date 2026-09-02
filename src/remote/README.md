# R15 — remote MCP: authenticated Streamable HTTP

One service layer, many transports: `ProductService` is the seam every
transport converges on (authorization rules, per-subject rate limits, and the
untrusted-input size cap live HERE, once). The remote endpoint, the accepted
local stdio server, and any future WebMCP/UI call the same methods — no
business or matching semantics in transport handlers, enforced by source-scan
test exactly as in every accepted layer.

```bash
python3 -m src.remote.server --port 8899 --issue-test-token
```

## Protocol (honest scope)

MCP **2025-03-26 Streamable HTTP**: `POST /mcp` carries JSON-RPC; responses
are always `application/json` (permitted by the spec in place of an SSE
stream); sessions via `Mcp-Session-Id` issued at `initialize`. `GET /mcp`
returns 405 — no server-initiated streaming in v0.1, stated rather than
half-implemented.

## Authentication (two grades, declared)

- **Bearer tokens** — full-strength for pilot/integration use: opaque
  random, constant-time compared, per-subject.
- **OAuth 2.1 authorization-code + PKCE (S256 only)** — the flow shape agent
  ecosystems require: `/oauth/authorize` binds a single-use, expiring code to
  the challenge; `/oauth/token` verifies the verifier. **Demo-grade by
  declaration:** static demo user, no consent UI, no refresh tokens,
  in-memory stores. A compliance surface for client interop, not an IdP.

## Rich results (maintainer scope update honored)

`discover_resonance` returns the full R8 DTO three ways at once:
`structuredContent` (versioned, machine-readable), a `text` JSON fallback,
and an `EmbeddedResource` SVG map (`image/svg+xml`) drawn ONLY from consented
match locations and aggregation buckets already present in the DTO — the
visual can never see hidden users or influence ranking. Clients without
image rendering still receive the complete structured/text payload.

## Remote tool surface (v0.1) and per-client interop honesty

Exposed: `ingest_thought`, `discover_resonance`, `compare_thoughts`,
`get_thought`. **Not exposed remotely:** `index_thought`,
`save_snapshot`/`load_snapshot` (shared-state writes and admin persistence
wait for #89's authorization/retention semantics), `explain_resonance`
(cache-coupled; use `compare_thoughts`). Calling them returns `-32601`.

Standard remote MCP support does **not** mean every client plan exposes every
capability: expect `structuredContent` and embedded resources to render
fully in MCP-native agent clients, text-only in minimal ones, and OAuth
availability to vary by ecosystem plan; the text fallback carries the
complete result everywhere. Verified in this repo: stdlib urllib client
(tests) end-to-end including PKCE.

## Security posture (subject to #89)

Authenticated subject on every call; per-subject token-bucket rate limit
(surfaced as a tool error, not a silent drop); UGC size-capped and never
evaluated; sessions unguessable; write path absent remotely. #89's full
threat-model gate (cross-user scoping over a durable store, retention,
abuse) intentionally lands with R11/R12 — this transport adds no shared
mutable state to protect yet.
