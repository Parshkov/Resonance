# Resonance Roadmap

This roadmap is intentionally execution-oriented. The project is being built in a short architecture-to-prototype sprint while keeping the research and engineering trail public.

The machine-readable operational source is [`work/queue.yaml`](work/queue.yaml). A phase may start only when its listed prerequisites are explicitly **ACCEPTED**.

## R0 — Scientific and algorithmic ground

Parallel independent missions:

- A — Structure Mapping and human analogy
- B1/B2 — Relational Constellation Fingerprinting, two independent runs
- C1/C2 — Approximate Graph Alignment, two independent runs
- D — Multiscale / granularity invariance
- E — Knowledge DNA / external knowledge coordinates
- F — Context → Thought Graph extraction research
- G — Benchmark / falsification design
- H — adversarial architecture red team

Outputs live under `research/`.

### Gate R0 — R0-SYNTHESIS (#13 / PR #35)

Core implementation stays blocked until synthesis is ACCEPTED. The gate freezes enough of:

- Decision Matrix
- Invariance Specification
- Retrieval ADR
- Verification ADR
- Thought DNA v0.1
- Benchmark v0.1 contract
- initial Resonance scoring/explanation contract

A merge or submission alone is not acceptance.

## R1 — Executable representation, interfaces and benchmark

### R1-SCHEMA — issue #38

- executable Thought DNA JSON Schema and Python model
- canonical serialization and stable identifiers
- mandatory node/edge semantics, confidence and provenance
- polarity/modality/direction and granularity metadata
- Knowledge DNA fields
- valid/invalid fixtures and versioning

### R1-INTERFACES — issue #46

After schema acceptance, freeze minimal engine boundaries so later implementation can run in parallel:

- extraction result
- index/query candidate result
- verifier result
- scoring/explanation payload
- store/facade interfaces
- version/config identifiers

MCP types are forbidden from these core interfaces.

### R1-BENCHMARK — issue #39

After schema acceptance, implement the frozen benchmark contract:

- calibration and immutable gate packs
- positive, analogy, complementarity and hard-negative families
- E1/generic-motif/two-world cases
- polarity/reversal, partial observation, granularity and extraction-noise cases
- machine-readable gold mappings
- deterministic runner, hashes and non-compensating PASS/FAIL reports

R1-INTERFACES and R1-BENCHMARK can proceed in parallel after R1-SCHEMA.

## R2 — Extraction and canonicalization — issue #40

After R1 interfaces + benchmark acceptance:

- text/context → Thought Graph
- exact source-span provenance and source hashes
- uncertainty, confidence and abstention
- polarity/modality/direction extraction
- repeatability / canonicalization tests
- manual graph input that bypasses LLMs

The matcher must remain usable with manually authored Thought DNA.

## R3 — Fast retrieval — issue #41

In parallel with R2/R4 after the same R1 gates:

- multi-scale D0+D1 landmarks
- typed/directed relational fingerprints
- DF/IDF/commonness filtering
- inverted structural index
- correspondence-consensus voting and seed mappings
- separate content / Knowledge DNA retrieval evidence
- E1 reproduction and scale instrumentation

Retrieval proposes candidates. It does not validate polarity or final resonance.

## R4 — Structural verification — issue #42

In parallel with R2/R3 after the same R1 gates:

- typed multi-relational soft proposal
- partial discrete one-to-one correspondence
- exact directed/typed structural rescore
- hard polarity/causal-direction rejection
- guarded edge-to-path granularity matching
- unseeded restart path
- QAP/RRWM comparison/fallback
- explainable mapping, contradictions and score components

## R5 — Integrated engine gate before MCP — issue #43

R5 starts only after R2, R3 and R4 are ACCEPTED.

Required engine path:

```text
context/manual graph
  -> Thought DNA
  -> validation/canonicalization
  -> index
  -> candidate retrieval
  -> structural verification
  -> scoring
  -> explanation
```

R5 runs the frozen benchmark end-to-end, attributes failures to the correct stage, and issues the explicit **GO / NO-GO for MCP**.

Required demonstrations include:

1. same words / different structure → low or rejected structural resonance
2. different words / analogous structure → recoverable analogical match
3. partial/different-granularity reasoning → recoverable mapping
4. polarity/causal inversion → contradiction, not resonance
5. complementary branches → useful directional result if v0.1 claims the mode

**R6-MCP remains BLOCKED until R5-INTEGRATION is ACCEPTED.**

## R6 — MCP surface — issue #44

MCP is a thin adapter over the accepted engine.

Expected operations:

```text
ingest_thought(context)
index_thought(thought)
find_resonance(thought, mode, k)
compare_thoughts(a, b, mode)
explain_resonance(a, b)
get_thought(id)
```

The core engine must still run with MCP absent. Retrieval, alignment, scoring and extraction logic must not exist only inside MCP handlers.

## R6-E2E — clean-client MCP acceptance — issue #45

A fresh external MCP client must discover the tools and execute the accepted scenarios through MCP only, with mappings, explanations, provenance and version/config metadata.

Acceptance of R6-E2E marks the **first working Resonance MCP milestone**. It is not a claim of production readiness or million-corpus scale.

## After the first MCP milestone

- packaging and reproducibility
- architecture/README updates
- public demo instructions
- clean research + engineering provenance
- known limitations and next falsification targets
- measured scale replay before any corpus-scale claim

## Beyond the first sprint

Potential later directions include privacy-preserving fingerprints, federation between personal agents, human expectation matching, larger knowledge graphs, temporal evolution of Thought Graphs, and consent-based introductions. These are deliberately not allowed to block the first working engine.