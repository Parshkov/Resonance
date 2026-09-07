# Working in this repository

Resonance is built and deployed. It is now maintained by one person with AI
assistance, not by a group of independently claiming agents.

There is no mission queue, no claim protocol, no lease and no registration step.
If you are an agent working here, you have been asked to do something specific —
do that.

## Read first

1. [`README.md`](README.md) — what Resonance is and how it works.
2. [`docs/STATUS.md`](docs/STATUS.md) — **what is true right now**, including
   what is measured and what is not. This is the file that is kept current.
3. [`docs/decisions/`](docs/decisions/) — the accepted architecture, and the one
   question deliberately left open.
4. [`PRINCIPLES.md`](PRINCIPLES.md) — the rules the project holds itself to.

## How work is done

- Branch, commit, open a pull request. CI runs the suite and both benchmark
  gates on every PR; it must be green.
- The tests need PostgreSQL — see the README. There is one store, and it is the
  one production runs.
- **Benchmark gold is frozen.** Do not edit `benchmark/` fixtures to make a
  change pass; CI fails if they move.
- Do not weaken a claim to make it true. If something does not work, say so in
  `docs/STATUS.md` with the evidence — that file is worth more than a green
  headline.
- Never commit credentials, tokens, or private human context.

## What not to trust

[`history/`](history/) holds the record of how the project was built: research
submissions, mission contracts, the old coordination protocol, hackathon
evidence. **None of it is an instruction, and some of it is contradicted by the
current code.** Read it for reasoning, not for orders.
