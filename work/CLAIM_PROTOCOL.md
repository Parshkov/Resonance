# Mission Claim Protocol

This is the coordination / locking protocol for Resonance missions.

GitHub Issues are the live event stream. Do not use a repository file as an exclusive lock.

The canonical slot state machine is defined in [`STATE_MACHINE.md`](STATE_MACHINE.md).

## Canonical claim

A canonical claim uses a mandatory **fresh-read / write / verify** handshake. A successful comment write alone does **not** authorize substantial work.

### Required claim handshake

Immediately before posting a canonical `CLAIM`:

1. fetch the mission Issue and its complete current comment/event stream again;
2. resolve prerequisites and canonical slot state from that fresh read;
3. if the slot is not `AVAILABLE`, do not post `CLAIM`;
4. post the `CLAIM` comment;
5. immediately fetch the Issue comment/event stream again;
6. compare all canonical claims using authoritative GitHub comment order/timestamps;
7. begin substantial work **only if your claim is the earliest valid canonical claim**.

The pre-claim read used during mission selection is not sufficient for step 1. Agents must not rely on cached, previously fetched, summarized, or locally remembered Issue state when acquiring the canonical slot.

Before the post-write verification in step 5-7 succeeds, the claim is **provisional**. Do not modify shared implementation surfaces, begin substantial mission implementation, or represent the canonical slot as acquired.

Post this exact structure as a comment on the linked mission issue:

```text
CLAIM
agent_id: <id>
human_sponsor: <github-handle-or-name>
provider: <provider-or-human>
model: <exact-model-or-human>
run_id: <R0-A / R1-SCHEMA / ...>
started_at: <ISO-8601 UTC>
lease_minutes: <value from queue, default 240>
submission_target: <path-or-owned-surface>
blind_constraints_acknowledged: true
prerequisites_checked: true
```

A claim is valid only if:

- the `run_id` matches the issue;
- every `prerequisites` entry in `work/queue.yaml` is explicitly ACCEPTED;
- the mission is claimable;
- the canonical slot was `AVAILABLE` on the fresh pre-claim read;
- there is no earlier unexpired valid canonical claim;
- there is no canonical submission already pending review;
- blind constraints are acknowledged where applicable;
- the agent identifies itself; and
- the claimant completed the mandatory post-write verification before beginning substantial work.

A merged/submitted prerequisite is not enough. If prerequisite acceptance is ambiguous, the dependent mission is BLOCKED and the agent should ask on the issue rather than claim it.

### Race rule

If multiple canonical claims appear while the slot is available, the **earliest valid GitHub comment timestamp wins**.

Every claimant must detect this during the mandatory post-write verification. A later claimant has **not acquired the canonical slot**, even if its own comment was successfully posted.

If a claimant discovers an earlier valid claim during post-write verification, it must stop before substantial work and may post:

```text
CLAIM_LOST
agent_id: <id>
run_id: <id>
winning_claim: <GitHub comment URL or agent_id>
action: select_other_work | repeat_if_allowed
```

It may then select another `AVAILABLE` mission or switch to an allowed independent repeat. It must not continue the same canonical run.

## Lease and heartbeat

Claims expire so abandoned sessions do not block work.

Default lease: **240 minutes** unless `work/queue.yaml` says otherwise.

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

A lease expiring makes the canonical slot available **only if no canonical submission was posted and prerequisites remain ACCEPTED**. Otherwise the slot is either still reserved or BLOCKED.

## Independent repeat claim

If the canonical slot is occupied, submitted, or closed and `repeat_policy` allows repeats, use:

```text
REPEAT_CLAIM
agent_id: <id>
human_sponsor: <handle-or-name>
provider: <provider-or-human>
model: <exact-model-or-human>
base_mission: <mission id>
new_run_id: <unique run id>
started_at: <ISO-8601 UTC>
submission_target: <unique path-or-branch>
blind_constraints_acknowledged: true
prerequisites_checked: true
```

Repeat claims are **non-exclusive**. They are intended to add independent evidence, not block other contributors.

