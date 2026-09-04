# Phase 5 — browser evidence (Playwright headless Chromium) against public origin

Origin: https://resonance-production-cfe3.up.railway.app
Started: 2026-09-04T06:28:44Z  Finished: 2026-09-04T06:29:05Z

**NATIVE document.modelContext: absent in Playwright Chromium 141.0.7390.37; harness run = page-registered tools executed via injected modelContext shim, NOT native WebMCP discovery**

## Run 1 — plain Chromium

- typeof document.modelContext: `undefined`
- typeof navigator.modelContext: `undefined`
- window.__resonanceWebMCP: `{"contract": "resonance-webmcp/0.1", "toolNames": ["resonance_prepare_thought", "resonance_get_share_preview", "resonance_share_prepared_thought", "resonance_discover", "resonance_get_match", "resonance_update_consent"], "mode": "live-product"}`
- page title: `Resonance — Visual Discovery`
- header consent text: `Shared with Resonance` (Private pill: False)
- WebMCP badge (#webmcp-status): `WebMCP · unavailable` (badge present: True)
- screenshot: phase5_page.png

```
Resonance

VISUAL DISCOVERY · R9

Shared with Resonance
CORPUS
5868db42…ca222f
Replay fixture
Live MCP
Collaboration
```

## Run 2 — Chromium with --enable-features=WebMCP,WebMCPTesting

- typeof document.modelContext: `undefined`
- typeof navigator.modelContext: `undefined`
- WebMCP badge: `WebMCP · unavailable`

## Run 3 — HARNESS (injected `document.modelContext` shim; NOT native WebMCP)

- registered tool names (from the page's own webmcp.mjs): `["resonance_request_intro", "resonance_list_requests", "resonance_respond_intro", "resonance_send_message", "resonance_read_messages", "resonance_create_workspace", "resonance_list_workspaces", "resonance_get_workspace", "resonance_respond_workspace_invite", "resonance_add_workspace_note", "resonance_add_workspace_task", "resonance_prepare_thought", "resonance_get_share_preview", "resonance_share_prepared_thought", "resonance_discover", "resonance_get_match", "resonance_update_consent"]`
- all tools carry inputSchema/annotations/execute: True
- state after load: consent=`Private · not discoverable` status=`WebMCP · private`
- preview returned a confirmation token: True (value not recorded)

| step | ok | header consent | WebMCP status | result summary |
|---|---|---|---|---|
| 1 discover(replay) | False | Private · not discoverable | WebMCP · private | `{"error": {"message": "unexpected product error", "code": "internal_error", "status": 500}}` |
| 2 prepare_thought(pulse-1) | True | Private · not discoverable | WebMCP · private draft ready | `{"session_id": "ses-2520e25614e4f3c3", "discoverable": false, "matches_count": 0, "rejected_count": 0}` |
| 3 get_share_preview | True | Private · not discoverable | WebMCP · private draft ready | `{"matches_count": 0, "rejected_count": 0}` |
| 4 share_prepared_thought(pulse-2, confirm=true) | True | Shared with Resonance | WebMCP · LIVE shared | `{"session_id": "ses-2520e25614e4f3c3", "shared": true, "discoverable": true, "matches_count": 0, "rejected_count": 0}` |
| 5 discover(live) | True | Shared with Resonance | WebMCP · LIVE DB discovery | `{"result_id": "result-e2b27a3688f3da003de857a0", "source": "live", "matches_count": 0, "rejected_count": 0}` |
| 6 get_match | skipped | | | no result_id or no matches from live discover |
| 7 update_consent(shared=false) | True | Private · not discoverable | WebMCP · private | `{"session_id": "ses-2520e25614e4f3c3", "shared": false, "discoverable": false, "matches_count": 0, "rejected_count": 0}` |

Screenshots: phase5_after_share.png, phase5_after_discover.png. Full detail (tokens redacted): phase5_browser.json

## Notes (honest reading)

- **Native WebMCP is absent** in this Playwright Chromium 141.0.7390.37, with and without
  `--enable-features=WebMCP,WebMCPTesting`. `typeof document.modelContext === "undefined"` in both runs, and the page's
  own badge reads `WebMCP · unavailable`. Nothing was faked; the harness run below is explicitly labelled.
- **Harness run: 17 tools were registered** by the page (the 6 from `/webmcp.mjs` plus 11 collaboration/workspace tools
  registered by another page module). All carry `inputSchema`, `annotations` and `execute`.
- **`resonance_discover {source:"replay"}` FAILED on the public origin**: the page's `/api/webmcp/discover?source=replay`
  answered HTTP 500 `{"error":"internal_error","message":"unexpected product error"}` (console: `Failed to load resource:
  the server responded with a status of 500`). Live discovery, prepare, preview, share and consent revoke all succeeded.
- **Live discover from the browser guest returned 0 matches / 0 rejected** (result_id issued, source `live`), so
  `resonance_get_match` was skipped (nothing to open). The page's right-hand panel in the screenshots shows the
  *replay fixture* cards, not live matches.
- **Header consent pill without WebMCP**: in the plain (non-harness) runs the header pill already read
  `Shared with Resonance` on a fresh, never-shared guest, while the harness run (where `applyAuthoritativeState` could
  run) correctly showed `Private · not discoverable` until the share and `Private · not discoverable` again after revoke.
  Static markup ships `Checking consent`; some other page module sets the fixture's "Shared" text when WebMCP is
  unavailable. Recorded as a UI-honesty observation, not changed.
- Sandbox-only workaround: Chromium was launched with `--ssl-version-max=tls1.2` and the container's HTTPS proxy
  because the proxy relay drops Chromium's TLS 1.3 ClientHello. This affects nothing about the product.
- State transitions observed in the harness (header consent / WebMCP badge):
  `Private · not discoverable / WebMCP · private` → prepare → `… / WebMCP · private draft ready` → share →
  `Shared with Resonance / WebMCP · LIVE shared` → discover(live) → `… / WebMCP · LIVE DB discovery` → revoke →
  `Private · not discoverable / WebMCP · private`.
