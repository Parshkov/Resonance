---
mission: R0-F
run: F2
contributor: Parshkov
agent_id: parshkov-openai-gpt5-codex-f682
agent_or_model: GPT-5-based Codex (exact deployed model/version not exposed to this run)
date: 2026-08-31
mission_modified: false
web_research_used: true
blind_constraints_preserved: not-applicable
code_execution_used: true
additional_agents_used: false
notes: Independent repeat after a later canonical CLAIM lost the GitHub timestamp race and was relabeled with REPEAT_CLAIM. The parallel canonical R0-F result was not inspected before this report was finalized.
---

# Decision

**QUALIFIED GO** for a staged, precision-first extraction contract: freeze and address the source; extract atomic, quoted units; classify them with a deliberately small vocabulary; extract only explicitly grounded relations; validate deterministically; then normalize without deleting provenance. The accepted graph must contain no node or edge that cannot point to an exact source span, except manually authored items carrying an explicit attestation. Keep low-confidence or implicit interpretations in a separate `proposed` channel that the matcher ignores by default. One-pass “produce a canonical Thought Graph” extraction is a NO-GO for v0.1.

# Confidence

**MEDIUM.** Shallow predicate/argument units, explicit stance cues, and span-backed relations are established annotation targets, and the contract is directly testable. The uncertainty is empirical: no Resonance corpus yet measures which roles and relations remain stable across people, domains, languages, and extractor models. Schema-conforming JSON proves syntax, not semantic faithfulness; all acceptance thresholds below are hypotheses until calibrated on adjudicated examples.

# Best Algorithm / Method

Use six stages, with immutable inputs and versioned outputs:

1. **Source registration:** normalize to Unicode NFC once; store an access-controlled `source_id`, SHA-256, language/media type, and Unicode-code-point offset convention. A hash is integrity metadata, not a privacy mechanism.
2. **Anchor extraction:** split into sentence-sized windows, then extract atomic verbatim spans. Every candidate carries `{source_id,start,end,exact}`; deterministic code verifies `source[start:end] == exact`.
3. **Shallow typing:** produce only `kind = concept | proposition`. Add a non-exclusive role overlay `goal | constraint | observation | hypothesis | method | question | unspecified`. This avoids pretending that one ontological partition is reliable.
4. **Explicit relation extraction:** allow `causes`, `prerequisite_for`, `supports`, `contradicts`, `part_of`, `addresses`, and `constrains`. Directions are fixed: cause to effect, prerequisite to dependent, evidence to claim, part to whole, method to problem/goal, constraint to constrained unit. `contradicts` is symmetric. Goal and constraint remain node roles, not overloaded edge names.
5. **Validation and selective acceptance:** reject malformed anchors/endpoints/enums; place implicit causal links, unresolved coreference, and unsupported normalization in `proposed`. Record model score separately from a nullable calibrated probability. Never interpret raw model confidence as correctness probability.
6. **Normalization:** normalize case/whitespace and propose a short `canonical_label`, but retain exact quotes and alternatives. Deduplicate only with explicit evidence (overlapping anchors or a reviewed equivalence). Canonical JSON serialization may hash an artifact; it must not create a cross-document semantic identity.

The extraction contract is JSON Schema Draft 2020-12 plus application invariants that JSON Schema alone cannot conveniently express. Required root objects are:

| Object | Required information |
|---|---|
| `source` | mode, stable reference, SHA-256 when text-backed, language/media type, normalization, offset unit; raw text may remain private |
| `producer` | `llm`, `human`, or deterministic parser; model/tool identifier, contract version, run ID |
| `nodes[]` | local ID, kind, role, canonical label, source stance, anchors, assessment |
| `edges[]` | local ID, type, endpoints, directed flag, anchors, assessment |
| `assessment` | `accepted | proposed | rejected`, raw score, nullable calibrated probability, policy version/basis |
| `attestation` | required for manual mode when span anchors are absent |

Application invariants: IDs are unique; endpoints exist; offsets reproduce `exact`; extracted `accepted` items have at least one valid anchor; manual unanchored items reference the root attestation; `contradicts` is canonicalized as an unordered pair; all other edges follow their declared direction; and failed items never enter the accepted graph.

What is reliable enough to test for acceptance: verbatim spans, explicit negation/questions/desires, shallow proposition boundaries, and relations with overt cues. What is not trusted in v0.1: implicit intent, unstated causality, long-range coreference, sarcasm, deep AMR-like scope, one-to-many granularity reconciliation, analogy/complementarity, or universal concept IDs.

