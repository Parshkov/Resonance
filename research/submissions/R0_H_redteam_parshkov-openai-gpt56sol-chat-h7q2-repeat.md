---
mission: R0-H
run: R0-H-REPEAT-H7Q2
agent_id: parshkov-openai-gpt56sol-chat-h7q2
contributor: Parshkov
agent_or_model: GPT-5.6 Sol
provider: OpenAI
runtime: ChatGPT chat
date: 2026-09-02
mission_modified: false
web_research_used: true
code_execution_used: true
base_commit_observed: b61e980b20812d700f5904a07ad7da3fc645633c
blind_group: null
blind_constraints_preserved: true
prior_R0_H_submission_contents_read: false
---

### Decision

**NO-GO for domain-invariant sparse structural fingerprints as Resonance's primary corpus retrieval key until they beat a cheap semantic/anchor baseline on hard negatives.** The architecture's strongest surviving idea is not “Shazam for thought”; it is **explicit typed relations plus a globally consistent verifier**. The Shazam analogy fails at the indexing layer because audio fingerprints exploit highly discriminative local measurements, while human reasoning graphs reuse a tiny vocabulary of generic motifs (`causes`, `enables`, `blocks`, chains, forks, feedback). Making those fingerprints invariant enough for cross-domain analogy strips exactly the semantics that make them discriminative. Keep two-stage retrieval/verification, but retrieve conservatively by semantic/functional anchors and verify with signed, directed, typed relational constraints. Structural fingerprints should remain an experimental secondary channel, not the identity of the engine.

### Confidence

**HIGH** on killing “structure-only/local-relational fingerprint = universal primary index.” **MEDIUM** on the replacement retrieval stack because the project still needs its own benchmark. The decisive uncertainty is empirical: whether a carefully typed functional-role vocabulary can preserve cross-domain analogy while keeping local fingerprints rare enough at million-item scale.

### Best Algorithm / Method

The cheapest falsification target is the retrieval stage.

Use two baselines against any proposed structural index:

1. **Semantic/anchor retrieval baseline**
   - semantic embedding of the thought summary/original text;
   - inverted index over high-precision typed anchors: node role, signed relation, modality, temporal direction, knowledge/concept identifiers where available;
   - union the top candidates.

2. **Constraint-aware structural verifier**
   - create candidate node correspondences from compatible functional roles / normalized concepts;
   - enforce edge direction, relation type, sign/polarity, modality and temporal constraints;
   - prefer a globally coherent mapping over a bag of local motif matches;
   - return an explicit node/edge correspondence or abstain.

This is closer to MAC/FAC than to Shazam. MAC/FAC's first stage is deliberately cheap and non-structural/content-vector based; the expensive stage uses structure mapping. That is evidence against assuming structural retrieval must itself be the novelty.

A structural-fingerprint channel can be tested in parallel, but it should earn its place by improving recall on cross-domain analogies without exploding false positives.

### Why It Fits Resonance

The red-team result follows from four pressure points:

- **Analogy is not a bag of motifs.** Structure-Mapping Theory emphasizes systems of relations and higher-order systematicity, so isolated two- or three-edge matches are weak evidence.
- **Human retrieval itself is surface-biased.** MAC/FAC was built partly to model the observation that retrieval is much more affected by superficial similarity than deliberate similarity judgment. A primary structural index fights that empirical fact and may pay a large recall cost.
- **Local graph descriptors are cheap because they are lossy.** Weisfeiler-Lehman subtree kernels efficiently count/refine local labeled neighborhoods, but local signatures are not a complete graph identity and do not directly yield the one coherent correspondence Resonance needs.
- **The expensive alternatives are genuinely expensive/fragile.** General graph edit distance is NP-hard. Gromov-Wasserstein-style objectives are non-convex numerical optimizations and produce soft couplings, useful experimentally but risky as an MVP default.

The architecture is therefore most vulnerable where it assumes a Shazam-like sparse relational fingerprint can be simultaneously invariant, rare, and meaningful.

### Required Thought DNA

