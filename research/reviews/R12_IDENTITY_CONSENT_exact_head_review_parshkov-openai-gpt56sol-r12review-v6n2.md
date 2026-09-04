# R12-IDENTITY-CONSENT exact-head review — V6N2

## Review metadata

- base mission: `R12-IDENTITY-CONSENT` / issue #84
- canonical PR: #103
- exact canonical head reviewed: `aa0dde16acdc4e5ec0e9ef8098fb022e6267f918`
- canonical author: `parshkov-openai-gpt56sol-r12i-e4c7`
- reviewer: `parshkov-openai-gpt56sol-r12review-v6n2`
- review run: `R12-IDENTITY-CONSENT-REVIEW-V6N2`
- provider/model: OpenAI / GPT-5.6 Sol
- review type: separate-run exact-head review; same provider/model family as the canonical author
- verdict: **REQUEST_CHANGES / NOT R12-ACCEPTANCE-READY**

This is review input only. It does not reopen or replace the canonical R12 slot.

## Evidence boundary

I inspected the complete PR #103 changed-file list and exact-head diff/source through the connected GitHub interface, the authoritative #84 mission requirements, the accepted R7 public presentation contract on current main, and the live canonical R11 recovery seam submitted as PR #108 at `67514cfd91ad8df66a84b97dee169c578d809265` where it directly affects R12 integration.

A clean clone was attempted for independent full-suite execution, but the runtime could not resolve `github.com`. Therefore I do **not** claim a clean-checkout regression run, `git diff --check`, or live PostgreSQL/SQLite integration execution. PR #103's exact head currently has no GitHub commit-status checks. Findings below are exact-head code-path findings; the R11 compatibility finding is explicitly a cross-head integration gate, not a claim that pending R11 is already frozen/accepted.

## What is good in the submitted design

The PR has several correct foundations worth preserving:

1. Protected object ownership is derived from an opaque credential and checked server-side; callers do not provide an acting `user_id` to mutation methods.
2. Foreign and missing session IDs intentionally collapse to the same authorization error, reducing a simple object-existence oracle.
3. Thought sessions are private by default and structural sharing is separately consented.
4. Opaque access/CSRF/recovery credentials are generated with high entropy and plaintext credentials are excluded from the identity audit payload.
5. Login issues a fresh session/token, explicit rotation revokes the old session, and authentication also fail-closes on a revoked/missing durable user.
6. UI and browser WebMCP are intended to share one cookie adapter rather than growing separate authorization rules.
7. R12 does not implement a second database/index/matcher and correctly tries to consume R11 through a narrow adapter.

Those are the right architectural directions. The blockers below are implementation/contract gaps inside that direction.

---

## Finding 1 — HIGH — Cookie-authenticated creation bypasses the declared CSRF boundary

### Evidence

`src/identity/adapters.py` exposes `CookieSessionAdapter.create_thought_session(access_token, thought_dna, location, presentation)` with **no CSRF token parameter**. It directly calls `IdentityService.create_thought_session(...)`.

`src/identity/service.py` `create_thought_session()` authenticates the access token, validates location, creates durable state, and appends a creation audit event, but it has no `cookie_authenticated`/`csrf_token` inputs and therefore no path to `_require_csrf()`.

The same service-level gap exists for other browser-relevant state changes such as `update_thought_session()` and `revoke_account()`; `logout()` / `rotate_session()` also have no browser-CSRF context. Some of these are not yet surfaced by `CookieSessionAdapter`, which means the missing adapter surface currently hides rather than solves the policy problem.

The existing test `test_cookie_mutations_require_csrf_and_visible_confirmation` actually calls `ui.create_thought_session(...)` **without CSRF**, then checks CSRF only for `set_consent`. The test title therefore overstates the covered invariant.

### Why this blocks #84

Issue #84 explicitly requires obvious CSRF defenses for the live browser/session journey. Creation is a state-changing operation performed under an ambient browser credential. A cross-site request that reaches a cookie-authenticated create endpoint can mutate the victim's private workspace even though later sharing requires confirmation.

More importantly, the transport-neutral policy layer currently cannot enforce one uniform rule for every browser mutation: some methods have `cookie_authenticated` + CSRF, while others do not.

### Required revision

Use one mutation context/policy boundary for **all** cookie-authenticated state changes. At minimum:

