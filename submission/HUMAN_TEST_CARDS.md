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

Prerequisite: a Chrome build that exposes `document.modelContext`. **Canary is
not needed.** Google Chrome **152 stable** ships WebMCP behind a flag; launch it
with the feature enabled and quit any running Chrome first, or the flag is
ignored:

```
open -a "Google Chrome" --args --enable-features=WebMCP
```

Verified on Chrome `152.0.7977.83`: `typeof document.modelContext` is
`"undefined"` without the flag and `"object"` with it. `navigator.modelContext`
does not exist either way. Older builds (Chromium 141) have no WebMCP at all.

If the pill reads `WebMCP · unavailable`, this browser has no
`document.modelContext` — stop and report the browser version. That pill states
the **browser's capability**, not your consent; your consent is the header pill
(`Private · not discoverable` / `Shared with Resonance`). Before #169 the
capability pill was overwritten with the consent state, so a browser without
WebMCP showed `WebMCP · private` and this step could not be trusted.

The whole card is also automated:

```
python3 submission/evidence/browser_harness.py https://<origin> \
    --exe "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
    --out submission/evidence/<dir>
```

It passes `--enable-features=WebMCP` itself, reports `mode: NATIVE` when the
browser really has the surface, and revokes its own share at the end. Executed
run on `8670568`: 24/24, `mode: NATIVE` —
`submission/evidence/public-origin-8670568/card-a-browser/`.

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
4. Ask the agent to extract the causal structure of something you are actually
   working on and call `resonance_prepare_thought`
   `{ "request_id": "card-a-1", "thought": { "topic": …, "domain": …, "nodes": [...], "relations": [...] } }`
   (or `{ "request_id": "card-a-1", "context": "<a few sentences>" }`) → expect
   `discoverable: false`, `input_kind: agent_structured` (or `raw_text_fallback`);
   WebMCP pill `WebMCP · private draft ready`. Without `thought`/`context` the
   page's visible thought is used instead.
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

Executed evidence for steps 1–4 and 7 (real Claude custom connector, OAuth,
production): `submission/evidence/hosted-client-claude/card_b_claude_connector_2026-09-04.md`.

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

## Card E — hosted MCP client, canonical URL only (Grok custom connector)

Grok supports custom **remote** MCP connectors, so this is a third independent
hosted client and not a "not supported" result. It cannot reach a local server;
the canonical public URL is exactly what it needs.

1. grok.com → **Connectors** → **New Connector** → **Custom**.
2. MCP server URL = `https://resonance-production-cfe3.up.railway.app/mcp`;
   complete the authentication the server asks for (OAuth is discovered).
3. The Resonance authorization page opens → **Continue as guest** → **Approve**.
4. New chat with the connector enabled: "Call resonance_whoami." → `person-…`.
5. Steps 5–8 of Card B.

On a Grok Business/Enterprise workspace a team admin has to provision the
connector first. **Not executed on any engine version.**
