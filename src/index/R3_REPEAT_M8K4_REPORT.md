# R3-RETRIEVAL-REPEAT-M8K4 report

Status: **submitted result is an over-budget structural-equivalence-class NO-GO with working implementation evidence**

## Provenance

- Agent: `parshkov-openai-gpt5-codex-r3r-m8k4`
- Human sponsor / GitHub handle: `Parshkov`
- Provider/runtime: OpenAI, Codex workspace
- Model: GPT-5-based Codex; exact deployed model/version was not exposed
- Python: 3.12.8
- Base: accepted `origin/main` at `4727a75ccdc6604e2e5a642d5015f2591d2d9e75`
- Mission: R3-RETRIEVAL independent repeat, issue #41
- Run: `R3-RETRIEVAL-REPEAT-M8K4`
- Mission modified: no
- Blind constraints: none for R3; no blind research submission was inspected
- Web research: none; repository documents, frozen fixtures, GitHub issue/PR
  event streams, and executable local experiments were used

Accepted inputs:

- interface contract: `resonance-interfaces/0.1`
- schema: `thought-dna/0.1`
- Benchmark v0.1 manifest SHA-256:
  `1700935134235ab1a376779c54b0fbc70db19cc72d9c93bc5f06f9485cd7e49e`
- Benchmark v0.1 evaluation-config SHA-256:
  `96c28068b1798ef17e236e91de484f747ec9f33977edf6a49959a0f922e101f8`
- retrieval config SHA-256:
  `cda12f23d282806395c7f109adb54e489235871e46a0380291c9535ff81538aa`
- index format: `resonance-candidate-index/0.2`
- tie policy: `competition-min-rank+explicit-cutoff-group/0.1`
- feature version:
  `resonance-relational-fingerprint/0.1+e6ec0f5918841164`
- gate corpus snapshot:
  `4aca0ea32762053e554856b45f53578c794efd7e73d98f3d18f332e5d8b0c140`

The run read the public review finding on canonical PR #61 before implementation.
It did not copy or modify that contributor's branch. The repeat was implemented
from accepted ADR-0002, R1 interfaces, and frozen benchmark inputs in a clean
worktree.

After initial submission, independent review of canonical PR #61 identified
F1: lexicographic hard-cap tie-breaking made Recall@K depend on graph names.
This repeat revision applies that cross-run finding through competition/minimum
rank, explicit tie diagnostics, and optional cutoff-tie expansion.

## Implementation handoff

The repeat adds:

- order/ID/label-independent D0+D1 typed/directed path features;
- all-equal-path enumeration rather than relation-ID-dependent path selection;
- fixed 64-feature structural queries with per-scale allocation;
- DF/IDF and hard common-motif suppression;
- an inverted structural index with mutually injective correspondence voting;
- inverted content and Knowledge DNA channels without a corpus-wide query scan;
- separate channel scores/ranks and deterministic seed correspondences;
- competition/minimum ranks for equal scores plus explicit tied-best and cutoff
  groups, with opt-in tie-aware expansion;
- fail-closed polarity/verification flags;
- incremental upsert/remove, lazy corpus snapshots, scale statistics, and
  channel-level postings/latency diagnostics; and
- integrity-checked persistence that retains and verifies the complete DF/config
  policy and rejects forged version metadata.

No verifier decision, semantic node-pair mask, MCP type, or benchmark gold was
added to the retrieval path.

## Frozen Thought-DNA gate

Command:

```text
PYTHONDONTWRITEBYTECODE=1 python3 tests/r3_repeat_m8k4_harness.py --full --scale-sizes 1000,10000,100000
```

Gate-only corpus: 96 candidate graphs. Structural channel only. Each query used
exactly 64 selected features and touched 4,334 postings.

| Metric | Result | Gate | Outcome |
|---|---:|---:|---|
| SOW | 12/12 | >= 10/12 | PASS |
| hard-cap specific-ID Recall@20 | 2/6 = 0.333 | >= 0.50 | **FAIL / name-dependent** |
| hard-cap specific-ID Recall@5 | 0/6 | >= 4/6 | **FAIL / name-dependent** |
| competition/min-rank Recall@5 | 6/6 | >= 4/6 | PASS |
| tie-aware Recall@20 | 6/6 | >= 0.50 | PASS, but returns 48 |
| analogue above generic distractor | 6/6 | 6/6 | PASS |
| generic structural margin | +0.680614 in every pack | positive | PASS |
| deterministic replay | identical rank/score/seed hash | required | PASS |
| polarity flag | `polarity_reliable=false` | required | PASS |

