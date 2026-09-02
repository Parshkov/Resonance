---
mission: R12B-SECURITY-DATA-GOVERNANCE
run: R12B-SECURITY-REVIEW-P8W1
review_type: independent exact-head review
contributor: Parshkov
agent_id: parshkov-xai-grok46-p8w1
agent_or_model: Grok 4.6 (exact mode not exposed)
date: 2026-09-02
mission_modified: false
web_research_used: false
code_execution_used: true
blind_constraints_preserved: not-applicable
reviewed_pr: https://github.com/Parshkov/Resonance/pull/106
exact_head: e35276dd5ec673fa727333934f1a9896a8ac738d
base_main: dd93f349808ec2006b902e226edf2fe2eb95763d
conflict_of_interest: >
  Different provider from the R12B author (OpenAI / GPT-5.6 Sol,
  agent_id parshkov-openai-gpt56sol-r12b-k7m2). Same GitHub actor as
  the repository owner because this session used the connected
  Parshkov account to publish the review. This identity did not
  author PR #106, src/security/**, or the R12B tests.
notes: >
  Not a canonical CLAIM on R12B-SECURITY-DATA-GOVERNANCE. Issue #89
  remains SUBMITTED / PENDING_REVIEW on PR #106. This review does
  not occupy or reopen the canonical slot.
---

# Scope

Independent exact-head review of canonical R12B PR #106, the
`resonance-security/0.1` runtime policy kernel.

This is review input. It is not maintainer `REVIEW_STATUS`.

The review distinguishes two questions:

1. Does the submitted kernel do what it claims, with reproducible tests?
2. Does that complete issue #89 as a public-pilot security *gate*?

# Inputs reviewed

| Artifact | Role |
|---|---|
| Issue #89 body + addenda | acceptance contract, MCP session binding, grant-drift, OAuth subject binding |
| `SECURITY.md`, `docs/THREAT_MODEL.md` | documented controls this kernel must encode |
| PR #106 at `e35276dd` | implementation under review |
| `src/security/**` | owned surface |
| `tests/test_security_policy.py` | claimed invariants |
| `engineering/missions/R12B_SECURITY_DATA_GOVERNANCE.md` | author provenance and disclosed gaps |
| `work/CURRENT_MILESTONE.md` | why this review was selected |

Pending R11/R12/R15 implementations were not treated as accepted
dependencies and were not copied into this review.

# Method

1. Fetched PR #106 files at exact head `e35276dd5ec673fa727333934f1a9896a8ac738d`.
2. Read `policy.py`, `store.py`, `oauth.py`, `guards.py`, `service.py`,
   `models.py`, and the test module rather than trusting the PR body.
3. Assembled the owned files in a local harness and executed the
   author's unit suite.
4. Added extra probes: unauthenticated context; owner
   `discovery:read` after revoke; OAuth `compare_digest` with
   mismatched client-id length.

Runtime: Python 3 on the review harness. The local Resonance working
copy was not a complete clean tree, so **full `unittest discover -s
tests` on the combined repository is not claimed**. The author's
26-test module was executed independently.

# Measured validation

```text
python3 -m compileall -q src tests
python3 -m unittest tests.test_security_policy -v
```

Result on the exact authored files: **26 tests, 26 OK** (0.003s).

`git diff --check` was not executed against a complete clone of the
PR ref; the submitted patch from GitHub is text/Python only and
contains no conflict markers.

Extra probes:

```text
PROBE unauth: AuthenticationRequired
PROBE owner-discover-after-revoke: Decision.ALLOW
PROBE oauth short client: OAuthGrantError
```

# Gate findings

## G1. Cross-user IDOR / forged owner — PASS (kernel)

`ResourceRef` accepts only `kind` + `resource_id`. Owner/workspace/peer
identity is resolved from `PolicySource`. User B cannot
`session:read_private` / `session:update` on `ses-a`. Reproduced.

## G2. Subject/client-bound MCP sessions — PASS (kernel)

`SessionGrantRegistry.require` rejects a valid `Mcp-Session-Id` used
with another subject or another client. Rotation invalidates the old
id. Reproduced.

## G3. Grant drift / current-policy re-evaluation — PASS (kernel)

Workspace membership removal denies the next `workspace:read` on the
same protocol session. Token scopes can only narrow an already-allowed
server decision; a broad token cannot read another user's private
session. Reproduced.

## G4. Revoke / projection / block — PASS for other users (kernel)

After `revoke_session("ses-a")`, user B's `discovery:read` and
`discovery_projection` fail closed. Display-name is consent-gated;
coarse location is omitted when not shared; `private_message` never
projects. Block is symmetric and denies discovery/intro/DM. Reproduced.

Non-blocking design note: the owner of a revoked session can still
`discovery:read` that session, because owner short-circuits before
consent checks. That is not a cross-user leak. If `discovery:read` is
ever used as the public discovery path for the owner as well, revoke
should be applied uniformly.

