# Engineering Mission Contract

This contract applies to implementation missions after the R0 architecture gate. It complements `AGENT_PROTOCOL.md`, `work/STATE_MACHINE.md`, and `work/CLAIM_PROTOCOL.md`.

## 1. Start conditions are hard gates

Do not start a mission whose `prerequisites` in `work/queue.yaml` are not ACCEPTED. A merged PR is not automatically scientific/engineering acceptance unless the maintainer has closed the prerequisite mission as accepted or explicitly recorded acceptance.

In particular, no core implementation begins before R0-SYNTHESIS is ACCEPTED, and R6-MCP remains blocked until R5-INTEGRATION is ACCEPTED.

## 2. Read before coding

Before CLAIM:

1. read the accepted synthesis/ADRs relevant to the mission;
2. read the mission file and GitHub Issue chronologically;
3. inspect current `main` interfaces and tests;
4. determine the live mission state from the issue;
5. state any unresolved dependency or architecture ambiguity instead of inventing an answer.

## 3. Branch and ownership

Use `agent/<agent_id>/<run-id>` or a fork. Keep changes inside the mission's declared ownership surface unless an interface change is required. If an accepted shared interface must change, stop and raise the incompatibility on the mission issue before changing it.

Do not overwrite another contributor's code, provenance, benchmark gold, or accepted decision records merely to make your branch pass.

## 4. Engineering submission requirements

A canonical engineering PR must include:

- implementation code and tests;
- exact commands used to run validation;
- dependency/runtime versions when material;
- benchmark/config/fixture hashes when applicable;
- measured results against the mission acceptance gate;
- explicit failures and unsupported modes;
- provenance (`agent_id`, sponsor, provider/model or human method, tools/runtime used);
- a short handoff describing public interfaces added/changed.

Do not submit only a design document when the mission asks for implementation.

## 5. Evidence over claims

A claim such as "passes", "deterministic", "fast", "scale-ready", or "compatible" must point to an executable test, benchmark output, or reproducible command. Synthetic-scale evidence must remain labelled synthetic. Do not convert a toy result into a production claim.

## 6. Frozen benchmark discipline

Calibration data may guide configuration. Immutable gate data must not be rewritten or re-labelled to make the current engine pass. A gate failure is a valid mission result and must remain visible.

If the benchmark contract changes, version it rather than silently editing the old gate.

## 7. Core/MCP boundary

The Resonance engine must run without MCP installed or configured. MCP is a transport adapter over accepted engine APIs. No retrieval, alignment, scoring, extraction, or benchmark logic may exist only inside MCP handlers.

## 8. Interface discipline

Use the accepted R1 interfaces. R2 extraction, R3 retrieval, and R4 verification should be independently testable and should not import one another's internal implementation details. Cross-module information travels through public typed contracts with version/config identifiers.

## 9. Submission lifecycle

After opening the PR, post `SUBMIT` using `work/CLAIM_PROTOCOL.md`. The canonical slot remains `SUBMITTED / PENDING_REVIEW` until maintainer review. Revision requests update the same run/PR unless the maintainer explicitly reopens canonical work.

## 10. Definition of done

A mission is done only when its acceptance gate is measured and the maintainer records ACCEPTED. Passing CI alone is not acceptance. Merging code alone is not acceptance. The next dependent mission may begin only after acceptance is explicit.