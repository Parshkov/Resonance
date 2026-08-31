# Thought DNA v0.1

Status: proposed

Date: 2026-08-31

## Purpose

Thought DNA v0.1 is the smallest source-grounded representation on which the
R0 retrieval, verification, multiscale, knowledge, extraction, and benchmark
contracts can all operate. It is a directed typed property multigraph with
stable node and proposition identity. It is not a universal knowledge graph,
an embedding, a fingerprint record, or a solver-specific matrix.

Normative words `MUST`, `SHOULD`, and `MAY` describe the v0.1 contract.

## Design Decisions

1. The canonical artifact remains source-grounded and is never overwritten by
   coarsening, reification, indexing, or matching.
2. A relation is a uniquely identified binary proposition record, not an
   anonymous adjacency entry. This preserves provenance and permits a derived
   statement-node view.
3. Relations are extracted only between grounded nodes from a small closed
   vocabulary. Higher-order relations are not invented at ingest.
4. Confidence is evidence strength, not truth. Missing or low-confidence data
   becomes unmatched/unknown rather than a contradiction.
5. Human-authored graphs use the same shape and may omit source spans.
6. Knowledge identifiers are optional node annotations. Structural roles do
   not leak into Knowledge DNA.

## Canonical Object

```json
{
  "schema_version": "thought-dna/0.1",
  "thought_id": "local-stable-id",
  "source": {
    "text": "Exact source text",
    "sha256": "lowercase-hex-sha256-of-utf8-text"
  },
  "provenance": {
    "kind": "extracted",
    "extractor": {"id": "extractor-id", "version": "version"}
  },
  "nodes": [],
  "relations": []
}
```

`provenance.kind` is `extracted` or `manual`. For manual input,
`provenance.extractor` MUST be `null` and a non-secret `human_id` MAY be
recorded. Credentials, private prompts, and private human context MUST NOT be
stored.

## Node Contract

Each node MUST contain:

| Field | Type | Rule |
|---|---|---|
| `id` | string | unique and stable within the thought |
| `label` | string | short display label; not structural identity |
| `role` | enum | one of the closed roles below |
| `spans` | array | exact source spans; may be empty only for manual input |
| `extract_conf` | number | `[0,1]`; manual assertions normally use `1.0` |
| `atomic` | boolean | default `true`; `false` only when safe elaboration is asserted |

Closed node roles:

```text
problem | mechanism | state | outcome | constraint |
method | evidence | resource | agent
```

An extracted object that cannot be assigned a role above the configured
confidence threshold is omitted; the extractor does not create an open role.
Future role additions require a schema version change.

A source span has this exact shape:

```json
{"start": 10, "end": 18, "text": "verbatim"}
```

Offsets are zero-based UTF-8-decoded string character offsets with an exclusive
`end`. For every extracted span, `source.text[start:end]` MUST equal `text`.
Overlapping spans are allowed. Span arrays are non-empty for extracted nodes.

Nodes MAY contain:

- `assertion`: `asserted | negated`, default `asserted`;
- `modality`: `actual | possible | conditional`, default `actual`; and
- `knowledge`, as defined below.

## Relation / Proposition Contract

Each relation MUST contain:

| Field | Type | Rule |
|---|---|---|
| `id` | string | unique proposition identity within the thought |
| `source` | node ID | directed source endpoint |
| `target` | node ID | directed target endpoint |
| `type` | enum | one of the closed relation types below |
| `extract_conf` | number | `[0,1]` |
| `spans` | array | grounding for the assertion; may be empty only for manual input |

Closed relation types:

```text
causes | prevents | requires | part_of |
constrains | supports | contradicts
```

`prevents`, `requires`, `supports`, and `contradicts` MUST NOT be normalized to
`causes`. Source and target MUST reference existing nodes. Parallel relations
are permitted and retain distinct IDs.

Relations MAY contain:

- `cue`: one exact source span for an explicit connective;
- `assertion`: `asserted | negated`, default `asserted`;
- `modality`: `actual | possible | conditional`, default `actual`; and
- `provenance_refs`: source-local identifiers when more than one source record
  supports the proposition.

Extracted `prevents` and `contradicts` SHOULD have an explicit cue. An implicit
relation MAY be kept only under a separately calibrated policy and MUST remain
distinguishable in provenance. Relation direction, type, assertion, and
modality participate in compatibility and anti-invariance checks.

