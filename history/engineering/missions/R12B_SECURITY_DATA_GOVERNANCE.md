# R12B-SECURITY-DATA-GOVERNANCE — run record

> **Superseded in part (2026-09-06).** This mission was written when the
> product had two persistence backends. Resonance now runs on **PostgreSQL
> only** — `src/persistence/sqlite_store.py` is deleted and there is no
> SQLite path to build, mirror or keep at parity. The rest of the contract
> stands; this file is kept as the record of what was asked at the time.

## Identity and claim

- agent_id: `parshkov-openai-gpt56sol-r12b-k7m2`
- human sponsor: `Parshkov`
- provider/model: OpenAI / GPT-5.6 Sol
- execution environment: ChatGPT connected session with direct GitHub read/write and local Python execution
- run_id: `R12B-SECURITY-DATA-GOVERNANCE`
- canonical issue: #89
- claim comment: `5504634007`
- claim time: `2026-09-02T05:01:22Z`
- base main at branch creation: `dd93f349808ec2006b902e226edf2fe2eb95763d`
- blind constraints: none

Fresh claim-time prerequisite resolution: queue v4 required R8-DISCOVERY; #73 had explicit `REVIEW_STATUS status: accepted` for R8 before this claim. A complete fresh #89 comment read showed no earlier canonical claim, and an immediate post-claim reread showed this claim as the only canonical claim.

## Inputs inspected before implementation

- `README.md`, `PRINCIPLES.md`, `START_HERE.md`, `AGENT_PROTOCOL.md`, `AGENT_MANIFEST.yaml`;
- `work/CURRENT_MILESTONE.md`, `work/queue.yaml`, `work/STATE_MACHINE.md`, `work/CLAIM_PROTOCOL.md`;
- `engineering/MISSION_CONTRACT.md`;
- `SECURITY.md`, `docs/THREAT_MODEL.md`, `docs/PRIVACY_AND_DATA_USE.md`, `docs/PILOT_TERMS.md`;
- issue #89 complete scope/addenda, including subject-bound MCP sessions and authorization grant-drift requirements;
- R11 #83 recovery state;
- R12 #84 pending PR #103 identity/consent seam;
- R15 #87 pending PR #93 remote-MCP seam.

No blind sibling output applies. Pending R12/R15 code was inspected only as an integration seam; it is not copied into this implementation and remains outside this mission's ownership.

## Implementation

Owned surface:

- `src/security/**`
- `tests/test_security_policy.py`
- this run record
- agent registry entry

Delivered runtime controls:

1. `PolicySource` authoritative-state protocol; clients cannot provide trusted owner/workspace/peer identity.
2. Fail-closed `SecurityPolicy` for owner, discovery, workspace, collaboration, block/report actions.
3. Subject/client-bound `SessionGrantRegistry` with expiry, rotation, revocation and policy-generation checkpoints.
4. Current-state re-evaluation so consent/membership/block changes defeat stale session grants immediately.
5. Token scopes as a narrowing constraint only; stale/broader token claims cannot widen server policy.
6. Content-minimized decision audit with correlation ID, subject, session/client, action/resource, grant version and allow/deny/confirm result.
7. Sensitive-write confirmation boundary.
8. Authenticated-subject OAuth authorization-code/PKCE broker bound to client, redirect URI, resource and audience; no username parameter.
9. CSRF/origin checks for cookie-authenticated writes.
10. Deterministic per-subject/action rate limiting.
11. JSON/Thought-DNA byte, node, edge and nesting-depth bounds.
12. Explicit untrusted-UGC wrapper + escaped browser rendering + `untrustedContentHint` metadata.
13. Coarse-location validation and configurable aggregate small-bucket suppression.
14. Hosted HTTPS/restrictive-origin/URL-secret guard.
15. Minimal block/report runtime facade.
16. Deterministic test-adapter snapshot/restore preserving access-control state.

## Validation actually executed

The execution sandbox cannot resolve GitHub hosts for `git clone`, and this repository has no `.github/workflows` CI workflow. Therefore no full-repository checkout/regression claim is made.

The authored files were assembled locally in `/tmp/r12b_work` and validated with:

```text
PYTHONPATH=/tmp/r12b_work python3 -m unittest tests.test_security_policy -v
```

Result after final policy refactor: **26 tests, all OK**.

Also executed:

```text
PYTHONPATH=/tmp/r12b_work python3 -m compileall -q /tmp/r12b_work/src/security /tmp/r12b_work/tests/test_security_policy.py
python3 -m py_compile /tmp/r12b_work/src/security/*.py /tmp/r12b_work/tests/test_security_policy.py
```

Result: clean / no syntax errors.

Acceptance-focused tests cover cross-user ID substitution, forged-owner prevention, subject/client-bound `Mcp-Session-Id` replay rejection and rotation, mid-session membership/policy-generation change, stale/broader token scope rejection, revoke disappearance from authorized discovery/projection, workspace member removal, block preventing discovery/intro/direct-message interaction, sensitive-write confirmation, private-by-default unknown actions, audit minimization, test-adapter restore, CSRF/origin enforcement, oversized/deep Thought DNA rejection, escaped/untrusted UGC, small-bucket suppression, deterministic rate limiting, exact-location rejection, HTTPS/restrictive-origin/no-URL-secret policy, and OAuth subject/client/redirect/PKCE/resource/audience binding with single-use codes.

## Explicit remaining evidence / integration gates

These are not represented as passing:

- full repository regression suite on a real checkout;
- integration against an **accepted** R11 persistence adapter (R11 recovery was still open when this run started);
- integration against accepted R12 identity/consent and R15 remote-MCP heads (their observed implementations were pending review);
- production HTTPS termination, CORS/CSP headers, private object storage, managed DB encryption, encrypted backup/restore, production retention, and deployed log inspection;
- independent security review of this exact PR head.

Those are required before #89 can receive final `REVIEW_STATUS status: accepted` and before public multi-user deployment. This submission provides the canonical runtime policy kernel and deterministic acceptance tests without fabricating deployment evidence.

## Continuous-execution recovery integration

After the first exact-head submission, independent xAI review run
`R12B-SECURITY-REVIEW-P8W1` accepted the isolated kernel but withheld gate
acceptance on three measured gaps: no product call sites, no durable R11/R12
`PolicySource`, and no complete-tree regression. This recovery head merges the
current R11 recovery head `5f06cad075d118280b11faa7c20afcad3a875510` and R12
recovery head `5cb06b96acb08aa16d562dd1ece4816a7a3800fe` and closes those gaps.

Delivered integration:

- durable `IdentityPolicySource` over R12's backend and R11's corpus/audit store;
- R12 `IdentityService` calls `SecurityPolicy.authorize()` for protected owner,
  discovery, account, block/report, and Thought mutation paths;
- subject/client-bound protocol-session construction from authenticated R12
  state and active-auth revalidation on every policy decision;
- exact-origin + CSRF enforcement in the shared UI/WebMCP cookie adapter;
- pre-storage Thought DNA/request bounds and the existing coarse-location rules;
- durable, minimized allow/deny/confirm events plus durable block/report state;
- account export without credentials and account revocation with profile
  anonymization and immediate corpus hiding;
- SQLite restart and backup/restore policy regressions.

Validation on the combined repository checkout:

```text
python3 -m unittest discover -s tests -v
```

Result: **254 tests / 252 passed / 2 live-PostgreSQL skips** on the final
recovery tree. The skipped tests explicitly require an isolated
`RESONANCE_TEST_POSTGRES_URL`; no live PostgreSQL result is claimed.
