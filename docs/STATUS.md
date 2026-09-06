# Resonance — Status

Updated: 2026-09-06 (audit corrections)

## Where the project actually is

| layer | state | evidence |
|---|---|---|
| Thought DNA schema v0.1 | frozen, validated, canonical hashing | `src/graph`, `tests/test_thought_dna_schema.py` |
| Deterministic semantics (no LLM) | engine 0.2: lexicon + stems + relatedness; optional local label encoder (ADR-0006, `RESONANCE_EMBEDDER`) | `src/semantics`, `tests/test_semantics.py`, `tests/test_label_encoder.py` |
| Retrieval | structural + concept + content channels, IDF, verified re-ranking | `src/fingerprint`, `src/index`, `src/engine/reports/r0-v0.2-e2e.json` |
| Verification / scoring | FGW conditional gradient + scoring policy v0.2 | `src/alignment`, `src/scoring`, ADR-0004 |
| Extraction from prose | cue extractor v0.2, edge F1 0.94 on 22 prose cases | `src/extraction`, `benchmark/extraction-v0.2` |
| Benchmark | v0.2: 8 skeletons × 4 domains × 18 families; S5–S8 gate split never used to fit thresholds, but see the caveat under "What is not validated" | `benchmark/r0-v0.2` |
| Product (MCP, WebMCP, OAuth, persistence) | deployed; one vocabulary of 21 tools for the chat and the browser (`src/product/mcp_bridge.py`, `/api/product/tools`) | `src/product`, `ops/DEPLOY.md` |
| Native browser WebMCP | demonstrated behind a flag: Chrome 152.0.7977.83 with `--enable-features=WebMCP`, Card A **24/24, `mode: NATIVE`** | `archive/hackathon/submission/evidence/public-origin-8670568/card-a-browser/` |
| The page | six screens over one state store (`demo/ui/main.mjs`, `store.mjs`, `strings.mjs`); groups with discussion, parts and shared understanding | `demo/ui/README.md`, `tests/test_product_http.py` |
| Release freeze | engine 0.2 freeze taken 2026-09-04 on `0aea577` (deployment `834818b1`) | `archive/hackathon/submission/RELEASE_MANIFEST.md` §0, `archive/hackathon/submission/evidence/public-origin-0aea577/` |

## Release state

The current freeze is **engine 0.2 on `0aea577`**, deployed as Railway deployment
`834818b1`. On that commit: 463 tests OK (1 skip), both v0.2 benchmark gates pass with gold
unedited, and the full acceptance set ran directly against the public origin — health shows
the engine 0.2 identity and `demo_personas_present: false`, onboarding probe 9/9 required,
OAuth smoke 27/27, the three-person A/B/C test over `/mcp` 36/36, Card A in a real browser
16/18, Card B through a real Claude custom connector. Evidence and the two Card A
non-passes are in `archive/hackathon/submission/evidence/public-origin-0aea577/SUMMARY.md`.

## 2026-09-06 rework

