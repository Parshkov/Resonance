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
- **`T_ANALOGICAL_STRUCTURE = 0.85`** — an analogy claim has no semantic
  support by definition and therefore demands stronger structural evidence;
  calibrated on the v0.1 calibration split (cross-domain ≈ 0.888 vs generic
  distractors ≈ 0.775). This is the DNA-native defence against generic motifs
  while `rarity_weighting=false` (no corpus snapshot exists yet).
