---
mission: R0-H
run: R0-H-REPEAT-S7D3
contributor: Parshkov
agent_id: parshkov-openai-gpt5-codex-s7d3
agent_or_model: GPT-5-based Codex (exact deployed model/version not exposed to this run)
date: 2026-08-31
mission_modified: false
web_research_used: true
code_execution_used: true
additional_agents_used: false
blind_constraints_preserved: not-applicable
prior_run_exposure: >
  The accepted R0 synthesis, read before this run, summarized the primary R0-H
  generic-motif attack. The primary R0-H submission itself was opened only
  after this repeat's experiment and conclusions were designed, to distinguish
  incremental evidence from duplication. R0-H has no blind group.
tools_used:
  - Git and GitHub CLI for protocol and repository inspection
  - web search/opening of primary papers and official library documentation
  - Python 3 standard library for the executable falsifier
---

# Decision

**NO-GO for unrestricted, context-free “resonance discovery” from Thought DNA
v0.1 alone; QUALIFIED GO for the explicitly gated retrieval/verifier
experiment.** The current architecture fixed the primary R0-H toy by combining
D0+D1 features, DF/IDF, endpoint consensus, and exact verification. That still
cannot solve two information-theoretic failures: (1) an intended analogy is
indistinguishable from many contextually irrelevant candidates with the same
typed graph, and (2) v0.1 cannot encode relations whose arguments are other
relations, joint/disjunctive causes, or scoped conditions. No fingerprint,
embedding, QAP, or FGW optimizer can recover information absent from its input.
Keep the gated experiment, but make “insufficient structural evidence” a normal
result, add a context/task channel before any product claim, and trigger the
already-declared v0.2 reification gate when higher-order collisions recur.

# Confidence

**HIGH** on the indistinguishability and schema-loss arguments: they follow
from the public v0.1 fields and are reproduced without hash collisions or model
noise. **MEDIUM** on prevalence: the experiment deliberately constructs a
motif-heavy corpus, while real motif and extraction distributions are not yet
measured. The result therefore kills an unrestricted claim, not the frozen
benchmark hypothesis. The main uncertainty is whether real user context gives
enough cheap discriminating signal before structural retrieval.

# Best Algorithm / Method

The attack is an **observational-equivalence test**, not another matcher.

Let `obs(G, q)` be every field a stage is permitted to consume under a frozen
configuration. If two candidates have identical `obs` but different desired
labels, any deterministic ranker must tie them. If there are `m` tied candidates
and no external ordering signal, worst-case Recall@K is zero for `m > K`, and
expected Recall@K is at most `K/m`. Adding a stronger optimizer after retrieval
cannot recover a candidate that was not retrieved; applying the same verifier
to identical typed graphs cannot distinguish their contextual relevance.

The executable [falsifier](../experiments/R0_H_repeat_falsifier.py) copies only
the published E1 primitives: exact Thought DNA roles/relations, D0 role
landmarks, one-round directed typed D1 descriptors, typed paths of length at
most three, MULTI union, and the accepted 0.5% DF stop policy. Keys are tuples,
not hashes, so cryptographic collision is excluded. It then runs three attacks:

1. place one contextually intended candidate last among 50 structurally
   identical four-node causal motifs in a 1,000-graph corpus;
2. perturb one relation, one branch, or one relation omission in an eight-node
   graph; and
3. flatten two different higher-order readings into the only available binary
   graph.

The cheapest surviving method is therefore not a new universal score. It is a
fail-closed cascade:

```text
explicit user task/context + content/knowledge candidates
  -> optional structural candidates only when live rare evidence exists
  -> small deterministic partial mapper (SME-lite first)
  -> typed exact rescore and contradiction checks
  -> result OR insufficient-evidence/ambiguous-tie
```

# Why It Fits Resonance

The hard negative “same words, different structure” justifies structural
verification. It does not establish the converse: that equal structure implies
the same relevance or intent. Gentner's formulation maps systems of relations,
including higher-order relations between propositions; Thought DNA v0.1
deliberately stores only binary propositions between grounded nodes. The
architecture is therefore strongest exactly where the representation is rich
and the candidate is already available, and weakest at autonomous reminding
and context-dependent interpretation.

