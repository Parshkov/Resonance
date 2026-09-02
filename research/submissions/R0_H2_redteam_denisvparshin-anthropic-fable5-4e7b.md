---
mission: R0-H
run: H2 (independent repeat, REPEAT_CLAIM)
contributor: DenisVParshin
agent_or_model: Claude Fable 5 (claude-fable-5), Claude Code CLI
date: 2026-08-31
mission_modified: false
web_research_used: true
independence_disclosure: >
  The canonical R0-H submission (PR #29) was NOT read: not its report body,
  arguments, attack pairs, or review discussion. Unavoidable exposure during
  board-state determination: the issue/PR title, which contains the canonical
  run's headline verdict ("QUALIFIED NO-GO"). Convergence on the headline
  verdict therefore does NOT count as independent; convergence or divergence
  on specific arguments, mechanisms, and attack constructions does. Merged
  sibling submissions (R0-A, R0-B2, R0-C2, R0-D) were also left unread; a
  repository-wide grep during a security review incidentally surfaced ~11
  fragment lines (9 from R0-D, 1 each from R0-B2 and R0-C2: WL/path-token
  and bucketing mentions, a Shazam bit-budget table row, one granularity
  remark). No substantive argument text was
  read. All primary sources cited below were fetched and checked directly
  during this run.
---

# Decision

NO-GO on the architecture as drawn. The pipeline `Thought Graph → relational
fingerprints → candidate retrieval → structural alignment → explanation` fails
at its load-bearing joint: Shazam-style relational fingerprinting cannot serve
as the **primary retrieval stage** over a corpus of independently extracted
Thought Graphs. Four independent attacks each suffice: (1) the Shazam robustness
model assumes query and database item are two copies of the *same underlying
signal*, which Resonance never has; (2) the entropy budget of typed-graph
tokens is roughly 10–14 skewed bits against the ~30 bits Shazam
needs at comparable corpus scale; (3) extraction noise exceeds what any
token-exact fingerprint can absorb — trained human experts annotating the *same
sentence* under a *frozen* schema agree only at Smatch ≈ 0.83–0.89; (4) the
mechanism that actually gives Shazam its precision — the O(N log N) global
time-offset consistency check — has no cheap graph analogue; its graph analogue
*is* the NP-hard alignment problem the architecture defers to the expensive
stage. What survives: the two-stage retrieve-then-verify pattern itself, and
the typed Thought Graph as the substrate for **verification and explanation**.
The simplest viable alternative keeps both survivors and moves retrieval to
embedding-led indexing, including a cheap de-lexicalized "structural skeleton"
text channel (§ What NOT To Build / Architecture Consequences).

# Confidence

MEDIUM-HIGH for the NO-GO on fingerprint-primary retrieval: the case rests on
published properties of the borrowed algorithm, arithmetic on the token space,
and measured human ceilings on graph annotation — but the Toy Experiment below
can empirically refute it, and the steelman section states the strongest
counterargument; the verdict is therefore conditional on that gate, not
settled by arithmetic alone. MEDIUM for
the proposed alternative: the de-lexicalized skeleton channel is plausible and
cheap but unproven; only the R0-G benchmark can show whether it adds recall on
cross-domain pairs over raw-text embeddings. Main uncertainty (<100 words): a
carefully quantized structural sketch might still earn a place as a *secondary*
recall channel for analogy; nothing in this attack rules that out — it rules
out structure as the primary index.

# Contract sections in brief

This mission's output emphasizes attacks and final questions; the contract's
remaining canonical sections, compressed: **Required Thought DNA / graph
representation** — this run consumes rather than proposes DNA; its attacks
force polarity and modality fields and one-level reification (details in
§ Architecture Consequences). **Invariances** — attacked rather than
claimed; § "Invariances destroy discrimination" covers A–I and their mutual
tension. **Retrieval vs Verification** — the core claim is that the cheap
stage cannot be structural (§§ b–c). **Computational cost** — the attacks
are analytical; the falsifier costs one evening. **Existing implementations
/ pseudocode** — not applicable to a red-team run; the falsifier's harness
(~200 lines of Python) is specified in § Toy Experiment.

# Where the Shazam analogy breaks mathematically

This answers mission question 5 first because the other attacks hang from it.
All claims below were checked against the primary source (Wang 2003) during
this run.

**(a) The same-signal assumption.** Wang defines robustness as: "hashes
generated from the original clean database track should be reproducible from a
degraded copy of the audio." Shazam matches a *degraded copy* against the
*original of the same recording*. Resonance matches two *independently
generated* representations of two *different* thoughts, produced by a noisy
extractor from different texts by different people. There is no clean/degraded
pair anywhere in the system. The analogy imports robustness guarantees whose
precondition is absent.

**(b) The entropy budget.** A Shazam hash is a pair of spectral peaks plus
their time offset, (f1, f2, Δt) ≈ 10+10+10 = 30 bits drawn from
continuous-valued spectral measurements, packed into 32 bits — and Wang notes a *single*
peak's 10 bits is uselessly unspecific, which is why combinatorial pairing
exists at all. Now count the Resonance analogue. The working node vocabulary is
~10 types (problem, goal, hypothesis, mechanism, constraint, evidence, method,
concept, knowledge-requirement, outcome) and realistically ≤10 edge types. A
landmark token (type_A, edge, type_B) carries log2(10·10·10) ≈ 10 bits *at
most* — before accounting for the fact that thought-graph motifs are heavily
Zipf-skewed (goal-directed thinking is saturated with problem→cause→effect and
goal→constraint→mechanism chains), which collapses effective entropy further
and produces corpus-sized posting lists for the common motifs. IDF weighting
does not create bits that are not there. At 1M thoughts you need ~20 bits of
discrimination *after* noise; the channel does not have them.

**(c) The missing consistency check.** Shazam's precision does not come from
individual hashes — Wang reports that a match can be declared when only ~1–2%
of query hashes survive. It comes from the histogram of time-offset
differences: many weak matches must agree on *one global 1-D rigid alignment*,
verifiable in O(N log N). That is the step that turns garbage matches into
near-zero false positives. The graph-world analogue of "many local matches
agreeing on one alignment" is a globally consistent one-to-one subgraph
correspondence — i.e., precisely the NP-hard alignment problem the architecture
schedules for the *expensive* stage. The cheap stage is left holding only
bag-of-tokens intersection, which is the weak half of Shazam with the strong
half amputated.

**(d) Shazam itself fails re-performance.** Wang §3.3: the algorithm "is not
expected to generalize to live recordings" and is "very sensitive to which
particular version of a track has been sampled" — even when the same artist
performs the same song nearly indistinguishably to human ears. A live
re-performance is the audio analogue of a *paraphrase*. The borrowed algorithm
demonstrably fails at the analogue of Resonance's easiest invariance (A), before
we even reach vocabulary substitution, granularity change, or cross-domain
analogy. The analogy is not merely loose; it points the wrong way.

# Extraction is the dominant noise source (Q1, Q9)

The best available ceiling for humans building semantic graphs is AMR: trained
expert annotators, a mature frozen schema, the *same sentence* — inter-annotator
Smatch ≈ 0.83–0.89 (reported range across AMR studies; 0.79 for webtext in
Banarescu et al.; per-pair lows ~0.64 reported in a cross-lingual AMR study).
Resonance's setting is strictly harder on every axis: schema not yet frozen
(explicitly deferred by the project), input is messy multi-sentence context,
extractor is an LLM whose outputs vary across runs, prompts, and model
versions. Consequences:

1. If two extractions of the *same* thought disagree on 15–30% of triples,
   token-exact fingerprints already fail **self-retrieval** — the query cannot
   reliably find its own duplicate, let alone an analogue. Any fingerprint
   proposal must pass a self-retrieval gate before its indexing math matters
   (see Toy Experiment).
2. Reification choices (is "degrades" an edge or a mechanism node?) are exactly
   the choices LLMs make inconsistently, and each flips the local topology that
   fingerprints hash.
3. **Version drift**: fingerprints are only comparable if produced by the same
   extractor. Every extractor upgrade silently invalidates the corpus index →
   full re-extraction of 1M thoughts as a recurring operational cost.
4. The Chalmers–French–Hofstadter critique of SME (1992) applies with full
   force in modernized form: when representations are hand-tailored (then: by
   researchers; now: by prompt engineering), the "matching engine" quietly
   relocates into whatever builds the representations. The project's own
   constraint — "the LLM is not the matching engine" — is then violated in
   spirit: matching outcomes are dominated by LLM extraction choices even
   though the comparison code is deterministic.

# Generic motifs and false positives (Q3)

Beyond the arithmetic in (b): essentially every goal-directed thought contains
the skeleton problem→goal→constraint→mechanism→outcome. Structure-only
retrieval fires on all of them (attack pair 3 below). Two independent bodies of
evidence say the cheap stage must not be structural:

- **Human evidence.** Gick & Holyoak (1980): with a perfectly analogous source
  story already *in memory*, only ~30% of subjects spontaneously retrieve and
  apply it (vs ~10% baseline, ~80% once hinted). Human memory access is
  dominated by surface features; structural retrieval is the hard, rare part.
- **The field's own scalable design.** MAC/FAC (Forbus, Gentner & Law, 1995) —
  built by the SMT authors — deliberately made stage 1 (MAC) *non-structural*:
  flat content vectors whose dot product merely estimates structural
  matchability; SME runs only in stage 2 on a handful of candidates. The
  canonical two-stage analogy architecture already concluded, thirty years ago,
  that structure cannot be the cheap stage. Resonance's candidate architecture
  proposes to reverse that conclusion without new evidence.

# Invariances destroy discrimination (Q7)

Each requested invariance (master brief A–I) is implemented by deleting
information from the fingerprint channel: granularity-invariance (F) contracts
paths toward their endpoints; domain-substitution (H) strips lexical identity
from the structural channel; irrelevant-branch robustness (D) demands sketching
/ IDF-flattening. Individually survivable; jointly they drive the channel
toward "some typed thing leads to some typed thing," which matches everything.
The wishlist A–I on one channel is close to self-contradictory: you can have a
high-recall, low-precision analogy net (all precision deferred to verification,
which then must run on thousands of candidates, not top-K) or a precise
near-duplicate detector — not both from the same index.

# Would embeddings dominate anyway? (Q6)

For invariances A (paraphrase), C (ordering), E (partial), I (extraction
noise), modern sentence embeddings over the raw text already deliver most of
the value at negligible cost with mature infrastructure. The *only* cases where
structure uniquely wins are B+H (different words, same structure) and the hard
negative (same words, different structure). So the architecture's unique value
concentrates in the **verifier/explainer**, not in retrieval. And a large slice
of the B+H recall can be recovered *inside* embedding space: verbalize the
de-lexicalized skeleton ("a system accumulates a byproduct that degrades its
own function until failure") and embed that string as a second vector per
thought. Cross-domain analogues then collide in text-embedding space with no
new index mathematics at all.

# Knowledge DNA adds mostly non-signal (Q4)

Same-domain: required-knowledge overlap is largely redundant with semantic
similarity (people thinking about batteries need battery knowledge).
Cross-domain — the flagship case: a battery engineer and an organizational
theorist with isomorphic failure structures share almost *no* required
knowledge; the channel is **anti-correlated** with exactly the matches the
project exists to find. Averaged in as independent evidence, it actively
suppresses analogical resonance. Keep it out of the resonance score. Legitimate
residual uses: complementarity mode ("whose knowledge begins where mine ends")
and explanation enrichment.

# Is two-stage retrieval/verification wrong? (Q8)

The pattern survives — it is MAC/FAC, and it is correct. What is wrong is the
assignment of content to stages: stage 1 must be predominantly
semantic/feature-based (embeddings, incl. the skeleton channel), with structure
at most a secondary re-ranking sketch; stage 2 is where typed structure lives.

# Verification-stage attacks (Q2)

Even granting perfect retrieval, the verifier is on thinner ice than the brief
assumes. GW/FGW objectives are non-convex; solvers are initialization-sensitive
and routinely trap in poor local minima (standard results in the GW literature;
multi-restart is the common mitigation, multiplying cost). More fundamentally:
nobody possesses a validated threshold separating "human-recognizable analogy"
from "generic small-graph similarity" on typed 10–100-node graphs, and no
labeled thought-analogy corpus exists to calibrate one — a circular dependency
on R0-G. Whether analogy is even decidable from frozen extracted structure is
the open cognitive question (context-dependence, Q2): SMT says systematicity of
*higher-order* relations carries analogy; first-order loop/chain overlap does
not (attack pair 9). Verification must therefore score higher-order relational
systematicity, not raw edge overlap — this constrains Thought DNA (below).

# Required attacks — ten concrete thought pairs

Each pair: construction → what breaks → component attacked.

1. **Causal inversion (same words, different structure — must NOT match).**
   "Stress causes poor sleep, which degrades performance" vs "Poor performance
   causes stress, which degrades sleep." Identical node bag, reversed edges.
   Breaks: any orderless/bag fingerprint; embeddings also score this pair high —
   the pair is the acid test the *verifier* must win.
2. **Thermal runaway ↔ information cascade (different words, same structure —
   MUST match).** "Battery → heat accumulation → degradation → failure" vs
   "Organization → unprocessed-information accumulation → coordination
   degradation → collapse." Breaks: any fingerprint retaining lexical identity;
   the project's own flagship case contradicts its retrieval channel.
3. **Generic goal-chain collision (must NOT match).** "Learn piano: goal,
   time+money constraints, practice mechanism, mastery outcome" vs "Launch a
   startup: goal, time+money constraints, iteration mechanism, exit outcome."
   Identical typed skeleton; de-lexicalized structure fires at full strength.
   Breaks: exactly the domain-invariant channel that pair 2 requires — pairs
   2+3 jointly bound the channel's achievable precision/recall.
4. **Granularity trap.** "Smoking → cancer" vs "Smoking → tar deposition →
   mutation accumulation → cancer" (should match) vs "Smoking → social stigma →
   isolation → depression" (must not). Path contraction that rescues the first
   comparison reduces all three to "smoking → bad outcome." Breaks:
   invariance F implemented by contraction.
5. **Polarity flip.** "Regular audits *prevent* fraud" vs "Regular audits
   *cause* fraud (by teaching evasion)." Same topology, same nodes, opposite
   polarity. Breaks: any schema with untyped or coarsely-typed causal edges —
   polarity must be a mandatory edge field or FPs are catastrophic and
   embarrassing.
6. **Modality flip.** "If we don't fix the roof, water will destroy the
   archive" (hypothetical, preventive) vs "We didn't fix the roof and water
   destroyed the archive" (factual, regret). Same causal core, different
   stance. Whether these *should* resonate is use-case-dependent; a system
   without a modality field cannot even represent the question.
7. **Padding / boilerplate dilution.** Take any thought; re-extract from a
   verbose retelling with 3× irrelevant branches (LLMs produce these
   faithfully). Breaks: IDF-weighted token overlap (diluted) and GW/FGW
   verification (mass normalization smears couplings under strong size
   asymmetry, 15 vs 80 nodes).
8. **Self-retrieval failure.** The same 4-sentence thought extracted twice by
   the same LLM: run 1 renders "lack of sleep degrades focus" as edge
   (sleep-deprivation)→[degrades]→(focus); run 2 reifies a mechanism node and
   splits "focus" into "attention" + "working memory." Smatch between the two
   ≈ 0.6–0.8 (at or below the human same-sentence ceiling). Breaks: everything
   downstream; this is the cheapest kill-shot and the first thing to test.
9. **Spurious systematicity (structure says yes, humans say no).** "Bank run:
   withdrawals → lower liquidity → more withdrawals" vs "Applause: some clap →
   social pressure → more clap." Isomorphic first-order positive-feedback
   loops; humans call it a cute observation, not "these two people should
   meet." Breaks: any scorer rewarding first-order structural overlap without
   higher-order relational context; SMT's own systematicity principle predicts
   this failure.
10. **Knowledge-DNA suppression.** Pair 2 again, scored with a
    knowledge-overlap term: electrochemistry/thermal-physics vs org-theory/
    information-science — near-zero overlap drags the aggregate below
    threshold. Breaks: Knowledge DNA as an additive independent evidence
    channel; the architecture's own components fight each other on its
    flagship case.

# The strongest counterargument (steelman)

The entropy attack compares single tokens; the strongest reply is that
text retrieval (BM25 over inverted indexes) discriminates billions of
documents with exactly such Zipf-skewed ~10-bit unigram tokens — because
discrimination comes from the IDF-weighted **conjunction** of ~10² tokens
per document, not from any single one. A thought emits ~10² tokens too,
and a semantically bucketed channel (256-cluster endpoints) pushes
per-token entropy toward ~20 bits. On this view the cheap stage needs only
recall — false positives are the verifier's job — and the negative verdict
cannot be settled by arithmetic. Two rejoinders keep the NO-GO, now
explicitly conditional: (1) BM25's tokens are *reproducible* — the same
document always emits the same tokens; Thought tokens pass through a noisy
extractor on both sides, and conjunctions decay multiplicatively with
per-token survival (Wang's own p² argument); (2) the bucketed channel
earns its extra bits from label *semantics*, converging with embedding
retrieval rather than adding independent structural signal. The honest
conclusion: the disagreement is empirical, and the self-retrieval gate
below — not this report's arithmetic — is the decision instrument.

# Toy Experiment

**Self-retrieval under re-extraction and paraphrase (≤2h, falsifies the
retrieval stage).** Inputs: 20 short thought-texts (4–8 sentences, mixed
domains). Generate 3 paraphrases each (LLM). Extract Thought Graphs from all 80
texts, plus a *second* independent extraction of the 20 originals (same model,
same prompt, fresh runs). Add 100 unrelated distractor graphs. Build whichever
fingerprint the B-track proposes (or a plain typed-edge-token baseline).
Metrics: (i) **self-consistency** — Smatch between the two extractions of each
original; (ii) **self-retrieval** — R@1/R@10 for each paraphrase's fingerprint
finding its original among 200 graphs. Expected outcome under this report's
thesis: median self-consistency < 0.85 and paraphrase R@10 < 0.9. **Decision
rule: if either holds, fingerprint-primary retrieval is falsified regardless of
indexing cleverness; if both fail to hold (extraction is stable and retrieval
works), this report's central attack is refuted.** Cost: an evening with an
LLM CLI + ~200 lines of Python.

# Failure Modes

The ten attack pairs above constitute the required concrete adversarial set;
the systemic failure modes they expose, in one line each: same-signal
assumption absent (pairs 2, 8); entropy starvation and motif collision (3, 9);
extraction instability as dominant noise (7, 8); invariance/discrimination
contradiction (2 vs 3, 4); missing mandatory semantics — polarity, modality
(5, 6); verifier miscalibration and spurious systematicity (9); channel
infighting (10); operational fragility under extractor version drift (8).

# What NOT To Build

- Shazam-style landmark hashing as the primary index — for the reasons above.
- Any GNN / learned matcher — violates the no-training constraint; also
  uncalibratable without the nonexistent labeled corpus.
- Full FGW as the default verifier in the MVP — α-tuning needs labeled data;
  non-convexity demands multi-restart; keep it as an *experiment*, not the
  spine.
- Hypergraph / reified-everything representations before the verifier demands
  them — every representational degree of freedom is another axis of extractor
  inconsistency (attack 8).
- Knowledge DNA inside the resonance score.
- Spectral/diffusion multiscale signatures (heat kernels, NetLSD-class) as
  primary retrieval — granularity robustness at the cost of exactly the
  discriminative bits retrieval lacks.

# Simplest alternative architecture

1. Extraction → typed Thought Graph (kept — it is the explanation substrate).
2. Per thought, two text renderings: the raw text, and a de-lexicalized
   verbalized skeleton generated deterministically from the graph ("a system
   accumulates X which degrades function Y until failure").
3. Embed both with a mature off-the-shelf encoder; ANN index (FAISS/HNSW);
   candidate set = union of both channels' top-K. All infrastructure exists.
4. Verifier on top-K: greedy typed alignment, SME-lite — one-to-one, relation-
   type-consistent, polarity-consistent, with an explicit systematicity bonus
   for connected higher-order systems — outputting the correspondence mapping,
   which *is* the explanation. Deterministic, O(K · n²)-ish, fits 40–50h.
5. Structural sketches, FGW, and Knowledge DNA enter later only if R0-G shows
   a measurable recall/precision gap they close.

# Which assumptions survive, which die (final questions)

**Survive:** thought-as-typed-graph (as verification/explanation substrate);
two-stage retrieve-then-verify; cheap-first-expensive-second; blind benchmark
discipline; LLM-at-the-boundary (with the §Extraction caveat that this
constraint is currently violated in spirit, not letter).

**Kill now:** Shazam landmark metaphor for retrieval; structure-primary
indexing at 1M scale; Knowledge DNA as independent resonance evidence; the
full A–I invariance wishlist on a single channel; schema freeze before
polarity/modality are mandatory fields.

**Abandonment criterion for the current engine architecture:** the Toy
Experiment's decision rule, plus one benchmark trigger — if on R0-G the
raw-text-embedding baseline is within noise of the full pipeline on every
category except hand-constructed cross-domain pairs, *and* the skeleton
channel closes less than half of the remaining gap, the structural retrieval
program should be abandoned and structure retained only for verification and
explanation.

# Architecture Consequences

- Mandatory Thought DNA edge fields: **polarity** (causes/prevents/enables/
  inhibits) and **modality** (factual/hypothetical/desired/counterfactual);
  without them attacks 5–6 are unanswerable.
- Mandatory provenance: source-text span per node/edge (audits extraction, the
  dominant noise source).
- Representation for MVP: directed typed multigraph with edge attributes; no
  hypergraphs, reify relations only where the verifier requires arguments-of-
  relations.
- Extractor identity (model+version+prompt hash) must be stored per graph; any
  index is scoped to one extractor version.
- A **self-retrieval CI gate** (Toy Experiment, automated) must pass before any
  retrieval work is trusted.
- Retrieval = embeddings over raw text + de-lexicalized skeleton rendering;
  graph tokens only as optional secondary re-ranking.
- Verifier scores higher-order systematicity, not raw edge overlap.
- Knowledge DNA relocated to complementarity/explanation; excluded from the
  resonance score.
- Benchmark (R0-G) must include: causal-inversion pairs, generic-skeleton
  colliders, polarity flips, padding attacks, and a self-retrieval track.
- Budget note: items 1–4 of the alternative fit 40–50h; nothing in the killed
  list does.

# Sources

1. Wang, A. — *An Industrial-Strength Audio Search Algorithm* (Shazam), ISMIR
   2003. Read in full this run. Supplies the same-signal robustness definition,
   the 30-bit combinatorial hash construction, the time-offset histogram
   mechanism, the ~1–2% surviving-hash statistic, and the §3.3 live-recording
   failure — the four load-bearing disanalogies.
2. Forbus, K., Gentner, D., Law, K. — *MAC/FAC: A Model of Similarity-Based
   Retrieval*, Cognitive Science 19(2), 1995. The canonical two-stage analogy
   architecture; its cheap stage is deliberately non-structural (content
   vectors), which directly contradicts structure-primary retrieval.
3. Gentner, D. — *Structure-Mapping: A Theoretical Framework for Analogy*,
   Cognitive Science 7(2), 1983. Systematicity: analogy lives in higher-order
   relational systems — grounds attack 9 and the verifier requirement.
4. Gick, M., Holyoak, K. — *Analogical Problem Solving*, Cognitive Psychology
   12, 1980. ~30% spontaneous vs ~80% hinted transfer: human structural
   retrieval is the bottleneck; surface dominates memory access.
5. Banarescu et al. — *Abstract Meaning Representation for Sembanking*, LAW
   2013, with subsequent AMR IAA studies reporting expert same-sentence Smatch
   ≈ 0.83–0.89 (0.79 webtext; per-pair lows ~0.64 in a cross-lingual
   study). The measured human ceiling for graph
   extraction consistency under a frozen schema.
6. Cai, S., Knight, K. — *Smatch: An Evaluation Metric for Semantic Feature
   Structures*, ACL 2013. The graph-overlap metric used for self-consistency
   in the Toy Experiment.
7. Chalmers, D., French, R., Hofstadter, D. — *High-Level Perception,
   Representation, and Analogy: A Critique of AI Methodology*, JETAI 4, 1992.
   Hand-tailored representations do the real matching work — modernized here
   as the prompt-engineering/extractor-dominance argument.
8. Vayer et al. — *Optimal Transport for Structured Data with Application on
   Graphs* (FGW), ICML 2019; plus the GW literature on non-convexity and
   initialization sensitivity (e.g., Xu et al., *Scalable Gromov-Wasserstein
   Learning*, 2019; POT documentation). Grounds the verifier-calibration and
   local-minima attacks.
