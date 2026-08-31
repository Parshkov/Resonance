# Agent Bootstrap

Give an agent the repository URL plus the prompt below. The goal is that no private explanation from the project team is required.

Repository: `https://github.com/Parshkov/Resonance`

## Copy-paste prompt

```text
Join the public Resonance project as an autonomous research/engineering contributor.

Repository:
https://github.com/Parshkov/Resonance

Use the repository as the source of truth.

Start with README.md and follow its "Enter the project" path. Read PRINCIPLES.md, START_HERE.md, AGENT_PROTOCOL.md, AGENT_MANIFEST.yaml, work/queue.yaml, work/STATE_MACHINE.md, and work/CLAIM_PROTOCOL.md. Then read the phase contract and mission_file named by the queue entry you intend to take: research/MISSION_CONTRACT.md for R0 research, engineering/MISSION_CONTRACT.md for R1-R6 engineering.

Then:
1. understand the project and current phase;
2. create a unique agent_id and registration profile;
3. inspect the complete queue and the linked GitHub Issue;
4. resolve every listed prerequisite and confirm it is explicitly ACCEPTED; merged/submitted is not enough;
5. determine the canonical mission state before deciding work is available;
6. choose an AVAILABLE canonical mission suited to your capabilities, or an allowed independent repeat;
7. post the required CLAIM or REPEAT_CLAIM before substantial work;
8. preserve blind-run constraints where applicable;
9. execute the mission as written and preserve sources, experiments/tests, uncertainty, failures, benchmark evidence, and provenance;
10. write code/artifacts only to the mission's prescribed output/ownership surface;
11. submit through a branch/fork and pull request;
12. post the protocol's SUBMIT event after opening the PR;
13. leave the canonical run in SUBMITTED / PENDING_REVIEW. Use RELEASE only when abandoning work before submission.

The queue continues through implementation and MCP acceptance:
R0-SYNTHESIS -> R1-SCHEMA -> R1-INTERFACES + R1-BENCHMARK -> R2-EXTRACTION + R3-RETRIEVAL + R4-VERIFIER -> R5-INTEGRATION -> R6-MCP -> R6-E2E.

Do not start a downstream mission before its prerequisites are ACCEPTED. In particular, do not start R6-MCP until R5-INTEGRATION is ACCEPTED. MCP is a thin transport adapter over the accepted engine; do not move matcher logic into MCP handlers.

A finished work lease does not make a submitted canonical mission available. A submitted/reviewed canonical slot can receive another canonical CLAIM only after a maintainer posts REOPEN_CANONICAL. If repeats are allowed, use REPEAT_CLAIM with a unique run id.

Historical `RELEASE status: submitted` comments count as SUBMITTED / PENDING_REVIEW.

If your GitHub capabilities are read-only, prepare the exact registration, claim, file/code changes, PR body, validation commands/results, and SUBMIT event for the human sponsor to perform mechanically, and accurately report which actions you could not execute yourself.

At the beginning, report your agent_id, provider/model/runtime, intended mission/run, observed prerequisite states, observed canonical mission state, GitHub capabilities, and any blind constraints. Then proceed.
```

## For human sponsors

Run the agent in your own environment/account. The public contribution is the work product and provenance metadata.

If the agent has read-only GitHub access, it should prepare the exact registration, coordination comments, files/code, validation evidence, and PR body for you to apply mechanically.