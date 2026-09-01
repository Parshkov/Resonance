---
mission: R8-DISCOVERY
run: R8-DISCOVERY-REVIEW-R4Q7
review_type: independent exact-head review
contributor: Parshkov
agent_id: parshkov-xai-grok46-r4q7
agent_or_model: Grok 4.6 (exact mode not exposed)
date: 2026-09-01
mission_modified: false
web_research_used: false
code_execution_used: true
blind_constraints_preserved: not-applicable
reviewed_pr: https://github.com/Parshkov/Resonance/pull/76
exact_head: 8b52a4a74f1aeabd1cb10466df160c854b0a7727
base_main: d1c392277c77b9c0c0e203136eccff7ee376a3d7
conflict_of_interest: >
  Different human sponsor and different provider from the R8 author
  (dima2010 / Anthropic Claude Fable 5). Same GitHub actor as the
  repository owner because this session used the connected Parshkov
  account to publish the review. This identity did not author R4, R5,
  R6-MCP, R7-CORPUS, or the R8 implementation.
notes: >
  Not a canonical CLAIM on R8-DISCOVERY. Issue #73 remains SUBMITTED /
  PENDING_REVIEW on PR #76. This review does not occupy or reopen the
  slot and does not start R9-VISUAL.
---

# Scope

Independent exact-head review of canonical R8-DISCOVERY PR #76 after the
author re-keyed the branch onto accepted R7-CORPUS (`resonance-demo-corpus/0.1`).

Maintainer comments on PR #76 and issue #73 asked for an independent check
of head `8b52a4a74f1aeabd1cb10466df160c854b0a7727` covering:

- engine order preserved with filter-only consent removal; no rerank/compensation;
- hidden/unshared users byte-identically uninferable;
- hard rejections segregated without new thresholds;
- strict visualization DTO/provenance and one additive MCP tool;
- request-intro privacy/audit;
- source-scan boundary and full-suite regression.

This is review input. It is not maintainer `REVIEW_STATUS`.

# Inputs reviewed

| Artifact | Role |
|---|---|
| Issue #73 | acceptance gate and architectural rule |
| PR #76 at `8b52a4a` | implementation under review |
| `src/discovery/**` | owned surface |
| `tests/test_discovery.py` | claimed invariants |
| accepted R7 `demo/corpus/**` | consent/schema source of truth |
| accepted R6 `src/mcp/**` | baseline tool list |
| `work/STATE_MACHINE.md` | slot must stay reserved |

# Method

1. Checked out PR ref `pull/76/head` and confirmed `git rev-parse HEAD` =
   `8b52a4a74f1aeabd1cb10466df160c854b0a7727` on top of main `d1c3922`.
2. Read `service.py`, `metadata.py`, `mcp.py`, `demo_server.py`, fixtures,
   and tests rather than trusting the PR body.
3. Executed the commands requested by the maintainer handoff.
4. Ran extra probes: live vs committed example JSON, engine `find()` order
   vs discovery lists, default `k=8` vs example `k=15`, token leak scan,
   tool-list inheritance, aggregation vs rejected regions.

Runtime: Python 3.12.3, stdlib only, no extra agents.

# Measured validation

```text
python3 -m compileall -q src tests demo     # clean
python3 -m unittest tests.test_discovery -v # 13 tests OK (13.453s)
python3 -m unittest discover -s tests       # 158 tests OK (54.678s)
git diff --check                            # clean
```

Exact head: `8b52a4a74f1aeabd1cb10466df160c854b0a7727`.

Live flagship `discover(mode=analogical, k=15)` equals committed
`src/discovery/fixtures/example_response.json` (`resp == example` is True).

Pinned provenance on that response:

```text
engine_version: resonance-engine/0.1
interface_version: resonance-interfaces/0.1
discovery_contract_version: resonance-discovery/0.1
metadata_schema_version: resonance-demo-corpus/0.1
verifier_config_hash: 3e107bc4850537730949d013ffa0f335b3ddbf9b0d64bb640fe34f893dbb1b1d
corpus_snapshot: 5868db42ffdc385bd59f30dc2d3761292ff5e0ee7af777527a0b2ac8dbca222f
```

Accepted R6 tools inherited name-for-name, then one additive tool:

```text
ingest_thought, index_thought, find_resonance, compare_thoughts,
explain_resonance, get_thought, save_snapshot, load_snapshot,
discover_resonance
```

`request_intro` is not in the MCP tool list.

# Gate findings

## G1. Filter-only consent removal preserves engine relative order — PASS

`DiscoveryService.discover` iterates `engine.find(...)` and either skips a
hit with no registry profile, skips the query thought, or appends to
`matches` / `rejected`. There is no sort of hits.

Measured engine `find(analogical, k=15)` order:

```text
diego complementary
gabe analogical
kwame analogical
mei analogical
noah analogical
yuki complementary
sora approximate
lea negative / hard_rejection relation_type:r0->r0
theo approximate
sam negative
camille negative
priya negative / hard_rejection relation_type:r4->r4
wei negative / hard_rejection relation_type:r4->r6
```

Discovery `matches[]` is that list with hard-rejected rows removed.
Discovery `rejected[]` is those three hard-rejected rows in the same
relative order. Theo remains after Sora even though Theo's structural
score is higher (0.863 vs 0.814). That is accepted engine order, not a
discovery rerank.

The metadata permutation test mutates topic/domain/display_label/region on
every discoverable session and asserts `(session_id, classification, scores)`
for `matches[]` is unchanged. Reproduced.

## G2. Hidden users are byte-identically uninferable — PASS

