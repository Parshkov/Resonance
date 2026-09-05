# Release evidence — public origin @ 3c7dc80 (pulse 4)

| Field | Value |
|---|---|
| Repo HEAD verified | `3c7dc80272702ce32c0e1946da57ba63189a14d6` (main) — `git rev-parse HEAD` matched, no checkout needed |
| Railway deployment | `86aebe9b-f196-44f0-99b2-9870a1619bde` (project `resonance-live`, status SUCCESS, created 15:39:02Z, commitHash 3c7dc80, branch main) |
| Origin / MCP | https://resonance-production-cfe3.up.railway.app · …/mcp |
| Health at start | `ok:true`, `mode:live`, db_generation 174 == serving_generation 174, `index_current:true` |
| Worker start / finish (UTC) | 2026-09-04 15:40:05 / 15:53 (hard stop 16:20 not reached) |
| Branch | `claude/release-evidence-pulse-4`, evidence under `submission/evidence/public-origin-3c7dc80/` |

No product code was modified. No GitHub comments were posted. No tokens, codes, cookies, confirmation tokens, proxy address or raw chat text are committed (every script asserts this before writing; the whole directory was grepped again before each push).

## Per-phase results

| Phase | Check | Result | Count | UTC | Evidence |
|---|---|---|---|---|---|
| P0 | Wait for `GET /oauth/consent.css` 200 AND `GET /api/product/health` 200 | PASS | ready on 1st poll | 15:40:54Z | `p0_ready.txt` |
| P1 | `HEAD /` 200 text/html, `HEAD /webmcp.mjs` 200 text/javascript, `HEAD /mcp` 405 `Allow: POST, DELETE`, `GET /oauth/consent.css` 200 `text/css; charset=utf-8` (2687 bytes, cache-control public max-age=3600) | PASS | 4/4 | 15:41:05Z | `p1_http.md` |
| P2 | `ops/oauth_smoke.py --auto-consent -v` | PASS | 27/27 | ~15:41–15:42Z | `p2_smoke.txt` |
| P2b | `ops/hosted_onboarding_probe.py --smoke --refresh --revoke --json` | PASS | 9/9 required; the smoke step PASSED (its sample chat still yields structure: "shared ses-…, discover ok (0 matches)") — the empty-draft refusal did not trigger there | ~15:42Z | `p2b_probe.json`, `p2b_probe.txt` |
| P3 | `submission/evidence/abc_mcp_test.py` over `/mcp` | PASS | 35/35 | ~15:42–15:44Z | `p3_abc.txt`, `p3_abc.json` |
| P4 | Remote-MCP empty-draft refusal: implicit prose → `isError` with "call again with `thought`"; `resonance_my_thoughts` → 0 sessions; cue-explicit prose → success, `structure = {nodes: 7, relations: 4}` | PASS | 7/7 | 15:45:02–15:45:15Z | `p4_empty_draft_refusal.md`, `p4_empty_draft_script.py` |
| P5 | Browser path (cookie + CSRF): prepare(5-node thought) → preview → share → `/api/context?source=live` shows own thought + topic → `?source=replay` shows `thought-aria-plasma-lens` → `/api/discover?source=live` 200 with 15 matches (first three: `approximate`, structural 0.8830) → consent shared=false; then implicit prose → 400 `validation_failed` mentioning `thought` → preview 409 | PASS | 11/11 | 15:44:55–15:45:28Z | `p5_browser_path.md`, `p5_browser_path_script.py`, `p5b_reservation_probe.py` |
| P6 | Playwright harness copy (solo re-run) | PASS (expected shape) | 17/18 — only the honest native `document.modelContext` probe fails | ~15:50–15:52Z | `p6_run1b_harness.txt`, `browser_run1b/` |
| P6 | Playwright harness copy (first run, overlapped with run 2) | 16/18 | extra FAIL on `resonance_get_match` explained below | ~15:47–15:49Z | `p6_run1_harness.txt`, `browser/` |
| P6 | Scripted own-thought run through page tools + screenshot | PASS with deviations | run 2: 10/11; run 2b: 11/13 (see deviations 3–4) | 15:48–15:49Z | `p6_run2_scripted.txt`, `p6_run2b_scripted.txt`, `p6_live_own_thought.png`, `browser/p6_run2*.json` |
| P6 | OAuth consent page for client "Claude (custom connector)" | PASS | client name shown; `main.consent` borderRadius == `22px`; `/oauth/consent.css` in `document.styleSheets` | 15:49Z | `p6_consent.png`, `p6_browser.md` |
| P7 | This summary | — | — | 15:53Z | `SUMMARY.md` |