# Why It Fits Resonance

The matcher receives controlled roles and relation types while remaining independent of the extracting model. Exact anchors make every match auditable back to private source context without publishing that context. Separate source stance (`asserted`, `possible`, `desired`, `conditional`, `questioned`, `negated`) prevents “the author wants X” from collapsing into “X is true”; separate extraction confidence prevents source uncertainty from being confused with parser uncertainty. Approximate canonicality comes from stable enums, direction conventions, shallow labels, and deterministic validation—not from demanding byte-identical graphs from paraphrases.

A manually authored graph uses the same contract and validator with `producer.kind = human`. It requires an attestation instead of fabricated spans and bypasses every LLM stage. This keeps the comparison engine extractor-agnostic.

# Required Thought DNA

The extraction layer can plausibly supply, without globally freezing Thought DNA:

- local node/edge IDs;
- node `kind`, optional role, canonical label, and source stance;
- typed edge, endpoint IDs, and direction/symmetry;
- exact source anchors for extracted items;
- extraction decision, raw score, optional calibrated probability, and policy version;
- source integrity/reference metadata and producer/run metadata;
- manual attestation when no source span exists.

It cannot safely supply stable global concept identity, true causal validity, social/person attributes, inferred complementarity, or a final granularity hierarchy.

# Required Graph Representation

A directed typed property multigraph, with symmetric `contradicts` canonicalized consistently and parallel edges permitted when separately grounded. Nodes are locally identified concepts/propositions; roles are properties rather than incompatible subclasses. If later Thought DNA needs relations about relations, reify the target relation explicitly; this extraction contract does not silently invent edge-to-edge semantics.

# Invariances

| Transformation | Supported | Partially | Not Supported | Mechanism |
|---|:---:|:---:|:---:|---|
| A. paraphrase | | X | | controlled roles/types and normalized labels; anchors necessarily differ |
| B. vocabulary substitution | | X | | canonical labels may converge, but no forced global ID |
| C. node ordering | X | | | arrays are sorted by anchor/ID after extraction |
| D. irrelevant branches | X | | | each unit is independently grounded; downstream matcher may ignore it |
| E. partial observation/missing nodes | | X | | abstention preserves precision but lowers coverage |
| F. different granularity | | | X | atomic splitting is versioned but not semantically invariant |
| G. different graph sizes | X | | | contract has no fixed counts |
| H. domain substitution, structure preserved | | X | | relation/role enums transfer; canonical concepts may not |
| I. modest extraction mistakes | | X | | proposed/rejected channels, confidence, provenance, reruns |

# Retrieval vs Verification

This method belongs **before both retrieval and verification**. It produces the canonical-enough input graph; it performs no cross-thought matching. Only `accepted` items are indexed by default. `proposed` items may be surfaced for human correction or an explicit sensitivity analysis, never silently mixed into the core graph.

# Computational Cost

For `T` input tokens, `n<=100` nodes, and `e` candidate relations, staged LLM work is linear in processed tokens plus generated candidates; chunk overlap adds a controlled constant. Deterministic validation is `O(T+n+e)`. Naive within-document deduplication is `O(n^2)`—10,000 comparisons at 100 nodes—and is acceptable offline. JSON Schema validation is negligible relative to model inference.

Plan on two required model stages (anchors; types/relations) and one optional normalization/verification stage, rather than one large prompt. Batch independent source windows, but reconcile boundary duplicates deterministically. Manual input performs zero model calls. At a million thoughts, extraction is an asynchronous ingestion cost; no LLM call occurs during candidate retrieval or graph comparison.

# Existing Implementations

- **`jsonschema` 4.26:** mature Python support for Draft 2020-12. Use it for structural validation, then custom checks for offsets, endpoints, and conditional manual provenance.
- **Pydantic 2.x:** useful strict Python models and generated JSON Schema; risk is accidental coercion unless strict mode is enabled.
- **spaCy Sentencizer:** lightweight deterministic sentence boundaries without a statistical parser; customize abbreviations/languages and do not mistake segmentation for semantic extraction.
- **Provider constrained/structured output:** useful for syntactically valid enums/objects, but provider-specific subsets and semantic errors require application validation.
- **RFC 8785 implementations:** deterministic JSON serialization for artifact hashes/signatures. This canonicalizes bytes, not meaning.