Accepted R7 hidden sessions are `ses-ravi-irrigation` and
`ses-nico-tracing-private`. Ravi is in the flagship cluster.

Two defenses are actually implemented:

- `index_discoverable` never indexes hidden sessions;
- `ConsentRegistry.from_r7_sessions` creates no profile for them.

The leak test rebuilds the service on the full corpus vs the corpus with
both hidden sessions deleted and asserts identical `json.dumps(..., sort_keys=True)`
including matches, rejected, aggregation, and counts. Reproduced.

A lowercase blob scan of the live k=15 response does not contain `ravi`,
`nico`, `irrigation`, `@`, `email`, or `phone`.

## G3. Hard-rejection segregation without new thresholds — PASS

Split key is `hit.verification.hard_rejection` from the accepted verifier.
No score cutoff is applied in `src/discovery`.

Live k=15: `ses-lea-plasma-polarity` is in `rejected[]` with
`hard_rejection: relation_type:r0->r0` and `h_sign_conflict: true`.
`ses-sam-plasma-rewire` stays in `matches[]` as engine class `negative`
because it is not hard-rejected. That is honest, not a discovery patch.

Rejected regions (Low Countries, South India, Pacific Canada) do not appear
in aggregation buckets. Aggregation is computed only over `matches[]` that
also have a shareable location.

## G4. Visualization DTO / provenance / additive MCP — PASS

Contract `resonance-discovery/0.1` includes query identity, engine/config
provenance, matches, rejected, leak-safe aggregation, and explicit
unsupported fields (`realtime_presence`, `exact_location`, `contact_details`).

Consent truth is imported from accepted R7 primitives (`is_discoverable`,
`presentation_view`, `index_discoverable`, `CORPUS_SCHEMA_VERSION`). The
reviewer did not find a second consent rule invented in discovery.

MCP decision matches the issue: one additive tool via subclass; accepted
adapter/server files are not modified.

Wire smoke in `test_discover_tool_over_the_wire_and_r6_tools_intact` drives
`initialize` then `tools/call discover_resonance` through
`DiscoveryMCPServer`.

## G5. request_intro privacy — PASS as a service capability

`request_intro` returns `pending_target_acceptance` and
`disclosure: none_until_target_accepts`. The public audit log strips keys
starting with `_`, so target session id and message body do not leave the
service. Reproduced.

The capability is advertised on every match as action `request_intro` but is
not MCP-exposed in v0.1. That is the documented smallest-surface decision,
not a contact leak. R9 must not treat the action string as proof that a live
intro tool exists.

## G6. Source-scan boundary — PASS with the usual string-scan limit

`service.py`, `mcp.py`, and `metadata.py` do not contain
`src.alignment`, `src.index.store`, `src.fingerprint`, `src.scoring`,
`solve_fgw`, `adjudicate(`, `sorted(match`, or `reverse=True`.

This does not prove the absence of every possible future compensation. It
does prove the current modules do not import verifier/index internals or
sort matches.

# Flagship usefulness

Issue gate: 2–4 useful seeded matches with mapping evidence.

At default tool `k=8`:

- 8 matches + 1 rejected (Lea polarity);
- 4 analogical cluster-mates in `accumulating-intermediary-failure`
  (Gabe / Kwame / Mei / Noah), each with ≥4 mapped nodes and preserved
  relations.

At example `k=15` (the committed R9 render fixture):

- 10 matches + 3 rejected;
- same four analogical cluster-mates plus complementary bridges
  (Diego, Yuki), approximates (Sora, Theo), and honest negatives
  (Sam rewire, Camille distractor).

The default MCP `k` is 8; the example payload is captured at 15. Clients
should pin `k` if they want the example card set rather than the default.

# Non-blocking nits

1. `tests/test_discovery.py::test_location_absent_unless_consented` contains
   a dead line `svc.registry.get(entry["session_id"]) if False else None`.
   The assertion still works via session-id comparison, but the test is
   sloppier than the leak test.
2. Source-scan cannot catch a later dynamic import or a compensation hidden
   behind an innocent helper name.
3. `k` is the accepted engine's candidate budget, not a hard cap on returned
   hits (`find(k=8)` returned 9 hits on this corpus). Discovery inherits that
   behavior; it does not invent it.
4. Match actions list `compare` / `explain` / `request_intro` even though
   only `discover_resonance` is added. Those first two already exist as R6
   tools; `request_intro` does not. Document this in R9 so the UI does not
   fake target acceptance.
5. Aggregation intensity is local-normalized among location-bearing matches
   only. That is correct for leak-safety. It is not a global population
   intensity.

None of these fail the issue #73 acceptance gate as written.

# Verdict

**ACCEPT as independent exact-head review input.**

PR #76 at `8b52a4a74f1aeabd1cb10466df160c854b0a7727` implements a thin
read-model over accepted R5/R6/R7. The four load-bearing properties were
reproduced on this machine. Known calibration gaps remain visible in the
DTO instead of being patched by discovery.

Recommended maintainer action: record `REVIEW_STATUS status: accepted` on
issue #73 if the maintainer agrees. This reviewer cannot and does not post
that event.

R9-VISUAL stays BLOCKED until that acceptance exists. This review does not
CLAIM #74.

# Confidence

**HIGH** that the reviewed head preserves engine order, leak-safety,
hard-rejection segregation, additive MCP, and full-suite green on
Python 3.12.3.

**MEDIUM** that string source-scan plus permutation tests will remain
sufficient after future edits; R9 should keep the permutation/leak tests as
merge blockers.

**LOW** that advertising `request_intro` in the DTO will be understood by
every client as capability-not-yet-on-the-wire without an R9 note.
