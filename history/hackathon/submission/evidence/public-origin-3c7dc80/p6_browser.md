# P6 — Playwright browser evidence on the public origin (HEAD 3c7dc80)

Origin: https://resonance-production-cfe3.up.railway.app · Chromium 141.0.7390.37 (pre-installed `/opt/pw-browsers/chromium-1194/chrome-linux/chrome` via `executable_path`) · Playwright (pip) · run 2026-09-04 15:47–15:52 UTC

Launch: `--enable-features=WebMCP,WebMCPTesting --ssl-version-max=tls1.2` plus the container HTTPS proxy as Playwright `proxy.server` (same egress workaround as the two previous passes; the proxy address is not recorded in any evidence file). No product code was modified; `p6_browser_harness_copy.py` is a copy of `submission/evidence/browser_harness.py` whose only change is the two-line env-driven launch args.

## Run 1 — harness copy (`p6_run1_harness.txt`, `browser/`)

Result: **16/18** (expected 17/18). Two FAIL lines:

1. `NATIVE document.modelContext present` — expected, honest: stock Chromium has no native WebMCP; the shim path is used for everything else.
2. `READ: resonance_get_match returns evidence for a live match` — the page tool returned an `isError` envelope. **This run overlapped in time with run 2 below, which shared and then revoked a new thought on the same live corpus while run 1 was between `resonance_discover` and `resonance_get_match`.** The product's contract for that situation is `stale_result` ("durable corpus changed after this discovery; run discovery again"), which is what the after-revoke step of the same run observed as a PASS on the previous pass. The stdlib reproduction (`p6c_get_match_script.py`, table below) shows `GET /api/webmcp/match` returning 200 for the first three live matches when nothing else is writing, and the solo harness re-run (`p6_run1b_harness.txt`, `browser_run1b/`) is recorded at the end of this file.

Other run-1 observations: with the shim, first load shows `#header-consent` = `Private · not discoverable` and the pill `WebMCP · private`; after prepare the pill reads `WebMCP · private draft ready`; after share `Shared with Resonance` / `WebMCP · LIVE shared`; after discover `WebMCP · LIVE DB discovery`; after revoke back to `Private · not discoverable` / `WebMCP · private`. Live discover returned 15 matches, 4 cards visible after clicking Live MCP. After revoke, `resonance_get_match` on the old result_id now returns `validation_failed` 400 "discovery result is unknown, expired, or not yours; run discovery again" (previous pass: `stale_result` 409); the harness accepts either.

### `GET /api/webmcp/match` reproduction (stdlib, no concurrent writers)