The Shazam analogy breaks at this point. Wang's fingerprints identify repeated
observations of one fixed recording using high-entropy landmark pairs and a
single time-offset vote. Resonance seeks a selected interpretation across
different objects, has no shared offset, and intentionally erases domain
identity. The more perfectly domain substitution becomes invariant, the more
unrelated copies of a common causal skeleton become observationally equal.

# Required Thought DNA

For the gated binary-graph scope, keep exactly the current fields: stable local
node/relation IDs; grounded labels/spans; closed node roles; directed closed
relation types; assertion, modality, confidence, atomicity, provenance; and
optional `about`/`requires` IDs. The attack does not justify fingerprint fields
inside canonical DNA.

For v0.2, add nothing until a collision pack proves need. The minimum candidate
extension is a **derived, provenance-backed statement view** in which a relation
may be an argument of `supports`, `contradicts`, `causes`, or `requires`, plus an
explicit connective for joint/alternative antecedents. Query/task context
should remain a request-level input, not be rewritten into source truth.

# Required Graph Representation

The current directed typed property multigraph is sufficient only for binary,
independently asserted propositions. Higher-order evidence, causal scope, and
joint/disjunctive mechanisms require reified statement nodes or a small
proposition DAG/hypergraph. This need not replace canonical v0.1 immediately:
an abstaining extractor may omit unsupported higher-order structure, but then
the engine must report that the requested distinction is unrepresentable.

# Invariances

| Transformation | Supported | Partially | Not Supported | Mechanism / attack |
|---|---:|---:|---:|---|
| A paraphrase | | yes | | only after duplicate-extraction gate |
| B vocabulary substitution | | yes | | MULTI survives when rare structure remains |
| C node ordering | yes | | | canonical sets/IDs |
| D irrelevant branch | | yes | | MULTI key Jaccard measured 0.6418 |
| E missing relation/nodes | | yes | | one missing edge measured 0.5357 |
| F granularity | | yes | | only guarded contraction; scoped mediators must remain |
| G graph size | | yes | | partial mapping, but score comparability remains gated |
| H domain substitution | | | unrestricted retrieval | identical motifs erase relevance signal |
| I extraction mistakes | | yes | | one relation-type error measured MULTI Jaccard 0.2195 |

H and discrimination cannot both be unconditional. Domain-invariant structure
may retrieve a class of candidates, but it cannot select the intended member
without context, content, knowledge, or rarity that breaks the invariance.

# Retrieval vs Verification

**Retrieval:** keep all channels separate. Structural retrieval must return no
candidate when all evidence is stopped or tied, rather than inventing an order.
Report live/total query features, maximum tie size, skipped DF mass, and a reason
such as `insufficient_structural_evidence`. Content and knowledge can break some
ties but do not prove analogy.

**Verification:** necessary, but not omniscient. A partial injective mapper with
typed exact rescore can reject reversal, polarity, and rewiring; it cannot infer
pragmatic intent or higher-order scope from identical binary graphs. Run a
transparent SME-lite baseline before paying the implementation cost of both
FGW and RRWM.

# Computational Cost

- The falsifier is standard-library Python and completes in about 1.2 seconds
  including compile and diff checks on the declared machine.
- D0/D1 feature extraction over a graph is bounded by the selected landmark
  pairs and path depth; the attack is about posting entropy, not CPU.
- For 50 identical candidates, any exact verifier repeats the same result 50
  times. At one million thoughts, a common-motif posting may be stopped or
  large; neither choice recovers contextual relevance.
- General graph matching is QAP-like and NP-hard. Heuristics are plausible for
  50×50 top-20 verification, but implementing and calibrating two non-convex
  proposal families plus exact adjudication is ambitious within 40–60 hours.
  POT itself documents GW as a non-convex quadratic program returning a local
  minimum.

# Existing Implementations

