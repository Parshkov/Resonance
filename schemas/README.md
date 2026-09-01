# Thought DNA schemas

`thought-dna-0.1.schema.json` is the portable JSON Schema for the accepted
Thought DNA v0.1 shape.

`demo-corpus-0.1.schema.json` is the portable envelope for R7 consented demo
sessions. It wraps Thought DNA; it does not extend or replace it.

The Python validator in `src/graph/validation.py` is additionally normative for
cross-field invariants that JSON Schema alone does not conveniently enforce:
source SHA-256, exact span slices, unique local IDs, relation endpoint existence,
and manual/extracted grounding rules.

## v0.x migration policy

1. `schema_version` is mandatory and is never silently coerced.
2. Changing a canonical role, relation type, provenance/grounding rule,
   polarity/modality semantics, or field meaning requires a new schema version.
3. Derived retrieval/alignment fields never enter Thought DNA merely to avoid a
   schema change.
4. Every migration is an explicit source-version -> destination-version pure
   transform with fixtures and semantic-loss tests; claimed reversibility needs
   round-trip tests.
5. Unknown versions fail closed with `MigrationRequired`.
6. v0.1 has no predecessor migration; its migration path to itself is empty.
7. Frozen benchmark gold retains its original version. Migrated fixtures are
   added as new versioned material rather than rewriting historical evidence.

Do not mutate v0.1 semantics in place to satisfy a downstream implementation.
