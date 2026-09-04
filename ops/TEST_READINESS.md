# Test readiness — engine 0.2 on production

Written 2026-09-04 after PR #158 merged (`main` `443ba1c`). This is the entry
point for a session whose job is to test and finish the product.

## What is deployed

| item | value |
| --- | --- |
| production origin | `https://resonance-production-cfe3.up.railway.app` |
| canonical MCP resource | `https://resonance-production-cfe3.up.railway.app/mcp` |
| Railway project / service / environment | `resonance-live` `670bcce5-…` / `resonance` `172aa183-…` / `production` `da338ecd-…` |
| deployed commit | `443ba1c` (auto-deploy from `main`; deployment `40a6c570`, SUCCESS 18:42 UTC) |
| entrypoint | `python3 -m src.product.competition_server … --db $RESONANCE_DB --origin $PUBLIC_ORIGIN` |
| startup log | `oauth: core attached; … grants durable` then `competition product … mode: LIVE+WebMCP` |
| engine | `resonance-engine/0.2`, scoring `resonance-score/0.2`, extractor `0.2.0` — confirm via `GET /api/product/health` → `engine.*` |

`GET /api/product/health` now also reports `corpus.demo_personas_present` and
`corpus.sessions_by_kind`. **Until `purge-demo` has run once on production the
database still holds the 25 demo personas seeded by earlier releases**; they are
labelled `display.demo_persona: true` in every discover row and refuse intros,
but for a clean test corpus purge them (see below).

## One-time production clean-up (owner or a session with Railway access)

1. Set the service variable `RESONANCE_PURGE_DEMO=1` (Railway redeploys).
2. In the deploy log expect `purge-demo: sessions_deleted=25 users_revoked=<n>`.
3. `GET /api/product/health` → `corpus.demo_personas_present: false`.
4. Set `RESONANCE_PURGE_DEMO=` (empty) so the next deploy does not re-run it
   (re-running is harmless: it reports zeros).

Never set `RESONANCE_SEED_DEMO=1` on production unless a demo corpus is wanted
on purpose.

## Automated checks (run from a machine with public egress; the Claude Code
## web sandbox cannot reach the public origin)

```bash
# repository gates (any machine)
python3 -m unittest discover -s tests                 # 460 tests, 1 skip without PostgreSQL
python3 benchmark/r0-v0.2/runner.py                  # engine gates, exit 0
python3 benchmark/extraction-v0.2/runner.py          # extractor gates, exit 0

# public origin, discovery-driven OAuth onboarding exactly as a hosted client does it
python3 ops/hosted_onboarding_probe.py --base https://resonance-production-cfe3.up.railway.app --smoke --refresh --revoke --json
python3 ops/oauth_smoke.py https://resonance-production-cfe3.up.railway.app/mcp

# real three-person structural test over /mcp (A retry storm, B panic buying analog, C same words weaker structure)
python3 submission/evidence/abc_mcp_test.py https://resonance-production-cfe3.up.railway.app/mcp --out submission/evidence/public-origin-443ba1c/abc.json
```

Expected under engine 0.2: B's discover ranks A (analogical, concept-aligned)
above C; C is `negative` or `approximate` with a `label_identity` /
contradiction explanation; polarity flips are hard-rejected; `confidence` is
`high|medium|low`, never `provisional`.

## Human test cards

`submission/HUMAN_TEST_CARDS.md` (Cards A–C: ChatGPT custom app, Claude custom
connector, browser WebMCP). Card B was executed on engine 0.1 (`#156`); repeat
it on 0.2 and record the result under `submission/evidence/public-origin-443ba1c/`.

## What "ready" means for the next freeze

- health shows engine 0.2 identity and `demo_personas_present: false` (or a
  deliberate `RESONANCE_SEED_DEMO=1` recorded in the manifest);
- the three automated public-origin scripts above pass;
- at least one human card executed on 0.2;
- `submission/RELEASE_MANIFEST.md` §0 re-pinned to the new SHA / deployment id
  and the 0.1 banner replaced by the 0.2 evidence.

## Known open items (not blockers for testing)

- Benchmark v0.2 gold is agent-authored; human review pending (ADR-0004).
- Corpus scale replay 10^4–10^5 not done.
- Native `document.modelContext` WebMCP discovery still requires a
  WebMCP-enabled browser (unchanged from R17).
