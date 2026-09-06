# Test readiness — engine 0.2 on production

Written 2026-09-04 after PR #158 merged (`main` `443ba1c`). This is the entry
point for a session whose job is to test and finish the product.

## What is deployed

**This table names identities, not a commit.** It used to pin `c66951b` as
"the deployed commit", which was true for a day and wrong for the hundred
commits after it. Production auto-deploys from `main`, so the only honest
answer to "what is running?" comes from the origin itself:

```bash
curl -s https://resonance.parshkov.com/api/product/health
```

That returns the engine identity (`engine.engine_version`,
`engine.classify_policy`, `engine.verifier_config_hash`,
`engine.label_encoder`), corpus composition
(`corpus.sessions_by_kind`, `corpus.demo_personas_present`) and index
freshness. Read it first; do not trust a commit hash written in a document.

| item | value |
| --- | --- |
| canonical origin | `https://resonance.parshkov.com` |
| canonical MCP resource | `https://resonance.parshkov.com/mcp` |
| platform alias | `https://resonance-production-cfe3.up.railway.app` — the same deployment, kept in the allowlist. It derives its **own** OAuth issuer from the Host it is reached on, so a client that registers there is audience-bound there. Test against the canonical origin unless the alias is what you are testing. |
| Railway project / service / environment | `resonance-live` `670bcce5-…` / `resonance` `172aa183-…` / `production` `da338ecd-…` |
| deployed commit | whatever `main` last auto-deployed — read the Railway deployment list, or the health endpoint above |
| entrypoint | `python3 -m src.product.web_server … --db $RESONANCE_DB --origin $PUBLIC_ORIGIN` |
| startup log | `oauth: core attached; … grants durable` then `resonance … mode: LIVE+WebMCP` |

`GET /api/product/health` also reports `corpus.demo_personas_present` and
`corpus.sessions_by_kind`.

## Production clean-up — done 2026-09-04 19:13 UTC

`RESONANCE_PURGE_DEMO=1` was set on the service, the redeploy (`275c646c`)
logged `purge-demo: sessions_deleted=0 users_revoked=0`, and the variable was
cleared again (`357dd391`, no purge line). The production database held **no**
seeded demo personas (every live session is `volunteer`; `db_generation`
stayed at 348), so `corpus.demo_personas_present` is `false` on `c66951b`.
Evidence: `archive/hackathon/submission/evidence/public-origin-c66951b/`.

The procedure stays valid for a future re-seeded environment:
`RESONANCE_PURGE_DEMO=1` → redeploy → read the log line → clear the variable.
Never set `RESONANCE_SEED_DEMO=1` on production unless a demo corpus is wanted
on purpose.

## Two ways to reach the public origin from an agent session

1. **Egress-capable machine** (owner laptop, CI, or a Claude Code environment
   with full network access): run the stdlib scripts below.
2. **Hosted-client path from claude.ai**: the Resonance custom connector
   (`https://resonance.parshkov.com/mcp`) is callable as
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
python3 -m unittest discover -s tests                 # 682 tests, 2 skips without PostgreSQL
python3 ops/lexicon_check.py                          # English scoring unchanged, exit 0
python3 benchmark/r0-v0.2/runner.py                  # engine gates, exit 0
python3 benchmark/extraction-v0.2/runner.py          # extractor gates, exit 0

# public origin, discovery-driven OAuth onboarding exactly as a hosted client does it
# READ THE NOTE BELOW FIRST: neither of these can complete on production any more.
python3 ops/hosted_onboarding_probe.py --base https://resonance.parshkov.com --smoke --refresh --revoke --json
python3 ops/oauth_smoke.py https://resonance.parshkov.com/mcp

# real three-person structural test over /mcp (A retry storm, B panic buying analog, C same words weaker structure)
# Runs only where guest accounts are enabled, and needs an `authorship` argument the
# archived copy does not send -- see below.
python3 archive/hackathon/submission/evidence/abc_mcp_test.py http://127.0.0.1:8901/mcp
```

### These scripts cannot finish against production, and that is correct

Production has real sign-in providers configured, so **anonymous guest creation
is refused by design** (`POST /api/product/guest` -> `403 sign_in_required`,
and the consent page offers no anonymous option; see `ops/DEPLOY.md`). Every
one of these scripts mints a guest to get an access token, so on production
they stop at exactly one step:

| script | against production | against a guest-enabled origin |
| --- | --- | --- |
| `ops/oauth_smoke.py` | **16/17** — everything through `consent POST redirects`, `exact redirect_uri`, `exact state round-trip`; then `[FAIL] 5 code returned`, because there is no signed-in account to issue a code to | **27/27** |
| `ops/hosted_onboarding_probe.py --smoke` | **4/5 required** — fails `authorize approve -> code + state` with `error=access_denied&error_description=sign+in+to+Resonance+before+connecting+a+client` | 9/9 required |
| `abc_mcp_test.py` | cannot start — needs three guest identities | 36/36 |

**That single failure is the sign-in policy working, not a fault.** The freeze
evidence figures (27/27, 9/9, 36/36) were recorded when guest accounts were
still enabled on production; they are not reproducible there today and should
not be quoted as if they were.

To exercise the full flow, run a guest-enabled origin locally and point the
scripts at it:

```bash
python3 -m src.product.web_server --host 127.0.0.1 --port 8901 \
        --db :memory: --origin http://127.0.0.1:8901 &