| Component | Existing implementation | Use / risk |
|---|---|---|
| partial assignment | SciPy `linear_sum_assignment` | mature rectangular assignment; structure still needs an affinity model |
| FGW proposal | POT `fused_gromov_wasserstein` | official solver; non-convex/local-minimum and initialization risk |
| RRWM proposal | `pygmtools.rrwm` + Hungarian | available, but its standard vision benchmarks do not validate Thought DNA |
| tiny oracle | NetworkX GED/edit paths | useful only for small diagnostics; official docs warn exact GED is NP-hard/slow |
| SME reference | Falkenhainer–Forbus–Gentner algorithm | best transparent baseline; higher-order predicates expose the v0.1 schema boundary |

# Minimal Pseudocode

```text
features = live_features(query, corpus_snapshot)
if features is empty:
    return INSUFFICIENT_STRUCTURAL_EVIDENCE

candidates = union(content_top_k, knowledge_postings,
                   structural_postings(features))
for tie_group in observationally_equal(candidates):
    if size(tie_group) > remaining_budget and no context signal:
        mark AMBIGUOUS_TIE                       # never break by hidden ID order

for candidate in bounded_candidates:
    mapping = partial_injective_sme_lite(query, candidate)
    exact = typed_rescore(mapping)
    if representation_supports_requested_scope:
        emit exact
    else:
        emit UNREPRESENTABLE_SCOPE
```

# Toy Experiment

Run:

```bash
python3 research/experiments/R0_H_repeat_falsifier.py
```

Observed with seed `20260831`:

| Attack | D0 | D1 | MULTI |
|---|---:|---:|---:|
| live keys after 50/1000 identical motifs, cutoff 5 | 0/12 | 0/12 | 0/24 |
| one relation-type error: key Jaccard | 0.3158 | 0.1364 | 0.2195 |
| one irrelevant branch: key Jaccard | 0.8333 | 0.4865 | 0.6418 |
| one missing relation: key Jaccard | 0.7200 | 0.3871 | 0.5357 |

Without DF stopping, all 50 motifs tie exactly and the contextual positive at
index 49 is outside arbitrary top-20. With stopping, no structural score exists.
The flattened higher-order pair has identical D0/D1 signatures. This does not
falsify the richer E1 constellation result; it falsifies any claim that the
channel can always retrieve or rank a contextually intended common motif.

# Failure Modes

Concrete pairs, each requiring an explicit correct outcome:

1. **Higher-order support:** “audit supports `[overload causes failure]`” vs
   “audit supports overload; overload causes failure.” Binary flattening is
   identical; omission loses the first claim.
2. **Joint vs alternative causes:** “A and B together cause C” vs “either A or
   B causes C.” Both become `A→C, B→C` without a connective.
3. **Conditional scope:** “if cooling fails, load causes heat” vs “cooling may
   fail; load causes heat.” Per-edge modality cannot bind the antecedent set.
4. **Same words, reversed structure:** “heat causes degradation causes failure”
   vs the same labels with arrows reversed. Embeddings must lose; verifier must
   reject.
5. **Polarity flip:** “cooling prevents failure” vs “cooling causes failure.”
   Retrieval may tie; exact adjudication must reject.
6. **Temporal distinction absent:** “intervention before escalation prevents
   failure” vs “intervention after escalation prevents failure.” No temporal
   relation is present in v0.1.
7. **Different-domain spurious analogy:** battery accumulation→degradation→
   failure vs resentment accumulation→relationship degradation→failure. Same
   typed motif does not establish useful relevance.
8. **Intended among spurious copies:** organization information overload is the
   requested analogy among 49 identical domain substitutions. Structure cannot
   rank it without query context.
9. **Meaningful mediator:** `A causes B` vs `A causes fraud-check causes B`.
   Marking the mediator `atomic=false` would create a false granularity match.
10. **Local match/global goal conflict:** two plans share resource→method→
    outcome, but one optimizes safety and the other speed. Goal is not an
    explicit v0.1 role/relation.
11. **Knowledge polysemy:** river bank erosion vs bank liquidity run. A wrong
    entity link creates strong false content evidence; a missing link gives no
    disambiguation.
12. **Extraction drift:** one extraction labels an edge `causes`, another
    `supports`; the measured MULTI overlap falls to 0.2195 although prose is
    unchanged.

# What NOT To Build

- A tie-breaker based on candidate ID, insertion time, or solver seed; it hides
  absent evidence as deterministic relevance.
