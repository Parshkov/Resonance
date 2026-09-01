# R8 — visualization-ready resonance discovery

A read-model over the ACCEPTED engine: joins `find()` results with consented
presentation metadata into the strict versioned DTO
`resonance-discovery/0.1`. No matching semantics live here — the source-scan
test forbids any reference to alignment/index/fingerprint/scoring internals,
and match order is exactly the engine's order with non-consented entries
removed (removal preserves relative order; a permutation test proves display
metadata cannot move a single score or position).

**Segregation, not compensation:** entries whose `VerifierResult` carries the
engine's own `hard_rejection` are returned under `rejected[]` with the reason
— a causal inversion is surfaced as a contradiction, never reported as
resonance (ADR-0003 / E2E scenario 5). The split reads one engine field;
no score threshold is applied anywhere.

**Leak-safety by construction and by test:** hidden sessions are absent from
`matches[]`, `rejected[]` AND `aggregation` — the committed test proves the
full response is byte-identical whether the hidden resonant session exists in
the metadata or not, so no count can reveal it. Locations appear only when
`location_shareable`; aggregation counts only those. No direct identifiers on
the wire (tested).

**MCP exposure decision (documented per the issue):** one additive tool,
`discover_resonance`, via `DiscoveryAdapter`/`DiscoveryMCPServer` subclasses —
the accepted R6 adapter, server, and its 8 tools are inherited unmodified
(asserted by test). `request_intro` stays a service capability (tested, with a
disclosure-free audit log) and is NOT exposed in v0.1: smallest additive
surface until R9 wires the action, at which point exposure is one schema.

```bash
python3 -m src.discovery.demo_server        # discovery-enabled MCP over the demo corpus
```

**Provisional pieces, named:** the metadata model
(`resonance-demo-metadata/0.1-provisional`) and the fixture corpus await the
R7-CORPUS (#72) schema freeze; both are strict-loaded so the freeze can only
tighten them. Final acceptance of this mission is expected to include
re-keying fixtures to the frozen R7 schema.

**Known honest surface for R9** (`fixtures/example_response.json` is the
render contract): the flagship query returns the paraphrase as `direct` and
the two cross-domain analogues with full scores/evidence but
`mode_classification: negative` — the frozen `T_ANALOGICAL_STRUCTURE=0.85`
calibration gap recorded at R4/R5 acceptance (analogues sit at 0.809–0.828).
Discovery reports it verbatim; the calibration round owns the fix.
