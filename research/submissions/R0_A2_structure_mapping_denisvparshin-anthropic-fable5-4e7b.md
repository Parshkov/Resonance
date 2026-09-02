---
mission: R0-A
run: A2 (independent repeat, REPEAT_CLAIM)
contributor: DenisVParshin
agent_or_model: Claude Fable 5 (claude-fable-5), Claude Code CLI
date: 2026-08-31
mission_modified: false
web_research_used: true
independence_disclosure: >
  The canonical R0-A submission was NOT read (it is merged to main; the file
  was deliberately left unopened). Unavoidable exposure: the issue title
  "R0-A: structure mapping and relational Thought DNA decision", seen during
  board-state determination — it reveals the canonical run's general direction
  (relational Thought DNA), so convergence on that headline is not independent;
  convergence/divergence on specific requirements and mechanisms is. Same-agent
  note: this run is one of eight sequential runs (H2 first, then A2, F3, B3,
  C4, D2, E2, G2) by the same agent in one session; my own runs anchor each
  other and are not mutually independent.
---

# Decision

If Resonance is to detect human-recognizable structural analogy rather than
topical similarity, the Thought Graph must preserve exactly the properties
Structure-Mapping Theory has shown carry analogy for four decades: **typed
relations with ordered argument roles**, **support for higher-order relations**
(relations whose arguments are other relations — above all `cause`, `implies`,
`explains`), **relational identity under a small closed vocabulary** (so that
"prevents" in two domains is the *same* relation, not two similar strings), and
**per-edge polarity**. Plain binary edges between labeled nodes are *almost*
sufficient: the one structural extension v0.1 cannot skip is reification of
relations that serve as arguments of other relations. The smallest usable
matcher is a greedy SME-style aligner (one-to-one, parallel connectivity,
depth-weighted systematicity), which runs in low-polynomial time and directly
outputs the correspondence mapping Resonance needs for explanation. Relational
and semantic similarity must be computed and reported as separate scores and
combined only at the very end, shallowly and visibly.

# Confidence

HIGH on the representational requirements: systematicity, one-to-one mapping,
and parallel connectivity are among the most replicated results in analogy
research, and every serious implementation (SME and successors) depends on
them. MEDIUM on "greedy SME-lite is enough for v0.1": greedy merge is known to
approximate optimal mappings well in practice, but Resonance graphs are noisier
than hand-curated SME cases. Main uncertainty (<100 words): whether
LLM-extracted graphs will express higher-order relations consistently enough
for systematicity scoring to fire at all; if extraction flattens everything to
first-order chains, the verifier degrades to typed edge overlap, which analogy
research says is not enough (see R0-F).

# Best Algorithm / Method

**Structure-Mapping Engine principles, greedy variant.** SMT (Gentner 1983)
defines analogy as a mapping preserving *systems of relations* under three
constraints: (1) **one-to-one** node correspondence; (2) **parallel
connectivity** — if two relations correspond, their arguments correspond
role-wise; (3) **systematicity** — mappings governed by higher-order relations
(causal/implication systems) are preferred over equal-sized bags of isolated
matches. SME operationalizes this: form local match hypotheses between
identical (or aligned-type) relations, grow structurally consistent clusters,
merge into global mappings scored by depth-weighted evidence. The original
exhaustive merge is worst-case factorial in partial mappings; the greedy merge
of Forbus & Oblinger (1990) constructs one or a few best interpretations in
polynomial time (the paper's own claim; the ~O(n² log n) figure comes from
later complexity analyses, not the original) and is the version all
large-scale SME work uses. What is actually computed for Resonance:

```
score(M) = Σ over matched relations r of w(r),  w(r) = base(type_match) · λ^depth(r)
```

with λ > 1 rewarding relations that support deeper relational systems, subject
to one-to-one and parallel-connectivity constraints; output = the mapping M
itself (the explanation) plus the score.

# Why It Fits Resonance

