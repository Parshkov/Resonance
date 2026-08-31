# Invariance Specification v0.1

Status: proposed

Date: 2026-08-31

## Purpose

This specification states what Resonance v0.1 may ignore, what it may tolerate
with degradation, and what it must treat as a meaning-changing difference. It
is a behavioral contract for extraction, retrieval, verification, and the
benchmark; it is not a claim that one hash or one score provides every
invariance.

## Terms

- **Invariant:** the transformation alone must not change the expected class,
  and the transformed candidate must remain ahead of its paired lexical hard
  negative.
- **Tolerant:** the score or mapping may degrade, but the candidate remains
  retrievable/verifiable within the stated family gate.
- **Conditional:** supported only when an explicit guard is satisfied.
- **Unsupported:** v0.1 makes no recall promise.
- **Anti-invariant:** the system must preserve and penalize the difference.

Invariance is evaluated on the canonical Thought DNA and its deterministic,
versioned derived views. It never licenses mutation of the canonical graph.

## Contract Matrix

| ID | Transformation | Extract | Retrieve | Verify | v0.1 level | Required mechanism |
|---|---|---|---|---|---|---|
| A | paraphrase | tolerant | content: invariant; structural: tolerant | tolerant | tolerant end-to-end | span grounding, normalized roles, optional concepts, typed structure |
| B | vocabulary substitution | tolerant | semantic: tolerant; structural shadow: target invariant | tolerant | tolerant | role/relation channel independent of label text |
| C | serialized node/edge order | invariant | invariant | invariant | invariant | canonical serialization and set/graph operations |
| D | irrelevant branch insertion | extra grounded branch allowed | tolerant | tolerant | tolerant | local features, partial mapping, unmatched branch, containment normalization |
| E | partial observation / missing nodes | must abstain, never fill | tolerant | tolerant | tolerant | partial candidate evidence and explicit unmatched nodes |
| F | different granularity | may differ | unsupported by default | conditional | conditional only | guarded suppression and bounded edge-to-path mapping |
| G | different graph sizes | expected | tolerant | invariant to padding/order, tolerant to content | tolerant | rectangular partial assignment and coverage reporting |
| H | domain substitution with preserved relations | no special action | unsupported by default content path; structural shadow target | tolerant | verification-only promise | functional roles and typed relation consistency |
| I | modest extraction mistakes | exposed by confidence/provenance | tolerant only after self-match gate | tolerant | tolerant, gated | confidence, abstention, partial mapping, duplicate-extract tests |

## Stage Responsibilities

### Extraction

Extraction is responsible for exact source offsets, closed role/relation values,
direction, assertion/modality when explicit, confidence, and abstention. It is
not responsible for analogizing two domains. Two extraction runs of the same
text need not serialize identical graphs, but their aligned structure must pass
the self-match gate in Benchmark v0.1.

### Retrieval

The default content/knowledge path supports paraphrase, same-domain, and
complementary recall. It does not promise domain-substitution invariance.
Structural fingerprints are a shadow channel until promoted by the Retrieval
ADR gates. Scores from semantic, knowledge, and structural channels remain
separate.

### Verification

Verification is the only v0.1 stage required to judge a supplied cross-domain
pair structurally. It accepts unequal graphs, returns a partial injective
mapping, and lists unmatched items and contradictions. It may use a guarded
derived coarse view, but every shortcut must expand to canonical relation IDs.

## Conditional Granularity Rule

`A -> B` may correspond to `A -> X -> ... -> B` only when every intermediate
node satisfies all of these conditions:

1. exactly one supported incoming and one supported outgoing edge in the active
   relation layer;
2. `atomic=false` was explicitly recorded;
3. it is not a branch, merge, goal/outcome, constraint, evidence, negation,
   modal boundary, temporal boundary, or provenance anchor;
4. relation types, assertion, polarity, and modality compose through a
   versioned allow-list; and
5. the derived shortcut records all realized node/relation IDs and minimum
   confidence.

Unknown relation compositions do not contract. A single false contraction in a
gate case fails the granularity component.

Relation matching uses a separate closed, versioned compatibility matrix.
Identity is `1`; explicitly licensed near-types may be in `(0,1)`; unknown,
opposite-polarity, reversed, or incompatible entries are `0`. The matrix is an
architecture/scoring artifact, not mutable per solver and not a Thought DNA
field. The guarded relation-composition table is stricter and remains a
different artifact.

## Anti-Invariances

The following transformations must not be normalized away:

- reversing a directed relation;
- changing `causes` to `prevents`, or asserted to negated;
- changing causal/mechanistic support to evidential `supports`;
- changing `requires` to `causes`;
- changing a goal/intent while retaining topic words;
- inserting an independently meaningful mediator, constraint, branch, or
  alternative mechanism;
- mapping a locally similar chain when the connected global system conflicts;
- treating extraction hallucination as additional evidence.

## Benchmark Mapping

| Contract | Benchmark family / metric | Mandatory outcome |
|---|---|---|
| A | paraphrase | positive-family Recall@5 ≥ 4/6 |
| B | vocabulary substitution; SOW | Recall@5 ≥ 4/6 and total SOW ≥ 10/12 |
| C | serialization permutation | identical score vector and mapping set after ID normalization |
| D | irrelevant branch | Recall@5 ≥ 4/6; unmatched branch present |
| E | partial graph | Recall@5 ≥ 4/6; surviving-pair F1 reported |
| F | transparent and meaningful subdivision | transparent recall target; zero meaningful-node contractions |
| G | size variation | no forced dummy match in explanation |
| H | cross-domain analogy | oracle-pair verifier ranks positive over lexical negative; retrieval reported separately |
| I | extraction error and duplicate extraction | self-match and error-family results reported; no silent fill |
| anti-invariance | reversal, polarity, intent, global conflict | each negative family has at most 1/6 false positives |

Passing a macro average cannot compensate for failing an anti-invariance or
serialization check.

## Versioning

Any change to the node-role vocabulary, relation vocabulary, relation
compatibility/composition table, contraction guards, or score semantics creates
a new invariance-spec version and requires replay of immutable prior benchmark
versions. Tuning a threshold alone is recorded in a candidate configuration,
not by rewriting this specification.

## Related Research

This specification reconciles R0-A through R0-H as documented in
[R0 Synthesis](../research/reviews/R0_SYNTHESIS_parshkov-openai-gpt5-codex-s7d3.md).
