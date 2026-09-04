# Resonance — release manifest

> **Status update (2026-09-04, post-competition):** the sponsor confirmed the
> competition entry was not registered, so the judging freeze below is
> historical. Production has moved on; see **§0 Current production** first.
> Sections 1–5 are the frozen competition record as of 07:37 UTC and are kept
> unchanged for provenance.

## 0. Current production (working-product track)

| field | value |
| --- | --- |
| `main` / production SHA | `9b51262ca595122a6df78ecb92443e5438a182fe` (PR #152; earlier #149 `3c7dc80`, #147 `01193f1`, #139 `f3ace6c`) |
| Railway deployment | `6ec0959e-6de5-43ae-9ad8-23742bb62d26` — SUCCESS 16:10:29 UTC; startup log `oauth: core attached; … grants durable` then `competition product … mode: LIVE+WebMCP` (earlier `86aebe9b`, `28ff8d4a`) |
| DB migrations | `0001_init` … `0004_workspaces`, **`0005_oauth_grants`** (durable OAuth codes / refresh grants / client registrations) |
| since the frozen record | durable OAuth grants (no re-authorization after redeploy); RFC 7009 refresh→access revoke cascade; HEAD support; browser `resonance_prepare_thought` accepts the agent's real `thought`/`context`; empty raw-text drafts refused with guidance; live view shows the person's own thought and renders direct/approximate resonances; styled OAuth consent page naming the client; R15D hosted-client probe tooling merged; raw-text Thought DNA ids namespaced per person/attempt (same sentences can be prepared again / by another person) |
| suites | 440 OK on `01193f1`; 443 OK on `3c7dc80`; 446 OK on `9b51262` (2 skipped each) |
| public-origin evidence | `submission/evidence/public-origin-01193f1/` (deployment `28ff8d4a`: HEAD 4/4, OAuth 27/27, A/B/C 35/35, revoke cascade 12/12, browser-path prepare 7/7, re-smoke 27/27); `public-origin-3c7dc80/` (deployment `86aebe9b`: HEAD + consent.css OK, OAuth smoke 27/27, hosted probe 9/9 required + 6/6 optional, A/B/C 35/35, remote-MCP empty-draft refusal 7/7, browser path 11/11 incl. `/api/context?source=live` = own thought and implicit-prose 400 + no draft left, Playwright: own thought rendered on Live MCP with 3 resonance cards for 15 backend rows, consent page named + styled); `public-origin-9b51262/` (deployment `6ec0959e`: OAuth 27/27, A/B/C 35/35, re-prepare regression 12/12) |
| hosted Claude client on production (Card B) | **executed 2026-09-04 ≈16:35 UTC** from the owner's claude.ai custom connector `Resonance` (OAuth, no manual key) inside a Claude Code cloud session: `whoami` → `person-b1bd2e2c90bc3c51`; `my_thoughts` → one discoverable thought (shared 15:12 UTC on the same account); `discover` → `result-19790231e038d12d3964071b`, 8 live rows with structural evidence, 1 hard-rejected; `explain_match` OK. Steps 5–6 not repeated and step 8 not executed (both change the owner's live share state and need their in-chat approval). Evidence: `submission/evidence/hosted-client-claude/card_b_claude_connector_2026-09-04.md` |
| still untested / must not claim | native `document.modelContext` in a WebMCP-enabled Chrome (Card A); ChatGPT developer-mode app (Card C); an approved share + stop_sharing issued from inside a claude.ai chat in one recorded run |
| ops gaps needing the repository/Railway owner | push auto-deploy is off and **cannot be enabled**: Railway reports `NO_INSTALLATION` — the Railway GitHub App is not installed on `Parshkov/Resonance` (merge `981d1be` of #154 at 16:17 UTC produced no deployment; every deployment has `meta.reason: deploy`, i.e. manual). Postgres volume `postgres-data` backup schedule is not exposed by the API and has **not been confirmed** — enable it in the dashboard (`ops/DEPLOY.md`, Option A notes). |

# WebMCP Challenge release manifest (frozen competition record)

> Filled only from executed evidence. Fields marked `PENDING` are filled at
> freeze by the R17 acceptance owner; nothing here is inferred.

## 1. Exact release identity

| field | value |
| --- | --- |
| public product URL | `https://resonance-production-cfe3.up.railway.app` |
| canonical remote MCP URL | `https://resonance-production-cfe3.up.railway.app/mcp` |
| release `main` SHA | **`91facc350ff11a66801190708c00d146478d12c8`** (PR #144 merge: consent-pill honesty fix on top of `bd161ad` = PR #142 blocker fix; includes #130 docs squash `13896b5` and R15A/R15C `4ab28a3`) |
| previous production candidate | `4ab28a30f986478562a88e1e1e6a83c81ef7bda9` = Railway deployment `b3bd196b-64a4-46e3-8ceb-db0352ec9ae4` (SUCCESS 06:00:36 UTC) |
| Railway project / service / env | `resonance-live` (`670bcce5-0908-4eeb-81a6-decbdaba7e4c`) / `resonance` (`172aa183-cb11-47f5-a38a-a33482f93cf8`) / `production` (`da338ecd-9e65-477a-917e-59ff96dd7253`) |
| release Railway deployment id | **`55ebb2c0-fbe9-44c8-9256-e75a941dcb44`** — SUCCESS 07:35:16 UTC, `commitHash 91facc35…`; previous candidate `f48d930e` (`bd161ad`, SUCCESS 06:32:02 UTC) retired; healthcheck passed before routing; startup log `oauth: core attached; issuer https://resonance-production-cfe3.up.railway.app; resource …/mcp` then `competition product on http://0.0.0.0:8080 (origins: ['https://resonance-production-cfe3.up.railway.app']; db: postgresql://postgres@postgres.railway.internal:5432/railway; mode: LIVE+WebMCP)`; previous deployment `b3bd196b` retired (REMOVED) |
| entrypoint | `python3 -m src.product.competition_server --host 0.0.0.0 --port $PORT --db $RESONANCE_DB --origin $PUBLIC_ORIGIN` (Dockerfile, `python:3.12-slim`, only dependency `psycopg[binary]==3.3.5`) |
| runtime | one origin, one process, one PostgreSQL (`pgvector/pgvector:pg16`, private host `postgres.railway.internal`); startup log `oauth: core attached; issuer https://resonance-production-cfe3.up.railway.app; resource …/mcp` then `competition product … mode: LIVE+WebMCP` (DSN redacted) |
| secrets | `RESONANCE_CONFIRMATION_SECRET`, `RESONANCE_DB`, `PUBLIC_ORIGIN`, `PORT` supplied by Railway variables only; none in the repo |
| health | `GET /api/product/health` → `{"ok": true, "mode": "live", "freshness": {"index_current": true, …}}` (public origin, 06:14 UTC) |

## 2. Schema / contracts

| contract | version / hash |
| --- | --- |
| DB schema | `resonance-persistence/0.2` models; migrations `0001_init`, `0002_recovery_generation`, `0003_collaboration`, `0004_workspaces` (16 tables incl. `schema_migrations`, `idempotency_keys`, `audit_events`) |
| Thought DNA | `thought-dna/0.1` (`schemas/thought-dna-0.1.schema.json`) |
| browser WebMCP | `resonance-webmcp/0.1`; six R10 tools `resonance_prepare_thought`, `resonance_get_share_preview`, `resonance_share_prepared_thought`, `resonance_discover`, `resonance_get_match`, `resonance_update_consent` (+ collaboration/workspace tools) registered via `document.modelContext.registerTool`; `demo/ui/webmcp_live.mjs` sha256 `e0aa5fa1908fb4514e1bff2c38b01a16d42e5e94cad821215dd2205fa34ad7c3` |
| remote MCP | `resonance-remote-mcp/0.1` bridge on `/mcp` (Streamable HTTP JSON-RPC, stateless, 12 tools: `resonance_whoami`, `resonance_prepare_thought`, `resonance_share_thought`, `resonance_my_thoughts`, `resonance_discover`, `resonance_explain_match`, `resonance_request_intro`, `resonance_list_intros`, `resonance_respond_intro`, `resonance_send_message`, `resonance_read_messages`, `resonance_stop_sharing`) |
| OAuth | OAuth 2.1 core R15A `c7d78a0` (`src/remote/oauth.py`) mounted by R15C (#141): RFC 9728 `/.well-known/oauth-protected-resource`, RFC 8414 `/.well-known/oauth-authorization-server`, RFC 7591 `/oauth/register`, `GET/POST /oauth/authorize` (consent page), `/oauth/token` (authorization_code + PKCE S256, refresh rotation, `offline_access`), RFC 7009 `/oauth/revoke`; bearer on `/mcp` = R12 access token (audience `{issuer}/mcp`) |
| seed corpus | `demo/corpus/sessions.jsonl` sha256 `eba6f76e23a702f891d356754cd9bf96df727bf6c61581cd8c8431c3d4dff925` (R7, create-only) |
| license | Apache-2.0 top-level `LICENSE` |

## 3. Executed evidence (privacy-safe; no tokens, no raw chat text)

| check | where | result |
| --- | --- | --- |
| full repository suite on `4ab28a3` | this sandbox, Python 3.11.15 | **433 tests OK, 2 skipped** (537 s) |
| full suite on `bd161ad` | this sandbox | **434 tests OK, 2 skipped** (542 s) |
| full suite on `91facc3` content | this sandbox | **435 tests OK, 2 skipped** (543 s) |
| public origin raw HTTP (health, 401 challenge, RFC 9728/8414 metadata, 405 GET, 400 bare authorize) | sibling session with egress, `submission/evidence/public-origin/phase1_http.md` | PASS (06:14 UTC) |
| public origin OAuth onboarding smoke `ops/oauth_smoke.py … --auto-consent` | sibling session, `submission/evidence/public-origin/phase2_oauth_smoke.txt` | **27/27** (06:15 UTC) |
| public origin A/B/C three-identity structural test over `/mcp` (deployment `b3bd196b`) | sibling session, `submission/evidence/public-origin/phase3_*` | **41/41** (06:20–06:21 UTC): B → A `analogical`, structural 0.8875, semantic 0.097, 7 mapped nodes, 5 preserved relations, `result-21330ad10b4fd06cf06984be` live; C absent; subject isolation, idempotent intro, accept/message/read, channel isolation, revoke → immediate disappearance + `stale_result` |
| public origin OAuth/MCP negatives | `submission/evidence/public-origin/phase4_negatives.md` | 18/20: all token/PKCE/redirect/resource/refresh/revoke/query-token/bogus-bearer negatives hold; two expectations did not (refresh-token revoke does not cascade to the sibling access token — RFC 7009 SHOULD; stateless bridge ignores `Mcp-Session-Id` — spec-permitted) |
| public origin browser run (Playwright Chromium 141, deployment `b3bd196b`) | `submission/evidence/public-origin/phase5_browser.md` | native `document.modelContext` absent (honest); shim-registered page tools: prepare → preview → share (pill → `Shared with Resonance`, `WebMCP · LIVE shared`) → LIVE discover `result-e2b27a3688f3da003de857a0`, **11 matches** → revoke; `discover(replay)` before share was the 500 fixed by #142 |
| public origin re-verification on deployment `f48d930e` (`bd161ad`, identical product code except the consent-pill JS fix) | `submission/evidence/public-origin-bd161ad/` | health ok (db_generation 106 = serving 106, index_current); OAuth smoke **27/27** unmodified; A/B/C **35/35**; fresh guest `/api/webmcp/discover` replay+live → **409 share_required** (blocker fix confirmed on production); browser harness 17/18 with LIVE discover `result-d0375551e41bce2cbe8f7119`, **13 matches**, **4 cards visible** after clicking Live MCP; the pre-fix pill issue reproduced there and is what `91facc3` fixes |
| public origin on the final deployment `55ebb2c0` (`91facc3`) | Railway deploy log + this manifest | deployment SUCCESS with healthcheck; the only code delta vs `bd161ad` is the consent-pill fix verified locally in headless Chromium (plain load `Private · not discoverable`); no second egress pass was run before the deadline — **UNTESTED on the public origin beyond health/deploy** |
| same A/B/C on the identical tree, local PostgreSQL 16 through `competition_server` | `submission/evidence/local-postgres/abc_local_postgres.json` | **35/35**: A "retry storm" ↔ B "panic buying" `analogical`, structural 0.8875, semantic 0.089, 6/6 relations preserved; C (shared vocabulary, no loop) absent; result_id subject-bound; intro idempotent → accept → message → read; C excluded from channel; stop_sharing → immediate disappearance, old result_id fails closed; stateless session + reconnect; query-string token 401; RFC 7009 revoke → 401 |
| local OAuth smoke through `competition_server` on PostgreSQL | this sandbox | 27/27 |
| browser page + tool registration + prepare/preview/share/discover/get_match/revoke with visible UI state | `submission/evidence/local-postgres/browser_harness.json` + screenshots | 17/18 — the one FAIL is the honest probe "native `document.modelContext` present" (absent in Chromium 141); tools were registered through the page's own `registerTool` call via a labelled shim |
| native `document.modelContext` discovery/invocation on the public origin in a WebMCP-enabled Chrome | sponsor Card A (`submission/HUMAN_TEST_CARDS.md`) | **UNTESTED / MUST NOT CLAIM** — sponsor Card A not executed before freeze |
| real hosted MCP client (Claude custom connector / ChatGPT developer-mode app) | sponsor Cards B/C | **UNTESTED / MUST NOT CLAIM** — Railway edge logs show an external OAuth client completing the full flow on the public origin (06:03–06:08 and 06:20–06:21 UTC), but no ChatGPT/Claude product session has been recorded |
| release blocker found + fixed during acceptance | PR #142 | `GET /api/webmcp/discover` for an unshared visitor → 500; now 409 `share_required` with regression test |

## 4. Known limitations (non-blocking, stated honestly)

- OAuth codes / refresh grants / client registrations are in process memory on the single replica: a redeploy makes hosted clients re-authorize once (R12 access tokens are durable).
- Native WebMCP requires a browser exposing `document.modelContext`; stock Chrome/Chromium 141 shows `WebMCP · unavailable` by design.
- The browser `resonance_prepare_thought` builds from the labelled page thought; real-conversation ingestion is the remote MCP path (`context=` / structured `thought`).
- The raw-text cue extractor is the honest floor for `context=` input; structured graphs from the chat's model give the strongest matches.
- Railway push auto-deploy does not fire; deployments are triggered through the Railway plugin and recorded here.
- R15B (#135) independent review of the OAuth core: see the issue for its final verdict; production carries the exact reviewed head.

## 5. Freeze

- [x] release SHA / deployment id above filled from the actual deploy (`91facc3` / `55ebb2c0`)
- [ ] `SUBMITTED / FROZEN FOR JUDGING` posted on #75 with this manifest
- [ ] no post-submission changes to `main`, the live origin, or the Devpost entry unless organizers authorize a correction
