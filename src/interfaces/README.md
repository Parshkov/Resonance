# Resonance engine interfaces v0.1

This package freezes the minimal pure-Python boundaries that let R2 extraction,
R3 retrieval and R4 verification be implemented independently.

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

- `CandidateIndex` returns graph candidates, channel scores/ranks and optional
  seed correspondences. Seeds are hints; the verifier is free to ignore them.
- Retrieval never supplies a semantic node-pair mask that constrains structural
  correspondence.
- `VerifierResult` exposes a score vector, mapping, contradictions, unmatched
  nodes **and relations**, retrieval flags, and structured provenance. There is
  no blended-only result type. Mapping/unmatched/contradiction payloads in
  `Explanation` must equal the parent `VerifierResult`.
- `ScoreVector` types Scoring v0.1 components (`N_role`, `R_direct`, `R_path`,
  `Y_systematicity`, `H_sign_conflict`, `E_nodes`, `E_relations`, …) and
  round-trips through `to_wire()` / `from_wire()`.
- `CandidateResult` snapshots channel maps; callers cannot alias-mutate them.
- `EdgePathMatch` carries query provenance and per-relation candidate provenance.
- `ConfigRef` carries schema/component/config identity through boundaries.
- `EngineFacade` is a core Python protocol, not a transport protocol. R6 may
  adapt it, but must not move matching logic into handlers.

## Versioning

`INTERFACE_VERSION = resonance-interfaces/0.1` and
`SCORE_CONTRACT_VERSION = resonance-score/0.1` are independent of the Thought
DNA schema version. An incompatible public type/method change requires a new
interface version rather than silent mutation.