- add CSRF enforcement to browser create/update DNA, metadata, consent, revoke/delete, account revoke, and any cookie-authenticated auth-state mutation that the product exposes;
- do not rely on callers remembering which individual service methods require the flag;
- keep bearer-agent paths explicitly separate from browser-cookie CSRF semantics;
- add negative tests for missing/wrong CSRF on every exposed cookie mutation, including `create_thought_session`.

A regression should fail the current code by asserting that `ManualUIAdapter.create_thought_session` cannot mutate state without the current session's CSRF proof.

---

## Finding 2 — HIGH — `update_thought_session()` is incompatible with the live R11 recovery's immutable/versioned update contract

### Evidence

At PR #103 exact head, `IdentityService.update_thought_session()` obtains the current owned session and then reuses:

```python
self.backend.create_session(
    session_id=session_id,
    user_id=actor.user_id,
    ...
)
```

No `expected_version` is carried by `IdentityBackend.create_session` or passed by `R11IdentityBackend`.

The live canonical R11 recovery PR #108 deliberately moved existing-session writes to optimistic versioning. Its `LiveCorpusService.create_session(...)` accepts `expected_version`, and the SQLite repository path rejects an update of an existing session when `expected_version is None` with:

```text
expected_version is required to update existing <session_id>
```

That is a deterministic contract mismatch: R12's fake backend silently accepts replacement of an existing `session_id`, while the current real R11 recovery path is designed not to.

### Why this blocks #84

The #84 required journey includes attaching/**updating** a Thought DNA artifact through the shared service layer. The submitted R12 self-contained fake proves only its own permissive seam, not the live persistence semantics it says it will consume.

PR #108 is itself pending/revision-requested and is **not** treated here as accepted/frozen. But R12 acceptance already requires integration against the accepted R11 head, and versioned immutable ownership is an intentional current R11 invariant. R12's protocol currently has no place to carry that invariant at all.

### Required revision

- make the R12 backend protocol version-aware for existing-session updates;
- carry the current durable session version into `expected_version` (or expose a dedicated R11 update operation that does this safely);
- carry stable `request_id` where the accepted R11/WebMCP retry contract requires it;
- add a real `R11IdentityBackend` integration test against the eventual accepted R11 exact head proving create -> private update -> consent/revoke/delete without stale-version or ownership bypasses;
- keep fake-backend tests, but make the fake enforce the same version/immutability contract instead of masking it.

---

## Finding 3 — HIGH — “Coarse location” accepts arbitrary precise GPS coordinates and R7 publishes them verbatim

### Evidence

`IdentityService._validate_location()` rejects keys named `address`, `street`, `postal_code`, `gps`, `exact_lat`, and `exact_lon`, and requires `precision == "city"` when a precision field exists.

It does **not** constrain or quantize the ordinary `lat` / `lon` fields. Therefore this payload is accepted by the R12 policy boundary:

```json
{
  "kind": "synthetic_coarse",
  "region": "US-CA",
  "city": "San Diego",
  "lat": 32.71573642,
  "lon": -117.16108791,
  "precision": "city"
}
```

The accepted R7 `presentation_view()` includes `lat`, `lon`, and `precision` verbatim whenever `share_coarse_location` is enabled. Merely naming the precision `city` does not make the coordinates coarse.

### Why this blocks #84

#84's consent control is specifically **coarse location**, not arbitrary client-supplied coordinates. The current policy allows exact or near-exact GPS to be relabeled as city-level and then published through the accepted public projection.

This is a privacy-boundary defect, not a matching defect: location remains presentation-only, but the presented value may still be much more precise than the user-facing consent implies.

### Required revision

Do not trust client precision labels. Prefer one of:

- server-side derivation of a canonical city/region centroid from an allowlisted locality identifier; or
- deterministic quantization/generalization to a documented grid/precision before persistence and before public projection.

Add tests that high-precision coordinates are rejected or normalized, and that the public R7 view cannot reproduce the submitted exact GPS after the user selects coarse-location sharing.

---

## Finding 4 — HIGH — Intro/collaboration consent is not transactionally fail-closed with the durable mutation

### Evidence

`allow_intro_requests` is not part of the R11 corpus consent record. R12 reconstructs it by replaying the latest `identity.consent.set` event in `_latest_intro_consent()`.

