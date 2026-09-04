# Public-origin release evidence — summary

- Repo: Parshkov/Resonance, evidence taken from `main` at HEAD `4ab28a30f986478562a88e1e1e6a83c81ef7bda9` (expected HEAD matched).
- Production origin: https://resonance-production-cfe3.up.railway.app (MCP: `/mcp`).
- Deployment identity (`/api/product/health`): `ok=true mode=live`, `db_generation` 78 at start → 81 after Phase 3,
  `serving_generation` equal to `db_generation` each time, `index_current=true`,
  `engine_snapshot=f7f839d595712aa5467cc12fd91b19c44ccc944f2f0a415f466b4240f8a05892`.
- Window: Phase 0 at 2026-09-04T06:12:41Z, last evidence written 2026-09-04T06:29:05Z (hard stop was 07:35Z).
- Nothing in product code was modified. No tokens, codes, cookies or raw private conversation text are in this tree
  (grep for `access_token`/`refresh_token` hits only boolean flag names).

| Phase | What | Result | Counts | File(s) |
|---|---|---|---|---|
| 0 | Egress + timestamp + HEAD | PASS | — | this file |
| 1 | Raw HTTP: health, unauth `/mcp` 401 + `WWW-Authenticate resource_metadata`, PRM, AS metadata, `GET /mcp` 405, `GET /oauth/authorize` 400, `/` 200 + title + `webmcp.mjs`, `/webmcp.mjs` (`document.modelContext` ×1, `registerTool` ×2), bogus bearer 401 | PASS | 9/9 requests as expected | `phase1_http.md` |
| 2 | `ops/oauth_smoke.py --auto-consent -v` | PASS with caveat | original run 1/2 (client-side header-case bug), re-run with case-insensitive header lookup **27/27** | `phase2_oauth_smoke.txt`, `run_oauth_smoke_ci_headers.py` |
| 3 | Real 3-identity A/B/C structural test over public `/mcp` | PASS | **41/41** steps | `abc_public_test.py`, `phase3_abc_public.json`, `phase3_abc_public.md` |
| 4 | OAuth/MCP negatives | PARTIAL | **18/20** (2 expectations did not hold, see below) | `phase4_negatives.py`, `phase4_negatives.md` |
| 5 | Playwright Chromium: native WebMCP probe + labelled harness run | PARTIAL | native modelContext **absent**; harness 6/7 tool calls ok, 1 skipped | `phase5_browser.py`, `phase5_browser.md`, `phase5_browser.json`, `phase5_page.png`, `phase5_after_share.png`, `phase5_after_discover.png` |

## Phase 3 headline numbers (public `/mcp`, three fresh OAuth guest accounts)

- B (panic-buying loop) discover → A (retry-storm loop, different vocabulary) ranked **#1** with
  `structural=0.8875`, `semantic=0.0966`, `preserved_relation_count=7/7`, `mapped_node_count=7`, `contradiction_count=0`;
  correspondences e.g. `shortage rumour↔partial upstream outage`, `synchronized bulk purchasing↔synchronized client retries`,
  `demand amplification↔request amplification`, `per-customer purchase cap↔per-client retry budget`.
- C (shared vocabulary, no feedback loop) was **not returned at all** (neither in matches nor in rejected): A above C holds trivially.
- Consent gates held: share without `confirm` → `confirmation_required`; A cannot read B's `result_id` (`validation_failed`);
  C (non-member) cannot read the A↔B channel; after A `stop_sharing`, B's re-discover no longer lists A and the old
  result is `stale_result`.
- Intro → accept → channel → message → read all succeeded; `request_intro` replay with the same `request_id` was idempotent.
- Observed, not asserted: C could `request_intro` to A without having discovered A first (state `requested`).
- Observed: the raw-text fallback extractor produced 0 nodes / 0 relations for the original 8-sentence A context
  (`input_kind=raw_text_fallback`, not shared); structured prepare was used for the shared thoughts.
- Production `/mcp` issues no `Mcp-Session-Id` header (stateless bridge).

## Everything that failed or deviated (exact, redacted)

1. **Phase 2, original run** — `[FAIL] 1 challenge carries resource_metadata`. Cause is client-side: the edge returns the
   header as `www-authenticate` and `ops/oauth_smoke.py` looks up `WWW-Authenticate` in a case-sensitive `dict`.
   Server behaviour is correct (Phase 1b shows the header). Re-run with a case-insensitive header view: 27/27.
2. **Phase 4** — `[FAIL] access token after refresh revocation on /mcp -> 401 {"status": 200}`: revoking the refresh token
   (200) did not invalidate its sibling access token; explicit access-token revocation then gave 401 (RFC 7009 §2.1 SHOULD).
3. **Phase 4** — `[FAIL] unknown Mcp-Session-Id on /mcp -> 404 {"status": 200}`: the production bridge is stateless and
   ignores the header; no 404 semantics exist there.
4. **Phase 5** — `resonance_discover {source:"replay"}` via the page's `/api/webmcp/discover?source=replay` →
   HTTP 500 `{"error":"internal_error","message":"unexpected product error"}`.
5. **Phase 5** — live discover from the browser guest returned 0 matches, so `resonance_get_match` was skipped.
6. **Phase 5** — without WebMCP the header pill reads `Shared with Resonance` on a never-shared guest (fixture text);
   with the harness the pill tracked real state (`Private · not discoverable` ↔ `Shared with Resonance`).
7. **Phase 5** — NATIVE `document.modelContext`: **absent** in Playwright Chromium 141.0.7390.37 with and without
   `--enable-features=WebMCP,WebMCPTesting`; the harness run is page-registered tools executed through an injected
   `modelContext` shim, NOT native WebMCP discovery.

Sandbox-only notes (not product findings): Python Playwright launched the pre-installed `/opt/pw-browsers/chromium`
binary via `executable_path` fallback, through the container's HTTPS proxy with `--ssl-version-max=tls1.2`.
