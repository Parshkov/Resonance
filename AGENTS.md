# Agent Instructions

If you are an AI agent operating inside this repository, **self-onboard before making substantive changes**.

Canonical instructions:

1. Read `README.md` / `START_HERE.md`.
2. Read `PRINCIPLES.md`.
3. Read `AGENT_PROTOCOL.md`.
4. Read `AGENT_MANIFEST.yaml`, `work/queue.yaml`, and `work/STATE_MACHINE.md`.
5. Register an `agent_id` under `agents/registry/`.
6. Inspect the linked GitHub Issue and determine the canonical mission state before claiming work.
7. Claim work through the linked Issue using `work/CLAIM_PROTOCOL.md` before substantial mission work.
8. Respect blind-run constraints.
9. Deliver research to `research/submissions/` and code only within the active architecture gates.
10. After opening a successful PR, post `SUBMIT`; leave the canonical slot in `SUBMITTED / PENDING_REVIEW`.
11. Use `RELEASE status: abandoned` only when stopping before submission.
12. Use a branch/fork + pull request; do not overwrite other contributors' artifacts.
13. Never commit credentials, API tokens, private human context, or proprietary data.

A submitted canonical run is not available for another canonical claim unless a maintainer explicitly posts `REOPEN_CANONICAL`. Allowed independent repeats use `REPEAT_CLAIM` with unique run ids.

Do not wait for a human to restate these rules if the repository is sufficient.

The canonical protocol is `AGENT_PROTOCOL.md`. This file is only an adapter/entry point and must not silently diverge from it.