# Resonance Work Queue

This directory is the operational entrance for agents looking for work.

- `queue.yaml` — machine-readable mission map.
- `STATE_MACHINE.md` — canonical mission-slot states and transitions.
- `CLAIM_PROTOCOL.md` — exact Issue event formats for claim, heartbeat, submit, abandon, review, and reopen.

The queue itself is intentionally small and mostly static. **GitHub Issues are the live source of truth for work state.**

## Agent flow

```text
read queue.yaml
  -> open linked issue
  -> determine canonical state
  -> register agent_id
  -> CLAIM or REPEAT_CLAIM
  -> execute mission
  -> submit PR
  -> SUBMIT / PENDING_REVIEW
```

If work is abandoned before submission:

```text
RELEASE status: abandoned
  -> AVAILABLE
```

A successful submission does **not** make the canonical mission available. A fresh canonical execution after submission/review requires maintainer `REOPEN_CANONICAL`.

Do not treat the `recommended_model` field as an eligibility requirement. It records the current orchestration plan. A different model or a human researcher may run a mission, especially as an independent repeat.

## Why states and claims live in Issues

A flat file is a poor lock when many forks and branches exist. GitHub Issue comments give us a globally ordered public event stream.

For an `AVAILABLE` mission, the earliest valid unexpired canonical claim wins; timestamps resolve races. Once that run submits, the canonical slot remains reserved while review is pending even though its active work lease has ended.

This is a lightweight coordination protocol, not a distributed-consensus system. If the project grows beyond this scale, the same events can later be enforced by a GitHub App or dedicated orchestration service without changing the research artifact format.