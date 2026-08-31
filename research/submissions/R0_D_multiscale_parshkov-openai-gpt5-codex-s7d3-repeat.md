---
mission: R0-D
run: R0-D-REPEAT-S7D3
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
  The accepted synthesis and v0.1 contracts exposed the canonical R0-D
  conclusion before this repeat. The canonical R0-D submission itself was read
  only after this repeat's executable guard matrix and frozen-benchmark audit
  were designed and run. R0-D has no blind group.
tools_used:
  - Git and GitHub CLI for live protocol and repository inspection
  - web research of primary papers and official documentation
  - Python 3 standard library for the executable contraction audit
---

# Decision

**GO only for bounded, reversible edge-to-path evidence inside verification;
NO-GO for global coarsening or multiscale retrieval in v0.1.** The accepted
conditional rule is directionally correct: preserve the canonical graph, match
one direct edge to a path of at most four relations, and expose every realized
node/relation. The load-bearing signal is the extracted `atomic=false` claim,
not graph degree. A syntactic guard reduces obvious false contractions but
cannot distinguish a transparent mediator from a meaningful mediator that was
mis-annotated with identical fields.

The immediate blocker is measurable: frozen Benchmark v0.1 has eight generated
transparent-subdivision positives, zero explicit negative-contraction cases,
and no gold field identifying nodes or paths that must not contract. Its
mandatory `false_meaningful_contractions == 0` gate sums an integer supplied by
the prediction itself. An engine can report zero regardless of its mappings.
Do not use that gate as acceptance evidence until a versioned benchmark adds
auditable negative gold and derives the count from predicted edge-path matches.

# Confidence

**HIGH** on the benchmark gap and on rejecting generic coarsening: both follow
from executable repository state and the mismatch between spectral guarantees
and semantic causal preservation. **MEDIUM** on the minimal composition policy:
the frozen positives exercise only homogeneous `causes` subdivision through an
`atomic=false` mechanism. Real extracted text may not supply reliable atomicity,
and causation is not universally transitive.

# Best Algorithm / Method

Use **local guarded path licensing**, never mutation:

```text
query edge (u, type, assertion, modality, v)
  + mapped candidate endpoints (u', v')
  -> enumerate simple directed candidate paths of length 2..4
  -> reject unless every intermediate:
       atomic=false
       in-degree=1 and out-degree=1 in the active relation layer
       non-boundary role (initially mechanism/state only)
       asserted + actual, with no branch/merge
  -> reject unless every path relation has compatible type/sign/assertion/modality
  -> emit EdgePathMatch with every original relation/node ID and provenance
```

For v0.1, the composition table should be **benchmark-minimal**: homogeneous
`causes` paths may support a direct `causes` edge only as *structural path
evidence*, not as a newly asserted direct causal fact. Leave `supports`,
`prevents`, `contradicts`, mixed types, and all unknown compositions disabled.
Calibrate `requires` and `part_of` separately before adding them; mathematical
transitivity does not imply domain-safe semantic composition.

The [executable audit](../experiments/R0_D_repeat_contraction_audit.py) compares
exact-only, naive path closure, and this guard on 15 cases. It also reads the
frozen benchmark and prediction schema without modifying them.

# Why It Fits Resonance

This is the smallest method that answers the actual invariance: edge
subdivision. It returns the correspondence required for explanation, is bounded
for 10–100-node graphs, preserves direction/type/polarity, and fails closed.
Global spectral or diffusion methods preserve a chosen mathematical property,
not the meaning of a mediator. Loukas and Jin et al. explicitly frame
coarsening around a property to preserve; Resonance's property is typed,
provenance-backed reasoning, not an undirected Laplacian spectrum.

The method belongs after endpoint hypotheses are available. Adding coarse-view
tokens to retrieval multiplies feature variants before extraction and
false-contraction precision have passed. The accepted Invariance Specification
already marks F unsupported in retrieval and conditional in verification; this
repeat supports that stricter placement.

# Required Thought DNA

No new canonical field is justified. Consume the existing stable IDs, roles,
`atomic`, direction/type, assertion, modality, confidence, spans, and
provenance. `atomic=false` must mean “safe elaboration for the declared
composition policy,” not merely “small” or “low salience.” Extraction should
default it to `true` and set `false` only from a grounded explicit construction
or manual assertion.

Derived path evidence additionally records:

- query relation ID and provenance;
- ordered candidate relation IDs and provenance;
- ordered realized intermediate node IDs and provenance;
- minimum confidence;
- composition-policy version and rejection reason.

