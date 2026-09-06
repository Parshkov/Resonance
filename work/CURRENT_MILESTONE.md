# Current Milestone Selection Policy

This file controls **autonomous mission selection**. It does not rewrite the historical record and it does not delete old missions.

## Current product milestone

The R10–R17 product chain is **built and deployed**. R17's original target (the
WebMCP Challenge submission) is closed and its record is in
`archive/hackathon/`. Pointing arriving agents at R10–R17 therefore sends them
at a milestone with no available work, which is what this file did until
2026-09-06.

The active milestone is **R18 — evidence and scale**, and it is deliberately
short. The product exists; what it does not have is proof that its central
claim survives contact with reality.

| id | work | why it is the milestone |
| --- | --- | --- |
| R18-A | A whole-thought **embedding baseline** on Benchmark v0.2, reported beside engine 0.2 | `WHY_NOT.md` rejects embeddings and ADR-0004 names "the lexicon channel adds nothing over whole-thought embeddings" as the condition for reconsidering. That comparison has never been run. It is the project's own falsification test. |
| R18-B | **Scale replay** at 10^4–10^5 graphs | Measured today: 148 ms at 176 graphs rising to 580 ms at 1408, linear from 352 up. ADR-0004 names non-sub-linear posting lists as a reconsideration condition, and `_require_bound()` re-hashes the corpus per query. |
| R18-C | **Human review of the v0.2 gold** | Every gold label and every benchmark graph is agent-authored. No external claim about `classification_accuracy` should outlive this. Settling ADR-0005 needs it too. |
| R18-D | A corpus of **real extracted thoughts**, consented, with two-human gold | The lexicon scored 0.00–0.07 on real pairs (ADR-0006). Everything measured so far is measured on authored graphs. |
| R18-E | **Continuous integration** actually running on pull requests | Added on the audit branch, never yet exercised on a PR. Until it runs, "the suite passes" is a claim about one machine. |

R18-A and R18-C are the two that can falsify the project. Prefer them.

**Where the numbers in this table come from:** `docs/STATUS.md`, section
"2026-09-06 audit corrections" and "What is not validated".

## Historical phases are archived for autonomous selection

Phases **R0 through R17 are archived for autonomous selection** (R0–R9 since
2026-09-01, R10–R17 since 2026-09-06 — they are built, deployed and evidenced).

An agent MUST NOT autonomously choose a new `REPEAT_CLAIM` on an R0-R17 mission merely because:

- its canonical slot is occupied, submitted, accepted, closed, or otherwise unavailable;
- `repeat_policy` in `work/queue.yaml` says `allowed` or `allowed_after_unique_run_id`;
- all currently visible product implementation slots are occupied or blocked.

For R0-R17, `repeat_policy: allowed` means the repeat is **protocol-permitted when explicitly requested**, not that it should be selected as fallback work by an autonomous agent.

A historical repeat requires one of:

1. an explicit human request for that repeat;
2. an explicit maintainer comment such as `MAINTAINER_REPEAT_GO` naming the mission/run; or
3. a current-milestone issue/review that specifically asks for historical reproduction as evidence.

Without one of those, do not post `REPEAT_CLAIM` on R0-R17.

## What to do when current product slots are occupied

Do not go backwards in the roadmap just to stay busy.

Use this order:

1. take an AVAILABLE canonical mission in the current R18 milestone whose prerequisites are accepted;
2. take an explicitly requested recovery/takeover of a current-milestone mission;
3. independently review/reproduce a current-milestone submitted PR when a review is useful and independence requirements permit it;
4. perform clearly additive maintainer-approved current-milestone documentation/integration work;
5. if none applies, report that no suitable current-milestone work is available rather than manufacturing historical repeat work.

Downstream missions remain blocked until their prerequisites are explicitly ACCEPTED. Do not claim them early.

## Current critical path

`R18-A embedding baseline` and `R18-C human gold review` in parallel, then
`R18-B scale replay` and `R18-D real corpus`; `R18-E CI` is independent and can
be taken at any time.

The delivered chain behind this milestone, for orientation only:
`R10 WebMCP -> R11 Persistence -> R12 Identity/Consent + R12B Security + R12C Ingestion -> R13 Live Product -> R13B Rich Results -> R14 Collaboration -> R14B Workspaces -> R15 Remote MCP -> R16 Deployment`.

## A note on how the last hundred commits were made

Between the `0aea577` freeze and 2026-09-06 the product was reworked over ~107
commits on `ux/*` and `claude/*` branches, driven directly by the maintainer,
outside the claim protocol. That is a legitimate way for a maintainer to work
and it is recorded here rather than hidden, but it means the queue stopped
describing the live state for several days. If it happens again, update this
file at the end of the run.

## Why this rule exists

The repository intentionally preserves old missions and allows independent repeats because they are valuable research evidence. Once the project advances to a later milestone, however, unrestricted fallback repeats can waste scarce agent/runtime capacity and make an autonomous agent appear to regress the roadmap.

Preserve the old work. Do not autonomously re-run it unless the current project actually asks for it.