The verifier cannot safely work if Thought DNA discards:

- node functional role (`goal`, `mechanism`, `constraint`, `evidence`, `outcome`, etc.);
- normalized concept plus original evidence span/provenance;
- edge relation type;
- edge direction;
- **polarity/sign** (`causes` vs `prevents`, supports vs contradicts);
- modality/strength (`may`, `likely`, `must`, `observed`);
- temporal ordering where causal interpretation depends on it;
- assertion vs hypothesis/question;
- optional grouping/higher-order relation or reified relation when a relation itself is qualified;
- extraction confidence/abstention.

Do **not** force global ontology IDs merely to make indexing convenient. A wrong canonicalization is worse than a missing one.

### Required Graph Representation

A **directed typed property graph with optional reified/higher-order relations** is the minimum safe representation.

A plain unlabeled graph is too lossy. A tree is too restrictive for converging causes, shared evidence, cycles and feedback. A hypergraph is not required for the MVP if n-ary/higher-order relations can be reified as nodes with typed incident edges.

### Invariances

| Transformation | Supported | Partially | Not Supported | Mechanism |
|---|---:|---:|---:|---|
| A paraphrase |  | yes |  | semantic normalization / anchor retrieval |
| B vocabulary substitution |  | yes |  | functional roles + concepts; verify structure |
| C node ordering | yes |  |  | graph representation |
| D irrelevant branches |  | yes |  | subgraph verification / bounded penalties |
| E missing nodes |  | yes |  | partial mapping with explicit confidence loss |
| F different granularity |  | yes |  | only contract demonstrably disposable mediators |
| G different graph sizes |  | yes |  | subgraph mapping, not whole-graph equality |
| H domain substitution |  | yes |  | only when functional relation semantics remain compatible |
| I extraction mistakes |  | yes |  | provenance/confidence + abstention; no magic invariance |

The dangerous invariance is **F**. If the system freely contracts `A -> X -> Y -> B` into `A -> B`, it erases meaningful mediators. Granularity invariance must be evidence-based, not a generic transitive closure rule.

### Retrieval vs Verification

**FAST RETRIEVAL:** semantic ANN + typed-anchor inverted lists, optionally unioned with an experimental structural channel.

**EXPENSIVE VERIFICATION:** a globally consistent, signed/directed typed mapping that returns the correspondence. An SME-like constraint system is attractive because the output is an interpretation/mapping rather than only a scalar. A bounded graph-edit or optimal-transport score may be an auxiliary feature, not the source of truth.

At 1M thoughts, the test is simple: if structural fingerprints cannot push known cross-domain positives into top-K **without** pulling thousands of generic-motif false positives, they fail as the primary index.

### Computational Cost

- **50 vs 50 nodes:** candidate correspondence generation is up to ~2,500 node pairs before pruning. A rule/role filtered verifier can remain practical if candidate sets are sparse.
- **Top 20 comparisons:** feasible for an SME-like or bounded approximate verifier; even roughly quadratic local bookkeeping is modest at 50 nodes.
- **1M corpus:** full pairwise structural comparison is impossible. ANN/inverted retrieval is appropriate. Structural fingerprint postings become dangerous if motifs are common because posting lists approach corpus scale.
- **Graph edit distance:** exact/general computation is NP-hard; unsuitable as the default verifier for this MVP.
- **Gromov-Wasserstein:** iterative, non-convex soft matching can be useful as a research comparator, but it adds numerical tuning and does not naturally encode all sign/modality constraints.

### Existing Implementations

- **NetworkX** — graph data structures, VF2-style matching utilities, WL graph hashing; mature Python baseline, but not a complete analogy engine.
- **GraKeL** — graph kernels including WL-family methods; useful for a retrieval baseline, not correspondence explanation.
- **POT (Python Optimal Transport)** — Gromov-Wasserstein routines; useful for experiments, with numerical/optimization dependency risk.
- **sentence-transformers / SBERT-family embeddings** — cheap semantic retrieval baseline that any structural index must beat on the project's hard-negative benchmark.
- **SME literature/code lineage** — conceptually strong for globally coherent mapping; integration effort and representation engineering are the main risks.

