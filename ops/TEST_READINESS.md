# Test readiness — engine 0.2 on production

Written 2026-09-04 after PR #158 merged (`main` `443ba1c`); updated the same day
after #159 (`c66951b`) deployed and the one-time purge ran. This is the entry
point for a session whose job is to test and finish the product.

## What is deployed

| item | value |
| --- | --- |
| production origin | `https://resonance-production-cfe3.up.railway.app` |
| canonical MCP resource | `https://resonance-production-cfe3.up.railway.app/mcp` |
| Railway project / service / environment | `resonance-live` `670bcce5-…` / `resonance` `172aa183-…` / `production` `da338ecd-…` |
| deployed commit | `c66951b` (auto-deploy from `main`; deployment `357dd391`, SUCCESS 19:17 UTC) |
| entrypoint | `python3 -m src.product.competition_server … --db $RESONANCE_DB --origin $PUBLIC_ORIGIN` |
| startup log | `oauth: core attached; … grants durable` then `competition product … mode: LIVE+WebMCP` |
| engine | `resonance-engine/0.2`, scoring `resonance-score/0.2`, extractor `0.2.0` — confirm via `GET /api/product/health` → `engine.*` |

`GET /api/product/health` also reports `corpus.demo_personas_present` and
`corpus.sessions_by_kind`.

## Production clean-up — done 2026-09-04 19:13 UTC

`RESONANCE_PURGE_DEMO=1` was set on the service, the redeploy (`275c646c`)
logged `purge-demo: sessions_deleted=0 users_revoked=0`, and the variable was
cleared again (`357dd391`, no purge line). The production database held **no**
seeded demo personas (every live session is `volunteer`; `db_generation`
stayed at 348), so `corpus.demo_personas_present` is `false` on `c66951b`.
Evidence: `submission/evidence/public-origin-c66951b/`.

The procedure stays valid for a future re-seeded environment:
`RESONANCE_PURGE_DEMO=1` → redeploy → read the log line → clear the variable.
Never set `RESONANCE_SEED_DEMO=1` on production unless a demo corpus is wanted
on purpose.

## Two ways to reach the public origin from an agent session

1. **Egress-capable machine** (owner laptop, CI, or a Claude Code environment
   with full network access): run the stdlib scripts below.
2. **Hosted-client path from claude.ai**: the Resonance custom connector
   (`https://resonance-production-cfe3.up.railway.app/mcp`) is callable as
   `resonance_*` tools from any claude.ai session, including a Claude Code
   remote session whose sandbox is otherwise blocked. `whoami` → `discover` →
   `explain_match` through it is exactly Card B; the `c66951b` evidence above
   was produced that way. The Browser / "Control Chrome" connectors, when
   enabled for the session at start, cover Card A (native WebMCP page) from
   the same place. Connectors bind at session start: enable them before the
   session is created.

## Automated checks (run from a machine with public egress; the Claude Code
## web sandbox with the default network policy cannot reach the public origin)

```bash
# repository gates (any machine)
python3 -m unittest discover -s tests                 # 460 tests, 1 skip without PostgreSQL
python3 benchmark/r0-v0.2/runner.py                  # engine gates, exit 0
python3 benchmark/extraction-v0.2/runner.py          # extractor gates, exit 0

# public origin, discovery-driven OAuth onboarding exactly as a hosted client does it
python3 ops/hosted_onboarding_probe.py --base https://resonance-production-cfe3.up.railway.app --smoke --refresh --revoke --json
python3 ops/oauth_smoke.py https://resonance-production-cfe3.up.railway.app/mcp

# real three-person structural test over /mcp (A retry storm, B panic buying analog, C same words weaker structure)
python3 submission/evidence/abc_mcp_test.py https://resonance-production-cfe3.up.railway.app/mcp --out submission/evidence/public-origin-c66951b/abc.json
```

Expected under engine 0.2: B's discover ranks A (analogical, concept-aligned)
above C; C is `negative` or `approximate` with a `label_identity` /
contradiction explanation; polarity flips are hard-rejected; `confidence` is
`high|medium|low`, never `provisional`.

## Human test cards

`submission/HUMAN_TEST_CARDS.md` (Cards A–C: ChatGPT custom app, Claude custom
connector, browser WebMCP). Card B was executed on engine 0.1 (`#156`); repeat
it on 0.2 and record the result under `submission/evidence/public-origin-c66951b/`
(the connector-driven `whoami`/`discover`/`explain_match` run recorded there is
Card B steps 1–6 executed by an agent; a human still has to do it once).

## What "ready" means for the next freeze

- health shows engine 0.2 identity and `demo_personas_present: false` (done on
  `c66951b`; re-check after any re-seed);
- the three automated public-origin scripts above pass;
- at least one human card executed on 0.2;
- `submission/RELEASE_MANIFEST.md` §0 re-pinned to the new SHA / deployment id
  and the 0.1 banner replaced by the 0.2 evidence.

## Known open items (not blockers for testing)

- The live corpus carries duplicated guest sessions left by repeated acceptance
  runs (4× panic buying, 4× retry observability, 2× "Shared thought" as of
  generation 348). They are real `volunteer` rows, so `purge-demo` leaves them.
  Either the owner deletes them, or the acceptance scripts learn to revoke
  their own guests at the end (`resonance_stop_sharing` / consent revoke).
- On production the classical A/A' pair (irrigation retry storm vs delivery
  retry storm) is `approximate` with one contradiction, not `analogical`; see
  the evidence summary. Whether one contradicting relation should demote an
  otherwise systematic mapping is for the ADR-0004 gold review.

- Benchmark v0.2 gold is agent-authored; human review pending (ADR-0004).
- Corpus scale replay 10^4–10^5 not done.
- Native `document.modelContext` WebMCP discovery still requires a
  WebMCP-enabled browser (unchanged from R17).
