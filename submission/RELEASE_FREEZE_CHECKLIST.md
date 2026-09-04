# R17 WebMCP Release / Submission Freeze Checklist

> **Engine 0.2 freeze, 2026-09-04.** The reset this file demanded after PR #158
> has been executed on the engine 0.2 deployment. Release identity is pinned in
> §1 below and in `submission/RELEASE_MANIFEST.md` §0; executed evidence is
> `submission/evidence/public-origin-0aea577/`.
>
> The three engine 0.2 gates are met: `python3 benchmark/r0-v0.2/runner.py` and
> `python3 benchmark/extraction-v0.2/runner.py` both exit 0 on the frozen SHA;
> production carries **no** demo personas (`purge-demo` ran and found nothing —
> the database never held any — and `RESONANCE_SEED_DEMO` has never been set on
> production); remote MCP identity is the product server only.
>
> **Sections 2, 9, 10 and 12 are historical.** The sponsor confirmed the
> competition entry was never registered, so the Devpost/video/judging gates
> describe a submission that does not exist. They are kept unticked and
> unchanged rather than being marked complete.
>
> Boxes below are ticked **only** where this run executed the check on the
> frozen SHA. Anything a human still has to do is left unticked on purpose;
> the outstanding list is at the end of this file.

> This is a **release gate**, not evidence that a checkbox has passed. Fill it only from the exact frozen release candidate.

## 1. Exact release identity

