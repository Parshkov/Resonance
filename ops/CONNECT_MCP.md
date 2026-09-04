# Connect a real chat to Resonance (remote MCP)

Resonance is meant to be used from the conversation you are already having
with an AI assistant. The live product exposes a **remote MCP server**
(Streamable HTTP, JSON-RPC 2.0) so that assistant can, with your approval,
hand the *structure* of what you are working on to Resonance and find people
whose reasoning resonates.

Endpoint: `https://resonance-production-cfe3.up.railway.app/mcp` (the only thing a user needs).

## 1. Connect with the URL only (canonical path — no key)

Give your MCP client exactly one thing:

```
https://resonance-production-cfe3.up.railway.app/mcp
```

The origin answers an unauthenticated request with a standard challenge
(`401` + `WWW-Authenticate … resource_metadata`), publishes RFC 9728 / RFC 8414
metadata and RFC 7591 registration, and opens a Resonance consent page in your
browser: continue as a pseudonymous guest, sign in with a recovery secret, or
continue as the account already signed in on this browser. Approve, and the
client receives an OAuth 2.1 token (PKCE S256, rotating refresh with
`offline_access`); the token *is* an R12 session of that account, so whatever
your chat shares appears in the same Collaboration panel.

- claude.ai custom connector / Claude Desktop / Claude Code: add the URL, let
  the client discover OAuth (`claude mcp add --transport http resonance
  https://resonance-production-cfe3.up.railway.app/mcp`).
- ChatGPT developer-mode app (Business / Enterprise / Edu): Create → MCP server
  URL → OAuth → Scan tools.
- Cursor / Windsurf / any `mcp.json` client with OAuth support: `{"url": "…/mcp"}`.

Disconnecting in the client (or `POST /oauth/revoke`) invalidates the grant
immediately; the next `/mcp` call is `401`.

## 2. Developer fallback — manual key (debug only, not the normal path)

For clients that cannot run OAuth at all you may mint a key in the browser
(Collaboration → **Connect your chat (MCP)** → **Create MCP key**) and send it
as `Authorization: Bearer <key>`, or as the capability URL `…/mcp/<key>` for
URL-only clients. The key is a second login for the same account; treat it
like a password and never publish the URL. This is a fallback for debugging,
not the onboarding judges or users are asked to perform.

The server answers `initialize`, `tools/list`, `tools/call`, `ping`; `GET /mcp`
is `405` (no SSE stream is offered), `DELETE /mcp` is `204`. The transport is
stateless: no `Mcp-Session-Id` is issued, so a redeploy never strands a client.

## 3. Run a real test

Say to your assistant, in your own words:

> Connect to Resonance. Extract the causal structure of what I'm working on
> from this conversation, show me exactly what would be shared, and only
> after I approve, share it and tell me who resonates and why.

What happens, tool by tool:

| step | tool | what it does |
|---|---|---|
| 0 | `resonance_whoami` | confirms the key maps to your account |
| 1 | `resonance_prepare_thought` | your assistant passes a labelled causal graph (`nodes` with roles problem / mechanism / state / outcome / constraint / method / evidence / resource / agent; `relations` typed causes / prevents / requires / part_of / constrains / supports / contradicts) or raw text as a fallback. Returns the exact preview and a one-time confirmation token. **Nothing is discoverable yet.** |
| 2 | `resonance_share_thought` | only with `confirm=true` after you approved the preview. Only the structural graph is stored; the conversation text is never retained. |
| 3 | `resonance_discover` | accepted structural discovery against everything other people share; matches in backend order with scores and mapped correspondences. |
| 4 | `resonance_explain_match` | full evidence for one match. |
| 5 | `resonance_request_intro` → `resonance_list_intros` → `resonance_respond_intro` → `resonance_send_message` / `resonance_read_messages` | consent-gated introduction and a relay channel between the two of you; every write needs your explicit `confirm=true`. |
| — | `resonance_stop_sharing` | revoke; your thought leaves discovery immediately. |

Two people running steps 1–3 from two different chats find each other when
the *shape* of their reasoning matches, even across domains (the regression
test pairs "retry storms after a partial outage" with "panic buying after a
supply rumour": structural 0.89, five of five relations preserved).

## Security model

- Bearer requests are the R12 non-cookie path: no CSRF, the same
  authorization, consent and freshness policy as the browser.
- Keys are minted only by a cookie + CSRF authenticated browser session
  (`POST /api/product/mcp_key`) and expire with the identity session TTL.
- Tool results that carry other people's text are marked
  `untrustedContentHint`; the bridge never passes contact details, only
  pseudonyms, session ids and structural evidence.
- No matching logic lives in the bridge (`src/product/mcp_bridge.py`); it
  calls `LiveProductService` exactly like the HTTP routes.

## Verification

`tests/test_remote_mcp.py` runs the whole flow over HTTP for two accounts and
two chat clients (header key and URL key), including refusal without
`confirm`, discovery before sharing (`share_required`, not a crash), intro
accept, relay message, revoke, raw-text fallback, 401/405 transport contract.
