---
mission: R0-A
run: R0-A
contributor: veronicagedd-dev
agent_id: veronicagedd-dev-openai-gpt5-codex-8cf4
agent_or_model: GPT-5-based Codex (exact version not exposed to this run)
model_mode: agentic coding and research
execution_environment: Codex desktop
date: 2026-08-31
mission_modified: false
web_research_used: true
code_execution_used: true
external_tools_used: GitHub connector, web search, local shell
additional_agents_used: false
blind_constraints_preserved: n/a
---

# Decision

**GO, narrowly:** make a proposition (statement) the unit of structural matching, not an ordinary edge. Thought DNA v0.1 should be a directed, typed, reified proposition graph: entities and statements are nodes; each statement has a normalized predicate and ordered argument-role links; statements may themselves be arguments of higher-order statements such as `CAUSE`, `ENABLE`, `PREVENT`, and `IMPLIES`. The first verifier should implement SME's durable core—one-to-one correspondence, parallel connectivity, semantic gating, and systematicity-weighted connected mappings—but not reproduce the full cognitive architecture. Semantic compatibility proposes or gates local matches; it must not be folded into the reported structural score. This is the smallest representation and mechanism that can distinguish relational analogy from shared topic.

# Confidence

**MEDIUM-HIGH.** The representation and consistency constraints have strong theoretical, empirical, and computational support. The main uncertainty is not whether relations must be explicit, but whether extraction can normalize predicate families and higher-order causal structure consistently enough for cross-domain matching. The proposed two-hour experiment directly tests that dependency before a larger implementation.

# Best Algorithm / Method

Use an **SME-lite local-to-global structural verifier** on two already-retrieved Thought Graphs.

1. Represent an entity as `E(id, concept_type)` and a statement as `S(id, predicate_id, [(role, argument_id)])`; an argument may reference an entity or another statement.
2. Generate statement match hypotheses `(s_b, s_t)` only when arity and argument roles are compatible and predicate compatibility `c_p` passes a threshold. Exact normalized predicate identity gets `1`; same narrow predicate family may receive a fixed value below `1`. Do not let free-text embedding similarity alone create a match.
3. Applying **parallel connectivity**, a statement match requires compatible hypotheses for corresponding arguments. Applying **one-to-one correspondence**, each base item maps to at most one target item and vice versa within a mapping.
4. Build connected, internally consistent kernels from the surviving hypotheses. Rank and greedily merge kernels while preserving both constraints; keep the best few alternatives rather than solving exact maximum common subgraph.
5. Implement **systematicity** with a transparent trickle-down score. Give a matched statement local evidence `w(s_b,s_t)=c_p * q_b * q_t`, where `q` is extraction confidence. For every matched higher-order statement, propagate `delta * w` to its matched argument statements and entities, recursively with `0 < delta < 1`. Sum evidence within the mapping.
6. Normalize for graph size:

   `structural = 2 * SES(M) / (SES(B,B) + SES(T,T))`

   where `SES(X,X)` is the same structural evaluation on a self-match. Report separately: `predicate_semantic_support`, matched correspondence list, connected-system coverage, unmatched branches, and contradictions. This prevents a high semantic score from masquerading as analogy and reduces the automatic advantage of larger graphs.

Classical SME's candidate inferences are useful later, but v0.1 should return them only as explicitly marked hypotheses supported by an otherwise valid mapping; they must not affect the match score.

# Why It Fits Resonance

Gentner's structure-mapping account defines analogy as preservation of relational systems rather than object attributes. SME operationalizes that idea with one-to-one mappings and parallel connectivity, and later work reports that semantic restrictions are necessary to avoid nonsensical graph isomorphisms. Human experiments further show a preference for a match embedded in a causal system over an equally plausible isolated match. Those are exactly Resonance's hard-negative requirements: different nouns may align when their relational roles agree, while repeated vocabulary must not override different argument structure.

This method also produces the required explanation directly: a mapping is a list of item correspondences grouped into connected kernels. It is deterministic after predicate compatibility and extraction confidence are fixed, works on 10–100-node graphs, and remains independent of any LLM at comparison time.

# Required Thought DNA

Essential for the first verifier:

- stable item identifier and `entity | statement` kind;
- for statements: normalized `predicate_id` and a small `predicate_family` used only for controlled non-identical matches;
- predicate arity plus ordered, named argument roles (`cause`, `effect`, `agent`, `object`, etc.); position alone is acceptable only for truly ordered formal predicates;
- argument references that may point to entities **or statements**;
- direction and polarity where they change meaning (`CAUSE(a,b)` is not `CAUSE(b,a)`; asserted and negated claims must not match);
- extraction confidence, used as local evidence rather than a hard truth value.

Required for provenance but not structural identity: source-span reference and extraction method/version. Keep these out of structural scoring.

Useful later, not required in v0.1: temporal interval algebra, modal nesting beyond simple assertion/negation, quantitative functions, predicate ontologies deeper than one controlled family level, pragmatic goals, and candidate-inference truth evaluation.

# Required Graph Representation

Use a **directed typed property graph encoding a reified hypergraph**. Entity nodes carry concept typing; statement nodes carry predicate identity; ordered role edges connect statements to their arguments. Because an argument can be another statement, higher-order relations are representable without special cases.

Ordinary binary entity-to-entity edges are insufficient as the canonical form. They conflate multiple instances of the same relation, handle ternary relations awkwardly, discard argument roles, and cannot cleanly express `CAUSE(statement_1, statement_2)` or provenance/confidence per assertion. Reification preserves proposition identity and reduces matching to ordinary node/edge traversal while retaining n-ary and higher-order semantics.

# Invariances

| Transformation | Supported | Partially | Not Supported | Mechanism |
|---|:---:|:---:|:---:|---|
| A. paraphrase |  | ✓ |  | extractor maps wording to the same predicate/entity concepts |
| B. vocabulary substitution |  | ✓ |  | controlled predicate families plus role-consistent mapping; arbitrary synonyms still depend on normalization |
| C. node ordering | ✓ |  |  | stable IDs and storage order are ignored; semantic argument roles are preserved |
| D. irrelevant branches |  | ✓ |  | highest-scoring connected kernels can omit them; normalization and coverage expose the omission |
| E. partial observation / missing nodes |  | ✓ |  | partial consistent kernels are allowed; missing higher-order links reduce systematicity |
| F. different granularity |  |  | ✓ | SME-lite has no path contraction or event decomposition equivalence; defer to the multiscale layer |
| G. different graph sizes |  | ✓ |  | partial mappings and self-score normalization; very unequal graphs may still create generic-motif false positives |
| H. domain substitution, structure preserved |  | ✓ |  | entity attributes are not required, but predicate normalization/compatibility must expose the shared relation |
| I. modest extraction mistakes |  | ✓ |  | confidence weighting and partial kernels tolerate local noise; wrong high-level causality remains damaging |

# Retrieval vs Verification

This method belongs in **EXPENSIVE VERIFICATION**. Inputs are two reified proposition graphs plus a deterministic predicate-compatibility table. Outputs are ranked mappings, each containing entity and statement correspondences, structural score, semantic-support score, matched connected systems, unmatched branches, contradictions, and optional candidate inferences.

MAC/FAC supports the two-stage architectural split, but its original content-vector dot product counts predicates and is a poor direct retrieval design for cross-domain cases with little predicate overlap. Resonance should use the separate relational-fingerprint mission for the 1M-item index; SME-lite runs only on top-K candidates.

# Computational Cost

Let `P_b,P_t` be statements and `H` surviving local hypotheses. Hypothesis generation is `O(P_b P_t)` before predicate/arity bucketing and close to the sum of compatible buckets afterward. Parallel-connectivity expansion is linear in matched argument links. Pairwise one-to-one conflicts and simple greedy kernel merging are at most `O(H^2)` in the MVP. Exact globally optimal structure mapping can be combinatorial; do not implement it.

- **50 vs 50 total items:** at most 2,500 raw item pairs, normally far fewer after kind/predicate/arity gates; easily interactive in Python.
- **Top 20 candidates:** at most 50,000 raw pairs plus small kernel merges; comfortably feasible on one CPU if alternatives are capped.
- **1M thoughts:** infeasible as pairwise verification (roughly `10^6` graph comparisons per query). Use an index to retrieve about 10–50 candidates first.

