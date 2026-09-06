# R4 scoring — exact adjudicator

The current classification policy is
`CLASSIFY_POLICY = scoring-v0.2-concept-aligned-analogy+same-subject-floor/0.3`
(ADR-0004, extended by #193). **Read "Scoring policy v0.2" at the bottom for
what the code does today.** The section immediately below records the
original v0.1 adjudicator and is kept for provenance: its component formulas
still stand, its classification rule does not.

## v0.1 adjudicator (RESONANCE_SCORING_v0.1) — historical

Evaluates a discrete partial injective mapping; a relaxation objective is
never the final decision. Implements the contract's component formulas
verbatim (`N_role`, `R_direct` (+unweighted), `R_path`, `Y_systematicity`,
`Q_containment`/`Q_symmetric`, `X_contradiction`, `H_sign_conflict`,
`E_nodes`/`E_relations`, evidence gate, structural score) plus the
non-structural channel (`S_semantic`, `K_about`/`K_requires`, directional
complement overlaps) and classification.

Deliberate implementation decisions, all recorded in the verifier config hash:

- **Query relations are obligations**: `R_direct`'s query-side denominator is
  ALL query relations, so un-mapping a problem node can never shrink what must
  be explained. Candidate side stays induced-only (containment).
- **`global_consistency` contradictions**: both graphs assert same-type
  structure from one mapped node over mapped nodes but to different targets.
  One empty side is unobserved evidence, never a contradiction.
- **Effective relation evidence diminishes for repeated patterns** (first
  occurrence 1.0, repeats 0.25) — a monotype generic chain cannot buy the
  evidence of diverse preserved structure.
- **Classification was knowledge-first with a versioned fallback**
  (`CLASSIFY_POLICY = scoring-v0.1-knowledge-first+semantic-fallback/0.1`,
  carried in the config hash). **Superseded by v0.2 below**; the knowledge
  branch survives inside it, the `T_ANALOGICAL_STRUCTURE = 0.85` threshold
  quoted here does not (it is 0.80 today). The Scoring v0.1 knowledge branch fires
  verbatim whenever both graphs carry `about` ids. The contract's
  knowledge-absent outcome is `direct_or_analogical_unknown`, which the
  benchmark wire enum cannot express, so the fallback resolves the unknown by
  the label-semantics proxy guarded by `T_ANALOGICAL_STRUCTURE = 0.85`
  (calibrated on the calibration split; cross-domain ≈ 0.888 vs generic
  distractors ≈ 0.775 — the DNA-native generic-motif defence while
  `rarity_weighting=false`).
- **Measured basis for the fallback** (v0.1 fixtures): 16 `about` refs across
  136 graphs (bridge families only), `K_about = 0.0` on all 128 pairs
  including paraphrase, `K_requires = 1.0` across paraphrase, vocabulary
  substitution, cross-domain analogy AND generic distractors alike (pack-
  scoped ids). Consequence, stated rather than hidden: on these fixtures
  `vocabulary_substitution` (gold approximate) and `cross_domain_analogy`
  (gold analogical) are indistinguishable in every knowledge channel and
  differ in label overlap by 0.04 vs 0.00 — the class boundary between them
  is not decidable from pair content, so the fallback keeps emitting
  `analogical` for both and `vocabulary_substitution` reports
  `classification_accuracy = 0` (no gate reads that metric). Real concept
  IDs from R0-E/R2 extraction will activate the knowledge branch and retire
  the fallback for annotated corpora.

## Scoring policy v0.2 (ADR-0004) — current

* `semantic` is lexicon similarity; `extras` carry `surface_semantic`,
  `concept_alignment` (mean over lexicon-covered pairs × sqrt(coverage)),
  `domain_overlap`, `rarity`, `n_role_exact`.
* `label_identity` contradictions: a mapped node whose unmistakable label twin
  (surface >= 0.8) sits elsewhere.
* Role/coverage terms scale with sqrt(R); path credit is additive to direct
  credit; the evidence gate is sqrt(min(1,n/4)·min(1,e/3)).
* Classification: complementary → hard sign → structural/contradiction gate →
  surface/domain overlap ⇒ direct/approximate → concept alignment >= 0.25 ⇒
  analogical → rare skeleton (corpus present) with weak concept support ⇒
  analogical → negative. Thresholds calibrated on Benchmark v0.2 S1–S4 only.
* **Same-subject floor** (#193, policy `/0.3`): when `semantic >= 0.40`,
  `contradiction == 0` and at least one relation is directly preserved, the
  structural bar drops from `T_STRUCTURE = 0.25` to
  `T_STRUCTURE_SAME_SUBJECT = 0.15`. `structural` compares whole graphs, so it
  falls as one person's picture grows, and the person working on one piece of
  your problem was being refused for knowing their own problem better. These
  two thresholds were fitted to a single real pair rather than to the
  calibration split; the v0.2 gate was used only as a regression check, so it
  is no longer a fully held-out measurement of this branch. Recorded here
  rather than left implicit.
* `confidence()` returns high / medium / low.
* The policy string is carried in the verifier config hash and is the only way
  a recorded verdict can be traced to the rule that produced it, so it moves
  whenever the decision boundary moves.
