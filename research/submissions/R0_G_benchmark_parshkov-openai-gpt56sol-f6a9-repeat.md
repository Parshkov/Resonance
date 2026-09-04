---
mission: R0-G
run: R0-G-REPEAT-F6A9
contributor: Parshkov
agent_id: parshkov-openai-gpt56sol-f6a9
agent_or_model: OpenAI GPT-5.6 Sol
model_mode: xhigh
runtime: Codex
date: 2026-09-01
mission_modified: false
web_research_used: true
code_execution_used: true
additional_agents_used: false
blind_constraints: none
prior_exposure: Accepted R0 synthesis, executable Benchmark v0.1, issue 56, and the merged R0-D contraction audit were read; the earlier R0-G submission was not read.
---

# Decision

Use a **64-pair contrastive metamorphic architecture gate**: four independent 10–14-node pivot packs, one calibration pack and three immutable gate packs, each with the accepted 16 behavioral families. Keep engine inputs, independently reviewed gold, and system predictions separate. Require structured node, relation, bridge, contradiction, and edge-to-path outputs; the evaluator derives every correctness metric from those outputs and gold. A system-supplied verdict or error counter is diagnostic only and can never grant PASS. For the current repository, preserve frozen v0.1 and make the contraction fix a versioned v0.2 delta, not a relabeling.

# Confidence

**MEDIUM-HIGH** for this as a same-day architecture kill test; **LOW** for population-level performance claims. The main uncertainty is whether three gate pivots cover enough structural diversity and whether independent reviewers agree on analogical and complementary mappings. A pass permits the next experiment, not a production claim. Current Benchmark v0.1's larger eight-pack design is preferable once authored; 64 pairs is the smallest useful starting instrument.

# Best Algorithm / Method

This is a measurement design, not a matching algorithm.

1. Author four domain-diverse pivot Thought Graphs.
2. Generate a local contrast set around each pivot. Transformations expected to preserve class test invariance; minimal meaning-changing transformations test anti-invariance.
3. Use synthetic transformations for paraphrase, vocabulary substitution, irrelevant branches, partial observation, transparent subdivision, serialization permutation, modest extraction error, and controlled polarity/direction/rewire negatives. Review generated outputs before freezing.
4. Manually author and independently review same-domain structural matches, cross-domain analogy, changed intent, globally inconsistent local motifs, generic motifs, accidental semantic overlap, and both complementary families.
5. Give the engine only graph/text inputs. Keep labels and mappings in the evaluator, analogous to a retrieval collection's separate corpus, queries, and relevance judgments.
6. Freeze schemas, fixture bytes, candidate configuration, and hashes before opening gate outputs.

For case `c`, let `M_c` be predicted node/relation/path mappings and `G_c` reviewed gold. Mapping precision/recall/F1 are computed on canonical ID pairs, maximizing over declared automorphic alternatives. For a predicted edge-to-path match `m=(e_q,[e_1...e_k])`, derive:

```text
bad(m,c) = path_is_malformed
        OR realized_intermediates(m) intersects must_preserve_nodes(c)
        OR m is in forbidden_edge_path_matches(c)
        OR m is not in allowed_edge_path_matches(c)
```

The contraction gate is `sum(bad(m,c)) == 0` **and** transparent-granularity recall passes. The candidate's `reported_false_contractions` is ignored for adjudication. Contrast consistency is non-compensating: each gate pack must cross the intended local decision boundary correctly, not merely raise a macro-average.

Minimum gate for three immutable packs:

- overall positive Recall@5 `>= 0.85`; each positive family at least `2/3`;
- structure-over-words `6/6`: vocabulary-substitution and cross-domain positives each outrank the paired same-vocabulary/wrong-structure negative; ties fail;
- resonance precision `>= 0.80`; zero false positives across the five hard-negative families in the tiny gate;
- node-pair F1 `>= 0.70`; directed typed-edge accuracy `>= 0.75`;
- transparent granularity `3/3` and evaluator-derived false contractions `== 0` on reviewed positive and negative subdivisions;
- serialization mapping/class/score-vector delta `== 0`; polarity/direction rejection `3/3`;
- every applicable gate must pass. Missing output is `not_evaluated`, never PASS.

These are falsification thresholds, not confidence intervals. Expand pack count before using rates as performance estimates.

# Why It Fits Resonance

Metamorphic pairs directly encode Resonance's invariances without needing a perfect scalar oracle. Contrast packs place “different words/same structure” next to “same words/different structure,” so lexical shortcuts cannot hide behind unrelated easy cases. Explicit mappings test the claimed product behavior—coherent correspondence—rather than only a class label. Stage-separated retrieval and oracle-inclusion verification localize failures. Evaluator-owned verdicts make the gate adversarially auditable.

# Required Thought DNA

The benchmark consumes, but does not extend, Thought DNA v0.1:

- stable graph/node/relation IDs and schema version;
- node role, optional normalized concept/knowledge anchors, `atomic`, confidence, and provenance;
- directed relation type, assertion, modality, confidence, and provenance;
- canonical serialization;
- derived mappings that always expand to canonical node/relation IDs.

Benchmark-only gold includes `gold_node_pairs`, typed/directed `gold_edge_pairs`, automorphic alternatives, `bridge_pairs`, `allowed_edge_path_matches`, `forbidden_edge_path_matches`, and `must_preserve_nodes`. These are evaluator data, never Thought DNA or engine input.

# Required Graph Representation

A directed typed property graph is sufficient. Multiedges should be representable because distinct relations can share endpoints. The benchmark must not require a tree, hypergraph, or hidden natural-language judgment at evaluation time. Complementarity uses directional bridge gold rather than pretending the pair is isomorphic.

# Invariances

| Transformation | Supported | Partially | Not Supported | Mechanism |
|---|:---:|:---:|:---:|---|
| A paraphrase | ✓ | | | paired surface rewrite; same canonical mapping |
| B vocabulary substitution | ✓ | | | structure-only paired rank and SOW |
| C node ordering | ✓ | | | canonical IDs/serialization; zero delta |
| D irrelevant branch | | ✓ | | partial map plus explicit unmatched branch |
| E missing nodes | | ✓ | | surviving-map F1 and containment |
| F granularity | | ✓ | | reviewed allow/forbid path gold; preservation nodes |
| G graph size | | ✓ | | partial mappings; separate containment/symmetric coverage |
| H domain substitution | | ✓ | | manual cross-domain gold; low-semantic structural control |
| I extraction mistakes | | ✓ | | grounded error injection and duplicate-extract scoring |

Direction, causal sign, assertion, modality, and changed intent are anti-invariances and must not be normalized away.

# Retrieval vs Verification

**BOTH**, with separate adjudication.

- Retrieval: ranked graph IDs, per-channel evidence, Recall@5/20, postings touched, latency, versions, and `polarity_reliable=false` for the structural channel.
- Verification under oracle inclusion: class, partial injective node mapping, direct relation mappings, realized edge-to-path mappings, unmatched regions, contradictions, component vector, and versions.
- End to end: a retrieval miss cannot be called a verifier error; a bad oracle-pair mapping cannot be hidden by retrieval.

# Computational Cost

Fixture generation/evaluation is linear in fixture and prediction size: `O(P(|V|+|E|+|M|))`, with `P=64`; it is trivial on one CPU. For a 50×50 pair, the benchmark times whatever verifier is submitted and checks its mapping in linear time. Twenty oracle candidate comparisons are feasible as an MVP but algorithm-dependent; the benchmark should retain the declared p95 target.

A 64-pair gate says nothing about retrieval over one million thoughts. Run a separate, labeled synthetic replay at `10^3..10^6` with recorded motif-frequency assumptions, then validate on an extracted distribution. Report index bytes, posting lengths/touches, latency, and recall; never infer million-scale behavior from the small gate.

# Existing Implementations

- Python standard library is sufficient for a deterministic generator/evaluator; the attached falsifier deliberately uses no dependencies.
- `jsonschema` plus JSON Schema Draft 2020-12 can close fixture/prediction records. Risk: format validation does not establish semantic validity.
- NetworkX `DiGraphMatcher`/VF2 can validate exact synthetic controls and enumerate alternative isomorphisms. Risk: it is not the approximate Resonance verifier and subgraph semantics must be explicit.
- NIST `trec_eval` can cross-check standard retrieval metrics. Risk: it does not score graph mappings or conditional invariances.
- Hypothesis can generate permutation, deletion, and subdivision property tests. Risk: unconstrained generators can create semantically invalid Thoughts, so generators need closed policies and fixed replay seeds.

# Minimal Pseudocode

```text
freeze(calibration, gate, schemas, review_ledger, manifest_hash)
freeze(candidate_commit, candidate_config)

for case in gate:
    ranked = retrieve(case.query)
    record Recall@K and channel evidence
    result = verify(case.query, case.candidate)  # oracle inclusion
    validate result IDs against canonical graphs
    score node/relation/bridge mappings against reviewed alternatives
    for path_match in result.edge_path_matches:
        reconstruct ordered path from candidate relation IDs
        derive bad(path_match, case) from preservation gold
    attribute exactly one failing stage

PASS iff every mandatory family/anti-invariance/replay gate passes
```

# Toy Experiment

Run:

```bash
python3 research/experiments/R0_G_repeat_benchmark_audit.py
```

The 11-case matrix contains two transparent positives and nine negative contractions: meaningful, atomic, branch, merge, relation mixture, sign, modality, assertion, and path-length boundaries. On Python 3.12.8, fixture SHA-256 was `e49c834e518f6c5d86c4f31de98a42acbc21b7c12b355159d7204fae01e949ef`.