python3 ops/oauth_smoke.py http://127.0.0.1:8901/mcp --auto-consent
PYTHONPATH=. python3 archive/hackathon/submission/evidence/abc_mcp_test.py http://127.0.0.1:8901/mcp
```

Completing the hosted flow **on production** requires a human to sign in with
Google or GitHub. **That was done on 2026-09-06** and is recorded in
`docs/STATUS.md` under "The hosted flow, completed on production": DCR ->
authorize with a real signed-in account -> code -> token -> MCP `initialize` ->
21 tools -> `resonance_whoami` -> RFC 7009 revoke -> `401`. Read-only; nothing
was written to the live corpus.

So the flow is proven. What no script can close is re-running it: each
execution needs a human at the consent screen. Cards B (claude.ai connector)
and C (ChatGPT developer mode) also remain unexecuted by a person.

### The archived A/B/C harness predates the authorship rule

`archive/hackathon/submission/evidence/abc_mcp_test.py` calls
`resonance_prepare_thought` without `authorship`, which
`src/product/authorship.py` (2026-09-05) made mandatory. Run as-is it now stops
at `5/6` with `validation_failed: state authorship: ...` — **the product
refusing correctly**, not a regression.

It is deliberately **not** patched: the freeze evidence records a 36/36 run of
*that* file, and editing it would break the correspondence between the record
and the artifact. To run the scenario against current code, copy it and add
`"authorship": "their_own_words"` to the `resonance_prepare_thought` call.
Verified on `85eeaba` that way: **36/36**, including `A ranks above C`
(rank 0 vs rank 14), subject-bound `result_id`, intro -> accept -> relay,
revocation removing A from a fresh discovery immediately, and a revoked bearer
being refused on `/mcp`.

Expected under engine 0.2: B's discover ranks A (analogical, concept-aligned)
above C; C is `negative` or `approximate` with a `label_identity` /
contradiction explanation; polarity flips are hard-rejected; `confidence` is
`high|medium|low`, never `provisional`.

## Human test cards

`archive/hackathon/submission/HUMAN_TEST_CARDS.md` (Cards A–C: ChatGPT custom app, Claude custom
connector, browser WebMCP). Card B was executed on engine 0.1 (`#156`); repeat
it on 0.2 and record the result under `archive/hackathon/submission/evidence/public-origin-c66951b/`
(the connector-driven `whoami`/`discover`/`explain_match` run recorded there is
Card B steps 1–6 executed by an agent; a human still has to do it once).

## What "ready" means for the next freeze

- health shows engine 0.2 identity and `demo_personas_present: false` (done on
  `c66951b`; re-check after any re-seed);
- the three automated public-origin scripts above pass;
- at least one human card executed on 0.2;
- `archive/hackathon/submission/RELEASE_MANIFEST.md` §0 re-pinned to the new SHA / deployment id
  and the 0.1 banner replaced by the 0.2 evidence.

## Known open items (not blockers for testing)

- The live corpus carries duplicated guest sessions left by repeated acceptance
  runs (4× panic buying, 4× retry observability, 2× "Shared thought" as of
  generation 348). They are real `volunteer` rows, so `purge-demo` leaves them.
  **New runs no longer add to the pile:** `archive/hackathon/submission/evidence/abc_mcp_test.py` and
  `hosted_onboarding_probe.py --smoke` now revoke their own guests before
  exiting (#161), and `archive/hackathon/submission/evidence/browser_harness.py` already did. Deleting the rows that
  accumulated before that fix is still an owner action.
- On production the classical A/A' pair (irrigation retry storm vs delivery
  retry storm) is `approximate`, not `analogical`. The earlier reading — that a
  single contradicting relation demoted an otherwise systematic mapping — was
  wrong and is corrected in [ADR-0005](../docs/decisions/ADR-0005-same-vocabulary-cross-domain-verdict.md): the pair shares
  vocabulary (`surface_semantic` 0.44 >= `T_SAME_WORDS` 0.30), so `classify()`
  takes the same-subject-matter branch where `analogical` is unreachable by
  construction, and returns `approximate` because one query relation has no
  counterpart (`r_direct` 0.86). Whether the analogy branch should be gated on
  domain overlap alone is an open policy question for the human gold review
  (ADR-0005); it needs human-authored gold, not a threshold change.

- Benchmark v0.2 gold is agent-authored; human review pending (ADR-0004).
- Corpus scale replay 10^4–10^5 not done.
- Native `document.modelContext` WebMCP discovery still requires a
  WebMCP-enabled browser (unchanged from R17).
