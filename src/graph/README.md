# Executable Thought DNA v0.1

This module implements the accepted R0 Thought DNA contract without extraction,
retrieval, alignment, scoring, or MCP transport.

Public surface:

- `ThoughtGraph.from_dict(...)` / `.to_dict()`
- `validate_thought(...)`
- `canonical_dict(...)`, `canonical_json(...)`, `canonical_sha256(...)`
- deterministic optional ID helpers in `ids.py`
- version policy in `versioning.py`

Canonicalization materializes the accepted assertion/modality defaults and sorts
semantically unordered arrays. It never infers relations, rewrites labels,
changes endpoints, or coarsens the graph.

Validation is intentionally split in two layers:

1. `schemas/thought-dna-0.1.schema.json` — portable shape/schema contract.
2. `src.graph.validation` — cross-field semantic checks such as SHA-256,
   exact source spans, unique IDs, endpoint existence, and manual-vs-extracted
   grounding rules.

Polarity is not an extra canonical field: it is preserved through relation
`type` (`causes` vs `prevents`/`contradicts`) plus `assertion`; the Python
`Relation.polarity` property is only a convenience view.