Do not add a floating salience field merely to tune contraction. A mislabelled
meaningful mediator remains indistinguishable even with a threshold.

# Required Graph Representation

A directed typed property multigraph, unchanged. Edge-to-path evidence is a
derived object, not a shortcut edge written back to DNA. Parallel relations,
branches, merges, assertions, modalities, and original proposition IDs must
remain visible. Reified propositions may be needed for higher-order scope, but
that is a separate v0.2 representation gate, not a reason to broaden v0.1
contraction.

# Invariances

| Transformation | Supported | Partially | Not Supported | Mechanism |
|---|:---:|:---:|:---:|---|
| A paraphrase | | X | | extraction/semantic endpoint support, not path guard |
| B vocabulary substitution | | X | | roles/types can survive; labels are not required |
| C node ordering | X | | | ID/set-based traversal |
| D irrelevant branch | | X | | partial mapping; a branch on the mediator forbids contraction |
| E missing nodes | | X | | unmatched evidence; never invent a path |
| F different granularity | | X | | only licensed direct-edge ↔ bounded transparent path |
| G graph sizes | | X | | local path plus containment reporting |
| H domain substitution | | X | | typed structure only after endpoints are proposed |
| I extraction mistakes | | X | | fail closed except a wrong `atomic=false`, which is not repairable downstream |

Meaningful mechanisms, branches/merges, polarity, modality, conditional scope,
temporal boundaries, and mixed relation types are anti-invariances.

# Retrieval vs Verification

**Verification only for v0.1.** Enumerate bounded paths between already proposed
endpoint pairs. A graph-level retrieval channel may still use the canonical
D0+D1 features, but must not emit shortcut/coarse fingerprints until an
independently scored contraction pack passes. This avoids indexing semantic
errors as durable corpus features.

The verifier must return structured path matches. The evaluator, not the
engine, determines whether those matches realize forbidden nodes/paths.

# Computational Cost

For `q` candidate endpoint pairs, maximum path length `L=4`, and branching `d`,
bounded enumeration is `O(q*d^L)` with hard caps; it does not require all-pairs
shortest paths. On the local machine the stdlib 15-case audit, benchmark scan,
compile, and diff check completed in under one second. The repository suite is
24 tests and completes in about 0.7 seconds.

Global heat kernels require spectral machinery and usually erase typed
direction; HKS was designed for near-isometric shape analysis. Generic graph
reduction offers spectral/cut guarantees, but proving those says nothing about
causal scope. Both are unjustified within the 40–60 hour MVP.

# Existing Implementations

| Tool | Immediate use | Risk |
|---|---|---|
| custom bounded DFS/BFS | shipping reference path enumerator | small, deterministic, easiest to provenance-test |
| NetworkX directed paths | tiny oracle/prototype | generic contraction does not implement semantic guards |
| SciPy assignment | endpoint mapping before path checks | assignment score does not license contraction |
| GraKeL/WL | no-multiscale retrieval control | neighborhood refinement is subdivision-sensitive |
| POT/pygmtools | proposal generators | neither supplies semantic relation composition |

# Minimal Pseudocode

```text
for (q_edge, mapped_source, mapped_target) in proposed_edge_endpoints:
    for path in directed_simple_paths(candidate, mapped_source,
                                      mapped_target, cutoff=4):
        if any(node.atomic for node in path.intermediates): continue
        if any(active_in_degree(node) != 1 or
               active_out_degree(node) != 1): continue
        if any(node.role not in SAFE_ROLES): continue
        if COMPOSE_V01[path.typed_signed_modal_sequence] != q_edge.type:
            continue
        emit EdgePathMatch(q_edge.id,
                           path.relation_ids,
                           path.intermediate_node_ids,
                           all_item_provenance,
                           policy_version)
```

# Toy Experiment

Run:

```bash
python3 research/experiments/R0_D_repeat_contraction_audit.py
```

Observed synthetic matrix:

| Policy | TP | FP | FN | Precision | Recall |
|---|---:|---:|---:|---:|---:|
| exact-only | 0 | 0 | 2 | undefined | 0.0000 |
| naive homogeneous path | 2 | 10 | 0 | 0.1667 | 1.0000 |
| guarded path | 2 | 1 | 0 | 0.6667 | 1.0000 |