## G5. CSRF, bounds, UGC, rate, location, URL secrets — PASS (kernel)

Cookie-authenticated mutations require an allowlisted origin and a
matching CSRF digest. Oversized/deep Thought DNA is rejected before
compute. UGC is HTML-escaped and carries `untrustedContentHint`.
Small location buckets `< 3` are dropped. Exact lat/lon/address keys
are rejected. Credentialed HTTP and `*` origins fail. Query keys
`token` / `access_token` / `authorization` / `password` / `secret` /
`api_key` are rejected. Deterministic rate limiter fires. Reproduced.

## G6. OAuth subject binding / PKCE / single-use — PASS (kernel)

`issue_code` has no `user`/`username` parameter. Codes bind subject,
client, redirect, resource, audience, and S256 challenge. Wrong client
or replay fails. Extra probe: short mismatched `client_id` still
raises `OAuthGrantError` rather than leaking through
`hmac.compare_digest`. Reproduced.

## G7. Audit minimization — PASS (kernel)

Decision records keep correlation id, subject, action, resource
kind/id, grant version, and decision. `safe_log_metadata` drops
`thought_dna`, `message`, `authorization`, and `access_token`.
Reproduced.

## G8. Full-repository regression and product wiring — NOT DEMONSTRATED

The kernel is not imported by demo UI, WebMCP, persistence, identity,
or remote MCP on this head. Issue #89 acceptance tests include
full-suite green plus transport/UI/WebMCP parity. The author correctly
disclosed that gap. This review independently confirms the unit suite
and independently confirms the wiring/full-suite evidence is still
absent.

Backup/restore is proven only on `InMemoryPolicySource`. That is a
test-adapter property, not hosted backup evidence.

# Blocking for #89 ACCEPTED

None of these are defects in the kernel's own tests. They block treating
PR #106 as the finished security *gate*:

1. **B1 — no product-path enforcement.** UI / WebMCP / remote MCP /
   persistence mutation paths on current `main` do not call
   `SecurityPolicy.authorize`. A merged but unused kernel does not
   make live objects fail-closed.
2. **B2 — no accepted `PolicySource` adapter.** The only implementation
   is the in-memory test/pilot store. Final acceptance still needs an
   adapter over accepted R11/R12 state so revoke/ownership/membership
   cannot drift from the durable source of truth.
3. **B3 — full repository suite not independently rerun** on a complete
   checkout of this exact head plus current `main` tests. This reviewer
   ran the 26 owned tests only.

# Non-blocking nits

1. Owner `discovery:read` ignores revoke/delete/share flags. Document
   or close that path if public discovery must be consent-identical
   for owners.
2. `AuthorizationCodeBroker.exchange_code` pops the code before binding
   checks. Failed redeem burns the code. Fail-closed and acceptable;
   worth one comment so integrators do not retry a mistyped redirect
   with the same code.
3. `HostedTransportGuard` requires `https` unconditionally. Loopback
   HTTP used by current demo/WebMCP servers will need an explicit
   local exemption or the guard will reject judge laptops.
4. No dedicated tests for `account:export` / `account:delete`,
   unauthenticated `RequestContext`, or workspace admin vs member
   write. Behavior exists in policy; coverage is thinner than the
   IDOR/session tests.
5. `peer_action_allowed` defaults to false. Fail-closed is correct,
   but R12 consent `allow_intro_requests` alone will not authorize
   intros until an adapter also writes the peer-permission tuple.

# Verdict

**ACCEPT the submitted kernel as independent exact-head review input.**

The 26 claimed tests pass on the authored files. The load-bearing
kernel invariants requested by #89 and the later MCP/OAuth addenda
are implemented and reproducible in isolation.

**Do not record `REVIEW_STATUS status: accepted` for #89 yet.**

The mission is a live-pilot security gate, not only a policy library.
Acceptance still requires product-path wiring, an authoritative
R11/R12 `PolicySource` adapter, and a full-suite run on a complete
checkout. Those gaps were disclosed by the author and independently
confirmed.

Recommended maintainer action:

- keep #89 `SUBMITTED / PENDING_REVIEW`;
- treat PR #106 as a mergeable foundation module if the maintainer
  wants the seam on `main` early;
- require a follow-up exact head that wires `authorize()` into the
  transport-neutral product service before unblocking R13/R14/R16
  public-launch acceptance.

This reviewer cannot and does not post maintainer `REVIEW_STATUS`.

# Confidence

**HIGH** that the reviewed kernel files behave as tested on this
machine and that cross-user/session/OAuth unit invariants hold.

**HIGH** that #89 is not finished as a deployment gate on this head.

**MEDIUM** that merging the kernel now is net-positive, provided
transports are not described as "protected by R12B" until they call it.
