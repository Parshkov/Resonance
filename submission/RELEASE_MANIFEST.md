# Resonance — release manifest

> **Engine 0.2 freeze taken (2026-09-04).** The engine 0.2 re-freeze that the
> previous banner demanded is done: the public-origin evidence was re-run on the
> engine 0.2 deployment, `purge-demo` ran on production (it found nothing to
> delete — the database never held seeded personas), and **§0 Current
> production** below is re-pinned to the new SHA, deployment id and suite count.
> Sections 1–5 describe **engine 0.1** (`resonance-engine/0.1`, verifier hash
> `3e107bc4…`) and are kept unchanged as the historical competition record; they
> are not the current release. Read §0 first.

> **Status update (2026-09-04, post-competition):** the sponsor confirmed the
> competition entry was not registered, so the judging freeze below is
> historical. Production has moved on; see **§0 Current production** first.
> Sections 1–5 are the frozen competition record as of 07:37 UTC and are kept
> unchanged for provenance.

## 0. Current production (working-product track)

| field | value |
| --- | --- |
| `main` / production SHA | **`0aea577fb0dbf2bc741f68e176be95c551d2b494`** — the last commit that changes runtime behaviour (PR #163, on top of #162 `9a79eb8` and #161 `b86016a`, themselves on `3267ea5` / `c66951b` / `443ba1c` = engine 0.2). Commits merged after it in this freeze (#164 evidence, this manifest update) are **documentation and evidence only** and do not alter the deployed engine. |
| Railway deployment | **`834818b1-d512-4e13-8bcf-638402e8b605`** — SUCCESS 20:53:20 UTC, `commitHash 0aea577f…`, branch `main`, auto-deploy; startup log `oauth: core attached; issuer https://resonance-production-cfe3.up.railway.app; resource …/mcp; grants durable` then `competition product on http://0.0.0.0:8080 (…; mode: LIVE+WebMCP)`; **no** `purge-demo` line. Earlier this day: `8971524a` (`9a79eb8`), `5b64991d` (`b86016a`), `140130fa` (`3267ea5`), `357dd391`/`275c646c`/`c3da2cae` (`c66951b`, the purge sequence). |
| Railway project / service / env | `resonance-live` (`670bcce5-0908-4eeb-81a6-decbdaba7e4c`) / `resonance` (`172aa183-cb11-47f5-a38a-a33482f93cf8`) / `production` (`da338ecd-9e65-477a-917e-59ff96dd7253`) |
| engine identity (from `GET /api/product/health`) | `resonance-engine/0.2`, `resonance-score/0.2`, `scoring-v0.2-concept-aligned-analogy/0.2`, `resonance-index/0.2.0`, `resonance-fingerprint/0.2.0-multi+concept`, `resonance-semantics/0.2.0+resonance-lexicon/0.2.6`, extractor `0.2.0`, `verifier_config_hash 12998d451e632759b828ccfb5d781587041bce7f740027b98fe528ecd966bd77` |
| demo personas | **none.** `corpus.demo_personas_present: false`, `demo_sessions: 0`, `sessions_by_kind {"volunteer": 62}`. `RESONANCE_PURGE_DEMO=1` was run once on `c66951b` and logged `sessions_deleted=0 users_revoked=0` — the production database never held seeded personas; the variable is empty again and `RESONANCE_SEED_DEMO` has never been set on production. |
| DB migrations | `0001_init`, `0002_recovery_generation`, `0003_collaboration`, `0004_workspaces`, `0005_oauth_grants` (`ops/migrations/`) |
| since the engine 0.1 record | engine 0.2 end to end (ADR-0004: deterministic lexicon semantics, concept retrieval channel, `label_identity` contradictions, classification v0.2, three-level confidence, over-fetch + verified ranking); extractor v0.2; Benchmark v0.2 and extraction-v0.2 gates; the second remote MCP server removed; persistent databases no longer seeded with demo personas; `engine.*` and `corpus.*` exposed in health; acceptance runs revoke their own guest shares (#161); a consumed candidate relation can no longer also be counted as contradicting (#162); `resonance_prepare_thought` accepts `topic`/`domain` on the `context` path (#163) |
| suites | **463 OK, 1 skipped** on `0aea577` (the skip needs a local PostgreSQL); 461 OK on `3267ea5` before this run's two new test classes |
| repository gates | `python3 benchmark/r0-v0.2/runner.py` → `overall_status: pass`, exit 0; `python3 benchmark/extraction-v0.2/runner.py` → `overall_status: pass`, exit 0. r0-v0.2 gate values: classification accuracy 1.0, polarity rejection 1.0, negative FPR 0.0, positive node F1 0.8469, Recall@5 1.0, Recall@20 1.0. **Gold was not edited and is still awaiting human review (ADR-0004).** |
| public-origin evidence | **`submission/evidence/public-origin-0aea577/`** — the first full acceptance set run *directly* against the public origin (health, `hosted_onboarding_probe` 9/9 required, `oauth_smoke` 27/27, `abc_mcp_test` 36/36, Card A in a real Chromium 16/18 with screenshots, Card B through the real Claude custom connector). Earlier: `public-origin-c66951b/` (purge + hosted-connector discover on engine 0.2), `public-origin-01193f1/`, `public-origin-3c7dc80/`, `public-origin-9b51262/` (all engine 0.1). |
| Card A (browser WebMCP) | executed on `0aea577` against the live origin in Chromium 141: 16/18. Native `document.modelContext` is **absent** in stock Chromium and remains **unclaimed**; the `cards=0` check is correct fail-closed behaviour (`primary_matches()` drops every `negative` match and every live match currently is `negative`) around two open R9 presentation defects. A human run in a WebMCP-enabled Chrome is still outstanding. |
| Card B (hosted Claude client) | executed on `0aea577` by an agent through the real Claude custom connector: `whoami` → `prepare_thought` → preview → `share_thought(confirm: true)` → `discover` → `explain_match` → `stop_sharing` (`revoked: true`), guest session revoked afterwards. **A human still has to run it once end to end.** |
| still untested / must not claim | native `document.modelContext` in a WebMCP-enabled Chrome (Card A step 1–2); ChatGPT developer-mode app (Card C); two real people in one recorded run (Card D); corpus scale replay 10^4–10^5; human review of the Benchmark v0.2 and extraction-v0.2 gold |
| known open items | ten pre-existing duplicate guest sessions in the live corpus (ids in the evidence summary) need an owner-side deletion; ADR-0005 (`approximate` vs `analogical` for same-vocabulary cross-domain pairs) is **open** and needs human-authored gold; the R9 page shows a match count with an empty primary rail and a stale evidence panel when every live match is `negative` |
| post-freeze deploy check | the freeze commit itself (`960fb47`, PR #165, documentation only) auto-deployed as **`184aad76-206e-41ab-be27-3f58251a72fb`**, SUCCESS 21:11:47 UTC, with the same startup log (`oauth: core attached; … grants durable`, `mode: LIVE+WebMCP`) and **no** `purge-demo` line. `GET /api/product/health` afterwards is byte-identical on every `engine.*` field and still reports `demo_personas_present: false`; `ops/oauth_smoke.py` re-run against the origin: **27/27**. The runtime is unchanged from `0aea577`, as intended. |
| secrets | `RESONANCE_DB`, `RESONANCE_CONFIRMATION_SECRET`, `PUBLIC_ORIGIN`, `PORT` supplied by Railway variables only; none in the repo. `RESONANCE_DB` and `RESONANCE_CONFIRMATION_SECRET` were not read or modified during this freeze. |

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