- A universal analogy claim from the six frozen gate packs; they test a
  configuration, not the real motif distribution.
- Relation reification at ingest without grounded evidence; that converts a
  schema limitation into extractor hallucination.
- A single blended score that lets semantic context hide structural failure.
- Both production-grade FGW and RRWM before SME-lite establishes whether the
  representation contains enough information.
- Knowledge IDs as truth or as a replacement for structural adjudication.
- Arbitrary path contraction to repair extraction/granularity mismatch.

# Architecture Consequences

1. Preserve the current gated prototype; narrow its claim to supported packs.
2. Add explicit insufficient-evidence and ambiguous-tie outcomes.
3. Measure live query evidence, tie size, and DF-skipped mass in R3.
4. Keep request context separate from canonical Thought DNA and expose it to
   candidate generation/adjudication under a versioned policy.
5. Add the three observational-equivalence pairs above to calibration first;
   do not rewrite frozen gate gold.
6. Trigger v0.2 only after repeated grounded higher-order/scope collisions.
7. Require SME-lite as the verifier complexity baseline.
8. Treat Knowledge DNA as optional evidence with explicit absence/ambiguity.
9. Do not claim domain-invariant ranking when candidates are structurally
   identical and context-free.
10. Radically revise the architecture if real extracted corpora show either
    (a) zero live structural evidence for >20% of target cross-domain queries,
    (b) contextual positives outside top-20 ties in >10%, or (c) repeated
    unrepresentable higher-order judgments in >5% of reviewed pairs.

# Sources

1. [Wang (2003), *An Industrial-Strength Audio Search Algorithm*](https://swh.princeton.edu/~cuff/ele201/files/Wang03-shazam.pdf) — high-entropy landmark hashes and one-dimensional offset voting; the exact assumptions behind the Shazam analogy.
2. [Gentner (1983), *Structure-Mapping: A Theoretical Framework for Analogy*](https://groups.psych.northwestern.edu/gentner/papers/Gentner83.2b.pdf) — systematicity and higher-order relations between propositions.
3. [Falkenhainer, Forbus & Gentner (1989), *The Structure-Mapping Engine*](https://groups.psych.northwestern.edu/gentner/papers/FalkenhainerForbusGentner89.pdf) — inspectable mapping baseline and representation requirements.
4. [Vayer et al. (2019), *Optimal Transport for Structured Data with Application on Graphs*](https://proceedings.mlr.press/v97/titouan19a/titouan19a.pdf) — primary FGW formulation.
5. [Vogelstein et al. (2015), *Fast Approximate Quadratic Programming for Graph Matching*](https://pmc.ncbi.nlm.nih.gov/articles/PMC4401723/) — QAP hardness and approximate graph matching.
6. [Shervashidze et al. (2011), *Weisfeiler-Lehman Graph Kernels*](https://www.jmlr.org/papers/v12/shervashidze11a.html) — efficient local structural features; useful retrieval machinery but not a relevance proof.
7. [Bast et al. (2023), *A Fair and In-Depth Evaluation of End-to-End Entity Linking Systems*](https://aclanthology.org/2023.emnlp-main.411/) — entity-linking ambiguity and domain-dependent error analysis.
8. [POT official user guide](https://pythonot.github.io/user_guide.html) — available FGW implementation and explicit non-convex/local-minimum warning.
9. [pygmtools official repository](https://github.com/Thinklab-SJTU/pygmtools) — available RRWM/Hungarian implementation and benchmark scope.
10. [NetworkX similarity documentation](https://networkx.org/documentation/stable/reference/algorithms/similarity.html) — tiny GED oracle and official complexity warning.
11. [SciPy `linear_sum_assignment` documentation](https://scipy.github.io/devdocs/reference/generated/scipy.optimize.linear_sum_assignment.html) — rectangular assignment primitive for partial-map prototypes.
12. Resonance [Thought DNA v0.1](../../docs/THOUGHT_DNA_v0.1.md), [Invariance Specification](../../docs/INVARIANCE_SPECIFICATION_v0.1.md), and [Benchmark v0.1](../../benchmark/R0_BENCHMARK_v0.1.md) — the exact local contracts attacked.
