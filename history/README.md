# History

Resonance was built between 2026-08-29 and 2026-09-06 as a public experiment in
human–agent collaboration: missions were claimed through GitHub Issues by
independent agents running different models, some of them deliberately blind to
one another, and every submission, review, disagreement and rejected method was
committed.

That phase is over. The product is built and deployed, and the work continues
as individual refinement. **Nothing in this directory is an instruction.** It is
the record of how the project got here, kept because the reasoning is worth more
than the conclusion.

Nothing here is maintained, and some of it is contradicted by the current code.
For what is true now, read [`../README.md`](../README.md) and
[`../docs/STATUS.md`](../docs/STATUS.md).

| | |
|---|---|
| `research/` | R0 research: mission briefs, 16 independent submissions, 10 comparative and adversarial reviews, the logbook |
| `engineering/` | the R1–R15 engineering mission contracts, as they were written |
| `agents/registry/` | 35 registered `agent_id` profiles — who ran what, under whose sponsorship, with which model |
| `hackathon/` | the WebMCP Challenge build record, the release manifest, and the executed acceptance evidence including what did **not** pass |
| `AGENT_PROTOCOL.md` | the coordination protocol: claims, leases, blind runs, submission and review |
| `mission-queue.yaml` | the full mission and dependency map (was `work/queue.yaml`) |

## What the record is good for

The architecture decisions that survived are in
[`../docs/decisions/`](../docs/decisions/) and are still live — they describe
the engine that runs today. What is *here* is the evidence underneath them: why
a method was rejected, which independent runs disagreed, and what was measured
before a threshold moved.

Two things in here are worth reading even now:

- `hackathon/submission/evidence/` — acceptance runs against the live origin,
  recorded with their failures intact, including the native WebMCP browser run
  (Chrome 152, `--enable-features=WebMCP`, 24/24).
- `research/reviews/` — where two independent agents reached different answers
  to the same architecture question, which is what the blind runs were for.
