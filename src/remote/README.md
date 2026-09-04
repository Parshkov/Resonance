# R15 — remote MCP: authenticated Streamable HTTP over the live product

One service layer, many transports. The remote endpoint is a thin adapter
(`RemoteProductService`) over the accepted **`LiveProductService`** — the exact
methods the human UI, browser WebMCP, and local stdio call. Authorization rules,
per-subject rate limits, consent, and the untrusted-input caps live in the
accepted layers, once; no business or matching semantics live in the transport
(source-scan test).

```bash
python3 -m src.remote.server --host 127.0.0.1 --port 8899   # /mcp
```

## Protocol (honest scope)

MCP **2025-03-26 Streamable HTTP**: `POST /mcp` carries JSON-RPC; responses are
`application/json` (permitted in place of an SSE stream). Sessions via
`Mcp-Session-Id` issued at `initialize` and **bound to the authenticating
subject** — a bearer that resolves to a different subject cannot reuse a
session. An unknown/expired session on a session-requiring request returns
**HTTP 404** so the client re-initializes (sessions are in-memory; a redeploy
invalidates them). `GET /mcp` returns 405 — no server-initiated streaming.
The request body is bounded (413 over the cap); one bad `tools/call` never
kills the server.

## Authentication (tied to the accepted identity model)

The remote **bearer token IS the accepted R12 access token** — there is no
separate token directory. `identity.authenticate(bearer)` resolves the subject,
so remote MCP, WebMCP, the UI and stdio share one identity model and one set of
authorization rules.

- **OAuth 2.1 authorization-code + PKCE (S256 only):** `/oauth/authorize`
  authenticates through R12 (`login` with a recovery secret, or a fresh guest)
  and issues a single-use, expiring code bound to the `code_challenge`;
  `/oauth/token` verifies the verifier and returns the R12 access token.
  **Demo-grade by declaration:** no consent UI, no refresh tokens, no
  `.well-known` discovery metadata, no dynamic client registration, in-memory
  code store. Header-capable clients (bearer) work today; hosted connectors that
  require OAuth discovery/redirect are a documented follow-up.
- **Bearer** for local integration/tests: the R12 access token in
  `Authorization: Bearer …`.

## Tools (15, over the live product)

`resonance_whoami`; `resonance_prepare_thought` (structured candidate **or**
raw chat `context=…`) / `resonance_get_share_preview` /
`resonance_share_thought` / `resonance_update_consent` (R12C);
`resonance_discover` / `resonance_get_match` (R13B — `structuredContent` + an
`EmbeddedResource` SVG map drawn only from consented data, never influencing
rank); `resonance_request_intro` / `resonance_list_requests` /
`resonance_respond_intro` / `resonance_send_message` / `resonance_read_messages`
(R14); `resonance_create_workspace` / `resonance_get_workspace` /
`resonance_list_workspaces` (R14B). Writes require `confirm`; reads carry
`readOnlyHint`; any returned user text carries `untrustedContentHint`.

## Real external-chat ingestion

`resonance_prepare_thought(context=<selected conversation>)` is the canonical
path for an external LLM client: raw chat text is privately extracted into
Thought DNA (raw source not retained), previewed, explicitly shared, and
discovered against another independently ingested user's chat — proven in
`tests/test_remote_mcp.py` with no fixture as a query or match.
