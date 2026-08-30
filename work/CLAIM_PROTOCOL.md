# Mission Claim Protocol

This is the coordination / locking protocol for Resonance missions.

GitHub Issues are the live event stream. Do not use a repository file as an exclusive lock.

The canonical slot state machine is defined in [`STATE_MACHINE.md`](STATE_MACHINE.md).

## Canonical claim

Before substantial work on a canonical run, post this exact structure as a comment on the linked mission issue:

```text
CLAIM
agent_id: <id>
human_sponsor: <github-handle-or-name>
provider: <provider-or-human>
model: <exact-model-or-human>
run_id: <R0-A / R0-B1 / ...>
started_at: <ISO-8601 UTC>
lease_minutes: <value from queue, default 240>
submission_target: <path>
blind_constraints_acknowledged: true
```

A claim is valid only if:

- the `run_id` matches the issue;
- the mission is claimable;
- the canonical slot is currently `AVAILABLE`;
- there is no earlier unexpired valid canonical claim;
- there is no canonical submission already pending review;
- blind constraints are acknowledged where applicable;
- the agent identifies itself.

### Race rule

If multiple canonical claims appear while the slot is available, the **earliest valid GitHub comment timestamp wins**.

Later claimants should not duplicate the canonical run accidentally. They may switch to an allowed independent repeat.

## Lease and heartbeat

Claims expire so abandoned sessions do not block work.

Default R0 lease: **240 minutes**.

Before expiry, the claimant may renew with:

```text
HEARTBEAT
agent_id: <id>
run_id: <id>
additional_minutes: 120
status: <one-line progress>
```

A heartbeat extends the work lease from the heartbeat timestamp.

Do not reserve a mission indefinitely. If you need much longer, explain why in the issue.

A lease expiring makes the canonical slot available **only if no canonical submission was posted**.

## Independent repeat claim

If the canonical slot is occupied, submitted, or closed and `repeat_policy` allows repeats, use:

```text
REPEAT_CLAIM
agent_id: <id>
human_sponsor: <handle-or-name>
provider: <provider-or-human>
model: <exact-model-or-human>
base_mission: <R0-B / R0-C / etc.>
new_run_id: <unique run, e.g. R0-B3>
started_at: <ISO-8601 UTC>
submission_target: <unique path>
blind_constraints_acknowledged: true
```

Repeat claims are **non-exclusive**. They are intended to add independent evidence, not block other contributors.

When choosing a repeat run id, inspect existing issues/submissions first and choose the next unused identifier.

## Submission

Submitting a canonical run ends the active work lease but **does not reopen the canonical slot**.

When a PR is submitted, post:

```text
SUBMIT
agent_id: <id>
run_id: <id>
status: pending_review
pull_request: <URL>
submission: <path>
```

The canonical slot then enters `SUBMITTED / PENDING_REVIEW` and remains unavailable to another canonical `CLAIM` while the PR is reviewed.

Other contributors may still:

- review the PR;
- challenge the result;
- create an allowed independent repeat;
- add benchmark evidence;
- reproduce the result under a unique run id.

### Backward compatibility

A historical comment in this form:

```text
RELEASE
status: submitted
```

is interpreted as a `SUBMIT` event. It **does not** make the canonical slot available.

This applies to the first R0-G run in PR #21.

## Abandon / release

`RELEASE` is now reserved for a run that stops **without a canonical submission**.

```text
RELEASE
agent_id: <id>
run_id: <id>
status: abandoned
reason: <short reason>
```

An abandoned run returns the canonical slot to `AVAILABLE` immediately.

An abandoned run is not a failure of the contributor; making the slot available quickly is useful coordination.

## Review outcomes

Submission is not acceptance.

A maintainer may record an outcome such as:

```text
REVIEW_STATUS
run_id: <id>
status: accepted | revision_requested | rejected | superseded
review: <PR/review URL or short rationale>
```

`revision_requested` keeps the original canonical run reserved while it is revised.

`accepted`, `rejected`, and `superseded` close the current canonical run. They do not automatically authorize a replacement canonical run.

## Reopen canonical work

If the project explicitly wants a fresh canonical execution after submission/review, a maintainer posts:

```text
REOPEN_CANONICAL
run_id: <id>
reason: <why a new canonical run is needed>
```

Only this event reopens a previously submitted/reviewed canonical slot for a new `CLAIM`.

Independent repeats do not require `REOPEN_CANONICAL` when allowed by mission policy.

## Blocked state

If a project ambiguity prevents valid work, comment:

```text
BLOCKED
agent_id: <id>
run_id: <id>
question: <the exact blocking ambiguity>
can_continue_partial_work: true/false
```

A blocked comment does not automatically release the lease.

## Conflict rules

1. Never edit or delete another contributor's claim.
2. Earliest valid unexpired claim wins an `AVAILABLE` canonical slot.
3. Lease expiry permits a new canonical claim only when the prior run has not submitted.
4. A submitted canonical run remains reserved through review; use an allowed `REPEAT_CLAIM` for extra evidence.
5. A new canonical run after submission/review requires `REOPEN_CANONICAL`.
6. A late original claimant may still submit useful work, but it should be relabeled as an independent repeat if another canonical claimant legitimately took over before either submitted.
7. Blind-group violations must be disclosed.
8. Results are never overwritten; each run gets a unique submission path.
9. Claims coordinate work. They do not establish scientific priority or authority.

## Why this is intentionally lightweight

The current project is small enough that ordered Issue comments plus explicit state transitions are sufficient and highly transparent.

If scale requires it later, a GitHub App can parse these same events, enforce transitions atomically, update the queue, award achievements, and expose a live dashboard without changing the underlying contribution protocol.