# Contributing

Resonance is built and deployed, and is now maintained individually. The
mission/claim protocol that ran during its construction is retired; its record
is in [`history/`](history/).

If you want to change something, open an issue or a pull request. There is no
registration step.

## Ground rules

**Evidence beats elegance.** A simpler method that survives the benchmark is
preferred to a better-sounding one that cannot be measured.

**Do not edit the gold to pass.** `benchmark/` fixtures are frozen. CI fails if
they change during a gate run. If a change makes the engine worse, that is a
result — report it.

**Say what is not true.** [`docs/STATUS.md`](docs/STATUS.md) has a section for
what is *not* validated, and it is the most valuable part of the file. A change
that narrows a claim is as welcome as one that widens it.

**Every decision leaves a trace.** If you change how the engine classifies,
move the policy version — it is carried in `verifier_config_hash`, and it is the
only thing that lets a recorded verdict be traced to the rule that produced it.
Record the reasoning in an ADR under [`docs/decisions/`](docs/decisions/).

**Never commit** credentials, access tokens, private human context, or
proprietary data.

## Running the checks

The suite needs PostgreSQL, because that is what the product runs on:

```bash
docker run -d -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=resonance_test \
    -p 55432:5432 postgres:16
pip install "psycopg[binary]"

python3 -m unittest discover -s tests
python3 benchmark/r0-v0.2/runner.py
python3 benchmark/extraction-v0.2/runner.py
python3 ops/lexicon_check.py
```

CI runs all of these on every pull request.

## Security

Report vulnerabilities privately as described in [`SECURITY.md`](SECURITY.md).
Do not open a public issue for a live vulnerability.
