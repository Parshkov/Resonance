# Human test cards — final release (sponsor-only steps, ≤10 minutes each)

Everything below runs against the public origin only. Never type a key, a
bearer token or a `/mcp/<secret>` URL in any of these cards: if a step asks
you for one, that is a FAIL to report.

- Origin: `https://resonance-production-cfe3.up.railway.app`
- Canonical MCP URL: `https://resonance-production-cfe3.up.railway.app/mcp`
- Report back: the deployment id shown in `submission/RELEASE_MANIFEST.md`, the
  step number where anything deviated, the visible text, and a screenshot /
  screen recording. No tokens, no raw chat text.

## Card A — native browser WebMCP (competition evidence; Chrome with WebMCP enabled)

Prerequisite: a Chrome build that exposes `document.modelContext` (Chrome
Canary/Dev with the WebMCP flag, or the ChatGPT in-app browser when it
supports WebMCP). Stock Chrome/Chromium 141 does **not** expose it — the page
then shows the pill `WebMCP · unavailable`; that is the browser, not the site.

1. Open the origin. Expect: the R9 page renders 4 replay cards; header pill
   `Private · not discoverable`; WebMCP pill `WebMCP · private` (registration
   succeeded) — if it says `WebMCP · unavailable`, the browser has no
   `document.modelContext`; stop and report the browser version.
2. In the browser's agent/tool panel (or DevTools → WebMCP panel) confirm the
   tools are listed: `resonance_prepare_thought`, `resonance_get_share_preview`,
   `resonance_share_prepared_thought`, `resonance_discover`,
   `resonance_get_match`, `resonance_update_consent` (plus collaboration /
   workspace tools).
3. Ask the agent to call `resonance_discover` with `{ "source": "live" }`
   BEFORE sharing. Expect: the tool fails closed with `share_required`
   ("discovery needs a shared thought first …"). Nothing is discoverable yet.
4. `resonance_prepare_thought` `{ "request_id": "card-a-1" }` → expect
   `discoverable: false`; WebMCP pill `WebMCP · private draft ready`.
5. `resonance_get_share_preview` `{}` → expect the Thought DNA nodes /
   relations and a `confirmation_token`. Read it: this is exactly what would
   become discoverable.
6. `resonance_share_prepared_thought`
   `{ "request_id": "card-a-2", "confirm": true, "confirmation_token": "<from step 5>" }`
   → expect `discoverable: true`; header pill flips to `Shared with
   Resonance`; WebMCP pill `WebMCP · LIVE shared`; Collaboration drawer shows
   `Shared · 1 discoverable thought`.
7. `resonance_discover` `{ "source": "live" }` → expect `source: "live"`, a
   `result_id`, ≥ 1 match; click **Live MCP** in the top bar → match cards
   render from live data (structural score, mapped nodes, preserved relations).
8. `resonance_get_match` `{ "result_id": "<step 7>", "session_id": "<first match>" }`
   → expect the evidence block (mapped nodes, preserved relations, verdict).
9. `resonance_update_consent` `{ "request_id": "card-a-3", "shared": false }`
   → expect `revoked: true`; header pill back to `Private · not discoverable`;
   `resonance_discover` `{ "source": "live" }` now fails closed again.
10. Record steps 2–9 on screen (this is the competition footage).

## Card B — hosted MCP client, canonical URL only (Claude custom connector)

1. Claude → Settings → Connectors → **Add custom connector** → URL
   `https://resonance-production-cfe3.up.railway.app/mcp`; leave auth to the
   client (OAuth is discovered automatically).
2. The client opens the Resonance authorization page. Choose **Continue as
   guest** (or sign in with a recovery secret), then **Approve**.
3. Back in Claude the connector shows connected and lists `resonance_*` tools.
4. New chat: "Call resonance_whoami." → expect `user_id: person-…`,
   `display_label: guest-…`.
5. Talk about something you are actually working on, then: "Extract the causal
   structure of what I'm working on and call resonance_prepare_thought; show
   me the preview." → expect nodes/relations, `discoverable: false`,
   `source_retention: not_retained`.
6. "I approve — share it." → `resonance_share_thought` with `confirm: true` →
   `discoverable: true`, `session_id: ses-…`.
7. "Who resonates with this?" → `resonance_discover` → matches with structural
   scores; "Explain the first match" → `resonance_explain_match`.
8. "Stop sharing." → `resonance_stop_sharing` → `revoked: true`.

## Card C — hosted MCP client, canonical URL only (ChatGPT developer-mode app)

Requires a ChatGPT workspace with developer mode (Business / Enterprise / Edu).

1. Settings → Apps & Connectors → Advanced → Developer mode → **Create**.
2. MCP server URL = `https://resonance-production-cfe3.up.railway.app/mcp`;
   authentication = **OAuth**; **Scan tools**.
3. The Resonance authorization page opens → **Continue as guest** → **Approve**.
4. ChatGPT lists the `resonance_*` tools. New chat with the app enabled:
   "Call resonance_whoami." → `person-…`.
5. Steps 5–8 of Card B.

Known limitation to state honestly: OAuth codes, refresh grants and client
registrations live in process memory on the single production replica; after
a redeploy a hosted client re-authorizes once (access tokens themselves are
durable R12 sessions).

## Card D — two people, two chats (the product story)

Two testers each run Card B or C from their own account and their own real
topic, both share, then either asks "Who resonates with this?" and requests an
introduction; the other accepts in their chat (`resonance_respond_intro`,
`confirm: true`) and replies (`resonance_send_message`). Report the two
pseudonymous ids, the session ids, the structural score and the preserved
relation count — nothing else.