### Minimal Pseudocode

```text
extract(context):
    G = typed_graph_with_provenance(context)
    validate_direction_sign_modality(G)
    return G

retrieve(G, text, K):
    C1 = semantic_ann(text, K_sem)
    C2 = inverted_anchor_lookup(high_precision_anchors(G), K_anchor)
    C3 = optional_structural_fingerprint_lookup(G, K_struct)
    return rank_union(C1, C2, C3)[:K]

verify(Gq, Gc):
    candidates = compatible_node_pairs(Gq, Gc)
    mapping = globally_consistent_mapping(
        candidates,
        hard_constraints=[direction, sign, incompatible_relation_types],
        soft_constraints=[concept_similarity, missing_nodes, extra_branches]
    )
    if mapping.coverage < threshold or contradictions(mapping) > limit:
        return ABSTAIN_OR_REJECT
    return mapping, evidence, confidence
```

### Toy Experiment

I executed a small deterministic collision probe (seed 42; 5,000 random 25-node DAGs; 3 relation labels; 4 generic node-role labels). It compares two tempting two-hop fingerprints:

1. **relation-sequence-only** — strips node semantics to maximize cross-domain invariance;
2. **typed-two-hop-path** — restores coarse node roles.

For one fixed query, Jaccard similarity against 4,999 unrelated random graphs was:

```text
relation-sequence-only: query_features=7 mean=0.593 p95=0.875 p99=0.875 max=1.000
typed-two-hop-path:     query_features=15 mean=0.012 p95=0.059 p99=0.095 max=0.200
```

This is not a benchmark of the Resonance engine. It is a falsifier for a design intuition: **removing semantic/role information to gain domain invariance can make local relational fingerprints catastrophically non-discriminative.** Reintroducing type information fixes collisions, but then cross-domain invariance depends on stable functional-role normalization—the hard problem has merely moved into extraction.

Reproduction: `python research/experiments/R0_H_repeat_h7q2_collision_probe.py`.

A real gate should repeat this with curated Thought pairs and corpus-scale posting-list statistics.

### Failure Modes

Concrete adversarial pairs a naive implementation must survive:

| # | Thought A | Thought B | Naive failure |
|---|---|---|---|
| 1 | `sleep loss -> stress` | `stress -> sleep loss` | same words, reversed causality |
| 2 | `increase dose -> reduces pain` | `increase dose -> increases pain` | polarity/sign erased |
| 3 | `idea -> safety review -> launch` | `idea -> bypass controls -> launch` | granularity contraction hides critical mediator |
| 4 | `A -> B <- C` | `A -> B -> C` | same nodes, collider vs chain |
| 5 | `signal -> amplifier -> output` | `output -> feedback -> amplifier -> output` | feed-forward vs feedback cycle |
| 6 | `heat accumulates -> degradation -> failure` | `rumor accumulates -> trust degradation -> failure` | structurally neat but may be useless spurious analogy without mechanism/goal context |
| 7 | `drug treats disease` | `disease selects drug resistance` | role/relation semantics swapped |
| 8 | `X may cause Y` | `X reliably prevents Y` | modality + polarity collapsed |
| 9 | `warning precedes intervention -> harm falls` | `harm rises -> warning -> intervention` | temporal/causal direction confused |
| 10 | `A -> X -> B` where X is bookkeeping | `A -> X -> B` where X is the actual mechanism | identical topology, mediator importance differs |
| 11 | `constraint blocks goal` | `evidence contradicts hypothesis` | same signed motif, different functional semantics |
| 12 | one extractor emits `A -> B`; another splits `A -> X -> Y -> B` | same underlying thought | extraction instability causes false non-match or unsafe contraction |

### What NOT To Build

