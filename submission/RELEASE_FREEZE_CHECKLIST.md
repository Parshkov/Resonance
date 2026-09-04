# R17 WebMCP Release / Submission Freeze Checklist

> **Reset for engine 0.2 (2026-09-04, PR #158):** the R17 freeze was taken on
> engine 0.1. Re-run this checklist from scratch on the engine 0.2 deployment.
> Additional gates for that freeze: `python3 benchmark/r0-v0.2/runner.py` and
> `python3 benchmark/extraction-v0.2/runner.py` exit 0; production demo
> personas purged (`purge-demo`) or `RESONANCE_SEED_DEMO=1` recorded as a
> deliberate choice; remote MCP identity is the product server only
> (`src/remote/README.md`).

> This is a **release gate**, not evidence that a checkbox has passed. Fill it only from the exact frozen release candidate.

## 1. Exact release identity

- [ ] release commit: `TBD` — pin the `main` SHA that is deployed at freeze time (production redeploys from `main`; current head at the time of writing: see `git log -1 origin/main`)
- [ ] release tag: `TBD` — proposed `v0.1.0-webmcp`
- [x] live URL: `https://resonance-production-cfe3.up.railway.app` (Railway, project `resonance-live`, PostgreSQL 16 + pgvector image; entrypoint `src.product.competition_server`; see `ops/DEPLOY.md`)
- [x] database schema/migration version: `resonance-persistence/0.4` — migrations `0001_init`, `0002_recovery_generation`, `0003_collaboration`, `0004_workspaces` (applied on production PostgreSQL at first boot; verify on the frozen SHA)
- [x] Thought DNA schema: `thought-dna/0.1` (`schemas/thought-dna-0.1.schema.json`)
- [x] contracts: discovery `resonance-discovery/0.1`; UI context `resonance-ui-context/0.1`; rich result `resonance-rich-result/0.1`; collaboration `resonance-collab/0.1`; workspaces `resonance-workspace/0.1`
- [x] WebMCP contract/tool manifest hash: contract `resonance-webmcp/0.1`, six tools (`resonance_prepare_thought`, `resonance_get_share_preview`, `resonance_share_prepared_thought`, `resonance_discover`, `resonance_get_match`, `resonance_update_consent`) served from `demo/ui/webmcp_live.mjs` on the live origin; record `sha256sum demo/ui/webmcp_live.mjs` at freeze
- [x] remote MCP contract/version: **included** — `resonance-remote-mcp/0.1` bridge on `/mcp` (12 tools, `src/product/mcp_bridge.py`) + canonical OAuth 2.1 core (`src/remote/oauth.py`, R15A `c7d78a0`, mounted by R15C #141); exact SHA/deployment in `submission/RELEASE_MANIFEST.md`
- [x] seeded corpus/snapshot hashes recorded: `demo/corpus/sessions.jsonl` sha256 `eba6f76e23a702f891d356754cd9bf96df727bf6c61581cd8c8431c3d4dff925` (R7 seed, create-only import; production seeded 25 sessions)
- [ ] build/deploy environment recorded without secrets

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

- [ ] full repository suite green on exact release commit
- [ ] WebMCP targeted tests green
- [ ] persistence/identity/security/collaboration targeted suites green
- [ ] `git diff --check` clean
- [ ] browser console clean on canonical judging path
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