Benchmark runtime because ambiguous repeated predicates can inflate `H`; cap alternative mappings and record truncation.

# Existing Implementations

- **Original SME description/algorithm:** authoritative and detailed enough to reimplement, but the historical Common Lisp system is not a practical dependency.
- **SME-clj:** MIT-licensed faithful Clojure implementation and a useful conformance oracle; old Clojure 1.2 dependencies and low activity make it unsuitable as the production base.
- **ANASIME:** GPLv3 Python implementation of SME and a greedy variant; Python 2-era code and GPL licensing make it reference/test material, not an embeddable dependency.
- **SMEPy:** small Python implementation with reified expressions and systematicity scoring; inspect and test it as a behavioral reference, but treat its maturity and maintenance as unknown.
- **NetworkX:** mature Python graph primitives can host the proposition graph and diagnostics. Its generic graph-edit-distance routine is not the proposed verifier and may time out; use custom constraints instead.
- **SciPy `linear_sum_assignment`:** mature option for a bounded one-to-one entity assignment substep, but assignment alone cannot enforce parallel connectivity or systematicity.

Recommendation: implement about 300–500 lines of project-owned Python against simple dataclasses/NetworkX, then compare canonical examples with at least two reference implementations.

# Minimal Pseudocode

```text
function verify(base, target, compatibility, delta=0.5, max_maps=3):
    H = {}
    for sb in base.statements:
        for st in target.statements_in_bucket(sb.arity, sb.roles):
            cp = compatibility(sb.predicate, st.predicate)
            if cp >= PREDICATE_GATE and polarity_compatible(sb, st):
                h = hypothesis(sb, st, local=cp * sb.conf * st.conf)
                recursively_attach_argument_hypotheses(h, sb, st)
                if parallel_connectivity_possible(h): H.add(h)

    conflicts = one_to_one_conflict_pairs(H)
    kernels = connected_consistent_components(H, conflicts)
    for k in kernels:
        k.ses = trickle_down_sum(k, delta)

    maps = []
    for seed in sort_desc(kernels, by=ses):
        m = seed
        for k in sort_desc(kernels, by=ses):
            if consistent(m, k): m = merge(m, k)
        maps.add(m)
        if len(maps) == max_maps: break

    for m in maps:
        m.structural = 2*m.ses/(self_ses(base)+self_ses(target))
        m.semantic_support = mean(predicate_scores(m))
        m.explanation = correspondences_and_unmatched_branches(m)
    return maps
```

# Toy Experiment

Implement the representation and verifier in under two hours, then create 24 hand-authored graph pairs in four balanced groups: (1) same words/different causal direction; (2) different domains/same three-step causal system; (3) same isolated relations but only one pair has a shared higher-order causal system; (4) true analogies with one irrelevant branch, one missing statement, or one extraction-label error. Compare three ablations: semantic/predicate overlap only, structure without systematicity, and full SME-lite.

Primary metric: pairwise ranking accuracy requiring every true structural analogue to outrank its lexical hard negative. Also report correspondence precision and score degradation under each perturbation. **Falsification criterion:** NO-GO for this representation/verifier if full SME-lite fails more than 20% of lexical hard-negative rankings, or if a single plausible predicate-normalization error reverses more than 25% of correct rankings. That outcome means extraction semantics, not mapping, is the bottleneck.

# Failure Modes

1. Two generic chains `A→B→failure` align strongly despite unrelated mechanisms; systematicity rewards a ubiquitous motif.
2. Same words with reversed causality align if argument roles or direction are lost.
3. A cyclic feedback system is flattened to a chain and matches a one-way process.
4. Two agents participate in repeated relations; greedy one-to-one selection locks onto the wrong symmetric mapping.
5. `ENABLE` and `CAUSE` are collapsed into one family, producing an overconfident causal analogy.
6. Negated and asserted propositions match when polarity is omitted.
7. One extractor emits `A→B`; another emits `A→X→Y→B`; v0.1 misses the granularity-equivalent analogy.
8. A higher-order causal link is hallucinated; systematicity amplifies rather than dampens the error.
9. A metaphor shares role structure but violates domain constraints, yielding a structurally sound yet pragmatically useless mapping.
10. Repeated boilerplate goals/constraints create large connected mappings that swamp the thought's distinctive mechanism.