Pack-local C09 hard-order positions are `6, 14, 22, 30, 38, 46`, but every
target now correctly carries structural channel rank 1.

### Failure attribution: over-budget observational equivalence class

All six gate queries have the same D0 roles and the same D1 directed,
relation-typed neighborhoods. For every query, these eight families in every
gate pack score exactly `1.0` structurally:

```text
C01 C02 C03 C06 C07 C09 C15 C16
```

That is 8 candidates x 6 packs = **48 perfect structural ties**. Gold marks only
the same-pack C09 as the cross-domain target. A structural-only system cannot
identify that pack-local member from canonical structure. Breaking the tie by
labels would blend semantic evidence into the structural score; breaking it by
`Gxx-C09` IDs would leak benchmark identity. Both violate ADR-0002.

The hard `CandidateIndex.query(..., k=20)` surface still returns at most 20 and
now explicitly reports that it truncated a 48-member cutoff tie. The tie-aware
diagnostic surface returns all 48 and gives every member competition rank 1.
This removes graph naming from the metric, but the tie group remains larger
than the roughly 20-candidate verifier budget. The gate therefore remains a
NO-GO for the current representation/corpus combination rather than becoming a
false PASS through tie semantics.

This is why the repeat preserves the NO-GO instead of gaming Recall@K. The
mechanics do distinguish the intended structure from same-words/wrong-structure
and generic-motif controls, but the current gold asks structural retrieval to
choose among representation-identical candidates.

Recommended versioned benchmark follow-up (without mutating v0.1): vary the
gate-pack relation systems, judge cross-pack candidates, or score retrieval by
reviewed structural equivalence class rather than one arbitrary pack-local ID.

## Legacy E1 regression

The full stipulated 12-case MULTI matrix passed:

- worlds: rich random (`R`) and 80% causal-chain (`Z`);
- default seed at 1k, 10k, and 30k per world;
- three additional fixed seeds at 10k per world; and
- noisy analogue above every generic chain in all 12 cases.

The required D0-only rich-world control at 10k failed: noisy analogue rank 5,
best chain rank 4. For the default rich-world MULTI runs, postings touched were
`216 -> 819 -> 1,834` at `1k -> 10k -> 30k`, reproducing the accepted reference
pattern. These legacy toy enums are provenance, not a substitute for the frozen
Thought-DNA result above.

## Synthetic scale replay

Distribution: repeated three-node causal-chain distractors plus one four-node
intended analogue. This is deliberately labelled synthetic.

| Corpus IDs | Build cumulative | Target rank | Postings touched | Query p50 | Cold-inclusive p95 | Estimated bytes |
|---:|---:|---:|---:|---:|---:|---:|
| 1,000 | 0.384 s | 1 | 16 | 0.369 ms | 1.902 ms | 1,154,944 |
| 10,000 | 3.906 s | 1 | 16 | 0.361 ms | 7.567 ms | 11,522,944 |
| 100,000 | 40.063 s | 1 | 16 | 0.361 ms | 102.552 ms | 115,202,944 |

Touched postings are constant under the fixed budget/commonness policy. The
cold-inclusive p95 includes lazy corpus-snapshot hashing on the first query.

Unsupported claim: no extracted real-distribution 100k/1m replay exists, so
this run does **not** claim real-corpus scale or one-million-ID readiness.

## Validation

```text
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
```

Result: 55 tests, all passing. Coverage includes accepted pre-existing tests,
fixed-budget observability, no content full scan, separate Knowledge complement,
injective seeds, equal-path/ID invariance, persistence replay/tamper rejection,
incremental replacement/removal, configuration validation, and the frozen
observational-collision regression.

## Explicit limitations

- Frozen structural Recall@K is a recorded NO-GO, not a promotion claim.
- Real-distribution scale is unmeasured.
- Content tokenization is a deterministic baseline, not a production semantic
  model.
- Knowledge matching uses exact versioned IDs; ontology expansion is outside
  the hot path and outside this mission.
- Retrieval proposes candidates only. Polarity, contradiction, final mapping,
  and resonance classification remain verifier responsibilities.
