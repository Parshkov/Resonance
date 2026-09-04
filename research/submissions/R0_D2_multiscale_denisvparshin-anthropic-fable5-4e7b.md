---
mission: R0-D
run: D2 (independent repeat, REPEAT_CLAIM)
contributor: DenisVParshin
agent_or_model: Claude Fable 5 (claude-fable-5), Claude Code CLI
date: 2026-08-31
mission_modified: false
web_research_used: true
independence_disclosure: >
  IMPORTANT — this is NOT a clean blind repeat. The canonical R0-D submission
  is merged to main and, although the file was deliberately left unopened, a
  repository-wide grep during an earlier security review surfaced ~9 fragment
  lines from it: mentions of path-length buckets {1,2,3+}, IDF-weighted
  inverted postings, a structural/semantic token split, per-thought token
  caps (64/64), coarse-view path hashes, and WL subtree tokens for
  iterations 0–2 on a contracted graph G_c. This reveals the canonical
  design's gist. This report also uses contraction views and bucketed path
  lengths; convergence on those elements is CONTAMINATED and must not be
  scored as independent confirmation. Divergences (e.g., this report's
  restrictive contraction-safety rule, its rejection of WL tokens, and its
  view-list verifier API) remain informative. Same-agent note: one of eight
  sequential runs by one agent in one session.
---

# Decision

Granularity invariance should live in **preprocessing (deterministic
contraction views) plus the verifier (best-of-views alignment)** — not in a
multiscale signature. The simplest sprint-affordable mechanism: for every
Thought Graph, derive 0–2 **coarse views** by contracting *only* chains that
pass a strict safety rule (degree-2 interior nodes, uniform edge type,
uniform polarity, no reified-relation participation), recording the
contracted span as provenance on the merged edge. Retrieval fingerprints
(R0-B) are computed on the union of views with the path-length bucket
{1,2,3+} absorbing small residual differences. Verification (R0-C) accepts a
list of views per thought and scores the best view pair. Spectral, heat-
kernel, diffusion, and persistent-homology signatures are rejected for v0.1:
they are size- and density-sensitive on 10–100-node sparse typed graphs,
unexplainable to users, uncalibratable without labeled data, and answer
"similar shape?" rather than "which branches correspond?". Deep granularity
mismatches (different decomposition *logic*, not just chain expansion) are
declared out of scope as invariants — they belong to analogy scoring, not
preprocessing.

# Confidence

MEDIUM-HIGH on "contraction views + verifier, not signatures" — the
reasoning is about controllability and explainability, and it is robust.
MEDIUM on the exact safety rule: it is intentionally conservative, and the
open question (<100 words) is coverage — if real extracted chains rarely
satisfy uniform-type/uniform-polarity interiors, the views rarely differ
from the base graph and granularity robustness silently vanishes. The toy
experiment measures exactly this coverage rate. Better to start too strict:
a wrong contraction *creates* false structure, and R0-H's attack catalogue
shows "everything contracts to A→failure" is the failure to fear.

# Answers to the mission's Resolve questions

1. **Simplest useful method:** deterministic safe-chain contraction views +
   best-of-views verification, as above. No new math, ~100 lines, fully
   explainable ("matched at coarse view: A→B ≙ A→X→Y→B", with the
   contracted span shown).
2. **Where should scale invariance live?** Preprocessing (views) and
   verifier (view selection). Fingerprints only inherit views and bucket
   path lengths; no separate multiscale signature. Rationale: invariance
   implemented in an index is invisible and undebuggable; implemented as
   explicit views it is inspectable data.
3. **Contracting low-information nodes without destroying causal
   structure — the safety rule:** contract interior node n of a chain
   e1: a→n, e2: n→b iff deg(n)=2, type(e1)=type(e2), polarity(e1)=
   polarity(e2), n is not an argument of any reified relation, and
   type(n) ∈ {state, event} (never goals, constraints, claims). The merged
   edge keeps the shared type/polarity, records `contracted:[n]`, and
   accumulates transitively (A→X→Y→B ⇒ A→B with contracted:[X,Y]). Nodes on
   branches, joins, or polarity changes never contract — those are exactly
   the places where meaning lives (R0-H attack 4: smoking→…→cancer and
   smoking→…→depression must not both collapse to "smoking→bad").
