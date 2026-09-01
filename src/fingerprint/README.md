# Structural fingerprints v0.1

MULTI landmark-pair fingerprints for R3 retrieval. This package does not
score resonance, verify mappings, or talk to MCP.

Default configuration is **MULTI** (D0 + D1). Role-only D0 is an ablation
control and is not a shippable default.

- `D0`: controlled functional role
- `D1`: one round of directed, relation-typed WL refinement
- pair keys: `(scale, desc_a, desc_b, typed-directed path signature, distance bucket)`
- path length at most 3
- no semantic/label bits in structural keys