- It is the only family of methods built specifically to distinguish
  *relational* analogy from *attribute/topical* similarity — the project's
  central hard negative ("same words, different structure" scores low because
  reversed causal arrows violate parallel connectivity; "different words, same
  structure" scores high because relation types and roles align).
- It returns node/edge correspondences, satisfying the explainability
  constraint natively — no post-hoc attribution needed.
- It is deterministic, trains nothing, and fits the no-LLM-in-the-core rule.
- Its cost profile (polynomial, small graphs) fits the verification stage for
  10–100-node graphs and top-K candidates.
- Its known weakness — sensitivity to representation quality (the
  Chalmers/French/Hofstadter 1992 critique: hand-tailored inputs do the real
  work) — is not avoided by any competitor and must be managed at the
  extraction layer regardless of verifier choice.

# Answers to the mission's Resolve questions

1. **Still useful from SME:** one-to-one, parallel connectivity,
   depth-weighted systematicity, greedy merge, candidate-inference reading of
   unmatched structure. These survive unchanged.
2. **What structure mapping requires from the representation:** relation
   *identity* (closed vocabulary, not free text) at least at match time;
   ordered argument roles; the ability for a relation to be an argument of
   another relation; polarity as part of relational identity (cause vs prevent
   must not unify).
3. **Are binary edges sufficient?** Nearly. First-order content fits typed
   binary edges. They fail exactly where analogy lives: higher-order relations
   (`cause(cause(A,B), C)`, "X explains why Y leads to Z").
4. **Reify or not:** reify **only** relations that appear as arguments of
   other relations. Representation: directed typed property multigraph in
   which an edge may be promoted to a relation-node with `arg0/arg1` role
   edges when referenced. Full reification of everything multiplies extraction
   inconsistency for no matching benefit; hypergraphs buy nothing v0.1.
5. **Smallest usable mechanism:** greedy typed aligner, ~200–300 lines:
   seed = pairs of edges with equal relation type (and polarity), extend by
   parallel connectivity, enforce one-to-one greedily by descending
   systematicity weight, output mapping + score. No pmap lattice, no
   exhaustive merge, no incremental mapping, no re-representation.
6. **Explicitly not reproduce from SME:** exhaustive gmap merging; LISP-era
   predicate-calculus input format; candidate-inference *generation* (later);
   pragmatic marking; incremental remapping.
7. **Scoring analogy separately from semantics:** two channels.
   `S_rel` = systematicity-weighted structural score over *delexicalized*
   graphs (labels hidden, types/roles/polarity visible).
   `S_sem` = node-label similarity (embeddings) summed over the
   correspondence produced by the aligner.
   Report both; combine only as a final visible weighted pair
   `(S_rel, S_sem)` — never fold semantics into the alignment constraints
   themselves, or cross-domain analogy dies (semantic collapse).
8. **Thought DNA fields made mandatory by this decision:** edge `type` from a
   closed vocabulary; edge `polarity`; ordered `roles` for relation
   arguments; reified-relation support; node `label` (free text) with the
   explicit rule that labels are evidence for `S_sem` only; provenance spans
   (so a human can audit why two branches were said to correspond).

# Required Thought DNA

Node: `id`, `type` (small closed set), `label` (free text), `span`
(provenance). Edge/relation: `id`, `type` (closed set), `polarity`
(positive/negative), `args` (ordered node-or-relation ids), `span`.
Nothing else is required by this verifier. Confidence fields, modality,
quantifiers, timestamps are *permitted* but the matcher does not consume them
in v0.1.

# Required Graph Representation

Directed typed **multigraph with optional relation reification** (property
graph). Not a tree (thoughts share substructure and converge); not a
hypergraph (ordered roles on reified relations cover n-ary cases the sprint
will actually see); not RDF-style triple soup (roles and higher-order
references become painful).

# Invariances

| Transformation | Supported | Partially | Not supported | Mechanism |
|---|---|---|---|---|
| A paraphrase | X | | | matching runs on types/roles, labels only via S_sem |
| B vocabulary substitution | X | | | delexicalized S_rel channel |
| C node ordering | X | | | alignment is order-free; roles are explicit |
| D irrelevant branches | | X | | unmatched structure ignored, but score normalization must not punish size (use max-normalized S_rel) |
| E partial/missing nodes | | X | | greedy alignment finds partial systems; deep systems truncated lose systematicity weight |
| F granularity | | X | | not solved here; needs R0-D contraction views |
| G size difference | | X | | same as D; normalize by smaller graph's matchable mass |
| H domain substitution | X | | | the core competence of structure mapping |
| I extraction mistakes | | X | | wrong relation *types* break seeds; agreement-core extraction (R0-F) is the real mitigation |

# Retrieval vs Verification

**EXPENSIVE VERIFICATION only.** Inputs: two Thought Graphs in the DNA above,
optional node-similarity matrix from embeddings. Output: correspondence
mapping (node pairs, relation pairs), `S_rel`, `S_sem`, and the matched
subsystem (the explanation). Structure mapping must not be pushed into
retrieval; the field's own scalable design (MAC/FAC, Forbus–Gentner–Law 1995)
made the cheap stage deliberately non-structural.

# Computational Cost

Greedy alignment ≈ O(|E1|·|E2|) seed generation + O(S log S) merge over S
seeds. 50×50-node graphs (~100–200 edges each): well under a second in
Python. Top-20 verification: seconds. Corpus of 1M: irrelevant — this
component never touches the corpus, only top-K.

# Existing Implementations

- Reference SME lineage: QRG's SME (Common Lisp; the searchable papers and
  code are public) — read for semantics, do not import.
- `SME-clj` (Clojure) and `ANASIME` (Python simulation environment) exist as
  community reimplementations — maturity low; useful as cross-checks, not
  dependencies.
- Practical recommendation: implement the ~300-line greedy aligner natively
  in the project language; dependency risk zero, semantics fully owned.

# Minimal Pseudocode