The audit of 2026-09-05 (PR #195) rebuilt the page as separate screens over one
state, gave groups a conversation and parts of the work, unified the browser
and chat tool vocabularies, retired the stdio adapter and the replay demo, and
added the opt-in label encoder. On that branch: 679 tests pass (lexicon only)
and the engine gates pass with the encoder on. Production runs the encoder once
`RESONANCE_EMBEDDER_MODEL` (build) and `RESONANCE_EMBEDDER` (run) are set on the
service.

## What is validated

- Same words / different structure → rejected (polarity flips are hard-rejected; full permutations raise `label_identity` contradictions).
- Different words / same abstract structure → `analogical`, on 8 skeletons × 3 other domains each, and on the hand-authored demo corpus.
- Same skeleton with concept-free labels (template coincidence) → `negative`.
- Partial, granular, paraphrased, permuted and extraction-noisy variants → retrieved in the top 5 among distractors and classified correctly.
- Prose → graph without an LLM for texts that carry explicit connectives; cue-free prose yields an honest empty graph.

## What is not validated

- Real user thoughts at scale: every benchmark graph is authored (by agents), not extracted from real conversations. Independent human review of the v0.2 gold is pending.
- Corpus scale 10^4–10^6: no replay beyond a few hundred graphs. Measured on the
  v0.2 corpus replicated in memory, mean query time is **148 ms at 176 graphs,
  170 ms at 352, 283 ms at 704 and 580 ms at 1408** — linear from 352 upward, not
  sub-linear, which is exactly the condition ADR-0004 names for reconsidering the
  concept channel. (Replicated graphs inflate posting lists, so treat this as an
  upper bound.) `ResonanceEngine._require_bound()` additionally re-hashes the whole
  corpus on every query by design.
- Extraction of implicit causation (no connective) is abstained by design.
- Native WebMCP **without a flag**: `document.modelContext` appears in Chrome 152 only under `--enable-features=WebMCP`, and not at all in stock Chromium 141. The flagged run passed 24/24 (see above), so native discovery is no longer unclaimed — what is unvalidated is a browser exposing WebMCP by default. The page reports the browser's real capability rather than faking it. One honest limitation through the native surface: Chrome wraps a failing tool as `UnknownError`, so an agent does not receive the product's own error code the way remote MCP delivers it.
- The **same-subject floor** (`T_STRUCTURE_SAME_SUBJECT`, `T_SAME_SUBJECT_SEMANTIC`,
  policy `/0.3`) was fitted to a single real pair, with the v0.2 gate used only as a
  regression check. For that branch the gate is therefore no longer a held-out
  measurement, and the honest reading of `classification_accuracy = 1.0` is "no
  regression", not "generalises". 13 thresholds against 72 gold pairs.
- Whether a same-vocabulary cross-domain pair should be `approximate` or `analogical`: Benchmark v0.2 has no gold case for "same words, different domain, same structure". Recorded as **open** in ADR-0005 rather than settled by moving a threshold.
- Human execution of the hosted-client cards **B (claude.ai) and C (ChatGPT developer mode)**; agents have executed B, a person has not. The underlying hosted OAuth flow is no longer unproven on production — see below — but those two named client integrations remain unexecuted by a human.

## Process notes

- Engine 0.1 gate reports under `src/*/reports/r0-v0.1-*.json` are kept as history; they were computed on the single-template v0.1 corpus and are not comparable with 0.2.
- Import-time monkey-patch modules (`review_hardening`, `review_alignment`) were folded into the classes they patched; behaviour is unchanged and now visible in one place.
- The second remote MCP server and its 15-tool vocabulary were removed; `src/remote/server.py` is a thin factory over the product server.
- Persistent databases are no longer seeded with demo personas by default (`--seed-demo` / `RESONANCE_SEED_DEMO=1` opt in; `python3 -m src.persistence --db <DSN> purge-demo` cleans an already seeded production). Production has never been seeded: the one `purge-demo` run deleted 0 rows.
- Acceptance scripts now revoke the guest thoughts they share, so a test run leaves the live corpus as it found it. Rows left by earlier runs are real `volunteer` records and are listed for owner deletion in the freeze evidence, not deleted by an agent.

## 2026-09-06 audit corrections

A full read of the repository against the deployed product found four defects
and a set of documents that had drifted from the code. All are fixed on this
branch; the findings are recorded here rather than only in a commit message.

**Code**

- `/.well-known/oauth-protected-resource/mcp` and the matching
  authorization-server path returned **404 in production**. RFC 9728 §3.1 and
  RFC 8414 §3.1 build the metadata URL by inserting the well-known segment
  before the resource path, and MCP clients try that form first. The OAuth core
  had always answered it; `oauth_mount.is_oauth_path` admitted only the bare
  paths, so nothing reached the core. Only clients that fall back to the root
  form worked. Fixed, with a test that asserts both forms without fallback.
- `CLASSIFY_POLICY` did not move when `classify()`'s decision boundary moved in
  #193, and it is carried in `verifier_config_hash`. The frozen `0aea577`
  evidence and every run after it therefore reported the same hash
  `12998d45…` for two different classifiers. The policy is now
  `scoring-v0.2-concept-aligned-analogy+same-subject-floor/0.3`
  (`e093d77f…`); gate values are unchanged, so this is provenance only.
- Cyrillic labels were refused as "not in the script the index compares" for a
  release after lexicon 0.3.0 gave **all 90 concept classes** Russian surface
  forms — a refusal whose stated reason had become false, turning away exactly
  the people it was written to protect. The script list is now derived from the
  lexicon's own terms (`semantics.lexicon.COVERED_SCRIPTS`), so it cannot drift
  again; the scripts the lexicon genuinely cannot read are still refused.
- No `Strict-Transport-Security` on the HTTPS origin. Added, gated on the same
  all-origins-are-https test the `Secure` cookie flag uses.

**Documents that contradicted the code** — `PROJECT_STRUCTURE.md` (described
`src/` as an engine plus a `src/mcp/` adapter that does not exist, and omitted
13 of 19 packages), `src/scoring/README.md` (documented the v0.1 classification
policy as current), `ops/TEST_READINESS.md` (pinned a deployed commit 100+
commits stale; now points at `/api/product/health`), this file and `README.md`
(understated native WebMCP, and claimed semantics never come from a model while
the hosted deployment runs the ADR-0006 encoder), `docs/decisions/README.md`
(omitted ADR-0006; ADR-0001 is still unwritten and now says so),
`docs/THREAT_MODEL.md` (named PostgreSQL as the hosted store; it is SQLite),
`src/discovery/fixtures/example_response.json` (two generations stale and
carrying a `metadata` block from the retired stdio adapter — regenerated).

**Known gaps not closed here**

- No CI existed for 396 commits; a workflow is added on this branch, but it has
  never run on a pull request yet.
- `src/persistence/{sqlite,postgres}_store.py` are two independent
  implementations of a 53-method protocol with no shared base; the PostgreSQL
  path is skipped unless `RESONANCE_TEST_POSTGRES_URL` is set, and production
  runs SQLite.
- `agents/SCOREBOARD.md` was never operated.
- The whole-thought embedding baseline that `WHY_NOT.md` and ADR-0004 both name
  as the falsification target still does not exist.

## Production verification of the audit corrections (2026-09-06)

Merged as #206 (`85eeaba`) and auto-deployed to Railway deployment
`b922ca19`, SUCCESS. Verified directly against
<https://resonance.parshkov.com>:

| check | result |
| --- | --- |
| CI, first run in the repository's history | 3/3 jobs green on a clean machine — suite, both gates, lexicon additivity |
| `classify_policy` | `scoring-v0.2-concept-aligned-analogy+same-subject-floor/0.3` |
| `verifier_config_hash` | `12998d451e632759…` → `e093d77f8cd987c8…` — the two classifiers are now distinguishable |
| `/.well-known/oauth-protected-resource/mcp` | **404 → 200**, `resource: https://resonance.parshkov.com/mcp` |
| `/.well-known/oauth-authorization-server/mcp` | **404 → 200**, `issuer` matches, S256 advertised |
| root discovery forms | still 200, unchanged |
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains`, on the canonical origin and the platform alias |
| other security headers | CSP, COOP, Permissions-Policy, nosniff, Referrer-Policy — unchanged |
| unauthenticated `/mcp` | 401 with the RFC 9728 challenge |
| health | `ok: true`, `mode: live`, `index_current: true`, `demo_personas_present: false`, encoder active |
| page and legal routes | `/`, `/webmcp.mjs`, `/privacy`, `/terms`, `/support`, `/auth/sign-in` all 200 |

Full-flow acceptance was run on the merged commit against a guest-enabled
local origin, because production refuses anonymous guests by design:
**OAuth smoke 27/27** and the **three-person A/B/C test over `/mcp` 36/36**
(A ranked above C at rank 0 vs 14, subject-bound `result_id`, intro → accept →
relay, revocation removing A from a fresh discovery immediately, revoked bearer
refused). What those scripts can and cannot prove against production is now
written down in `ops/TEST_READINESS.md` rather than left as a trap.

Not closed: completing the hosted flow **on production** needs a human to sign
in with Google or GitHub. No script can do it, and that remains the outstanding
hosted-client item below.

## The hosted flow, completed on production (2026-09-06)

`ops/TEST_READINESS.md` records that no script can finish the hosted flow on
production, because anonymous guests are refused and the authorize step needs a
signed-in human. That step has now been executed, in the maintainer's own Chrome
against <https://resonance.parshkov.com>, on `9e2b41c`:

| step | result |
| --- | --- |
| dynamic client registration (RFC 7591) | `201`, `client_id` issued |
| `GET /oauth/authorize` with PKCE S256 | consent page renders, names the client, the account (`mail@parshkov.com` / *Quiet Lapidary*) and exactly what is granted |
| consent approved by the signed-in human | redirect to the exact loopback `redirect_uri`, **`code` returned**, exact `state` round-trip |
| token exchange | `200`, `token_type: Bearer` (no refresh token — `offline_access` was not requested, which is correct) |
| MCP `initialize` over `/mcp` | `200`, protocol `2025-03-26`, server `resonance` |
| `tools/list` | **21 tools** |
| `resonance_whoami` | resolves to the real account, *Quiet Lapidary* |
| `resonance_my_thoughts`, `resonance_pending_resonances`, `resonance_topics` | all answer for the real account |
| `POST /oauth/revoke` (RFC 7009) | `200`, and the revoked bearer is immediately **`401` on `/mcp`** |

**This was deliberately read-only.** Nothing was prepared, shared, revoked or
written in the live corpus, and the access token was revoked at the end. It is
the exact step the automated probes stop at (`[FAIL] 5 code returned`,
`access_denied: sign in to Resonance before connecting a client`), and it
passes when a human is signed in — which is what those probes were always
telling us.

The page itself was checked in the same browser: it renders the signed-in home
screen with real data — a match at 0.83 with its "See why", the account's own
thoughts with one shared and one private, a group and a conversation — with **no
console errors**.

**Native WebMCP was not re-verified here.** That Chrome is 152.0.7977.77, the
version that supports it, but `document.modelContext` is `undefined` because the
profile is not running with `--enable-features=WebMCP`. The flagged 24/24 run
recorded in `archive/.../public-origin-8670568/card-a-browser/` stands as the
native evidence; nothing in this session adds to or subtracts from it.

## Next falsification targets

1. A corpus of real extracted thoughts (consented) with two-human gold; compare engine 0.2 against a whole-thought embedding baseline.
2. Scale replay of the concept channel at 10^4–10^5 graphs.
3. Lexicon coverage audit on real labels; add classes only with two independent examples.
