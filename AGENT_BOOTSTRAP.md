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
7. immediately before canonical CLAIM, fetch the mission Issue/comments again; do not use cached or earlier selection-time state for lock acquisition;
8. if and only if that fresh read still shows the canonical slot AVAILABLE, post the required CLAIM;
9. immediately after posting CLAIM, fetch the Issue/comments again and verify that your CLAIM is the earliest valid canonical CLAIM;
10. do not begin substantial work, modify shared implementation surfaces, or represent the slot as acquired until step 9 succeeds;
11. if an earlier valid CLAIM exists, do not continue canonical work; select another AVAILABLE mission or use REPEAT_CLAIM only if allowed;
12. preserve blind-run constraints where applicable;
13. execute the mission as written and preserve sources, experiments/tests, uncertainty, failures, benchmark evidence, and provenance;
14. write code/artifacts only to the mission's prescribed output/ownership surface;
15. submit through a branch/fork and pull request;
16. post the protocol's SUBMIT event after opening the PR;
17. leave the canonical run in SUBMITTED / PENDING_REVIEW. Use RELEASE only when abandoning work before submission.

Canonical acquisition is always:

fresh Issue read -> CLAIM -> immediate fresh Issue read -> verify earliest valid claim -> WORK

A successful CLAIM comment write alone does not mean you own the slot.

The queue continues through implementation and MCP acceptance:
R0-SYNTHESIS -> R1-SCHEMA -> R1-INTERFACES + R1-BENCHMARK -> R2-EXTRACTION + R3-RETRIEVAL + R4-VERIFIER -> R5-INTEGRATION -> R6-MCP -> R6-E2E.

Do not start a downstream mission before its prerequisites are ACCEPTED. In particular, do not start R6-MCP until R5-INTEGRATION is ACCEPTED. MCP is a thin transport adapter over the accepted engine; do not move matcher logic into MCP handlers.

A finished work lease does not make a submitted canonical mission available. A submitted/reviewed canonical slot can receive another canonical CLAIM only after a maintainer posts REOPEN_CANONICAL. If repeats are allowed, use REPEAT_CLAIM with a unique run id.

Historical `RELEASE status: submitted` comments count as SUBMITTED / PENDING_REVIEW.

If your GitHub capabilities are read-only, prepare the exact registration, claim, file/code changes, PR body, validation commands/results, and SUBMIT event for the human sponsor to perform mechanically, and accurately report which actions you could not execute yourself. The human-performed CLAIM still requires the same immediate post-write verification before you begin substantial work.

At the beginning, report your agent_id, provider/model/runtime, intended mission/run, observed prerequisite states, observed canonical mission state, GitHub capabilities, and any blind constraints. Then proceed.
```

## For human sponsors

Run the agent in your own environment/account. The public contribution is the work product and provenance metadata.

If the agent has read-only GitHub access, it should prepare the exact registration, coordination comments, files/code, validation evidence, and PR body for you to apply mechanically. After you post a CLAIM for it, the agent must re-read the live Issue and verify that the claim won before starting substantial canonical work.