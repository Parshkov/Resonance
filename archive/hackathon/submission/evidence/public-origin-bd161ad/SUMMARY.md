# Release evidence — public origin, second pass (HEAD bd161ad)

| Field | Value |
|---|---|
| Repo HEAD verified | `bd161ad12d196cf095c4fc71d1f625ad4b86fba5` (main) |
| Railway deployment | `f48d930e-1190-4ba8-bc84-50108ac9da0c` |
| Origin | https://resonance-production-cfe3.up.railway.app |
| MCP | https://resonance-production-cfe3.up.railway.app/mcp |
| Started (UTC) | 2026-09-04 06:33:40 |
| Finished (UTC) | 2026-09-04 06:39 (browser run completed 06:36) |
| Hard stop | 07:20 UTC (not reached) |
| Worker | Claude Code verification worker, branch `claude/release-evidence-pulse-2` |

No product code was modified. No GitHub comments were posted. No tokens, codes, or raw chat text are committed (see redaction notes).

## Per-phase results

| Phase | Check | Result | Count | File |
|---|---|---|---|---|
| P1 | `GET /api/product/health` | PASS | HTTP 200, `ok:true`, `mode:live`, db_generation 106 == serving_generation 106, `index_current:true` | `health.txt` |
| P2 | `ops/oauth_smoke.py --auto-consent -v` | PASS | 27/27 | `smoke.txt` |
| P3 | `submission/evidence/abc_mcp_test.py` | PASS | 35/35, no FAIL lines | `abc_public.txt`, `abc_public.json` |
| P4 | Never-shared guest → `/api/webmcp/discover?source=replay` and `?source=live` | PASS | 409 `share_required` on both (previously 500) | `webmcp_discover_409.md` |
| P5 | `browser_harness.py` (copy) against the origin in headless Chromium 141.0.7390.37 | PASS (expected shape) | 17/18; the single FAIL is the honest "NATIVE document.modelContext present" probe | `browser/`, `browser_run1.txt`, `browser_run2.txt`, `browser_harness_copy.py` |
| P6 | This summary | — | — | `SUMMARY.md` |

## P2 notes

The smoke ran unmodified on this deployment. Step 1 (401 challenge / `WWW-Authenticate` lookup) passed directly, so the lowercase-normalising wrapper used in the previous pass was not needed. The authorization code in the redirect line is emitted as `<redacted>` by the script itself.

## P5 notes (browser)

- **Connectivity.** Run 1 (no proxy args) failed at `page.goto` with `net::ERR_CONNECTION_RESET`, same as the previous pass. Run 2 succeeded with the container HTTPS proxy passed as the Playwright `proxy.server` and `--ssl-version-max=tls1.2` added to Chromium args. Those are the only launch changes; they were applied through environment variables in `browser_harness_copy.py`, a copy of the harness committed here. The product harness file was not edited. No proxy address or credential appears in `browser_run2.txt`.
- **Harness copy diff vs `submission/evidence/browser_harness.py`.** Two additions: (1) optional `CHROME_EXTRA_ARGS` / `CHROME_PROXY` env vars for the launch; (2) captures `#header-consent` on the plain-Chromium (no shim) first load as `native_header_consent` and prints it as an `[INFO]` line. Nothing else changed.
- **LIVE discover after share.** `resonance_discover {source: live}` returned `source=live`, `result_id=result-d0375551e41bce2cbe8f7119`, and **13** entries in `matches_in_backend_order` (previous pass on the old deployment: 0). After clicking Live MCP, **4** match cards were visible (`cards=4`), screenshot `browser/browser_04_after_discover.png`. The sidebar in that screenshot reads "BACKEND ORDER PRESERVED · 04 shown" and a footer row "12 other backend results" (4 + 12 = 16 does not equal the 13 reported by the tool result; recorded as observed, not investigated).
- **Header consent pill on first load in PLAIN Chromium (no shim).** `#header-consent` = **`Shared with Resonance`** and `#webmcp-status` = **`WebMCP · unavailable`** on a never-shared guest. This is unchanged from the previous pass. With the shim installed, the same first load shows `Private · not discoverable` and `WebMCP · private`, and after the explicit share it flips to `Shared with Resonance` / `WebMCP · LIVE shared`. So the misleading "Shared with Resonance" pill on a never-shared guest is specific to the WebMCP-unavailable path and is still present on bd161ad.
- **Other observations.** Console on both loads: `Error with Permissions-Policy header: Unrecognized feature: 'tools'.` (warning). Four `409` resource-load console errors in the shim run are the expected fail-closed discover calls. Post-revoke `resonance_get_match` on the old result_id returns `stale_result` 409 rather than share_required; the harness accepts either.

## Deviations from the expected shape

1. P5 native header consent pill still reads `Shared with Resonance` on a never-shared guest when WebMCP is unavailable (carried over from the previous pass; not fixed by bd161ad).
2. P5 visible-vs-reported count mismatch in the screenshot text (13 reported by tool, sidebar says 4 shown + 12 other).
3. P5 required proxy + TLS 1.2 launch args from inside this container; this is a container egress constraint, not an origin fault (curl and the Python harnesses reached the origin directly).

Nothing else deviated. All five verification phases passed.

## Redaction notes

- `webmcp_discover_409.md`: guest `csrf_token` and `recovery_secret` values replaced with `<redacted>`.
- `browser_run2.txt`: contains no proxy address or credentials (checked).
- `smoke.txt`: authorization code already redacted by the script; no bearer/refresh token values are printed.
- `abc_public.json` / `abc_public.txt`: no token values present (the only "access_token" / "bearer" mentions are check names).
- `browser/browser_harness.json`: no confirmation_token / access token values present.
