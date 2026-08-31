---
mission: R0-G
run: R0-G
contributor: Parshkov
agent_id: parshkov-openai-gpt5-codex-a6f2
provider: OpenAI
agent_or_model: GPT-5 family (exact Codex model/version not exposed to this run)
model_mode: not exposed
execution_environment: Codex desktop
date: 2026-08-30
mission_modified: false
web_research_used: true
code_execution_used: true
external_tools_used: web search, local Python, Git, GitHub CLI
additional_agents_used: false
blind_constraints_preserved: true
---

# Decision

Build Benchmark v0.1 as a **contrastive metamorphic behavioral suite**, not a large natural-language dataset: eight hand-authored 10–14-node seed Thought Graph packs, each expanded into the 14 required families plus node-order and extraction-error controls (128 judged pairs, at most about 136 graphs). Every pack must oppose a different-vocabulary/same-structure candidate to a same-vocabulary/wrong-structure candidate. Freeze six packs as the architecture gate and expose two only for threshold calibration. This is implementable in three hours, tests the claimed invariances separately, yields gold node mappings, and can reject a system that succeeds through words or generic motifs.

# Confidence

**HIGH** that this is the smallest useful R0 measuring instrument; **MEDIUM** that its numerical thresholds will transfer beyond authored graphs. The main uncertainty is annotation validity for analogical and complementary cases. v0.1 should gate engineering, not support population-level scientific claims. A second human should review the gold relations before an ADR treats failures as algorithm failures.

# Best Algorithm / Method

Use a capability-by-test matrix inspired by behavioral testing, with deterministic **metamorphic relations** generated from each seed and manually authored contrast cases. This gives known expected changes without pretending that arbitrary human-thought similarity has an objective oracle.

Each of eight domain-diverse packs contains one seed and one candidate for each family:

| Class | Families per seed |
|---|---|
| Direct/approximate positive | paraphrase; vocabulary substitution; irrelevant branch; partial graph; granularity expansion; same-domain structural match; serialization-order permutation; modest extraction error |
| Analogical positive | cross-domain causal analogy |
| Negative | same vocabulary/different structure; same topic/different intent; locally similar/globally inconsistent; generic motif; accidental semantic similarity |
| Complementary | branch continuation; disjoint useful method/knowledge branch |

That is 16 judgments per pack: 2 calibration packs (32) and 6 gate packs (96). Transformations operate on copied graph objects with deterministic seeds. Paraphrase changes only concept text; ordering permutes serialized nodes/edges; irrelevant/partial/granularity/extraction transformations record their edit manifest and surviving gold mapping. Same-domain, analogy, intent, accidental-semantic, and complementary candidates are manually authored. Two reviewers should adjudicate only those manually authored cases; generator-derived mappings are exact by construction.

Use JSONL for graphs and judgments. Engine input is separate from benchmark-only gold data:

```text
graphs.jsonl: {graph_id, nodes:[{id,type,concept}],
               edges:[{id,source,target,type}]}
pairs.jsonl:  {case_id, split, family, query_graph, candidate_graph,
               gold_class, evaluation_mode, relevant,
               gold_node_pairs, gold_edge_pairs, bridge_pairs,
               transform_manifest, rationale}
```

`gold_class` is exactly `direct | approximate | analogical | complementary | negative`. `bridge_pairs` is populated only for complementarity; it identifies the query endpoint and candidate start/method node rather than falsely claiming an isomorphism. No expected numeric score is stored.

Compute:

- **Recall@K**, macro-averaged by query and family, from mode-specific relevance sets.
- **Resonance precision** `TP/(TP+FP)` after selecting a threshold on calibration packs only.
- **Node correspondence F1** on the set of predicted versus gold node pairs; also report exact-map accuracy. Pair F1 avoids the inflated “accuracy” of a mostly-empty correspondence matrix.
- **Edge-preservation accuracy**: fraction of gold mapped relations whose type and direction are preserved.
- **Robust@5(f)**: Recall@5 for transformation family `f`; report every family and their macro mean.
- **Negative FPR(f)**: accepted negatives divided by negatives in family `f`.
- **Structure-over-words win rate (SOW)**: for each gate seed, compare both vocabulary-substituted and cross-domain structural positives with its same-vocabulary rewired negative; score 1 only when `s(seed, structural) > s(seed, lexical_negative)`. Ties fail.

Freeze the candidate configuration and commit hash before opening gate results. Because the repository is public, this is procedural isolation, not secrecy; after the first gate run, add new cases in v0.2 rather than tuning v0.1.

# Why It Fits Resonance

The suite makes the hard negative a paired preference rather than hoping aggregate accuracy reveals shortcutting. Metamorphic transforms isolate invariances A–I; pack-level splits prevent variants of one idea leaking between calibration and gate sets. Gold partial correspondences test explainability. Mode-specific qrels prevent a complementary graph from being mislabeled as direct resonance. The suite is algorithm-independent: retrieval, verification, semantic-only, and ablated systems produce the same ranked lists, scores, classes, and mappings for evaluation.

# Required Thought DNA