No off-the-shelf library supplies a trustworthy Resonance Thought Graph. PropBank/AMR resources inform the contract but are not drop-in extractors for goals, constraints, and reasoning relations.

# Minimal Pseudocode

```text
extract(source, producer, contract):
    registered = freeze_source(source, normalization="NFC", offsets="code_point")
    windows = deterministic_segment(registered)

    candidates = llm_extract_verbatim_atomic_spans(windows, contract.anchor_schema)
    candidates = [c for c in candidates if exact_span_matches(c, registered)]

    typed_nodes = llm_classify_nodes(candidates, contract.node_enums)
    candidate_edges = llm_extract_explicit_edges(typed_nodes, windows,
                                                  contract.edge_enums)

    graph = schema_validate(typed_nodes, candidate_edges)
    graph = application_validate_ids_offsets_endpoints(graph, registered)
    graph = route_implicit_or_uncertain_to_proposed(graph)
    graph = normalize_labels_without_merging_provenance(graph)
    graph = calibrate_if_calibration_set_exists(graph)
    return canonical_json_order(graph), validation_report(graph)

accept(item):
    return valid_schema(item) and valid_provenance(item) and
           item.decision == "accepted" and passes_versioned_policy(item)
```

# Toy Experiment

In under two hours, manually annotate 24 short contexts: eight planning, eight causal/mechanistic, and eight argument/evidence examples. Include negation, conditional language, repeated concepts, and adversarial prompts containing plausible but unstated relations. Create one paraphrase of each. Run the staged extractor twice on originals and once on paraphrases.

Measure anchored-node precision/recall, role macro-F1, labeled-edge precision/recall (correct endpoints, type, direction, and evidence), accepted hallucination rate, Brier/ECE when calibrated probabilities exist, risk versus accepted coverage, and repeat/paraphrase graph agreement after optimal local-node alignment. Falsify this contract if accepted node precision is below 0.95, accepted edge precision below 0.90, any accepted item lacks mechanically valid provenance, accepted hallucinated-edge rate exceeds 0.01, or repeated-run relation Jaccard is below 0.80. Low recall is permitted initially but must be reported as coverage, not hidden.

# Failure Modes

1. Exact quotes are real but do not entail the normalized label or edge.
2. Cross-sentence coreference maps “it/that claim” to the wrong node.
3. A desired or hypothetical outcome is extracted as an asserted fact.
4. Long sentences split into inconsistent atomic units across reruns.
5. A fixed relation list pressures the model to choose a plausible but unsupported edge.
6. Character offsets drift after Unicode or newline normalization.
7. High raw model confidence is mistaken for calibrated probability.
8. Deduplication merges two similar but intentionally distinct claims.
9. Quoted provenance leaks private source text when artifacts are exported.
10. Manual authors use attestations to encode unsupported claims; provenance shows responsibility but does not prove truth.

# What NOT To Build

- Do not ask for a full canonical graph in one prompt.
- Do not adopt full AMR, unrestricted OpenIE predicates, or deep discourse/coreference as v0.1 Thought DNA.
- Do not accept an inferred edge merely because a second LLM agrees.
- Do not use self-reported confidence as a probability without held-out calibration.
- Do not publish raw private source text merely to preserve provenance; keep references access-controlled.
- Do not assign cross-document semantic IDs from generated labels or hashes.
- Do not let the extraction LLM compare people/thoughts; its output ends at the validated graph.

# Architecture Consequences

- Version the extraction contract, prompt, enums, and acceptance policy independently.
- Preserve immutable source addressing and exact anchors internally.
- Start with two node kinds plus a role overlay, not a deep ontology.
- Preserve distinct causal, prerequisite, evidential, contradiction, hierarchy, goal, and constraint semantics.
- Separate source stance from extraction uncertainty.
- Keep accepted, proposed, and rejected channels distinct.
- Require deterministic schema, offset, ID, and endpoint validation.
- Make manual graphs first-class inputs through attestation.
- Benchmark precision, coverage, calibration, and repeat stability before adding fields.
- Do not treat this extraction contract as final Thought DNA.

# Sources

