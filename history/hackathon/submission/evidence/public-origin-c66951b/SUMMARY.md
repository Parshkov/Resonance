# Deployment evidence — public origin @ c66951b (engine 0.2, readiness)

- **Commit under test:** `c66951b49faa01a9862077af6807360444e06774` (main, squash of #159 on top of #158 `443ba1c`)
- **Origin:** https://resonance-production-cfe3.up.railway.app · **MCP:** https://resonance-production-cfe3.up.railway.app/mcp
- **Railway:** project `670bcce5-…`, service `resonance` `172aa183-…`, environment `production`
- **Method:** Railway MCP (deployments, variables, logs) plus the Resonance custom connector in claude.ai, which reaches `/mcp` through the hosted-client path. The Claude Code sandbox itself cannot open the public origin (proxy `CONNECT` 403), so the stdlib acceptance scripts were **not** run here. No tokens, codes or raw text recorded; pseudonyms only.

| Step | What | Result | UTC | Evidence |
|---|---|---|---|---|
| D1 | auto-deploy of `c66951b` from `main` | SUCCESS, deployment `c3da2cae` | 19:13:20Z | Railway deployments |
| D2 | `RESONANCE_PURGE_DEMO=1` → redeploy `275c646c` | SUCCESS; log `purge-demo: sessions_deleted=0 users_revoked=0` | 19:13:48Z | Railway deploy log |
| D3 | `RESONANCE_PURGE_DEMO=` (empty) → redeploy `357dd391` | SUCCESS; startup log has no purge line; `oauth: core attached … grants durable`; `mode: LIVE+WebMCP` | 19:17:14Z | Railway deploy log |
| H1 | `resonance_whoami` via the claude.ai connector | `index_current: true`, `db_generation = serving_generation = 348` | 19:1xZ | `hosted-connector-discover.json` |
| H2 | `resonance_discover(k=8)` from the volunteer thought "Irrigation retry storms after pressure drops" | 8 rows, `rejected: []`; every row carries `display.demo_persona: false` and `confidence ∈ {high, medium, low}` (engine 0.2 fields) | 19:1xZ | same |
| H3 | `resonance_explain_match` on the top row | same evidence block as the discover row; verdict `approximate`, 5/7 relations preserved, 1 contradiction | 19:1xZ | same |

## Observations

- **Demo personas were not present in production.** The purge found no session with `record_kind != volunteer` and no demo persona account that was not already hidden; `db_generation` stayed at 348 (no write). `ops/TEST_READINESS.md` previously assumed 25 seeded personas were still there; that assumption was wrong for this database. `corpus.demo_personas_present` is therefore `false` by construction on `c66951b`.
- **Engine 0.2 verdicts on real production rows.** The irrigation retry-storm thought against "Retry storm overloads delivery queue" (the classical A/A' pair): `approximate`, structural 0.776, `r_direct` 0.714, one contradiction (the irrigation graph's `pipe overload supports cycle failure` has no preserved counterpart), confidence `low`. Under engine 0.1 this pair was `analogical` (structural 0.88 in the 01193f1 evidence). The v0.2 verdict is recorded as returned; whether one contradicting relation should demote an otherwise systematic mapping from `analogical` to `approximate` is a scoring-policy question for the human gold review (ADR-0004), not something to tune here.
- Panic-buying rows (B family): `negative`, confidence `high`, structural 0.626 with `semantic` 0.115 — same role skeleton, different concepts, correctly refused as analogy. Observability rows (C family): `negative`, structural 0.302.
- **Corpus hygiene.** The live corpus holds duplicated guest sessions from repeated acceptance runs: 4× "Panic buying after a shortage rumour", 4× "Retry and outage observability", 2× "Shared thought". They are `volunteer` rows (created through the real guest flow by `submission/evidence/abc_mcp_test.py` and manual card runs), so `purge-demo` does not and must not touch them. Cleaning them needs either the owner deleting those sessions or an acceptance script that revokes its own guests at the end.

## Deviations

None from the intended deploy → purge → clear sequence. The purge count differed from the documented expectation (0 instead of 25); see above.
