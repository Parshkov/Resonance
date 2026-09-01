# Resonance engine interfaces v0.1

This package freezes the minimal pure-Python boundaries that let R2 extraction,
R3 retrieval and R4 verification be implemented independently.

Requires **Python ≥ 3.10** (`dataclass(slots=True)`). The validation and
canonicalization interface is `GraphValidator` plus the accepted `src.graph`
canonical functions.

```text
context
  |
  v
Extractor -> ExtractionResult -> ThoughtGraph
                               |
               +---------------+---------------+
               |                               |
               v                               v
          ThoughtStore                   CandidateIndex
                                               |
                                               v
                                        CandidateResult
                                               |
                                 optional seed hints only
                                               |
                                               v
                                      StructuralVerifier
                                               |
                                               v
                                         VerifierResult
                                      / score + explanation

R5 implements EngineFacade from these ports.
Future transports wrap EngineFacade only.
```

## Dependency rule

`src.interfaces` may depend on `src.graph` and the Python standard library.
It must not import extraction, fingerprint/index, alignment/scoring
implementations, or any transport package. R2/R3/R4 implement these protocols;
they do not import one another's internals.

## Important semantic boundaries

- `CandidateIndex.query`, `EngineFacade.find`, and `EngineFacade.compare` take a
  frozen v0.1 `mode` from `RESONANCE_MODES`: `structural`, `analogical`,
  `complementary`. Use `require_mode()`; unknown names are non-conforming.
- `CandidateIndex` returns graph candidates, channel scores/ranks and optional
  seed correspondences. Seeds are hints; the verifier is free to ignore them.
  `SeedCorrespondence.support` is channel-relative and not comparable across
  channels.
- Retrieval never supplies a semantic node-pair mask that constrains structural
  correspondence.
- `VerifierResult` exposes a score vector, mapping, contradictions, unmatched
  nodes **and relations**, retrieval flags, and structured provenance. There is
  no blended-only result type. Mapping/unmatched/contradiction payloads in
  `Explanation` must equal the parent `VerifierResult`.
- `ScoreVector` types Scoring v0.1 components (`N_role`, `R_direct`,
  `R_direct_unweighted`, `R_path`, `Y_systematicity`, `H_sign_conflict`,
  `E_nodes`, `E_relations`, `knowledge_evidence_present`, `rarity_weighting`, …)
  and round-trips through `to_wire()` / `from_wire()`. `from_wire()` requires
  the complete v0.1 field set, rejects unknown top-level keys, rejects
  non-finite / non-numeric / boolean-as-float values, and keeps extension
  diagnostics only under `extras`. Python field `retrieval_content` is the
  Scoring v0.1 wire name `retrieval_semantic`.
- `CandidateResult` snapshots channel maps; callers cannot alias-mutate them.
- `EdgePathMatch` carries query provenance, per-relation candidate provenance,
  and parallel provenance for `realizes_nodes`. Provenance `item_id` values
  must equal the canonical IDs they describe.
- `VerifierResult` mappings are partial and mutually injective. Matched
  relation IDs are unique on each side. Mapped node/relation IDs are disjoint
  from the unmatched sets.
- `ResonanceHit` requires `candidate.candidate_id == verification.candidate_id`.
  It does not bind `query_id`; the caller must not mix a candidate from one
  query with a `VerifierResult` from another.
- `ConfigRef` carries schema/component/config identity through boundaries.
- `EngineFacade` is a core Python protocol, not a transport protocol. R6 may
  adapt it, but must not move matching logic into handlers.

## Versioning

`INTERFACE_VERSION = resonance-interfaces/0.1` and
`SCORE_CONTRACT_VERSION = resonance-score/0.1` are independent of the Thought
DNA schema version. An incompatible public type/method change requires a new
interface version rather than silent mutation.