The engine receives only what the tests exercise.

**Each node must contain:** stable `id`; functional `type` (problem, goal, mechanism, constraint, evidence, method, outcome, or the later canonical equivalent); normalized/display `concept` text.

**Each edge must contain:** stable `id`; `source`; `target`; typed relation `type`. Direction is encoded by source/target. Parallel typed edges are permitted.

Graph IDs, gold mappings, family, transform manifest, rationale, and split are benchmark metadata, not Thought DNA. Confidence, timestamps, embeddings, provenance, and knowledge links are not required by this benchmark and must not be added merely to satisfy it.

# Required Graph Representation

A **directed typed multigraph**. Direction and relation type are necessary for same-words/different-reasoning negatives; multiedges avoid collapsing distinct causal, evidential, and constraining relations. Hyperedges and reified relations are out of scope for v0.1 because the gate cannot justify them yet. JSON list order has no semantics.

# Invariances

| Transformation | Supported | Partially | Not Supported | Mechanism |
|---|---:|---:|---:|---|
| A paraphrase | ✓ | | | concept-only metamorph |
| B vocabulary substitution | ✓ | | | synonym and cross-vocabulary variants |
| C node ordering | ✓ | | | list permutation sanity control |
| D irrelevant branches | ✓ | | | add typed distractor branch |
| E missing nodes | | ✓ | | delete 20–30%; surviving gold map |
| F different granularity | | ✓ | | subdivide one edge into 2–3 edges |
| G different graph sizes | | ✓ | | D–F jointly vary size |
| H domain substitution | | ✓ | | manual cross-domain analogy |
| I extraction mistakes | | ✓ | | one mistyped node or edge plus one spurious node |

“Supported” here means the expected relation should not change. Partial cases permit degradation but must remain retrievable. A causal reversal, changed intent, or information-bearing intermediate mechanism is explicitly **not** invariant.

# Retrieval vs Verification

The benchmark evaluates **BOTH** stages but does not prescribe either algorithm. Retrieval consumes each query plus a corpus and returns ranked graph IDs; direct/approximate, analogical, and complementary modes have separate relevance sets. Verification consumes a query-candidate pair and returns `{class, score, node_pairs, edge_pairs, bridge_pairs}`. Evaluate end-to-end results and an oracle-retrieval verifier run separately, so a missed candidate is not misdiagnosed as bad alignment.

# Computational Cost

Creating or validating the 128 cases is `O(128(V+E))`. Metric calculation is linear in returned rankings and mappings. For 50-vs-50 nodes, set-based correspondence scoring is `O(|M_pred|+|M_gold|)`; even scanning a dense 2,500-cell correspondence matrix is trivial. Twenty candidate verifications expose at most 50,000 matrix cells to the harness. The roughly 136-graph v0.1 corpus cannot validate million-corpus latency. For 1M thoughts, replay the fixed queries against 1M synthetic nonrelevant IDs and separately require index size, build time, p50/p95 latency, and Recall@K; do not infer scalability from this accuracy suite.

# Existing Implementations

- **NetworkX**: mature Python graph construction, isomorphism helpers, and edit paths; use for validation and transformations, not exact GED in the gate because exact GED is NP-hard and can be slow.
- **JSON Schema Draft 2020-12** plus Python `jsonschema`: stable validation for graph and judgment files; a small extra dependency.
- **NIST `trec_eval`**: authoritative, mature ranked-retrieval metrics and qrels format; C build is unnecessary if the small evaluator reproduces Recall@K in tests.
- **scikit-learn**: maintained TF-IDF/cosine semantic-shortcut baseline.
- **GraKeL**: supplies WL kernels for a rapid structural baseline, but its maintainers explicitly request help and modern dependency compatibility is a risk. Prefer a 30-line deterministic WL baseline for the gate, then cross-check GraKeL.

# Minimal Pseudocode

```text
seeds = author_8_seed_packs()
for seed_index, seed in enumerate(seeds):
    split = "calibration" if seed_index < 2 else "gate"
    for family in required_16_families:
        candidate, manifest, gold_map = make_or_author(seed, family)
        validate(candidate)
        emit_graph(candidate)
        emit_pair(seed, candidate, split, family, gold_map)

freeze(candidate_config_hash)
thresholds = calibrate(run(calibration_pairs))
pred = run(gate_pairs, thresholds)
metrics = score_rankings_classes_and_mappings(pred, gate_gold)

pass = (SOW >= 10/12
        and recall_at_5 >= .85
        and every_positive_family_recall_at_5 >= 4/6
        and resonance_precision >= .80
        and negative_fpr <= .10
        and every_negative_family_false_positives <= 1/6
        and node_pair_f1 >= .70
        and directed_edge_accuracy >= .75)
return "GO" if pass else "NO-GO"
```

If the system claims complementary retrieval, additionally require complement Precision@3 ≥ 0.67; otherwise report it as unsupported, not as a core false positive. Mandatory checks do not average into one score: strong semantics cannot compensate for failed structure controls.

# Toy Experiment

