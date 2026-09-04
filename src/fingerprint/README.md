# Structural fingerprints v0.1

MULTI landmark-pair fingerprints for R3 retrieval. This package does not
score resonance, verify mappings, or talk to MCP.

Default configuration is **MULTI** (D0 + D1). Role-only D0 is an ablation
control and is not a shippable default.

- `D0`: controlled functional role
- `D1`: one round of directed, relation-typed WL refinement
- pair keys: `(scale, desc_a, desc_b, typed-directed path signature, distance bucket)`
- path length at most 3
- equal-length paths are canonicalized by the lexicographically smallest
  `(direction, type, assertion)` token sequence, independent of relation IDs
- no semantic/label bits in structural keys

## v0.2 (ADR-0004)

Two key families now exist. `fingerprints()` is unchanged in spirit: label-free
D0/D1 landmark pairs joined by the canonical typed path (<= 3). `concept_fingerprints()`
adds keys over `(role, abstract concept class)` from `src/semantics` with typed
paths <= 2 plus single-landmark keys, so an analogy in another domain shares
keys while a template coincidence with concept-free labels does not. Query-side
class expansion (`expand=True`) reaches strongly related classes. Adjacency is
computed once per graph. `FEATURE_VERSION` carries the lexicon version.