- **Do not build a universal structure-only hash as the primary index.**
- Do not use transitive closure/contraction as a blanket granularity fix.
- Do not treat WL/kernel similarity as proof of analogy; it is a candidate feature.
- Do not make exact graph edit distance the MVP verifier.
- Do not make Gromov-Wasserstein the default simply because it handles unequal spaces.
- Do not let an LLM “repair” bad graph matches after the fact; that destroys reproducibility.
- Do not freeze a large Thought DNA ontology before demonstrating that each field changes retrieval or verification.
- Do not claim cross-domain analogy unless the system beats semantic retrieval on intentionally different-domain positives **and** generic-motif negatives.

### Architecture Consequences

1. Keep retrieval and verification separate.
2. Kill the assumption that both stages must be structural.
3. Make direction, sign, modality and provenance non-negotiable.
4. Treat functional roles as a critical experimental variable, not decoration.
5. Make mediator contraction opt-in and benchmarked.
6. Require every accepted match to expose one coherent mapping.
7. Add a semantic/anchor baseline to every structural retrieval benchmark.
8. Measure fingerprint document frequency/posting-list size at scale; common fingerprints are not fingerprints.
9. Require an abstention path when extraction or mapping is ambiguous.
10. **Abandon or radically revise the primary structural-index architecture if it fails to improve cross-domain top-K recall over the cheap baseline at matched false-positive budget, or if useful invariance makes fingerprint postings non-selective.**

### Sources

1. Dedre Gentner, **“Structure-Mapping: A Theoretical Framework for Analogy”** (Cognitive Science, 1983), DOI: https://doi.org/10.1207/s15516709cog0702_3 — establishes relational mapping and systematicity; supports the attack on isolated local motifs.
2. Brian Falkenhainer, Kenneth D. Forbus, Dedre Gentner, **“The Structure-Mapping Engine: Algorithm and Examples”** (Artificial Intelligence, 1989), DOI: https://doi.org/10.1016/0004-3702(89)90077-5 — shows globally consistent structure mapping can be computationally practical for modest representations.
3. Kenneth D. Forbus, Dedre Gentner, Keith Law, **“MAC/FAC: A Model of Similarity-Based Retrieval”** (Cognitive Science, 1995), DOI: https://doi.org/10.1207/s15516709cog1902_1 — directly relevant: cheap first-stage retrieval is non-structural/content-vector based; structural comparison happens after filtering.
4. Nino Shervashidze et al., **“Weisfeiler-Lehman Graph Kernels”** (JMLR, 2011), https://www.jmlr.org/papers/v12/shervashidze11a.html — efficient local/subtree-like graph features; useful baseline but not a guarantee of full structural correspondence.
5. Zhiping Zeng et al., **“Comparing Stars: On Approximating Graph Edit Distance”** (PVLDB, 2009), DOI: https://doi.org/10.14778/1687627.1687631 — documents the general NP-hardness pressure behind exact graph-edit matching.
6. Gabriel Peyré, Marco Cuturi, Justin Solomon, **“Gromov-Wasserstein Averaging of Kernel and Distance Matrices”** (ICML, 2016), https://proceedings.mlr.press/v48/peyre16.html — relevant soft relational matching approach; also exposes non-convex iterative optimization complexity.
7. Nils Reimers, Iryna Gurevych, **“Sentence-BERT”** (EMNLP-IJCNLP, 2019), DOI: https://doi.org/10.18653/v1/D19-1410 — establishes a cheap semantic retrieval baseline suitable for falsifying the need for a structural primary index.
8. Pengcheng Jiang et al., **“GenRES: Rethinking Evaluation for Generative Relation Extraction in the Era of Large Language Models”** (NAACL, 2024), DOI: https://doi.org/10.18653/v1/2024.naacl-long.155 — relation extraction varies in granularity, factualness and completeness; fixed relation/entity prompting can induce hallucinations, making extraction stability a first-class risk.
9. Yinghao Li, Rampi Ramprasad, Chao Zhang, **“A Simple but Effective Approach to Improve Structured Language Model Output for Information Extraction”** (Findings of EMNLP, 2024), DOI: https://doi.org/10.18653/v1/2024.findings-emnlp.295 — evidence that structured IE output itself can be inconsistent and needs explicit handling rather than being assumed reliable.