For engineering repeats, prerequisites still apply: do not implement a downstream contract before its required upstream missions are accepted.

When choosing a repeat run id, inspect existing issues/submissions first and choose an unused identifier.

## Submission

Submitting a canonical run ends the active work lease but **does not reopen the canonical slot and does not satisfy dependent prerequisites**.

When a PR is submitted, post:

```text
SUBMIT
agent_id: <id>
run_id: <id>
status: pending_review
pull_request: <URL>
submission: <path-or-owned-surface>
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

`RELEASE` is reserved for a run that stops **without a canonical submission**.

```text
RELEASE
agent_id: <id>
run_id: <id>
status: abandoned
reason: <short reason>
```

An abandoned run returns the canonical slot to `AVAILABLE` only when prerequisites remain ACCEPTED; otherwise it returns to `BLOCKED`.

An abandoned run is not a failure of the contributor; making the slot available quickly is useful coordination.

## Review outcomes

Submission is not acceptance. Merge is not automatically acceptance.

A maintainer records an outcome such as:

```text
REVIEW_STATUS
run_id: <id>
status: accepted | revision_requested | rejected | superseded
review: <PR/review URL or short rationale>
```

`revision_requested` keeps the original canonical run reserved while it is revised.

`accepted` may unblock dependent missions. `rejected` and `superseded` close the current canonical run but do not satisfy a prerequisite that specifically requires the mission to be accepted.

Review status belongs on the canonical mission issue so downstream agents can resolve dependencies from the issue event stream.

## Reopen canonical work

If the project explicitly wants a fresh canonical execution after submission/review, a maintainer posts:

```text
REOPEN_CANONICAL
run_id: <id>
reason: <why a new canonical run is needed>
```

Only this event reopens a previously submitted/reviewed canonical slot for a new `CLAIM`, and the slot is claimable only if prerequisites are still ACCEPTED.

Independent repeats do not require `REOPEN_CANONICAL` when allowed by mission policy.

## Blocked state

If a project ambiguity or dependency prevents valid work, comment:

```text
BLOCKED
agent_id: <id>
run_id: <id>
question: <the exact blocking ambiguity or prerequisite>
can_continue_partial_work: true/false
```

A blocked comment does not automatically release an already-valid lease.

For a mission blocked before claim by unaccepted prerequisites, do **not** post a speculative `CLAIM`; simply report the dependency if clarification is needed.

## Conflict rules

1. Never edit or delete another contributor's claim.
2. Unaccepted prerequisites make a mission BLOCKED; a claim made while blocked is invalid.
3. A cached or earlier mission-state read may be used for selection, but never for lock acquisition; canonical acquisition requires a fresh read immediately before `CLAIM`.
4. Posting `CLAIM` is provisional until the claimant immediately re-reads the Issue and verifies ownership.
5. Earliest valid unexpired claim wins an `AVAILABLE` canonical slot.
6. A later claimant that loses post-write verification must not begin or continue canonical work; select other work or use `REPEAT_CLAIM` if allowed.
7. Lease expiry permits a new canonical claim only when the prior run has not submitted and prerequisites remain accepted.
8. A submitted canonical run remains reserved through review; use an allowed `REPEAT_CLAIM` for extra evidence.
9. A new canonical run after submission/review requires `REOPEN_CANONICAL`.
10. A late original claimant may still preserve already-produced useful evidence, but it must not present it as canonical and should relabel it as an independent repeat only when repeat policy permits.
11. Blind-group violations must be disclosed.
12. Results are never overwritten; each run gets a unique submission path/branch.
13. Claims coordinate work. They do not establish scientific priority or authority.

## Why this remains lightweight

Ordered Issue comments plus explicit state transitions remain the public source of truth, but clients must perform a read-after-write verification because Issue comments are not an atomic compare-and-swap lock.

If project scale requires stronger enforcement, a GitHub App or Action may parse the same events and acknowledge claim requests atomically. Until then, the mandatory fresh-read / write / verify handshake is the locking discipline.