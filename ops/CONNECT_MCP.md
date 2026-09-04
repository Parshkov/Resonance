# Connect a real chat to Resonance (remote MCP)

Resonance is meant to be used from the conversation you are already having
with an AI assistant. The live product exposes a **remote MCP server**
(Streamable HTTP, JSON-RPC 2.0) so that assistant can, with your approval,
hand the *structure* of what you are working on to Resonance and find people
whose reasoning resonates.

Endpoint: `https://<live origin>/mcp` (production: see `HACKATHON.md`).

## 1. Get your key (30 seconds, in the browser)

1. Open the live origin in Chrome. A guest account is created for you.
2. Top bar → **Collaboration** → **Connect your chat (MCP)** → **Create MCP key**.
3. Copy the snippet for your client. The key is shown once; it is a second
   login for the same account, so everything your chat does appears in the
   same panel. Anyone holding the key acts as you: treat it like a password.

## 2. Connect your client

**Claude Code / Claude Desktop (CLI)**

```bash
claude mcp add --transport http resonance https://<live origin>/mcp \
  --header "Authorization: Bearer <key>"
```

**Cursor, Windsurf, any `mcp.json` client**

```json
{"mcpServers": {"resonance": {"url": "https://<live origin>/mcp",
                              "headers": {"Authorization": "Bearer <key>"}}}}
```

**Clients that accept only a URL** (claude.ai custom connector, ChatGPT
connectors in developer mode): use the capability URL
`https://<live origin>/mcp/<key>` with authentication set to "none".
The key travels in the path; do not paste that URL anywhere public.

The server answers `initialize`, `tools/list`, `tools/call`, `ping`; `GET /mcp`
is `405` (no SSE stream is offered), `DELETE /mcp` is `204`.

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