# What NOT To Build

- Do not clone full classical SME, its cognitive timing model, exhaustive global mappings, abstraction learning, or rerepresentation machinery.
- Do not encode higher-order semantics as untyped binary entity edges.
- Do not accept pure graph isomorphism: semantic gating is necessary to avoid structurally valid nonsense.
- Do not use whole-graph embedding cosine as the analogy score; it cannot expose correspondence consistency.
- Do not use exact graph edit distance or maximum common subgraph in the MVP; worst-case cost and opaque edit weights do not buy the required causal semantics.
- Do not make candidate inferences claims of truth; they are hypotheses requiring target-domain validation.
- Do not build a universal relation ontology. Begin with a small normalized predicate set plus one-level families and measure extraction agreement.

# Architecture Consequences

1. Adopt entity and statement nodes with ordered role edges as Thought DNA's canonical relational substrate.
2. Permit statements to reference statements so causal/logical higher-order structure survives extraction.
3. Store normalized predicate identity separately from surface text and a controlled compatibility family.
4. Preserve direction, argument roles, polarity, and extraction confidence.
5. Keep provenance beside every statement but outside structural scoring.
6. Make one-to-one correspondence and parallel connectivity hard verifier constraints.
7. Make systematicity a transparent, ablatable scoring term and normalize it against self-matches.
8. Return structural score and predicate-semantic support as separate values, never one opaque scalar.
9. Defer granularity equivalence to an explicit multiscale transform rather than hiding it in predicate similarity.
10. Proceed only if the lexical-hard-negative toy benchmark passes; otherwise revise extraction/normalization before scaling retrieval.

# Sources

1. [Gentner (1983), *Structure-Mapping: A Theoretical Framework for Analogy*](https://doi.org/10.1207/s15516709cog0702_3) — establishes relational selectivity, higher-order relations, and systematicity as the distinction between analogy and attribute similarity.
2. [Falkenhainer, Forbus & Gentner (1989), *The Structure-Mapping Engine: Algorithm and Examples*](https://www.qrg.northwestern.edu/papers/Files/smeff.pdf) — primary algorithm for local hypotheses, structural consistency, kernels, greedy mappings, and structural evaluation.
3. [Clement & Gentner (1991), *Systematicity as a Selection Constraint in Analogical Mapping*](https://doi.org/10.1207/s15516709cog1501_3) — experiments showing that people prefer relations embedded in matching causal systems over isolated matches.
4. [Forbus, Gentner & Law (1995), *MAC/FAC: A Model of Similarity-Based Retrieval*](https://doi.org/10.1207/s15516709cog1902_1) — primary evidence/model for separating cheap retrieval from structural verification; also exposes the surface-retrieval limitation.
5. [Markman & Gentner (1993), *Structural Alignment During Similarity Comparisons*](https://doi.org/10.1006/cogp.1993.1011) — empirical support for structural alignment when object and relational similarity conflict.
6. [Gentner & Forbus (2011), *Computational Models of Analogy*](https://groups.psych.northwestern.edu/gentner/papers/gentner%26Forbus_2011.pdf) — authoritative synthesis connecting higher-order causal/logical representations to selective inference and semantic restrictions.
7. [Forbus (2017), *Extending SME to Handle Large-Scale Cognitive Modeling*](https://doi.org/10.1111/cogs.12377) — updated SME constraints, tiered identicality, three-phase algorithm, greedy mapping, and practical scaling behavior.
8. [SME-clj](https://github.com/svdm/SME-clj) — open-source Clojure reference implementation; useful for conformance, with explicit age/dependency risk.
9. [ANASIME](https://github.com/Tijl/ANASIME) — open Python implementations of SME and the greedy variant; useful as GPL-licensed reference code, not a production dependency.
10. [NetworkX graph similarity documentation](https://networkx.org/documentation/stable/reference/algorithms/similarity.html) — authoritative implementation reference for graph diagnostics and the timeout/cost caveats of generic edit distance.

**Final conclusion: GO for a reified proposition graph plus SME-lite verification; NO-GO for ordinary-edge Thought Graphs, pure structural isomorphism, or semantic similarity presented as analogy.**