1. [Palmer, Gildea & Kingsbury, “The Proposition Bank” (2005)](https://aclanthology.org/J05-1004/) — demonstrates a practical shallow predicate/argument layer and explicitly leaves higher-order phenomena such as coreference outside scope.
2. [Banarescu et al., “Abstract Meaning Representation for Sembanking” (2013)](https://aclanthology.org/W13-2322/) — useful upper-bound reference for richer semantic graphs; its breadth motivates not requiring AMR-level analysis in v0.1.
3. [W3C Web Annotation Data Model](https://www.w3.org/TR/annotation-model/) — authoritative text-position and text-quote selector model for durable source grounding.
4. [JSON Schema Draft 2020-12](https://json-schema.org/draft/2020-12) — portable structural contract and validation vocabulary.
5. [Guo et al., “On Calibration of Modern Neural Networks” (ICML 2017)](https://proceedings.mlr.press/v70/guo17a.html) — evidence that raw neural confidence is not automatically calibrated and that post-hoc calibration must be measured.
6. [Geifman & El-Yaniv, “Selective Classification for Deep Neural Networks” (NeurIPS 2017)](https://papers.neurips.cc/paper_files/paper/2017/hash/4a8423d5e91fda00bb7e46540e2b0cf1-Abstract.html) — basis for explicit abstention and reporting risk against coverage.
7. [Josifoski et al., “GenRES” (NAACL 2024)](https://aclanthology.org/2024.naacl-long.155/) — shows that generative relation-extraction evaluation needs more than naive precision/recall and that fixed relation/entity prompts can induce hallucinations.
8. [RFC 8785, JSON Canonicalization Scheme](https://www.rfc-editor.org/rfc/rfc8785.html) — deterministic artifact serialization for repeatable hashes, clearly separate from semantic canonicalization.
9. [`jsonschema` documentation](https://python-jsonschema.readthedocs.io/en/stable/) — maintained Python implementation with Draft 2020-12 support.
10. [spaCy Sentencizer documentation](https://spacy.io/api/sentencizer) — immediate deterministic segmentation primitive and its limits.

## Example 1 — span-grounded LLM extraction

```json
{
  "contract_version": "r0-f2-extraction-0.1",
  "graph_id": "tg-demo-battery-01",
  "source": {
    "mode": "text",
    "source_id": "private:demo/battery/01",
    "sha256": "d9f2418a948a1167fbb8de310618f689aa5c880075e4add8db732d2ec05a9e2e",
    "media_type": "text/plain",
    "language": "en",
    "normalization": "NFC",
    "offset_unit": "unicode_code_point",
    "text": "We need to reduce battery failures. Heat buildup degrades cells. Logs show temperature rises before capacity drops; this supports the heat-degradation claim. Adding cooling addresses the failure goal, but cooling must keep total pack weight below 2 kg."
  },
  "producer": {
    "kind": "llm",
    "id": "example-extractor",
    "contract_version": "r0-f2-extraction-0.1",
    "run_id": "demo-run-01"
  },
  "nodes": [
    {
      "id": "n1", "kind": "proposition", "role": "goal",
      "canonical_label": "reduce battery failures", "source_stance": "desired",
      "anchors": [{"source_id": "private:demo/battery/01", "start": 11, "end": 34, "exact": "reduce battery failures"}],
      "assessment": {"decision": "accepted", "raw_score": 0.98, "calibrated_probability": null, "policy": "precision-v0"}
    },
    {
      "id": "n2", "kind": "proposition", "role": "hypothesis",
      "canonical_label": "heat buildup degrades cells", "source_stance": "asserted",
      "anchors": [{"source_id": "private:demo/battery/01", "start": 36, "end": 63, "exact": "Heat buildup degrades cells"}],
      "assessment": {"decision": "accepted", "raw_score": 0.95, "calibrated_probability": null, "policy": "precision-v0"}
    },
    {
      "id": "n3", "kind": "proposition", "role": "observation",
      "canonical_label": "temperature rises before capacity drops", "source_stance": "asserted",
      "anchors": [{"source_id": "private:demo/battery/01", "start": 65, "end": 114, "exact": "Logs show temperature rises before capacity drops"}],
      "assessment": {"decision": "accepted", "raw_score": 0.97, "calibrated_probability": null, "policy": "precision-v0"}
    },
    {
      "id": "n4", "kind": "proposition", "role": "method",
      "canonical_label": "add cooling", "source_stance": "asserted",
      "anchors": [{"source_id": "private:demo/battery/01", "start": 158, "end": 172, "exact": "Adding cooling"}],
      "assessment": {"decision": "accepted", "raw_score": 0.96, "calibrated_probability": null, "policy": "precision-v0"}
    },
    {
      "id": "n5", "kind": "proposition", "role": "constraint",
      "canonical_label": "pack weight below 2 kg", "source_stance": "asserted",
      "anchors": [{"source_id": "private:demo/battery/01", "start": 205, "end": 251, "exact": "cooling must keep total pack weight below 2 kg"}],
      "assessment": {"decision": "accepted", "raw_score": 0.97, "calibrated_probability": null, "policy": "precision-v0"}
    }
  ],
  "edges": [
    {
      "id": "e1", "type": "supports", "source": "n3", "target": "n2", "directed": true,
      "anchors": [{"source_id": "private:demo/battery/01", "start": 116, "end": 156, "exact": "this supports the heat-degradation claim"}],
      "assessment": {"decision": "accepted", "raw_score": 0.94, "calibrated_probability": null, "policy": "precision-v0"}
    },
    {
      "id": "e2", "type": "addresses", "source": "n4", "target": "n1", "directed": true,
      "anchors": [{"source_id": "private:demo/battery/01", "start": 173, "end": 199, "exact": "addresses the failure goal"}],
      "assessment": {"decision": "accepted", "raw_score": 0.96, "calibrated_probability": null, "policy": "precision-v0"}
    },
    {
      "id": "e3", "type": "constrains", "source": "n5", "target": "n4", "directed": true,
      "anchors": [{"source_id": "private:demo/battery/01", "start": 201, "end": 251, "exact": "but cooling must keep total pack weight below 2 kg"}],
      "assessment": {"decision": "proposed", "raw_score": 0.78, "calibrated_probability": null, "policy": "precision-v0"}
    }
  ]
}
```

## Example 2 — manual bypass with attestation

```json
{
  "contract_version": "r0-f2-extraction-0.1",
  "graph_id": "tg-manual-org-01",
  "source": {
    "mode": "manual",
    "source_id": "manual:org-analogy-01",
    "sha256": null,
    "media_type": "application/vnd.resonance.manual+json",
    "language": "en",
    "normalization": "NFC",
    "offset_unit": "unicode_code_point"
  },
  "producer": {
    "kind": "human",
    "id": "manual-author",
    "contract_version": "r0-f2-extraction-0.1",
    "run_id": "manual-run-01"
  },
  "attestation": {
    "id": "attestation-01",
    "author": "manual-author",
    "created_at": "2026-08-31T00:00:00Z"
  },
  "nodes": [
    {
      "id": "m1", "kind": "concept", "role": "unspecified",
      "canonical_label": "information backlog", "source_stance": "asserted", "anchors": [],
      "assessment": {"decision": "accepted", "raw_score": null, "calibrated_probability": null, "policy": "manual-attestation-v0", "attestation_id": "attestation-01"}
    },
    {
      "id": "m2", "kind": "concept", "role": "unspecified",
      "canonical_label": "coordination delay", "source_stance": "asserted", "anchors": [],
      "assessment": {"decision": "accepted", "raw_score": null, "calibrated_probability": null, "policy": "manual-attestation-v0", "attestation_id": "attestation-01"}
    },
    {
      "id": "m3", "kind": "concept", "role": "unspecified",
      "canonical_label": "project failure", "source_stance": "asserted", "anchors": [],
      "assessment": {"decision": "accepted", "raw_score": null, "calibrated_probability": null, "policy": "manual-attestation-v0", "attestation_id": "attestation-01"}
    }
  ],
  "edges": [
    {
      "id": "me1", "type": "causes", "source": "m1", "target": "m2", "directed": true, "anchors": [],
      "assessment": {"decision": "accepted", "raw_score": null, "calibrated_probability": null, "policy": "manual-attestation-v0", "attestation_id": "attestation-01"}
    },
    {
      "id": "me2", "type": "causes", "source": "m2", "target": "m3", "directed": true, "anchors": [],
      "assessment": {"decision": "accepted", "raw_score": null, "calibrated_probability": null, "policy": "manual-attestation-v0", "attestation_id": "attestation-01"}
    }
  ]
}
```

**Conclusion: QUALIFIED GO** for staged grounded extraction with selective abstention and manual bypass; **NO-GO** for one-pass canonical graph generation or ungrounded inferred relations.