| UTC | step | status | detail |
|---|---|---|---|
| 15:49:49Z | guest F: prepare cue FRESH text again (does a private draft reserve globally?) | 409 | {"error": "conflict", "message": "thought_id is already reserved; a new session (including re-share after delete) requires a new Thought DNA id"} |
| 15:49:49Z | guest E: preview (own draft still there) | 200 | {"draft_id": "set", "source_retention": "not_retained"} |
| 15:49:53Z | prepare | 200 | input_kind=agent_structured |
| 15:49:55Z | share | 200 | shared=True |
| 15:49:57Z | GET /api/webmcp/discover?source=live | 200 | n=15 result_id=set first_session=ses-bb2d935993bb38c5 |
| 15:49:57Z | GET /api/webmcp/match (match #1, session=ses-bb2d935993bb38c5) | 200 | {"source": "live"} |
| 15:49:57Z | GET /api/webmcp/match (match #2, session=ses-c041572ff069dafd) | 200 | {"source": "live"} |
| 15:49:58Z | GET /api/webmcp/match (match #3, session=ses-ef6d5093f53a09d5) | 200 | {"source": "live"} |
| 15:49:59Z | GET discover again | 200 | same_result_id=True n=15 |
| 15:49:59Z | GET /api/webmcp/match immediately after 2nd discover | 200 | {"source": "live"} |
| 15:50:02Z | consent shared=false | 200 | revoked=True |

## Run 2 — scripted own-thought flow through the page's WebMCP tools (`p6_run2_scripted.txt`, `p6_run2b_scripted.txt`, `browser/p6_run2.json`, `browser/p6_run2b.json`)

Same shim as the harness. Tools called in order: `resonance_prepare_thought` **with** the structured 5-node panic-buying `thought` → `resonance_get_share_preview` → `resonance_share_prepared_thought` (confirm + confirmation_token) → `resonance_discover {source:"live"}` → wait 2 s → read the page → screenshot → `resonance_update_consent {shared:false}`.

| check | run 2 (15:48Z) | run 2b (15:49Z, adds a click on `#source-live` afterwards) |
|---|---|---|
| prepare with structured thought → `input_kind=agent_structured`, `discoverable=false` | PASS | PASS |
| preview shows the own 5 labels, topic "Panic buying after a shortage rumour", confirmation_token set | PASS (5 nodes, 5 relations) | PASS |
| share (confirm + token) → `shared=true, discoverable=true` | PASS | PASS |
| `resonance_discover {source:live}` → `source=live`, result_id, matches | PASS (n=15) | PASS (n=15) |
| `#thought-heading` after 2 s starts with "Panic buying after a shortage rumour" | **FAIL** — still `plasma lens thermal bloom → ionization cascade`; `#map-status-text` = `Calling accepted discovery MCP…` (page still mid-call at the 2 s mark) | PASS — `Panic buying after a shortage rumour → synchronized bulk purchases`; `#map-status-text` = `3 resonances · backend order intact` |
| `.match-card` count == 4 | PASS (4 — but those were the replay cards; see the heading row) | **FAIL — 3** (classes `match-card is-selected`, `match-card`, `match-card`; card texts `01 guest-… structural 0.8830 Panic buying after a shortage rumour`, `02 …`, `03 …`; sidebar reads "03 shown" and "12 other backend results", 3 + 12 = 15 = tool result) |
| after clicking `#source-live`: heading / count | — | heading PASS (unchanged); count still 3 |
| `resonance_update_consent {shared:false}` → `revoked=true, discoverable=false` | PASS | PASS |
| totals | 10/11 | 11/13 |

Screenshot `p6_live_own_thought.png` (run 2b, after the click; identical to `p6_live_own_thought_before_click.png`): the active-thought panel shows the person's own thought id `thought-mcp-panic-buying-after-a-shortage-rumour-…`, heading "Panic buying after a shortage rumour → synchronized bulk purchases", the 5-node causal chain, header pill "Shared with Resonance", Live MCP source selected, three match cards each labelled `approximate` / structural 0.8830, and the footer "LIVE · accepted discover_resonance MCP path · analogical / k=15".

Reading: the page does follow the tool-driven live discover (heading, status, cards) without any manual source switch — run 2 simply sampled the DOM while the page's own discover fetch was still in flight (its status text said so), and run 2b, sampled at the same 2 s delay, had already rendered. The rendered card count is 3 on this deployment for this thought, not the 4 the previous pass saw; the tool result still has 15 matches and the sidebar accounts for all of them.

## OAuth consent page for a client named "Claude (custom connector)" (`p6_consent.png`)

Registered via `POST /oauth/register` (JSON `client_name` + `redirect_uris`, public client) and opened `/oauth/authorize` with a PKCE S256 challenge, `scope=resonance offline_access`, `resource=…/mcp`.

| check | result |
|---|---|
| page status / title | 200 / `Authorize Resonance access` |
| client name rendered | PASS — body contains `Claude (custom connector)` (bold, followed by the registered client_id in monospace) |
| stylesheet applied | PASS — `document.styleSheets` lists `…/oauth/consent.css`; `getComputedStyle(document.querySelector('main.consent')).borderRadius` == `"22px"` |

The screenshot shows the styled card (rounded dark panel, gold "Allow access" button, guest/existing-account radio group, Account ID and Recovery secret fields left empty). The only identifier visible is the throwaway public `client_id` created for this screenshot; no code, token or cookie appears.

## Redaction / hygiene

- `browser/browser_harness.json`, `browser/p6_run2*.json`, `*.txt`: scanned for bearer/refresh tokens, cookie values, confirmation tokens and the proxy address — none present (the run-2 scripts assert this before writing).
- No product code was modified. All shared thoughts were revoked (`shared=false`) at the end of each run.

## Run 1b — harness copy re-run alone (`p6_run1b_harness.txt`, `browser_run1b/`, ~15:50–15:52Z)

Result: **17/18** — the expected shape. The only FAIL is the honest native `document.modelContext` probe. `resonance_get_match` on a live match PASSES when no other run is writing to the corpus, which confirms the run-1 failure above was interference from the concurrent run 2 share/revoke (a `stale_result`-class refusal, which is the product's intended fail-closed behaviour), not a regression on 3c7dc80.