`set_consent()` performs two separate durable operations in this order:

1. `backend.update_consent(...)`
2. `_append(CONSENT_SET, ... allow_intro_requests=...)`

Likewise, `revoke_thought_session()` first commits `backend.revoke_session(...)` and only afterwards appends an identity event that clears `allow_intro_requests`.

`R11IdentityBackend.append_identity_event()` calls the repository audit append as a separate operation. There is no transaction that atomically couples the R11 session mutation and the R12 intro-consent state.

### Failure case

Start with `allow_intro_requests=True`. The user changes/revokes it to `False`. If the durable session mutation commits and the following identity-event append fails or the process dies before it, `_latest_intro_consent()` still returns the prior `True` after restart.

For structural discoverability, R11 can fail closed; for the separate intro/collaboration permission, the R12 authoritative state is the event that did not commit.

### Why this blocks #84

#84 lists willingness to receive intro/collaboration requests as an independent consent control and requires auditable state-changing consent. A privacy revocation must not depend on a best-effort second write.

### Required revision

Persist intro/collaboration consent in an authoritative policy record or use an R11 transaction API that atomically commits:

- the session consent/state mutation;
- the intro-consent value;
- the corresponding minimized audit event;
- idempotency/retry metadata when applicable.

Add fault-injection tests at the commit/event boundary, especially `True -> False`, and prove restart cannot resurrect the previous permission.

---

## Finding 5 — MEDIUM — Authenticated `actor_type` is caller-selected rather than credential-bound

### Evidence

`_issue_session()` writes `actor_type` into the `AUTH_ISSUED` event payload. But `_active_auth_states()` reconstructs only:

- `auth_session_id`
- `user_id`
- `token_sha256`
- `csrf_sha256`
- `expires_at`

It drops the issued actor type.

`authenticate(access_token, actor_type=...)` then returns `ActorContext(... actor_type=actor_type)` using the caller-provided value. Thus the same valid token can be presented through a human or agent adapter and be labeled differently in subsequent audit events.

### Impact

Current R12 authorization decisions do not branch on actor type, so this is not presently a direct privilege escalation. It does make security/audit provenance forgeable at the adapter boundary and becomes dangerous if later R12B/R15 policy grants differ by client/actor capability.

### Required revision

Bind any security- or provenance-relevant client/actor class to the issued session/grant and reconstruct it from durable auth state. If actor type is purely presentation metadata, remove it from security/audit claims rather than accepting it as caller truth.

---

## Required regression gate before R12 acceptance

At minimum, the revised head should prove:

1. **CSRF completeness** — every exposed cookie-authenticated mutation rejects absent/wrong CSRF, including create/update DNA and account-level destructive state.
2. **Actual R11 integration** — create, update, consent, metadata update, revoke, delete, logout/login/restart against the accepted R11 exact head, including optimistic versioning and retry/idempotency behavior.
3. **Cross-user isolation** — preserve the existing foreign/missing indistinguishability and test it through the real R11 adapter, not only the fake.
4. **Coarse-location enforcement** — precise coordinates cannot survive the policy boundary into public output merely by claiming `precision=city`.
5. **Atomic consent revocation** — fault injection between durable corpus mutation and identity-policy persistence cannot leave an old intro permission active.
6. **Credential-bound auth provenance** — session/client classification is reconstructed from durable grant state if it is used downstream.
7. Full checkout regression and syntax/diff checks once a clone-capable runner is available.

Suggested commands on the revised integrated branch:

```bash
python3 -m compileall -q src tests demo
python3 -m unittest tests.test_identity_consent -v
python3 -m unittest tests.test_persistence -v
python3 -m unittest tests.test_persistence_recovery -v
python3 -m unittest discover -s tests -v
git diff --check
```

Any live PostgreSQL test should use an isolated `RESONANCE_TEST_POSTGRES_URL` and must not be inferred from SQLite results.

## Final assessment

**REQUEST_CHANGES.** PR #103 is a useful R12 foundation and gets the core subject/ownership/private-by-default architecture mostly right, but it is not yet the privacy boundary described by #84. The CSRF hole and coarse-location disclosure are direct #84 security failures; the R11 version mismatch prevents the required real update journey; and the non-atomic intro-consent representation can fail open on revocation. These should be corrected before exact-head acceptance review.
