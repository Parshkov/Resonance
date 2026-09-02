# Maintainer Continuous Execution Directive — Fable

Target agent: `dima2010-anthropic-fable5-7328` / Anthropic Claude Fable 5.

This is an explicit human/maintainer assignment under `AGENT_PROTOCOL.md` and `work/CURRENT_MILESTONE.md`.

## Objective

Operate continuously on the full current Resonance product roadmap until R17/full launch, without reducing functionality, privacy, security, collaboration, workspace, remote-MCP, deployment, or submission scope.

Current product path:

`R10 WebMCP -> R11 Persistence -> R12 Identity/Consent + R12B Security + R12C Ingestion -> R13 Live Product -> R13B Rich Results -> R14 Collaboration -> R14B Workspaces -> R15 Remote MCP integration -> R16 Deployment/Pilot -> R17 Submission`.

Do not stop after one review, one fix, one mission, or one PR.

## Continuous operating loop

Repeat until the full roadmap is accepted/launched or a genuinely external/human-only action is required:

1. Fresh-read `main`, `work/CURRENT_MILESTONE.md`, `work/queue.yaml`, relevant issue streams, current PRs, and every new review/maintainer comment. GitHub issue streams are authoritative; never rely on stale memory.
2. Take the earliest protocol-legitimate useful current-milestone work: requested exact-head review, requested recovery, AVAILABLE canonical mission with accepted prerequisites, integration/deployment prep, or regression/adversarial testing.
3. For a canonical claim, use the full fresh-read -> CLAIM -> immediate fresh-read verification handshake before substantive work.
4. For independent review, use a fresh clean checkout of the exact SHA; run focused and full suites where possible; probe cross-layer seams adversarially; publish `REVIEW_INPUT` immediately with ACCEPT or precise blockers.
5. When you find blockers, publish them immediately. Do not wait for a maintainer response before moving to other legitimate work.
6. When you materially author/fix a PR, do not independently approve that same exact head. Request another independent reviewer and continue elsewhere while waiting.
7. Publish every completed unit immediately: test -> commit/push if authoring -> PR/update -> protocol event -> continue.
8. Never bypass prerequisite ACCEPT, duplicate an occupied canonical slot, self-approve your own material changes, fall back to archived R0-R9 repeats, or weaken required behavior to make a gate green.

## Immediate priority as of this directive

### A. Re-review R11 first

Mission #83 / PR #108.

Fresh exact head currently requested by maintainer: `772eac8db56b940bd074bb784e2d6cb0cb1dafb9`.

Reproduce the prior B1/B2 findings and verify the new recovery specifically:
- duplicate `thought_id` on service and direct SQLite repository paths returns typed `PersistenceConflictError`, never raw driver exceptions;
- inspect PostgreSQL UNIQUE mapping for equivalent typed behavior;
- documented v0.1 tombstone/re-share policy is enforced consistently;
- malformed/incomplete/extra-field/precise location is rejected before commit;
- a legacy malformed discoverable row leaves startup bootable but degraded/fail-closed and can be repaired/revoked through normal service methods;
- public audit excludes `identity.auth.*` and `identity.account.registered`, while raw internal identity events remain available to R12 replay;
- run the new focused regressions plus prior persistence/recovery suites and full repo suite.

Post exact-head `REVIEW_INPUT` immediately.

### B. Re-review R12 immediately after R11

Mission #84 / PR #103.

Fresh exact R12 head currently requested by maintainer: `64fd2f6298cb8bbae22b5a7e2653b330c243e8b0`.

Review standalone R12 and then synthetic-integrate it with exact R11 head `772eac8db56b940bd074bb784e2d6cb0cb1dafb9`.

Verify:
- exact location allowlist requires `kind/region/city/lat/lon/precision`;
- unknown fields cannot smuggle precise coordinates;
- bounds/finite checks and 0.1-degree rounding remain correct;
- public audit contains no token/csrf/recovery verifier hashes and no auth-session event graph;
- internal login/auth replay still functions after public-audit redaction;
- all prior R12 auth/ownership/CSRF/version/intro-consent fixes remain green.

Post exact-head `REVIEW_INPUT` immediately.

### C. Do not idle while maintainer fixes a blocker

If R11 or R12 needs another revision, publish the blocker and immediately continue with adversarial current-milestone review work that will not be invalidated by the known blocker.

Preferred next work:
1. fresh-read #92 / PR #102 and review **R12C-owned** prepare -> preview -> explicit confirmed share, raw-source minimization, owner scoping, restart/replay/idempotency/HMAC confirmation and transport parity. Clearly distinguish inherited R11/R12 failures from R12C-local failures; do not ACCEPT a stale integrated gate merely because local code is good.
2. fresh-read #89 / PR #106 and review **R12B-owned** authorization/security integration, bypass resistance, policy-source durability, cross-user isolation, CSRF/origin/UGC/rate/bounds/location/audit privacy. Again distinguish inherited upstream failures from security-owned failures.
3. The moment corrected R11/R12/R12B/R12C exact heads appear, prioritize their exact-head re-reviews so the critical path can unlock R13.

### D. Continue through R13-R17 without another personal assignment

After prerequisite gates are explicitly ACCEPTED, fresh-read and take/review the next protocol-legitimate mission in roadmap order.

- R13: complete live authenticated DB-backed product, same authorized state in UI/WebMCP, freshness/generation, fail-closed revoke/delete, idempotency and cache isolation.
- R13B: structured + rich/image results parity.
- R14: consent-safe intro lifecycle and private messaging after mutual acceptance.
- R14B: persistent workspaces, membership/roles, notes/tasks/messages/artifacts, agent context and revocation.
- R15: you previously authored PR #93, so you may revise it when needed but must not independently approve your own material changes; request an independent reviewer.
- R16: public HTTPS deployment/pilot, DB, migrations, health/readiness, secrets, backup/restore, >=100-user acceptance and judge path.
- R17: release freeze, Devpost/judge instructions, public <3-minute video assets/evidence, exact versions/tag, public-URL review and submission package.

## External blockers

Do not stop merely because review is pending. Stop only when the next required action is genuinely unavailable to your runtime or human-only (for example missing production credentials or a manual external submission/upload). In that case prepare everything possible, publish the exact blocker and the exact mechanical action the human must perform, then continue any other legitimate work.

## No-idle rule

Do not wait for the maintainer to say “continue.” Re-read live GitHub state after every published result and continue autonomously.
