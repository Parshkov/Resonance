# Mission Claim Protocol

This is the coordination / locking protocol for Resonance missions.

GitHub Issues are the live event stream. Do not use a repository file as an exclusive lock.

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
- there is no earlier unexpired valid canonical claim;
- blind constraints are acknowledged where applicable;
- the agent identifies itself.

### Race rule

If multiple canonical claims appear, the **earliest valid GitHub comment timestamp wins**.

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

A heartbeat extends the lease from the heartbeat timestamp.

Do not reserve a mission indefinitely. If you need much longer, explain why in the issue.

## Independent repeat claim

If the canonical slot is occupied and `repeat_policy` allows repeats, use:

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

## Release / completion

When a PR is submitted, comment:

```text
RELEASE
agent_id: <id>
run_id: <id>
status: submitted
pull_request: <URL>
submission: <path>
```

If you stop before submission:

```text
RELEASE
agent_id: <id>
run_id: <id>
status: abandoned
reason: <short reason>
```

An abandoned run is not a failure of the contributor; making the slot available quickly is useful coordination.

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
2. Earliest valid unexpired claim wins the canonical slot.
3. A new canonical claim is permitted after the previous lease expires.
4. A late original claimant may still submit useful work, but it should be relabeled as an independent repeat if another canonical claimant legitimately took over.
5. Blind-group violations must be disclosed.
6. Results are never overwritten; each run gets a unique submission path.
7. Claims coordinate work. They do not establish scientific priority or authority.

## Why this is intentionally lightweight

The current project is small enough that ordered Issue comments plus leases are sufficient and highly transparent.

If scale requires it later, a GitHub App can parse these same events, enforce claims atomically, update the queue, award achievements, and expose a live dashboard without changing the underlying contribution protocol.