Within two hours, author four 4-node causal chains. For each, make (a) a different-domain graph with identical node-role/typed-edge structure and disjoint concept words and (b) a same-word graph with rewired directions/relation types. Compare concept-token TF-IDF cosine against a two-round, role-initialized, direction-and-edge-type-aware WL histogram cosine. Measure SOW.

A standard-library pilot executed during this run produced TF-IDF-like token-bag SOW `0/4` (structural-positive scores `0.0`, lexical-negative scores approximately `1.0`) and typed-WL SOW `4/4` (respectively `1.0` and `0.333`). This deliberately tiny result validates the test's ability to expose the shortcut, not WL as the architecture. Falsify the recommendation if the lexical baseline passes SOW, graph serialization changes results, or independent annotators cannot agree on at least 5/6 gate analogies.

# Failure Modes

1. Hand-authored analogies encode the author's theory and reward the expected architecture.
2. Transform templates leak family-specific artifacts that a system detects without resonance.
3. Generic chains make topology-only methods look better than they are.
4. Node correspondence gold is ambiguous under symmetric or repeated roles.
5. Public gate cases invite manual tuning and cease to measure generalization.
6. A single global threshold hides family- or mode-specific calibration failure.
7. Synthetic noise is cleaner than extraction errors from real contexts.
8. A 136-graph corpus says nothing reliable about million-corpus collision rates or latency.

# What NOT To Build

- No publication-scale crowdsourced dataset before the first algorithm survives 128 judgments.
- No random edge-rewiring-only benchmark; random negatives are too easy and unlike semantic confounds.
- No single “resonance accuracy” aggregate or unreviewed LLM-as-judge labels.
- No benchmark built from the candidate algorithm's own fingerprints.
- No embedding similarity as ground truth.
- No hidden test service, leaderboard, or synthetic million-graph corpus in the three-hour MVP.
- No exact GED dependency in the evaluator.

# Architecture Consequences

- Thought DNA v0.1 must preserve node role, concept, edge type, and direction.
- All comparison APIs must ignore serialization order.
- Retrieval must expose ranked IDs, not only a best match.
- Verification must return explicit partial node and edge correspondences.
- Direct, analogical, and complementary evaluation modes need distinct relevance judgments.
- Scores need calibration without assuming comparability across modes.
- The harness must support one-to-many gold pairs for granularity changes.
- Retrieval and verifier failures must be reported separately.
- Architecture changes require replaying immutable benchmark versions.
- The first GO is provisional until real extracted graphs and a larger collision corpus agree.

# Sources

1. [Ribeiro et al., *Beyond Accuracy: Behavioral Testing of NLP Models with CheckList* (ACL 2020)](https://aclanthology.org/2020.acl-main.442/) — capability × test-type organization and invariance/directional test patterns.
2. [Chen, Cheung, and Yiu, *Metamorphic Testing: A New Approach for Generating Next Test Cases* (1998)](https://www.cse.ust.hk/~scc/publ/CS98-01-metamorphictesting.pdf) — primary basis for deriving follow-up cases with known relations when a complete oracle is difficult.
3. [McCoy, Pavlick, and Linzen, *Right for the Wrong Reasons* (ACL 2019)](https://aclanthology.org/P19-1334/) — demonstrates why controlled lexical-overlap failures are necessary.
4. [Gentner, *Structure-Mapping: A Theoretical Framework for Analogy* (1983)](https://doi.org/10.1207/s15516709cog0702_3) — supports relation-preserving cross-domain gold cases rather than attribute overlap.
5. [NIST, TREC 2021 Overview, §2.2](https://trec.nist.gov/pubs/trec30/papers/Overview-2021.pdf) — authoritative definitions and macro use of cutoff precision/recall.
6. [Wang et al., *Deep Learning of Partial Graph Matching via Differentiable Top-K* (CVPR 2023)](https://openaccess.thecvf.com/content/CVPR2023/html/Wang_Deep_Learning_of_Partial_Graph_Matching_via_Differentiable_Top-K_CVPR_2023_paper.html) — motivates partial correspondence and scale-varying/outlier cases.
7. [Shervashidze et al., *Weisfeiler-Lehman Graph Kernels* (JMLR 2011)](https://www.jmlr.org/papers/v12/shervashidze11a.html) — efficient transparent structural baseline, not benchmark ground truth.
8. [NetworkX similarity documentation](https://networkx.org/documentation/stable/reference/algorithms/similarity.html) — immediate graph/edit-path tooling and explicit exact-GED cost warning.
9. [Siglidis et al., *GraKeL: A Graph Kernel Library in Python* (JMLR 2020)](https://www.jmlr.org/papers/v21/18-370.html) and [current repository notice](https://github.com/ysig/GraKeL) — prototype implementation plus maintenance/dependency risk.
10. [JSON Schema Draft 2020-12](https://json-schema.org/draft/2020-12) — authoritative machine-validation format for durable fixtures.

**GO** for this benchmark design. **NO-GO** for any first fingerprint+verifier configuration that misses any mandatory gate above; retain its per-family failures as evidence rather than averaging them away.
