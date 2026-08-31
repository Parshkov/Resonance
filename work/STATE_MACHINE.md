# Canonical Mission State Machine

This file defines the lifecycle of a **canonical mission slot**. It exists separately from an agent's personal run lifecycle because a submitted canonical run must remain reserved while it is under review.

GitHub Issues are the live event stream. `work/queue.yaml` describes the mission, its prerequisites, and its phase; Issue comments and linked PRs determine live state.

## States

```text
BLOCKED (one or more prerequisites not ACCEPTED)
   |
   | all prerequisites explicitly ACCEPTED
   v
AVAILABLE
   |
   | CLAIM
   v
CLAIMED / WORKING
   |                 \
   | SUBMIT           \ RELEASE status: abandoned
   v                   v
SUBMITTED / PENDING_REVIEW     AVAILABLE
   |
   | maintainer review
   v
+-------------------------------+
| ACCEPTED                      |
| REVISION_REQUESTED            |
| REJECTED                      |
| SUPERSEDED                    |
+-------------------------------+
```

A terminal or review state does **not** automatically make the canonical slot available again.

Only an explicit maintainer `REOPEN_CANONICAL` event returns a submitted/reviewed canonical mission to `AVAILABLE`, and only when its prerequisites are still ACCEPTED.

## State rules

### `BLOCKED`

A mission with a non-empty `prerequisites` list is BLOCKED while any prerequisite lacks an explicit maintainer `REVIEW_STATUS ... status: accepted` (or equivalent unambiguous maintainer acceptance recorded on the prerequisite issue).

A merged PR, closed PR, successful CI run, or `SUBMIT` event is **not** prerequisite acceptance by itself.

Do not post a canonical `CLAIM` on a BLOCKED mission to reserve future work. Independent preparatory thinking may happen off-slot, but it must not mutate shared implementation surfaces or pretend the canonical mission has started.

When every prerequisite becomes ACCEPTED, the mission becomes `AVAILABLE` if no prior canonical run already occupies the slot.

### `AVAILABLE`

A new canonical `CLAIM` is allowed only when:

- all queue prerequisites are explicitly ACCEPTED;
- no valid active canonical claim exists; and
- no canonical submission is pending review; and
- no accepted/rejected/superseded canonical run remains closed unless a maintainer explicitly reopened it.

### `CLAIMED / WORKING`

The earliest valid unexpired `CLAIM` owns the canonical slot. The lease may be renewed by `HEARTBEAT`.

If the lease expires **without a submission**, the slot becomes `AVAILABLE` again only if prerequisites remain ACCEPTED; otherwise it is `BLOCKED`.

### `SUBMITTED / PENDING_REVIEW`

A canonical submission reserves the canonical slot even though active compute work is finished.

The agent posts `SUBMIT` with the PR and artifact/path. Other contributors may review, challenge, or — if the mission permits — create independent repeats, but they must not create a new canonical `CLAIM`.

Legacy `RELEASE status: submitted` comments are interpreted as `SUBMIT`, not as reopening the canonical slot.

### `REVISION_REQUESTED`

The original canonical run remains the canonical run while its PR is revised. The slot is not open to a new canonical claimant.

A maintainer may explicitly reopen the canonical slot if a fresh run is preferable.

### `ACCEPTED`, `REJECTED`, `SUPERSEDED`

These are maintainer review outcomes. None implicitly creates a new canonical slot.

`ACCEPTED` may unblock dependent missions listed in `work/queue.yaml`.

A new canonical run requires:

```text
REOPEN_CANONICAL
run_id: <canonical run>
reason: <why a new canonical execution is needed>
```

Independent repeats remain governed by `repeat_policy` and can be added without reopening the canonical slot.

## Why submission is not release

A work lease protects against abandoned compute sessions. A canonical slot protects the identity of the project's primary run. A prerequisite gate protects downstream work from starting against an unaccepted contract.

Those are different locks.

Submitting ends the **work lease**, but it does not erase the **canonical slot reservation** or satisfy downstream prerequisites. Otherwise a second agent could accidentally replace a valid run while the first PR is merely waiting for review, or begin an implementation against architecture that has not been accepted.

## Source of truth

When determining current state:

1. read the mission entry in `work/queue.yaml`;
2. resolve every `prerequisites` mission through its issue event stream;
3. if any prerequisite is not ACCEPTED, state is `BLOCKED`;
4. otherwise inspect the mission Issue in chronological order and apply these events:
   - `CLAIM`
   - `HEARTBEAT`
   - `SUBMIT`
   - `RELEASE status: abandoned`
   - `BLOCKED`
   - maintainer review outcome
   - `REOPEN_CANONICAL`

PR state is supporting evidence. The Issue event stream remains the coordination source of truth.