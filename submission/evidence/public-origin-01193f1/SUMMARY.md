# Release evidence — public origin @ 01193f1 (pulse 3)

- **Commit under test:** `01193f13a689edb9fc94978dca7212b484c5558a` (main, Railway redeploy)
- **Origin:** https://resonance-production-cfe3.up.railway.app · **MCP:** https://resonance-production-cfe3.up.railway.app/mcp
- **Worker start:** 2026-09-04T15:10:41Z · **finish:** 2026-09-04T15:14:35Z (all phases inside the 45-minute budget)
- **Method:** stdlib-only scripts from this repo (`ops/oauth_smoke.py`, `submission/evidence/abc_mcp_test.py`) plus two throwaway stdlib scripts for P4/P5 that reuse `ops.oauth_smoke.Smoke`. No product code modified, no GitHub comments posted, no tokens/codes/cookies/raw text recorded.

| Phase | What | Result | Count | UTC | Evidence |
|---|---|---|---|---|---|
| P0 | Wait for new deployment (health 200 AND `HEAD /` 200) | PASS | ready on 1st poll | 15:11:16Z | `p0_ready.txt` |
| P1 | HEAD vs GET on `/`, `/api/product/health`, `/webmcp.mjs`; `HEAD /mcp` | PASS | 4/4 endpoints | 15:11:36Z | `p1_head.md` |
| P2 | OAuth discovery/DCR/PKCE/consent/token/refresh smoke | PASS | 27/27 | ~15:11:4xZ | `p2_smoke.txt` |
| P3 | Real multi-user A/B/C structural test over `/mcp` | PASS | 35/35 | ~15:12–15:13Z | `p3_abc.txt`, `p3_abc.json` |
| P4 | Refresh-token revoke cascade | PASS | 12/12 | 15:13:57–15:14:01Z | `p4_revoke_cascade.md` |
| P5 | Browser-style cookie+CSRF prepare → preview → share → discover → consent, plus negative | PASS | 7/7 | 15:14:03–15:14:10Z | `p5_browser_prepare.md` |
| P6 | OAuth smoke re-run after all of the above | PASS | 27/27 | ~15:14:3xZ | `p6_smoke.txt` |

## Key observations

- **P0:** the new deployment was already live at the first poll (health `200`, `HEAD /` → `200`, versus `501` on the old deployment). No waiting was needed.
- **P1:** `HEAD` returns the same status, `Content-Type` and `Content-Length` as `GET` for `/` (text/html, 12875), `/api/product/health` (application/json, 202) and `/webmcp.mjs` (text/javascript, 12522). `HEAD /mcp` → `405` with `Allow: POST, DELETE`.
- **P4 (new cascade):** after `POST /oauth/revoke` with the refresh token (`200`), the refresh grant returns `400 invalid_grant`, and the still-unexpired **access token is rejected with `401`** on `tools/list` (WWW-Authenticate present) and on a fresh `initialize`. On the previous deployment this returned `200`. Token exchange honoured `scope=resonance offline_access` verbatim and issued a refresh token.
- **P5:** `prepare` with a real structured thought → `input_kind=agent_structured`, `discoverable=false`, `source_retention=not_retained`. Preview showed all five node labels and the presentation topic/domain. After share, live discover returned a `result_id` with **12 matches**; top match structural score **0.8829**. Consent `shared=false` → `revoked=true, discoverable=false`. Negative prepare (role `vibe`, no ids) → `400 validation_failed`. (Note: in the discover rows the topic sits under `display`, so the `top_topic` column in the P5 table is blank; the score was read from `scores`.)
- **P6:** OAuth smoke still 27/27 after the revoke/share/revoke traffic.

## Deviations

None. Every phase matched its expected status/count. No secrets appear in any evidence file (each script asserts that tokens, codes, verifiers, cookie values and confirmation tokens are absent from its output; the only random value shown in the smoke logs is the OAuth `state` nonce, which is not a credential).
