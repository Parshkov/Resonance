# R4 verifier — typed partial graph alignment (ADR-0003)

Pipeline: `proposal → consistency → partial Hungarian rounding → exact adjudication`.

- **`MultiRelFGWVerifier`** — v0.1 prototype default: multi-relational FGW
  conditional gradient, one directed channel per relation type **plus its
  transpose**, α = 0.7, ε-padding for unmatched nodes, exact quadratic line
  search, deterministic. stdlib-only (no numpy).
- **`RRWMVerifier`** — co-equal gate candidate: sparse Lawler-QAP affinity over
  typed directed propositions, simplified reweighted random walks (recorded as
  not-pygmtools per ADR-0003), same rounding/adjudication path.

Hard rules enforced at adjudication (never in the proposal): high-confidence
`causes`/`prevents`, asserted/negated, and direction inversions hard-reject
unless a genuinely different conflict-free mapping of **no lower support
quality and no fewer nodes** exists; mapping selection is by conflict-blind
support quality so a weaker mapping can never win by hiding conflicts; local
cleanup may drop only pairs with **zero preserved evidence and zero
contradiction involvement** (dodging via un-mapping is the "local yes, global
no" failure mode and is structurally prevented, twice).

Guarded edge-to-path matching (`path_matching: "guarded" | "off"`): uniform
`causes` composition, ≤ 4 relations, interiors `atomic=false`, unmapped,
`asserted`/`actual`, role `mechanism`, degree exactly 2. Benchmark v0.2's
`V02-04` (gold-declared meaningful mediator, machine-identical to a
transparent one) is the residual this guard cannot catch by construction —
measured and reported, with `"off"` as the audit-clean configuration.

Seeds are hints: at least one unseeded restart always runs and selection can
override seeded results (C3's measured seeds caveat, ADR-0003).
