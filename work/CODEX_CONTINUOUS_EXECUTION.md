# Maintainer Continuous Execution Directive — Codex

Issued by maintainer for the deadline sprint. This is an explicit human/maintainer assignment under `AGENT_PROTOCOL.md` and `work/CURRENT_MILESTONE.md`.

## Objective

Work continuously through the **full current product roadmap**, in order, without reducing feature scope:

`R10 WebMCP -> R11 Persistence -> R12 Identity/Consent + R12B Security + R12C Ingestion -> R13 Live Product -> R13B Rich Results -> R14 Collaboration -> R14B Workspaces -> R15 Remote MCP integration -> R16 Deployment/Pilot -> R17 Submission`.

The goal is not one task. The goal is a **sequence of completed, repository-backed tasks with no avoidable idle time**.

## Continuous operating loop

Repeat this loop until the roadmap is complete or the human maintainer explicitly stops the run:

1. Fresh-read `main`, `work/CURRENT_MILESTONE.md`, `work/queue.yaml`, the relevant Issue, current PR(s), and all new review comments.
2. Identify the earliest unfinished/current-milestone work in the roadmap that is protocol-legitimate for this run.
3. If an existing canonical PR is in `REVISION_REQUESTED` or has explicit maintainer blockers, **fix that existing canonical branch/PR rather than creating a duplicate canonical claim**, when repository permissions allow it.
4. If a canonical mission is genuinely AVAILABLE and prerequisites are explicitly ACCEPTED, use protocol v0.4 fresh-read -> CLAIM -> immediate fresh-read verification before substantial implementation.
5. Implement the smallest complete change that closes the current blockers/acceptance contract without deleting or weakening required functionality.
6. Run all targeted tests plus the broadest available regression suite, compile/static checks, and `git diff --check`. Never fabricate unavailable evidence.
7. **Immediately commit and push each completed task/fix to the repository.** Do not accumulate several finished milestones locally before publishing them.
8. Open or update the correct PR immediately, post the required `SUBMIT`, `REVIEW_INPUT`, or review-request provenance, and record the exact head SHA.
9. If an independent review is required, request it immediately. **Do not sit idle waiting for review.** Move to the next protocol-legitimate current-milestone task, review, integration preparation, deployment preparation, or regression work. Return immediately when new review feedback arrives.
10. If an exact-head review ACCEPTS the canonical PR and all protocol/acceptance conditions are satisfied, merge using the repository's normal maintainer procedure when permitted; otherwise leave it merge-ready and continue useful work.
11. Re-read live state before every new claim/merge because other agents may have changed the queue while this run was working.

## Current starting sequence

### 1. R10 WebMCP — PR #97 / issue #82

Start here. Preserve all six browser-native WebMCP tools and all accepted safety/idempotency/source-fidelity behavior.

Resolve the latest maintainer blockers on the current exact head, including:
- fix `HTTPError` import (`urllib.error.HTTPError`);
- add the concise root README WebMCP Challenge/judge-test section requested by maintainer;
- run targeted/full tests and JS checks;
- push the new exact head immediately;
- request a new exact-head independent WebMCP review because acceptance must bind to the changed content.

Do not redesign R10 while fixing these final blockers.

### 2. R11 Persistence — PR #108 / issue #83

Then fix the exact-head review blockers, preserving the stronger recovery design:
- crash-safe/idempotent SQLite migration checkpointing around `0002`;
- prevent stale profile upserts from clearing a committed user revocation in SQLite and PostgreSQL semantics;
- durable request-id/idempotency + recovery/healing semantics for user state-changing operations, not only session paths;
- add focused regression probes for all three findings;
- rerun persistence/recovery/full regression checks;
- push immediately and request new exact-head independent review, preferably different-provider/clone-capable.

### 3. R12 Identity/Consent — PR #103 / issue #84

Fix the current exact-head blockers and integrate against the current/accepted R11 seam:
- CSRF proof on cookie-authenticated create-thought-session mutation;
- optimistic `expected_version` on existing-session updates;
- enforce truly coarse location instead of accepting arbitrary precise `lat/lon` labeled `city`;
- make disabling `allow_intro_requests` durable/fail-closed across crash/restart;
- reconstruct trusted `actor_type` from auth/session state rather than caller classification;
- add regressions and run integration tests against the latest R11 contract;
- push immediately and request exact-head review.

### 4. R12B Security — PR #106 / issue #89

Preserve the independently reviewed security kernel. Complete gate integration rather than rewriting the kernel:
- wire accepted/current R11/R12 product paths through `SecurityPolicy.authorize`;
- provide the real durable `PolicySource` adapter;
- run full cross-user/auth/consent regression on the integrated product state;
- preserve HTTPS/origin/CSRF/bounds/rate/UGC/location/privacy invariants;
- push each completed integration increment promptly.

### 5. R12C Session Ingestion — PR #102 / issue #92

Finish the existing private-first foundation against accepted/current R11/R12:
- durable owner-scoped prepared drafts/share handoff as required by the accepted architecture;
- manual UI/WebMCP/remote parity through the same service boundary;
- preserve `prepare -> preview -> explicit confirmed share` and raw-source minimization;
- push and submit for exact-head review.

### 6. R13 Live Product — issue #85

Once prerequisites are explicitly ACCEPTED, claim correctly and implement the complete live DB-backed product path:
- authenticated user/session lifecycle;
- create/update/list owned Thought sessions;
- live share/revoke/delete;
- accepted structural discovery from durable state;
- same authorized state in UI and WebMCP;
- evidence/map/heat/coarse-distance presentation;
- generation/freshness markers;
- fail-closed stale-index behavior;
- idempotent writes and cross-user cache isolation;
- deterministic replay remains clearly separate from LIVE mode.

### 7. Continue without stopping

Then continue in roadmap order, without cutting features:

- **R13B #90:** versioned structured + rich/image result parity across agent surfaces.
- **R14 #86:** consent-safe intro lifecycle and private messaging after mutual acceptance.
- **R14B #91:** persistent multi-person idea workspaces, roles/membership, notes/tasks/messages/artifacts, agent context/cursors, removal revocation.
- **R15 #87 / PR #93:** repair protocol/security findings and integrate Remote MCP with the same accepted live product/auth/state; prove generic/client interoperability.
- **R16 #88:** public HTTPS deployment, real DB, health/readiness, migrations, secrets, backup/restore, >=100-user mixed pilot, cross-layer acceptance matrix, public judge path.
- **R17 #75:** freeze exact release candidate, fill Devpost truthfully, finalize judge instructions, public <3-minute video, record release/tag/schema/tool versions, independent public-URL review, submit before deadline and freeze.

## No-idle rule

Waiting for another agent/reviewer is not a reason to stop. While a required review is pending, choose only work that is still protocol-legitimate, for example:

- fix another already-submitted current-milestone PR with maintainer-requested revisions;
- perform an independent current-milestone exact-head review when independence permits;
- prepare deployment/operations/test scaffolding that does not falsely claim a blocked downstream mission complete;
- run broader regression/reproduction work;
- improve judge/runbook/release evidence without claiming unaccepted functionality.

Do **not** bypass prerequisite acceptance, manufacture duplicate canonical claims, self-approve an independent-review gate, regress into archived R0-R9 repeats, or weaken privacy/security/functionality merely to move faster.

## Repository publishing rule

Every meaningful completed unit should become visible immediately:

`implement/fix -> test -> commit -> push -> update/open PR -> post provenance/review request -> continue`

Do not wait for the human maintainer to ask "continue" after each task. Continue autonomously until blocked by a genuinely human-only/external action or until the full R10-R17 roadmap is complete.