The remaining false positive is intentionally identical in all machine fields
to a positive but has a meaningful mediator in source interpretation. This is
not a claim that precision will be 0.6667 in reality; it proves that structural
guards cannot repair a false `atomic=false` annotation.

Read-only frozen-benchmark audit:

- transparent positive cases: 8, all review status `generated`;
- explicit negative contraction cases: 0;
- gold `meaningful_nodes`/`must_preserve_nodes`/forbidden path fields: none;
- `false_contractions`: required from prediction and summed by the runner.

Falsify this recommendation if a versioned calibration pack with independently
judged transparent/meaningful subdivisions shows the guard gains less than 0.10
Recall@5 over exact-only, any forbidden contraction, or unacceptable
duplicate-extraction disagreement on `atomic`.

# Failure Modes

1. A meaningful insulin mechanism is marked `atomic=false` and disappears.
2. A branch/merge is evaluated only along the selected path and its second edge
   is ignored.
3. `causes → prevents` is collapsed to a positive causal shortcut.
4. A negated or conditional edge inherits `actual/asserted` from its neighbor.
5. A path of five relations bypasses the declared complexity/semantic bound.
6. Two parallel paths collapse to one explanation and hide disagreement.
7. A solver maps endpoints correctly but reverses the candidate path.
8. A derived shortcut is persisted and later treated as source truth.
9. The engine self-reports zero false contractions although its path mapping
   crosses a gold meaningful node.
10. Generated positives calibrate recall but no negative pack measures safety.

# What NOT To Build

- Generic node contraction, transitive closure, or shortest-path equivalence.
- Spectral/heat/persistent-homology machinery before the local guard fails.
- Coarse-view retrieval tokens before auditable false-contraction gold exists.
- A broad relation-composition table based on intuition.
- A self-reported safety metric; derive it from mappings and gold.
- Canonical shortcut edges or provenance-free natural-language explanations.

# Architecture Consequences

1. Keep granularity conditional and verifier-local in v0.1.
2. Freeze a tiny composition-policy version; unknown means no match.
3. Default extracted nodes to `atomic=true`.
4. Require node as well as relation provenance on every path match.
5. Add calibration negatives for atomic mechanisms, roles, branch/merge,
   polarity, assertion, modality, length, and mis-annotation.
6. Version benchmark gold with `must_preserve_nodes` and/or
   `forbidden_edge_path_matches`.
7. Compute false contractions from predicted paths against that gold.
8. Independently review transparent and meaningful subdivision judgments.
9. Keep exact-only as a required failing recall control and naive closure as a
   required failing precision control.
10. Abandon granularity support if duplicate extraction cannot reproduce
    `atomic` or any independently judged meaningful node is contracted.

# Sources

1. [Gentner (1983), *Structure-Mapping*](https://groups.psych.northwestern.edu/gentner/papers/Gentner83.2b.pdf) — systematic relational mapping; an intermediate can be part of the explanatory system rather than noise.
2. [Halpern, *Actual Causality*](https://www.cs.cornell.edu/home/halpern/papers/causalitybook-ch1-3.html) — causal chains and explicit limits/conditions on transitivity.
3. [Loukas (2019), *Graph Reduction with Spectral and Cut Guarantees*](https://www.jmlr.org/papers/v20/18-680.html) — precise guarantees for a different preservation objective; why generic coarsening is not semantic preservation.
4. [Jin, Loukas & JaJa (2020), *Graph Coarsening with Preserved Spectral Properties*](https://proceedings.mlr.press/v108/jin20a.html) — coarsening must name the property preserved.
5. [Sun, Ovsjanikov & Guibas (2009), *Heat Kernel Signature*](https://www.lix.polytechnique.fr/~maks/papers/hks.pdf) — primary multiscale spectral shape signature; useful contrast, not a typed causal explanation.
6. [Shervashidze et al. (2011), *Weisfeiler-Lehman Graph Kernels*](https://www.jmlr.org/papers/v12/shervashidze11a.html) — efficient multiradius structural control, not subdivision invariance.
7. [NetworkX simple-path documentation](https://networkx.org/documentation/stable/reference/algorithms/simple_paths.html) — prototype bounded path enumeration surface.
8. Resonance [Thought DNA v0.1](../../docs/THOUGHT_DNA_v0.1.md), [Invariance Specification](../../docs/INVARIANCE_SPECIFICATION_v0.1.md), [Benchmark v0.1](../../benchmark/R0_BENCHMARK_v0.1.md), and frozen executable bundle — exact local contracts and gate audited.
