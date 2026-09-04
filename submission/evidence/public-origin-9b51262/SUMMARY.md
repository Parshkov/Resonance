# Release evidence — public origin, pulse 5 (HEAD 9b51262)

| Field | Value |
|---|---|
| Repo HEAD verified | `9b51262ca595122a6df78ecb92443e5438a182fe` (main; `git rev-parse HEAD` matched, no checkout needed) |
| Railway deployment | `6ec0959e-6de5-43ae-9ad8-23742bb62d26` (service `172aa183-…`, commitHash `9b51262…`, status SUCCESS, created 16:10:08Z, SUCCESS at 16:10:29Z; previous deployment `86aebe9b…` for 3c7dc80 REMOVED at 16:10:41Z) |
| Origin | https://resonance-production-cfe3.up.railway.app |
| MCP | https://resonance-production-cfe3.up.railway.app/mcp |
| Started (UTC) | 2026-09-04 16:10:34 |
| Finished (UTC) | 2026-09-04 16:16 |
| Hard stop | 16:35:34 UTC (not reached) |
| Worker | Claude Code verification worker, branch `claude/release-evidence-pulse-5` |

No product code was modified. No GitHub comments were posted. No tokens, codes, cookies, confirmation tokens, or raw chat text are committed (see redaction notes).

## Per-phase results

| Phase | Check | Result | Count | File |
|---|---|---|---|---|
| P0 | Wait for new code: poll `GET /api/product/health` from ≥120 s after start, require 60 s continuous HTTP 200 | PASS | window opened 16:12:34Z, streak start 16:12:34Z, READY 16:13:35Z, zero non-200 during the window; final payload `ok:true`, `mode:live`, db_generation 252 == serving_generation 252, `index_current:true` | `p0_ready.txt` |
| P1 | `ops/oauth_smoke.py … --auto-consent -v` | PASS | 27/27 (0 FAIL lines) | `p1_smoke.txt` |
| P2 | `submission/evidence/abc_mcp_test.py … --out p2_abc.json` | PASS | 35/35 (0 FAIL lines) | `p2_abc.txt`, `p2_abc.json` |
| P3 | Re-prepare regression (fix under test): same raw `context` re-prepared by the same guest after share + stop_sharing, by a second guest, and via the browser cookie+CSRF path | PASS | 12/12 | `p3_reprepare.md`, `p3_reprepare_script.py` |
| P4 | This summary | — | — | `SUMMARY.md` |

## P3 notes (the fix under test)

- G1 prepare #1 from the exact three-sentence retry-storm text: `raw_text_fallback`, structure nodes=7 relations=4, private draft with confirmation token; share (confirm=true) → discoverable; stop_sharing (confirm=true) → revoked.
- G1 prepare #2 with the SAME exact text: **success**, new draft_id (previously this returned 409 "thought_id is already reserved").
- G2 (second OAuth guest) prepare with the SAME exact text: **success**, new draft_id.
- Browser path: `POST /api/product/guest` → cookie + csrf; `POST /api/webmcp/prepare` with the SAME exact `context` → **200**, private draft (`discoverable:false`). `POST /api/webmcp/consent shared=false` was not needed (never shared on this path) and was not called.
- All four draft_ids are pairwise distinct (equality table in `p3_reprepare.md`).
- Timing: the deployment for 9b51262 was live (SUCCESS 16:10:29Z, old deployment removed 16:10:41Z) before the P0 window opened at 16:12:34Z, so every P1–P3 request hit the new code.

## Deviations from the expected shape

None. P0 saw no non-200 during the readiness window, P1 27/27, P2 35/35, P3 12/12 with every expected-success step returning `ok`.

## Redaction notes

- `p0_ready.txt`: health JSON only (no secrets).
- `p1_smoke.txt`: authorization code emitted as `<redacted>` by the script; no bearer/refresh token values (grep for `access_token`/`refresh_token`/`Bearer <value>` finds only check names and the `WWW-Authenticate` realm line).
- `p2_abc.txt` / `p2_abc.json`: no token values (grep for `access_token`/`refresh_token`/`confirmation_token`/`csrf_token` values finds none).
- `p3_reprepare.md`: script asserts that no access token, confirmation token, cookie, csrf_token or recovery_secret string appears in the output; only pseudonymous person ids, session ids, draft ids and counts are recorded.