- exact-only: zero false contractions but transparent recall `0.0` → FAIL;
- map-everything and self-report zero: recall `1.0`, self-report `0`, evaluator derives `9` false contractions → FAIL;
- gold-compliant: recall `1.0`, derived false contractions `0` → PASS.

The read-only audit also found eight v0.1 transparent positives, zero explicit negative-contraction cases, no preservation fields, no structured edge-path prediction field, and direct summation of the candidate's required counter. This reproduces the auditability failure without modifying frozen gold.

# Failure Modes

1. A lexical baseline passes because negatives have lower word overlap than positives.
2. Transform generators leak family-specific node counts or ID patterns.
3. One arbitrary mapping penalizes a correct automorphism.
4. The author encodes their preferred analogy into manual gold; no independent reviewer catches it.
5. An engine returns only a scalar or self-reported error count, making the gate unauditable.
6. Exact-only matching avoids false contractions by missing every valid subdivision.
7. A path matcher contracts meaningful, atomic, branching, modal, negated, or overlong mediators.
8. Macro accuracy hides a polarity, direction, or global-consistency failure.
9. Public immutable packs are repeatedly tuned against and become de facto training data.
10. Uniform synthetic distractors create a false million-corpus scaling claim.

# What NOT To Build

- Do not use an LLM as gold judge or pairwise evaluator.
- Do not store expected model scores; store classes, mappings, and constraints.
- Do not blend retrieval and verifier metrics into one number.
- Do not let the candidate report its own correctness counters.
- Do not mutate v0.1 fixtures or thresholds after observing a failure.
- Do not build a publication-scale corpus before the architecture survives 64 contrastive pairs.
- Do not claim real-distribution or million-scale performance from synthetic replay.

# Architecture Consequences

- Add structured realized `edge_path_matches` to verifier predictions.
- Add reviewed `allowed_edge_path_matches`, `forbidden_edge_path_matches`, and `must_preserve_nodes` to benchmark gold.
- Derive contraction violations in the evaluator; deprecate adjudication by self-report.
- Keep graph input projection free of all benchmark gold.
- Freeze calibration, gate, candidate config, schemas, and hashes before evaluation.
- Preserve per-family and per-stage results; no compensating aggregate.
- Require automorphism-tolerant mapping alternatives.
- Keep complementary bridges directional and separately scored.
- Version fixture/gold changes; replay old versions unchanged.
- Treat small-suite PASS as permission to scale the experiment, not evidence of production readiness.

# Sources

1. T. Y. Chen, S. C. Cheung, and S. M. Yiu, [“Metamorphic Testing: A New Approach for Generating Next Test Cases”](https://www.cse.ust.hk/faculty/scc/publ/CS98-01-metamorphictesting.pdf), HKUST-CS98-01, 1998. Foundation for deriving follow-up cases and checking relations between outputs when a full oracle is expensive.
2. Matt Gardner et al., [“Evaluating Models' Local Decision Boundaries via Contrast Sets”](https://aclanthology.org/2020.findings-emnlp.117/), Findings of EMNLP 2020. Supports expert-authored minimal perturbations and all-members contrast consistency.
3. Marco Tulio Ribeiro et al., [“Beyond Accuracy: Behavioral Testing of NLP Models with CheckList”](https://aclanthology.org/2020.acl-main.442/), ACL 2020. Supports a capability × test-type matrix and reporting failures beyond aggregate accuracy.
4. Yuan Zhang, Jason Baldridge, and Luheng He, [“PAWS: Paraphrase Adversaries from Word Scrambling”](https://research.google/pubs/paws-paraphrase-adversaries-from-word-scrambling/), NAACL 2019. Demonstrates why high lexical-overlap nonmatches are necessary to expose word-order/structure shortcuts.
5. NIST, [“How To TREC”](https://trec.nist.gov/howto.html). Authoritative precedent for separating corpus, topics, relevance judgments, runs, and evaluation protocol.
6. Hongteng Xu et al., [“Gromov-Wasserstein Learning for Graph Matching and Node Embedding”](https://proceedings.mlr.press/v97/xu19b.html), ICML 2019. Confirms that structural graph comparison should expose a correspondence, not only a distance.
7. [JSON Schema Draft 2020-12 specification](https://json-schema.org/specification). Authoritative format for closed, versioned fixture and prediction validation.
8. [NetworkX VF2 documentation](https://networkx.org/documentation/stable/reference/algorithms/isomorphism.vf2.html) and [Hypothesis documentation](https://hypothesis.readthedocs.io/en/latest/). Immediately usable exact-control and property-generation tools, with the limitations stated above.

**GO — use the 64-pair design as the smallest architecture falsifier, preserve the stronger frozen v0.1 evidence, and require evaluator-derived contraction judgments in the next version. NO-GO for any benchmark gate that trusts a candidate's self-reported correctness counter.**
