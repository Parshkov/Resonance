# R4 scoring — exact adjudicator (RESONANCE_SCORING_v0.1)

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
- **Classification is knowledge-first with a versioned fallback**
  (`CLASSIFY_POLICY = scoring-v0.1-knowledge-first+semantic-fallback/0.1`,
  carried in the config hash). The Scoring v0.1 knowledge branch fires
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

## Scoring policy v0.2 (ADR-0004)

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
* `confidence()` returns high / medium / low.
