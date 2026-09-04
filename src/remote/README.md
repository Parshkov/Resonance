# R15 — remote MCP: authenticated Streamable HTTP + canonical OAuth (R15A)

One service layer, many transports. The remote endpoint is a thin adapter
(`RemoteProductService`) over the accepted **`LiveProductService`** — the exact
methods the human UI, browser WebMCP, and local stdio call. Authorization rules,
per-subject rate limits, consent, and the untrusted-input caps live in the
accepted layers, once; no business or matching semantics live in the transport
(source-scan test).

```bash
python3 -m src.remote.server --host 127.0.0.1 --port 8899   # /mcp
python3 -m src.remote.server --port 8899 --issuer https://your.public.origin
```

## Canonical goal (R15A)

A hosted MCP client is handed only the ordinary resource URL —
`https://<origin>/mcp` — and connects through standard authorization. **No
manually created MCP key, bearer token, capability URL, or custom header is
needed in the normal user flow.** The client discovers the authorization
requirements from the resource itself and drives an ordinary browser
authorization-code flow.

## Protocol (honest scope)

MCP **2025-03-26 Streamable HTTP**: `POST /mcp` carries JSON-RPC; responses are
`application/json` (permitted in place of an SSE stream). Sessions via
`Mcp-Session-Id` issued at `initialize` and **bound to the authenticating
subject** — a bearer that resolves to a different subject cannot reuse a session.
An unknown/expired session on a session-requiring request returns **HTTP 404**
so the client re-initializes (sessions are in-memory; a redeploy invalidates
them). `GET /mcp` returns 405 — no server-initiated streaming. The request body
is bounded (413 over the cap); one bad `tools/call` never kills the server.

## OAuth 2.1 authorization core (`src/remote/oauth.py`)

Transport-neutral: `OAuthCore.handle(method, path, query, headers, body, *,
issuer)` returns `(status, headers, body)` and never touches a socket, so the
standalone Streamable-HTTP server and the production `ProductHandler` (R15C)
mount the same object. The issuer and every absolute URL are **injected**, never
read from `Host`.

Surface:

- **`GET /.well-known/oauth-protected-resource`** (RFC 9728): advertises the
  `/mcp` `resource` and its `authorization_servers`. An unauthenticated `/mcp`
  request returns **401** with
  `WWW-Authenticate: Bearer …, resource_metadata="{issuer}/.well-known/oauth-protected-resource"`.
- **`GET /.well-known/oauth-authorization-server`** (RFC 8414): issuer,
  authorize/token/register/revoke endpoints, `code_challenge_methods_supported:
  [S256]`, `grant_types_supported: [authorization_code, refresh_token]`,
  `resource_indicators_supported: true`, scopes.
- **`POST /oauth/register`** (RFC 7591): dynamic client registration for public
  clients (`token_endpoint_auth_method: none`). Clients that do not register can
  still connect as ephemeral public clients bound to an exact `redirect_uri`.
- **`GET /oauth/authorize`**: renders an **explicit human consent screen**
  (server-rendered HTML, no inline script/style — CSP `default-src 'self'`
  safe). It offers pseudonymous **guest** continuation, **login** with an
  existing account's recovery secret, or — when the browser identity cookie is
  present on the same-site POST — continuing as the **current account**.
- **`POST /oauth/authorize`**: authenticates through the accepted R12 identity
  model, then **302** back to the exact validated `redirect_uri` with a
  single-use code and the exact `state`.
- **`POST /oauth/token`**: `authorization_code` (PKCE S256 verified,
  `redirect_uri`/`client_id`/`resource` matched, code single-use even after a
  failed verify) and `refresh_token` (rotating, issued only when
  `offline_access` was granted).
- **`POST /oauth/revoke`** (RFC 7009): revokes the access token (R12 logout) and
  the subject's refresh grants; always answers 200.

Guarantees: **PKCE S256 mandatory**; strict `state` round-trip; strict
`redirect_uri` validated **before** any redirect (no open redirect); RFC 8707
`resource`/audience bound to `{issuer}/mcp` (wrong resource → `invalid_target`).
The issued access token **IS the accepted R12 access token** — identity is bound
to the existing R12 model and never caller-selected; there is no parallel user
store. Codes, refresh grants and client records live behind a `GrantStore`
interface (JSON-serialisable records; default in-memory, so a redeploy
invalidates them — R15C may back it with durable storage). No token, code,
verifier, or recovery secret is logged or echoed outside the token response body
and the redirect `Location`. Consent for **Thought sharing stays separate** from
this OAuth consent: authorizing a client makes nothing discoverable — every
share still needs its own in-tool confirmation.

Known limits (declared): in-memory grant store by default; a single protected
resource, so audience is structural rather than per-token; the consent page is
functional HTML, styled by a same-origin stylesheet the transport may add.

## Tools (15, over the live product)

`resonance_whoami`; `resonance_prepare_thought` (structured candidate **or** raw
chat `context=…`) / `resonance_get_share_preview` / `resonance_share_thought` /
`resonance_update_consent` (R12C); `resonance_discover` / `resonance_get_match`
(R13B — `structuredContent` + an `EmbeddedResource` SVG map drawn only from
consented data, never influencing rank); `resonance_request_intro` /
`resonance_list_requests` / `resonance_respond_intro` / `resonance_send_message`
/ `resonance_read_messages` (R14); `resonance_create_workspace` /
`resonance_get_workspace` / `resonance_list_workspaces` (R14B). Writes require
`confirm`; reads carry `readOnlyHint`; any returned user text carries
`untrustedContentHint`.

## Verified in this repo

- `tests/test_remote_oauth.py` — focused OAuth protocol suite: discovery ×2,
  registration, full authorize→consent→code+state→token→initialize→tools/list→
  `resonance_whoami`, wrong verifier, replayed code, wrong/tampered redirect,
  wrong resource, revoke-then-reuse, refresh rotation + reconnect, login binding.
- `tests/test_remote_mcp.py` / `tests/test_remote_mcp_realchat.py` — the full
  remote journey and two independent real-chat users discovering each other on
  structure, both over the real consent flow.
- `tests/e2e/oauth_probe.py` (+ `tests/e2e/test_oauth_probe_harness.py`) — an
  external-style black-box probe that starts from a base URL alone.