- [x] release commit: **`0aea577fb0dbf2bc741f68e176be95c551d2b494`** — the last commit that changes runtime behaviour, deployed as Railway deployment **`834818b1-d512-4e13-8bcf-638402e8b605`** (SUCCESS 20:53:20 UTC, branch `main`, auto-deploy). Commits merged after it in this freeze are documentation/evidence only.
- [ ] release tag: `TBD` — proposed `v0.2.0-engine` (tagging is an owner action; the competition-era `v0.1.0-webmcp` name no longer describes this release)
- [x] live URL: `https://resonance-production-cfe3.up.railway.app` (Railway, project `resonance-live`, PostgreSQL 16 + pgvector image; entrypoint `src.product.competition_server`; see `ops/DEPLOY.md`)
- [x] database schema/migration version: `resonance-persistence/0.4` — migrations `0001_init`, `0002_recovery_generation`, `0003_collaboration`, `0004_workspaces`, **`0005_oauth_grants`** (`ops/migrations/`, applied on production PostgreSQL at first boot; the frozen SHA boots against them and serves `/api/product/health` with `index_current: true`)
- [x] Thought DNA schema: `thought-dna/0.1` (`schemas/thought-dna-0.1.schema.json`)
- [x] contracts: discovery `resonance-discovery/0.1`; UI context `resonance-ui-context/0.1`; rich result `resonance-rich-result/0.1`; collaboration `resonance-collab/0.1`; workspaces `resonance-workspace/0.1`
- [x] WebMCP contract/tool manifest hash: contract `resonance-webmcp/0.1`, six tools (`resonance_prepare_thought`, `resonance_get_share_preview`, `resonance_share_prepared_thought`, `resonance_discover`, `resonance_get_match`, `resonance_update_consent`) served from `demo/ui/webmcp_live.mjs`; **`sha256sum demo/ui/webmcp_live.mjs` = `b8df6a5cdad2157856ef0ea8e97cd344268ecc0be9000008076ce8f8ac67bfaa`** on the frozen SHA. Verified live in Chromium: the page exposes exactly those six names in `window.__resonanceWebMCP` and registers 17 tools in total (the six plus collaboration/workspace tools)
- [x] remote MCP contract/version: **included** — `resonance-remote-mcp/0.1` bridge on `/mcp` (12 tools, `src/product/mcp_bridge.py`) + canonical OAuth 2.1 core (`src/remote/oauth.py`, R15A `c7d78a0`, mounted by R15C #141); exact SHA/deployment in `submission/RELEASE_MANIFEST.md`
- [x] seeded corpus/snapshot hashes recorded: `demo/corpus/sessions.jsonl` sha256 `eba6f76e23a702f891d356754cd9bf96df727bf6c61581cd8c8431c3d4dff925` (R7 seed, create-only import). **Production is NOT seeded**: `corpus.demo_personas_present: false`, `demo_sessions: 0`, `sessions_by_kind {"volunteer": 62}`
- [x] engine identity recorded: `resonance-engine/0.2`, `resonance-score/0.2`, `scoring-v0.2-concept-aligned-analogy/0.2`, `resonance-index/0.2.0`, `resonance-fingerprint/0.2.0-multi+concept`, `resonance-semantics/0.2.0+resonance-lexicon/0.2.6`, extractor `0.2.0`, `verifier_config_hash 12998d451e632759b828ccfb5d781587041bce7f740027b98fe528ecd966bd77` (read from `GET /api/product/health` on the frozen deployment)
- [x] build/deploy environment recorded without secrets: Dockerfile `python:3.12-slim`, single dependency `psycopg[binary]`, entrypoint `python3 -m src.product.competition_server --host 0.0.0.0 --port $PORT --db $RESONANCE_DB --origin $PUBLIC_ORIGIN`; `RESONANCE_DB`, `RESONANCE_CONFIRMATION_SECRET`, `PUBLIC_ORIGIN`, `PORT` come from Railway variables only (`ops/DEPLOY.md`). Neither secret was read or modified during this freeze

## 2. Competition eligibility

- [ ] public repository reachable logged-out
- [ ] Apache-2.0 top-level `LICENSE` detected by GitHub
- [ ] `HACKATHON.md` clearly separates pre-existing work from challenge-period work
- [ ] live public HTTPS application reachable free by judges
- [ ] judge/test path documented and usable without maintainer intervention
- [ ] actual browser WebMCP tools registered with `document.modelContext.registerTool(...)`
- [ ] independent native WebMCP browser invocation evidence exists
- [ ] at least one read tool and one state-changing tool visibly affect the live product correctly
- [ ] no classic/remote MCP behavior is mislabeled as WebMCP
- [ ] all third-party code/assets/data used by submission are license-compatible/authorized

## 3. Product completeness

- [ ] pseudonymous register/login/session restoration
- [ ] owned thought sessions
- [ ] private prepare -> preview -> explicit share
- [ ] durable DB is product source of truth
- [ ] accepted structural engine remains ranking authority
- [ ] live consent-filtered discovery
- [ ] 2–4 evidence-backed matches on canonical flow
- [ ] coarse consented geography/map; location not used for ranking
- [ ] structured match result available to agent surface
- [ ] visual/rich result available where supported
- [ ] intro request -> target accept/decline
- [ ] no private contact disclosure before mutual acceptance
- [ ] private messaging/inbox state
- [ ] persistent 2+ member idea workspace
- [ ] at least one note/task/message/artifact action
- [ ] authorized agent can perform approved workspace action
- [ ] removed/left member loses future private access
- [ ] workspace content is not automatically republished to discovery

## 4. Privacy and security release blockers

- [ ] private-by-default server-side authorization
- [ ] cross-user ID substitution tests fail safely
- [ ] CSRF/cross-origin write protections
- [ ] secure hosted auth/session configuration
- [ ] revoke/delete makes session immediately undiscoverable
- [ ] injected index-rebuild failure after revoke fails closed; stale index cannot serve old user
- [ ] restart/rebuild preserves revocation
- [ ] hidden/revoked users absent from aggregates/rich visuals
- [ ] coarse location only; small-bucket heatmap anti-inference active
- [ ] UGC escaped in browser and treated as untrusted for agents
- [ ] prompt-injection test cannot change tool/auth behavior
- [ ] request/graph size limits
- [ ] auth/discovery/invite/message rate or abuse limits
- [ ] block/report minimal pilot flow
- [ ] private artifact/media authorization tested if media ships
- [ ] representative logs contain no credentials/auth headers/private messages/raw private chats/unnecessary Thought DNA
- [ ] account/session export/delete behavior matches published policy
- [ ] backup/restore preserves consent and authorization
- [ ] independent security-focused exact-release review has no acceptance-critical blockers

## 5. Agent write consistency

- [ ] state-changing WebMCP requests use stable idempotency keys
- [ ] same key + same input returns original committed result
- [ ] same key + conflicting input fails
- [ ] cancelled/unknown-outcome write can reconcile authoritative state
- [ ] intro/message/workspace retries cannot create duplicates
- [ ] optimistic concurrency/version guard where blind overwrite could lose collaborative work
- [ ] all human UI/WebMCP/remote MCP writes use one authenticated product/service layer

## 6. Cross-transport parity

- [ ] manual UI and WebMCP share/discovery state are identical
- [ ] LIVE match detail uses the same authoritative discovery result/source
- [ ] remote MCP, if included, returns same authorized match IDs/order/scores/evidence
- [ ] remote MCP writes persist in same durable DB if advertised
- [ ] two remote users remain isolated
- [ ] rich MCP visual contains only fields authorized in structured result
- [ ] unsupported client capabilities documented honestly

## 7. Persistence / pilot operations

- [ ] PostgreSQL (or final hosted durable DB) migrations applied from clean environment
- [ ] restart-safe user/session/collaboration state
- [ ] deterministic index rebuild from DB
- [ ] >=100-user mixed private/shared pilot test
- [ ] concurrent prepare/share/discover smoke
- [ ] acceptable interactive latency measured/documented
- [ ] health/readiness endpoint works
- [ ] backup + restore + reset runbook works
- [ ] deployment secrets supplied only by environment/secret manager
- [ ] restrictive CORS/CSP/Permissions-Policy on hosted origin
- [ ] no dependency on developer laptop/private manual DB edits

## 8. Regression / reproducibility

- [x] full repository suite green on exact release commit — **463 OK, 1 skipped** on `0aea577` (the skip needs a local PostgreSQL)
- [x] WebMCP targeted tests green — included in the full run; Card A additionally exercised the six tools against the live origin
- [x] persistence/identity/security/collaboration targeted suites green — included in the full run
- [x] `git diff --check` clean on the frozen SHA
- [x] browser console clean on canonical judging path — only `Permissions-Policy: Unrecognized feature: 'tools'` (a Chromium 141 warning about the WebMCP header it does not yet know) and the expected `409` fail-closed responses before sharing
- [x] engine 0.2 gates green on the exact release commit — `benchmark/r0-v0.2` and `benchmark/extraction-v0.2` both `overall_status: pass`, exit 0, gold unedited
- [ ] 1920x1080 layout has no blocking clipping/overflow
- [ ] clean-checkout runbook independently reproduced
- [ ] deterministic replay remains labeled and reproducible
- [ ] known Benchmark v0.1 Recall@5/calibration limitations remain documented and unchanged

## 9. Video

- [ ] final runtime < 3:00 (target <= 2:50)
- [ ] real WebMCP invocation visible
- [ ] actual functioning product shown, not mock screens
- [ ] share/consent is visibly explicit
- [ ] structural match + evidence shown
- [ ] contradiction/negative behavior shown compactly
- [ ] intro/collaboration shown only if actually in frozen release
- [ ] no private data/secrets/exact unauthorized locations in frame
- [ ] English narration/translation
- [ ] no unlicensed music/media
- [ ] public YouTube URL works logged-out
- [ ] video behavior matches frozen release

## 10. Devpost truthfulness / judging criteria

- [ ] WebMCP Leverage evidenced by real browser tools + stateful interaction
- [ ] Execution evidenced by coherent hosted multi-user flow
- [ ] Potential Impact explains the real discovery/collaboration problem
- [ ] Creativity & Ambition explains cross-domain structural resonance without overstating current scale
- [ ] no claim of mind-reading or inferred private beliefs
- [ ] no claim of current global network/population if pilot is synthetic/small
- [ ] future capabilities explicitly labeled future
- [ ] remote MCP called an additional transport, not the competition WebMCP requirement

## 11. Independent judge-style acceptance

Reviewer starts with only the **public live URL + public repo instructions** and completes:

- [ ] register/login
- [ ] private prepare
- [ ] inspect preview
- [ ] explicit share
- [ ] browser agent discovers/calls WebMCP tool
- [ ] live discovery updates map/cards
- [ ] inspect match evidence
- [ ] revoke and verify fail-closed
- [ ] re-share safely if needed
- [ ] request intro
- [ ] second user accepts
- [ ] create/open collaboration workspace
- [ ] perform one shared work action
- [ ] verify privacy boundary from another unauthorized identity

Reviewer records exact release SHA and **GO FOR SUBMISSION** only if no acceptance-critical blockers remain.

## 12. Freeze

- [ ] Devpost entry actually submitted before deadline
- [ ] final live URL saved in issue #75
- [ ] final public YouTube URL saved in issue #75
- [ ] exact release commit/tag saved in issue #75
- [ ] final Devpost text snapshot saved in repo/issue
- [ ] `SUBMITTED / FROZEN FOR JUDGING` maintainer event posted
- [ ] submitted repo/site/entry left unchanged during judging unless organizers explicitly authorize correction
- [ ] post-deadline development, if any, occurs in a separate branch/fork/environment

## 13. Outstanding at this freeze (engine 0.2, 2026-09-04)

Nothing below is claimed as done. Each item names who has to do it.

**Human / owner actions**

- Run **Card B** end to end as a human in claude.ai (an agent executed steps 4–8 through the real custom connector; a person has not).
- Run **Card C** (ChatGPT developer-mode app) — never executed on any engine version.
- Run **Card A steps 1–2** in a **WebMCP-enabled Chrome**. Stock Chromium 141 exposes no `document.modelContext`, so native WebMCP discovery stays **unclaimed**.
- Delete the ten pre-existing duplicate guest sessions listed in `submission/evidence/public-origin-0aea577/SUMMARY.md`. They are real `volunteer` rows, so `purge-demo` cannot remove them, and this run deliberately did not delete sessions it had not created.
- Human review of the **Benchmark v0.2** and **extraction-v0.2** gold (ADR-0004, "Known Failure Modes"). Both gates pass, but the gold is agent-authored, so no external claim should rest on it yet.
- Decide **ADR-0005** (`approximate` vs `analogical` for same-vocabulary cross-domain pairs). It is deliberately open and needs human-authored gold; it must not be settled by moving a threshold.
- Create the release tag if one is wanted.

**Confirmed after the freeze commit merged**

- The freeze commit `960fb47` (documentation only) auto-deployed as Railway deployment
  `184aad76-206e-41ab-be27-3f58251a72fb`, SUCCESS 21:11:47 UTC, startup log
  `oauth: core attached; … grants durable` then `competition product … mode: LIVE+WebMCP`, no
  `purge-demo` line. `GET /api/product/health` is unchanged on every `engine.*` field and still
  reports `demo_personas_present: false`; `ops/oauth_smoke.py` re-run against the origin: 27/27.
  The deployed runtime is the same as `0aea577`.

**Engineering, not blocking this freeze**

- ~~R9 presentation: when every live match is `negative` the page shows a match count with an empty primary rail and keeps stale REPLAY evidence.~~ **Fixed and deployed** (#167, `b6b43c5`): the empty case is now its own state with honest counts and an explanation, and an error clears every surface a rendered result owns. Verified against the live origin with `submission/evidence/r9_empty_state_harness.py`: 16/16 — evidence in `submission/evidence/public-origin-b6b43c5/`.
  - Left open, small: `submission/evidence/browser_harness.py` still asserts `cards > 0` after a LIVE discover. That is now an imprecise expectation rather than a defect — the correct assertion is `cards > 0` **iff** the payload holds at least one discoverable non-`negative` match. Until the assertion is made precise (or the live corpus holds a resonance for the page's own thought), Card A reports 16/18 with that check red for a correct product state. Not changed here so that no acceptance assertion is relaxed inside a freeze.
- Corpus scale replay at 10^4–10^5 graphs.
- Card D (two real people, one recorded run).