4. **Cheap-enough multiscale signature for retrieval?** None adopted. The
   {1,2,3+} path-length bucket on fingerprint tokens *is* the retrieval-
   stage concession: it makes a 1-step and a 2-step chain of identical
   typing collide intentionally. Anything richer (WL at multiple radii,
   diffusion signatures) adds fragility faster than recall on graphs this
   small — WL subtree labels over a 6-type vocabulary saturate by radius 2
   while amplifying single-type extraction errors multiplicatively.
5. **Scale transformations that cannot be treated as invariant:**
   (a) re-decomposition that changes branching topology (one thought splits
   a mechanism into two parallel causes, another chains them);
   (b) abstraction that changes node/edge *types* (a mechanism summarized as
   a constraint); (c) contraction across polarity flips or joins;
   (d) summarization that drops a causal actor entirely. These are
   legitimate *differences between thoughts*, and a system that irons them
   out has destroyed its own discriminative power (the invariance/
   discrimination trade-off, argued in full in R0-H2).
6. **Thought DNA fields for safe coarsening:** edge type + polarity (the
   rule's preconditions); node type; reified-relation references (contraction
   blocker); span provenance (merged edges must carry the contracted nodes'
   spans so explanations can expand them); `view_id` + `contracted` lists on
   derived views; extractor/view-generator version.
7. **≤2h experiment:** below.

# Required Thought DNA / Graph Representation

No new node/edge fields beyond R0-A2/F3; adds a *view* wrapper:
`{thought_id, view_id: base|c1|c2, generator_version, graph}`. Views are
derived artifacts — regenerable, never authored.

# Invariances

This mission is the F-row of every other report's table; the honest summary:

| Case | Handled | Mechanism |
|---|---|---|
| A→B vs A→X→Y→B (uniform chain) | yes | c-views collide them; verifier explains via contracted span |
| chain vs chain, different interior lengths | yes | both contract to same coarse edge |
| expansion with branching interior | no (by design) | branch = meaning; treated as partial match, not granularity |
| type-changing abstraction | no (by design) | different DNA is different thought |
| mixed: some chains contract, some don't | partial | best-of-views takes the dominant scale |

# Retrieval vs Verification

BOTH, as a data transform: views feed fingerprinting (union of views'
tokens, capped) and verification (view-pair selection). The transform itself
is O(nodes) and runs at extraction time.

# Computational Cost

View generation: linear, microseconds; ≤ 2 extra views ⇒ index grows ≤ ~2×
token count before caps (caps unchanged, so real growth is selection
pressure, monitor recall). Verifier tries ≤ 3×3 view pairs but can prune:
try (base,base), then coarse pairs only if S_rel below threshold — expected
< 2× verification cost. 1M corpus: storage +≤2 small views per thought.

# Existing Implementations

networkx `contracted_nodes` / minors module (mature) covers the mechanical
contraction; the safety rule is ~50 lines on top. Graph-coarsening
libraries (spectral coarsening et al.) and NetLSD-class signature code
exist and are deliberately not adopted (wrong invariance class,
unexplainable). No new dependencies.

# Minimal Pseudocode

```
def coarse_view(G):
    H, merged = G.copy(), True
    while merged:
        merged = False
        for n in list(H.nodes):
            e_in, e_out = sole_in(H,n), sole_out(H,n)
            if (e_in and e_out and H.deg(n)==2
                and e_in.type==e_out.type and e_in.pol==e_out.pol
                and n.type in {"state","event"} and not reified_arg(H,n)):
                H.merge_edge(e_in, e_out, contracted=+[n]); merged=True
    return H if H != G else None       # emit only if it differs
```

