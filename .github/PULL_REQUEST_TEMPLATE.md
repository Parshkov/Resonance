## What this changes

State the result plainly. A negative result, a failed experiment or a narrowed
claim is a good pull request.

## Evidence

Commands run and what they returned. For anything touching the engine, include
the gate results.

```bash
python3 -m unittest discover -s tests
python3 benchmark/r0-v0.2/runner.py
python3 benchmark/extraction-v0.2/runner.py
```

## Checklist

- [ ] CI is green.
- [ ] `benchmark/` gold is unedited (CI checks this, but say so if you tried).
- [ ] If the engine's behaviour changed, the policy version moved and an ADR
      records why.
- [ ] If a claim in `docs/STATUS.md` is now wrong, it is corrected — including
      narrowing one that was too strong.
- [ ] No credentials, tokens or private human context committed.
