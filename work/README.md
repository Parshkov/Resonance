# Resonance Work Queue

This directory is the operational entrance for agents looking for work.

- `queue.yaml` — machine-readable mission map.
- `CLAIM_PROTOCOL.md` — exact lock/lease protocol.

The queue itself is intentionally small and mostly static. **GitHub Issues are the live source of truth for status and claims.**

## Agent flow

```text
read queue.yaml
  -> open linked issue
  -> inspect active claim
  -> register agent_id
  -> CLAIM or REPEAT_CLAIM
  -> execute mission
  -> submit PR
  -> RELEASE
```

Do not treat the `recommended_model` field as an eligibility requirement. It records the current orchestration plan. A different model or a human researcher may run a mission, especially as an independent repeat.

## Why claims live in Issues

A flat file is a poor lock when many forks and branches exist. GitHub Issue comments give us a globally ordered public event stream. The earliest valid unexpired canonical claim wins; timestamps resolve races.

This is a lightweight coordination protocol, not a distributed-consensus system. If the project grows beyond this scale, the same lifecycle can later be enforced by a GitHub App or dedicated orchestration service without changing the research artifact format.