# Toy Experiment

≤2h, against a no-multiscale baseline. From 15 seed graphs, generate
expansion variants: (i) 15 uniform-chain expansions (insert 1–3 interior
states on one causal edge); (ii) 10 unsafe expansions (interior with a
branch, or polarity flip); (iii) 20 distractors. Run verifier
correspondence and fingerprint self-retrieval twice: base-only vs
with-views. Metrics: match rate on (i) — expect ≈ baseline+large; false
collapse rate on (ii) — must stay 0 with the safety rule (any wrong
contraction is a hard failure); coverage — fraction of (i) whose expansion
actually contracted (< 0.7 means the rule is too strict → relax type(n)
condition first). **Falsifier:** if with-views does not beat base-only on
(i) by ≥ 30 points of match rate at zero (ii) violations, contraction views
are not worth their complexity and F-invariance should be dropped from v0.1
claims.

# Failure Modes

1. Everything-ends-in-failure degeneration: aggressive contraction reduces
   diverse thoughts to endpoint stubs — prevented by the uniform-type/
   polarity interior rule; monitor coarse-view token DF as a canary.
2. Coverage collapse (rule too strict) — views ≡ base, silent loss of the
   feature; coverage metric in CI.
3. Extraction grain interacts: two-pass agreement core (R0-F) may already
   pick the sparse reading, making query coarse but corpus fine —
   views must be generated on *both* sides symmetrically.
4. Contracted spans dropped from explanation → user sees A→B claimed
   present in a text that never states it directly — span provenance on
   merged edges is mandatory.
5. View explosion on pathological chain-heavy graphs (k levels) — hard cap
   at 2 derived views.
6. Fingerprint cap eviction: view tokens displace base tokens under the
   per-thought cap — select by IDF across the union, monitor.

# What NOT To Build

Heat-kernel/diffusion/spectral signatures (NetLSD-class) for retrieval or
verification v0.1; persistent homology (wrong scale, wrong invariants,
heavy dependency); multi-radius WL token pyramids over noisy 6-type labels;
learned coarsening; aggressive semantic contraction ("merge similar
nodes" — that is entity resolution, a different and dangerous feature);
granularity handled inside FGW cost matrices only (invisible, uncontrollable).

# Architecture Consequences

- Thought record = base graph + ≤2 derived coarse views, all versioned;
  views are cache, not truth.
- Contraction safety rule is a frozen, versioned spec (dna-views-0.1);
  changing it invalidates indexes like an extractor upgrade does.
- Verifier API takes view lists and returns which view pair won — surface
  this in explanations ("matched at coarse granularity").
- Fingerprint tokens carry no view marker (collision across scales is the
  point); ablate views separately in R0-G.
- Unsafe-expansion false-collapse rate is a permanent regression metric
  with a zero-tolerance threshold.
- Deep re-decomposition is officially a *difference*, not noise — product
  copy and benchmark labels must not promise otherwise.

# Sources

1. Wang — ISMIR 2003. The origin of the "landmarks must survive local
   perturbation" framing that motivates bucketed lengths rather than exact
   path lengths.
2. Forbus, Oblinger 1990 / Falkenhainer et al. 1989 (SME lineage). Best-of-
   views alignment is plain SME over alternative representations; the
   verifier needs no modification.
3. networkx minors/contraction documentation. The implementation substrate
   for safe-chain contraction.
4. Shervashidze et al. — WL Graph Kernels, JMLR 2011. Basis for the
   saturation/fragility argument against multi-radius WL tokens on small
   6-type graphs.
5. Tsitsulin et al. — NetLSD (KDD 2018). Representative of the spectral-
   signature class evaluated and rejected: global-shape descriptors without
   correspondences, size-sensitive, threshold-uncalibratable here.
6. Banarescu et al. — AMR IAA studies. Grounds the claim that extraction
   grain itself drifts, which contraction views must absorb symmetrically.