## Exact deviations (all redacted, none is a failed phase)

1. **Content-derived thought ids are reserved globally, and a refused prepare reserves one too.** The first P4/P5 attempt used the task's exact prose; the MCP-side cue-explicit draft reserved that text's thought id, and the browser-side implicit-prose step then got `409 conflict` "thought_id is already reserved; a new session (including re-share after delete) requires a new Thought DNA id" instead of `400 validation_failed`. The isolation probe (`p5_browser_path.md`, appendix) shows: a never-seen implicit text → 400 `validation_failed` and no draft (preview 409 "no prepared private draft exists") **but the same text from a fresh guest 4 s later → 409 "already reserved"**; a never-seen cue text → 200 private draft, and the same text from another guest → 409. So a refusal that leaves no draft still consumes the id, and a private never-shared raw-text draft blocks every other user from preparing the same text. P4/P5 were re-run with a nonce sentence appended and pass on first use. (The probe was inadvertently executed a second time at 15:49Z with nonce `x` during the get_match reproduction; same results.)
2. **P6 run 1 `resonance_get_match` FAIL is interference, not a regression.** Run 1 overlapped with run 2, which shared and revoked a new live thought between run 1's discover and get_match; the product fails closed on a changed corpus. The solo re-run (run 1b) passes that step (17/18), and the stdlib reproduction shows `GET /api/webmcp/match` returning 200 for the first three live matches.
3. **P6 heading timing.** In run 2, 2 s after the tool-driven live discover the page still showed the replay heading and `#map-status-text` = "Calling accepted discovery MCP…" (fetch in flight). Run 2b at the same 2 s delay showed `#thought-heading` = "Panic buying after a shortage rumour → synchronized bulk purchases" and "3 resonances · backend order intact", before and after clicking Live MCP. The page does follow the own thought; the 2 s sample is racy.
4. **P6 visible card count is 3, not 4.** `.match-card` count = 3 (classes `match-card is-selected`, `match-card`, `match-card`, each labelled `approximate`, structural 0.8830), sidebar "03 shown" + "12 other backend results" = 15 = the tool's match count. Run 1/1b (fixture thought, after clicking Live MCP) still show 4 cards.
5. After revoke, the page tool `resonance_get_match` on the old result_id returns `validation_failed` 400 "discovery result is unknown, expired, or not yours" (previous pass: `stale_result` 409). The harness accepts either.
6. P0 note: `/health` is 404 on this origin; the health endpoint is `/api/product/health` (the poll script was corrected before its first successful iteration; `p0_ready.txt` records the successful poll).
7. Container egress: Chromium needed the container HTTPS proxy + `--ssl-version-max=tls1.2` (same as the two previous passes); curl and the stdlib scripts reached the origin directly.

## Redaction notes

- `p2_smoke.txt`: authorization code emitted as `<redacted>` by the script; no bearer/refresh values.
- `p4_*.md`, `p5_*.md`: user_id truncated; cookie/csrf/confirmation_token only recorded as set/missing; the two scripts assert the access/refresh tokens, cookie and confirmation token are absent from their output.
- `p6_*`: harness JSON contains no confirmation_token/access token values; the scripted-run JSON asserts the confirmation token and consent client_id are absent; the throwaway public `client_id` shown in `p6_consent.png` is not a credential (public client, `token_endpoint_auth_method: none`).