## Knowledge DNA

A node MAY contain two independent fields:

```json
{
  "knowledge": {
    "about": [
      {"id": "wd:Q267298", "conf": 0.91, "via": "human"}
    ],
    "requires": [
      {"id": "wd:Q568", "conf": 0.82, "via": "extractor"}
    ]
  }
}
```

- IDs are namespaced: `wd:`, `openalex:`, `acmccs:`, or `local:`.
- `about` denotes the domain concept represented by the node.
- `requires` denotes knowledge needed to understand or solve it.
- Each field is capped at eight references per node.
- References below `conf=0.5` are dropped by the default writer.
- Generic structural roles such as system, process, failure, and degradation
  belong in node roles and relation structure, not `about`.
- Empty/missing arrays mean no knowledge evidence, not negative evidence.

Concept-parent caches, resource lists, papers, experts, and live ontology
queries are not part of Thought DNA. Resources may later attach to concept IDs
in an external layer.

## Extraction Contract

The default extracted path is staged:

```text
anchor exact spans
  -> assign closed node roles
  -> propose closed relations over existing nodes
  -> validate grounding, cues, endpoints, and confidence
  -> optional knowledge linking with abstention
  -> canonical validation
```

One-pass free JSON, free-text predicates, and ungrounded nodes are invalid.
Extraction and manual ingestion produce the same canonical object. No LLM is
called while comparing two stored graphs.

## Derived Views

Derived artifacts MUST identify all input Thought DNA versions and algorithm
versions. They are disposable and MUST NOT replace canonical nodes or
relations.

Allowed derived views include:

- **statement view:** each relation record becomes a statement node with named
  source/target argument links; connected chains may contribute a systematicity
  feature but do not become new asserted source claims;
- **guarded coarse view:** transparent `atomic=false` chain nodes are suppressed
  only under the Invariance Specification, with `realizes_nodes` and
  `realizes_relations` back-pointers;
- **retrieval features:** semantic buckets, embeddings, WL labels, path tokens,
  fingerprints, document frequencies, and posting records; and
- **solver features:** candidate-pair masks, affinity matrices, transport plans,
  and normalized structural costs.

Versioned relation-compatibility and guarded relation-composition tables are
also derived architecture policy. They reference the closed DNA vocabulary but
are not authored independently inside each thought.

None of those fields belongs in the canonical DNA solely because one current
algorithm consumes it.

## Canonicalization and Validation

At minimum, validation MUST check:

1. `schema_version` is known;
2. `thought_id`, node IDs, and relation IDs are unique in their scopes;
3. SHA-256 matches `source.text` when text is present;
4. every extracted span exactly matches the source slice;
5. roles and relation types are closed enum values;
6. every relation endpoint exists;
7. confidence values are finite and in `[0,1]`;
8. extracted nodes and relations have grounding;
9. concept references are namespaced, capped, and above policy threshold; and
10. list ordering has no semantic effect.

Canonical JSON serialization for hashing sorts object keys and sorts nodes and
relations by `id`; span order is `(start,end,text)`. Canonicalization must not
rewrite labels, merge nodes, or infer relations.

## Explicit Non-Goals

Thought DNA v0.1 does not include:

- a universal ontology or global concept graph;
- whole-thought embeddings or learned graph encoders;
- fingerprints, posting-list keys, WL colors, or solver costs;
- resources, books, courses, datasets, patents, or experts on thought nodes;
- open relation phrases;
- inferred nested `CAUSE[R1,R2]` as source truth; or
- a promise that two extraction runs are byte-identical.

## Conditions for v0.2

Reconsider the schema only with recorded benchmark evidence. Likely triggers
are: grounded n-ary or relation-as-argument claims that cannot compile from
binary propositions; stable explicit goal extraction; a proven new relation
type; or repeated verifier failures caused by information absent from v0.1.

## Related Decisions

- [Invariance Specification](INVARIANCE_SPECIFICATION_v0.1.md)
- [Retrieval ADR](decisions/ADR-0002-retrieval-candidate-generation.md)
- [Verification ADR](decisions/ADR-0003-structural-verification.md)
- [Scoring Contract](RESONANCE_SCORING_v0.1.md)
- [R0 Synthesis](../research/reviews/R0_SYNTHESIS_parshkov-openai-gpt5-codex-s7d3.md)