```
def align(G1, G2, sem_sim):            # graphs in Thought DNA form
    seeds = [(e1,e2) for e1 in G1.rels for e2 in G2.rels
             if e1.type==e2.type and e1.polarity==e2.polarity]
    for s in seeds: s.w = LAMBDA ** depth(s.e1)      # systematicity weight
    mapping, used1, used2 = {}, set(), set()
    for s in sorted(seeds, key=lambda s: -s.w):
        pairs = role_pairs(s.e1.args, s.e2.args)     # parallel connectivity
        if any(conflict(p, mapping) for p in pairs): continue
        commit(s, pairs, mapping, used1, used2)      # one-to-one enforced
    S_rel = sum(s.w for s in mapping.rels) / rel_mass(min(G1,G2))
    S_sem = mean(sem_sim[a,b] for (a,b) in mapping.nodes)
    return mapping, S_rel, S_sem
```

# Toy Experiment

≤2h. Hand-build 8 classic analogy pairs as Thought Graphs (solar-system/atom,
water-flow/heat-flow, battery-overheating/organizational-overload, bank-run/
applause-cascade, plus 4 fresh ones) and 8 topical-twin non-analogies (same
vocabulary, different causal arrows — including the causal-inversion pair from
R0-H). Run the greedy aligner. Metric: separation of `S_rel` distributions
(analogies vs topical twins); success = zero overlap or AUC ≥ 0.95.
**Falsifier:** if `S_rel` cannot separate hand-built clean pairs — with no
extraction noise at all — the structural verification thesis fails and no
downstream engineering can rescue it.

# Failure Modes

1. Extraction flattens higher-order relations → systematicity weight never
   fires → verifier ≈ typed edge counting (mitigation: R0-F must test for
   higher-order recovery explicitly).
2. Relation-type vocabulary drift between extractions → seed generation
   fails on identical thoughts (closed vocabulary + validator required).
3. Generic skeleton false positives (goal→constraint→mechanism everywhere) —
   S_rel alone flags them; must be co-reported with S_sem and motif
   commonness (R0-B/G).
4. Polarity unified ("prevents"≈"causes") → catastrophic wrong analogies.
5. λ mis-tuned: too high → one deep chain dominates; too low → bag-of-edges.
6. Greedy merge locks into a wrong early commitment on symmetric graphs
   (mitigation: 2–3 randomized restarts, still cheap).

# What NOT To Build

Full SME (exhaustive merge, pragmatics, incremental mapping); connectionist
analogy engines (ACME/LISA — uncalibratable here); learned graph matchers
(violates no-training); semantic-similarity-guided alignment as a *hard*
constraint (kills cross-domain); free-text relation labels at match time.

# Architecture Consequences

- Closed relation-type vocabulary with polarity is a hard prerequisite —
  freeze ~8 types before any matcher work.
- Reified relations only when referenced by other relations; extractor must
  support one level of nesting (cause-of-cause).
- Ordered argument roles mandatory on all relations.
- Delexicalized S_rel and label-based S_sem are separate fields in every
  result; UI and benchmark must never see a single fused number only.
- The aligner's mapping object is the canonical "explanation" format —
  design it as a first-class artifact (JSON), not a by-product.
- Systematicity depth requires extraction to preserve *why-chains*; R0-F
  contract must include a higher-order-relation test case.
- λ (systematicity base) is the single most sensitive constant — expose it
  in config, calibrate on the R0-G gold pairs.

# Sources

1. Gentner, D. — *Structure-Mapping: A Theoretical Framework for Analogy*,
   Cognitive Science 7(2), 1983. Defines the constraints this report makes
   mandatory (systematicity, one-to-one, parallel connectivity).
2. Falkenhainer, Forbus, Gentner — *The Structure-Mapping Engine* (SME),
   Artificial Intelligence 41, 1989. The algorithmic operationalization;
   source of the match-hypothesis/merge architecture.
3. Forbus, K., Oblinger, D. — *Making SME Greedy and Pragmatic*, CogSci 1990.
   Greedy merge: polynomial-time best-interpretation construction — the
   variant recommended here.
4. Forbus, Gentner, Law — *MAC/FAC: A Model of Similarity-Based Retrieval*,
   Cognitive Science 19(2), 1995. Places structure mapping firmly in the
   expensive stage; cheap stage non-structural.
5. Forbus et al. — *Extending SME to Handle Large-Scale Cognitive Modeling*,
   Cognitive Science 41(5), 2017. Evidence that greedy SME scales and which
   simplifications survived 25 years of use.
6. Chalmers, French, Hofstadter — *High-Level Perception, Representation,
   and Analogy*, JETAI 4, 1992. The representation-dependence caveat that
   bounds every claim above.
7. Gick, Holyoak — *Analogical Problem Solving*, Cognitive Psychology 12,
   1980. Why relational competence must be paired with non-structural
   retrieval (humans fail structure-first retrieval too).
