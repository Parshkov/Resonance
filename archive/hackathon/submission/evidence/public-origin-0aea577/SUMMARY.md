# Deployment evidence — public origin @ `0aea577` (engine 0.2, final test before freeze)

- **Commit under test:** `0aea577fb0dbf2bc741f68e176be95c551d2b494` (`main`, squash of #163 on top of #162 `9a79eb8` and #161 `b86016a`)
- **Origin:** https://resonance-production-cfe3.up.railway.app · **MCP:** https://resonance-production-cfe3.up.railway.app/mcp
- **Railway:** project `670bcce5-…`, service `resonance` `172aa183-…`, environment `production` `da338ecd-…`
- **Deployment:** `834818b1-d512-4e13-8bcf-638402e8b605` — SUCCESS 20:53:20Z, `commitHash 0aea577f…`, branch `main` (auto-deploy)
- **Startup log:** `oauth: core attached; issuer https://resonance-production-cfe3.up.railway.app; resource …/mcp; grants durable` then `competition product on http://0.0.0.0:8080 (…; mode: LIVE+WebMCP)`; **no** `purge-demo` line (`RESONANCE_PURGE_DEMO` is empty and stayed empty)
- **Method:** this session has public HTTPS egress, so the stdlib acceptance scripts ran **directly against the public origin** — unlike the `c66951b` evidence, which had to go through the hosted-connector path. Card B additionally executed through the real Claude custom connector. No tokens, codes or raw text recorded; pseudonyms, ids, scores and structure only.

## Repository gates (on `0aea577`)

| gate | result |
|---|---|
| `python3 -m unittest discover -s tests` | **463 tests OK, 1 skipped** (~470 s; the skip needs a local PostgreSQL) |
| `python3 benchmark/r0-v0.2/runner.py` | `overall_status: pass`, exit 0 — `benchmark_r0_v0.2.json` |
| `python3 benchmark/extraction-v0.2/runner.py` | `overall_status: pass`, exit 0 — `benchmark_extraction_v0.2.json` |

r0-v0.2 gate values are unchanged from before this run's scoring fix: classification accuracy 1.0,
polarity rejection 1.0, negative FPR 0.0, positive node F1 0.8469, Recall@5 1.0, Recall@20 1.0.
Benchmark gold was not edited.

## Public-origin acceptance

| # | check | result | artefact |
|---|---|---|---|
| P1 | `GET /api/product/health` | `ok: true`, `mode: live`, `index_current: true`; `engine_version resonance-engine/0.2`, `scoring_version resonance-score/0.2`, `classify_policy scoring-v0.2-concept-aligned-analogy/0.2`, `extractor_version 0.2.0`, `verifier_config_hash 12998d45…`; `corpus.demo_personas_present: false`, `demo_sessions: 0`, `volunteer 62` | `health.json` |
| P2 | `ops/hosted_onboarding_probe.py --smoke --refresh --revoke --json` | **ONBOARDING PASS: 9/9 required**, all optional steps pass, incl. the new `smoke cleanup (revoke own guest share)` → `revoked=True discoverable=False` | `hosted_onboarding_probe.{json,txt}` |
| P3 | `ops/oauth_smoke.py <origin>/mcp --auto-consent` | **27/27 checks passed** (RFC 9728 / 8414 / 7591, PKCE S256, exact state round-trip, replayed code + wrong verifier + wrong redirect_uri all rejected, refresh maps to the same account) | `oauth_smoke.txt` |
| P4 | `submission/evidence/abc_mcp_test.py <origin>/mcp` | **36/36 checks passed** — three independent OAuth guest identities, private draft → explicit confirm → share, B ranks A above C, subject-bound `result_id`, intro → accept → relay message, C isolated from both, revoke removes A from a fresh discovery immediately, stale `Mcp-Session-Id` tolerated on the stateless transport, `access_token` in a query string rejected (401), RFC 7009 revoke kills the bearer | `abc.{json,txt}` |
| P5 | Card A — `submission/evidence/browser_harness.py` (real Chromium 141 against the live origin) | **16/18**; the two that did not pass are explained below | `card-a-browser/` incl. 5 screenshots |
| P6 | Card B — real Claude custom connector on `/mcp` | steps 4–8 executed: `whoami` → `prepare_thought` → preview → `share_thought(confirm)` → `discover` → `explain_match` → `stop_sharing` (`revoked: true`) | this document |

`oauth_smoke.py` needs `--auto-consent` in a non-interactive session; without it, it prompts for a
pasted callback URL and exits on EOF. That is the script working as designed, not a product failure.

## Card A — what the two non-passing checks mean

1. **`NATIVE document.modelContext present` — expected.** Stock Chromium 141 exposes neither
   `document.modelContext` nor `navigator.modelContext`. The harness already excludes NATIVE checks
   from its exit code, and the page correctly reports the browser's limitation rather than faking it.
   Native WebMCP evidence still needs a WebMCP-enabled Chrome; **this remains unclaimed.**
2. **`visible match cards/results after discover — cards=0` — a real observation, not a crash.**
   Traced to the source: `demo/ui/presentation.primary_matches()` drops every `negative` match by
   design, and against the current live corpus every live match for the page's default thought is
   `negative`, so the primary rail is *correctly* empty (fail closed, do not advertise a false
   analogy). Two presentation defects sit around that correct behaviour and are **not** fixed here:
   - `#response-summary` reads `10 matches · 5 rejected` while zero cards are shown;
   - the evidence panel keeps stale REPLAY content ("Why Kwame A. resonates", replay mapping rows)
     with the LIVE source selected, instead of an empty state.

   In REPLAY mode the same selector finds 4 `.match-card` elements, so the harness's selector is
   right and the page renders normally. No acceptance assertion was relaxed to make this run green.

## The A/A' verdict on production — corrected

`ops/TEST_READINESS.md` and the `c66951b` summary recorded that the classical A/A' pair
(*"Irrigation retry storms after pressure drops"* vs *"Retry storm overloads delivery queue"*) is
`approximate` because "one contradicting relation demoted an otherwise systematic mapping from
`analogical`". **That causal story is wrong**, and `docs/decisions/ADR-0005-…` now records the
correction: `classify()` reaches `analogical` only when surface similarity **and** domain overlap are
both below their thresholds. This pair shares vocabulary ("retry", "overload", "fixed retry budget"),
so it takes the same-subject-matter branch, where the only possible outcomes are `direct` and
`approximate`. **`analogical` was never reachable for this pair under v0.2, with or without a
contradiction.** Whether the analogy branch should instead be gated on domain overlap alone is a
policy question with no gold case behind it; ADR-0005 is open and must be settled by the human gold
review, not by moving a threshold.

Measured on this deployment (query = the irrigation session, candidate `ses-a95528cc2a90ef11`):

```
mode_classification approximate · confidence low
structural 0.776 · semantic 0.464 · r_direct 0.714 · y_systematicity 1.0
coverage_containment 1.0 · contradiction 0.143 · 7 nodes mapped · 5 relations preserved · 1 contradiction
```

**Correction to PR #162's commit message.** That commit says "On the production A/A' pair:
contradiction 0.071 -> 0.0, confidence medium -> high". Those numbers are from the *synthetic
reproduction* built for the regression test — where the contradicting candidate relation had already
been consumed by an exact match — and the PR body says so, but the commit message does not make the
distinction. On the **real** production rows above the remaining contradiction is genuine: the
candidate asserts a differently-typed, *unconsumed* relation between the mapped pair, which is
exactly the case the fix deliberately leaves alone. The production verdict is therefore still
`approximate` with one contradiction, and the fix correctly did not touch it.

## Corpus hygiene

Acceptance runs no longer leave guests behind (#161): `abc_mcp_test.py` reports
`cleanup: this run leaves no discoverable guest session behind` with `still_discoverable=[]`, the
onboarding probe revokes its smoke share, and `browser_harness.py` revokes its own consent. Card B's
guest session was revoked at the end of the run.

The rows that accumulated **before** that fix are still present and are **not** deleted by this run
(they are real `volunteer` records, so `purge-demo` neither can nor should remove them). Full
inventory of what is discoverable on the live corpus at `db_generation 426`:

| topic | session ids | note |
|---|---|---|
| Panic buying after a shortage rumour | `ses-bb2d935993bb38c5`, `ses-9583f257ab7acd0c`, `ses-c041572ff069dafd`, `ses-ef6d5093f53a09d5` | **4 duplicates** — keep at most one |
| Retry and outage observability | `ses-f141cc4c7a1e1fdb`, `ses-e1771799a599ed59`, `ses-9ef6e59df883a8da`, `ses-1e48f4558db17120` | **4 duplicates** — keep at most one |
| Shared thought | `ses-4eea2164ed2bccbb`, `ses-5a8a8932b46be630` | **2 duplicates** — left by `hosted_onboarding_probe --smoke` before #161/#163 |
| Retry storm overloads delivery queue | `ses-a95528cc2a90ef11` | single; keep (the A/A' candidate) |
| Irrigation retry storms after pressure drops | `ses-099c77441b96db62` | single; keep (the A/A' query, owner's Card B session from 15:12 UTC) |

Deleting the ten duplicate rows is an **owner action**; this run deliberately did not touch sessions
it did not create. Their effect is visible and measurable: in the `9a79eb8` A/B/C run the genuine
cross-domain analogy A sat at rank 4 behind three exact copies of B's own thought, all scoring
structural 1.0.

The **cause** of the "Shared thought" rows is fixed in #163: `resonance_prepare_thought` derived the
durable presentation only from `thought.topic`/`thought.domain`, so the `context` path — the one the
tool tells callers to prefer — could not name the thought and every raw-text share was published as
`Shared thought` / `general` / `shared-thought`. Verified on this deployment through the connector:
a `context` prepare with `topic: "Named raw-text share verification"` now returns
`presentation.cluster_id: named-raw-text-share-verification`.

## Deviations

- Card A ran in stock Chromium, not a WebMCP-enabled Chrome, so the native check cannot pass here.
- The browser had to reach the origin through this session's egress relay, which cannot carry a
  TLS 1.3 handshake; the run used `--browser-arg=--ssl-version-max=tls1.2`. Certificate verification
  was **not** disabled and the connection was ordinary verified TLS 1.2.
- `RESONANCE_DB` and `RESONANCE_CONFIRMATION_SECRET` were not read or changed, and
  `RESONANCE_SEED_DEMO` was never set.
