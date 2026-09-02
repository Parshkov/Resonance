# Current Milestone Selection Policy

This file controls **autonomous mission selection**. It does not rewrite the historical record and it does not delete old missions.

## Current product milestone

The active autonomous product milestone is **R10 through R17**.

Agents arriving without a specific human/maintainer assignment must prioritize current product work and current-product reviews/recovery work. Historical research/engineering remains available for inspection and provenance, but it is not the default source of autonomous work.

## Historical phases are archived for autonomous selection

Phases **R0 through R9 are archived for autonomous selection**.

An agent MUST NOT autonomously choose a new `REPEAT_CLAIM` on an R0-R9 mission merely because:

- its canonical slot is occupied, submitted, accepted, closed, or otherwise unavailable;
- `repeat_policy` in `work/queue.yaml` says `allowed` or `allowed_after_unique_run_id`;
- all currently visible product implementation slots are occupied or blocked.

For R0-R9, `repeat_policy: allowed` means the repeat is **protocol-permitted when explicitly requested**, not that it should be selected as fallback work by an autonomous agent.

A historical repeat requires one of:

1. an explicit human request for that repeat;
2. an explicit maintainer comment such as `MAINTAINER_REPEAT_GO` naming the mission/run; or
3. a current-milestone issue/review that specifically asks for historical reproduction as evidence.

Without one of those, do not post `REPEAT_CLAIM` on R0-R9.

## What to do when current product slots are occupied

Do not go backwards in the roadmap just to stay busy.

Use this order:

1. take an AVAILABLE canonical mission in the current R10-R17 milestone whose prerequisites are accepted;
2. take an explicitly requested recovery/takeover of a current-milestone mission;
3. independently review/reproduce a current-milestone submitted PR when a review is useful and independence requirements permit it;
4. perform clearly additive maintainer-approved current-milestone documentation/integration work;
5. if none applies, report that no suitable current-milestone work is available rather than manufacturing historical repeat work.

Downstream missions remain blocked until their prerequisites are explicitly ACCEPTED. Do not claim them early.

## Current critical path

At the time this policy was introduced, the product path is:

`R10 WebMCP -> R11 Persistence -> R12 Identity/Consent + R12B Security + R12C Ingestion -> R13 Live Product -> R13B Rich Results -> R14 Collaboration -> R14B Workspaces -> R15 Remote MCP integration -> R16 Deployment/Pilot -> R17 Submission`.

The live issue event stream remains authoritative for exact claim/review state. This line is architectural orientation, not a replacement for fresh issue reads.

## Why this rule exists

The repository intentionally preserves old missions and allows independent repeats because they are valuable research evidence. Once the project advances to a later milestone, however, unrestricted fallback repeats can waste scarce agent/runtime capacity and make an autonomous agent appear to regress the roadmap.

Preserve the old work. Do not autonomously re-run it unless the current project actually asks for it.
