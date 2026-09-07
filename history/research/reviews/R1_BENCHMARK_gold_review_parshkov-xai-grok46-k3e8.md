---
mission: R1-BENCHMARK
run: R1-BENCHMARK-GOLD-REVIEW
review_type: independent public gold review
contributor: Parshkov
agent_id: parshkov-xai-grok46-k3e8
agent_or_model: Grok 4.6 (Grok Build TUI; exact mode not exposed)
date: 2026-08-31
mission_modified: false
web_research_used: false
code_execution_used: true
blind_constraints_preserved: not-applicable
notes: >
  Not a canonical CLAIM on R1-BENCHMARK (already ACCEPTED, PR #51).
  Fills the freeze-policy independent-review slot that kept
  gate_execution_ready false. Did not author the fixtures.
conflict_of_interest: >
  Same human sponsor as the fixture author (Parshkov). Different agent_id
  and model family (xAI Grok 4.6 vs OpenAI GPT-5 Codex). Author identity
  parshkov-openai-gpt5-codex-s7d3 did not write the approval ledger.
---

# Scope

Independent public review of the authored Benchmark v0.1 gold, as required by
`benchmark/r0-v0.1/README.md` and the maintainer acceptance note on issue #39.

The fixture author cannot self-approve. This run inspects the generator and
the 64 manual-review pair cases plus 16 extraction-reference observations,
corrects one suite-level construction defect, and records approvals in
`benchmark/r0-v0.1/review_approvals.json`.

It does not claim R1-INTERFACES or start R2/R3/R4.

# Inputs Reviewed

| Artifact | Role |
|---|---|
| `benchmark/r0-v0.1/build_fixtures.py` | reviewable source of gold |
| `benchmark/r0-v0.1/pairs.jsonl` / `graphs.jsonl` / `extraction_runs.jsonl` | generated corpus |
| `benchmark/R0_BENCHMARK_v0.1.md` | family contracts |
| `docs/THOUGHT_DNA_v0.1.md` | closed roles/relations |
| Issue #39 maintainer acceptance | independent gold review is mandatory before `gate_execution_ready` |

# Method

1. Read the generator, not only the JSONL.
2. Empirically compared family graphs (label/relation equality, mappings, subtypes).
3. Checked analogical identity mappings against the shared directed skeleton.
4. Checked negatives for a real anti-invariant rather than a relabel.
5. Checked complementary cases for an explicit `requires → about` bridge.
6. Regenerated the corpus after the family-2 correction and the approval ledger.

# Material findings

## F1. Vocabulary substitution was a copy of the analogical graph (blocking, corrected)

For every pack, family 2 (`vocabulary_substitution`, gold `approximate`) and
family 9 (`cross_domain_analogy`, gold `analogical`) used the same
`analogy_labels` and the same relation skeleton. The two SOW positives were
therefore the same graph under two names.

That violates Benchmark v0.1: family 2 is vocabulary substitution (invariance
B); family 9 is disjoint-domain analogy (invariance H). It would have made
the two SOW comparisons duplicates.

**Correction applied in the generator:** family 2 now uses a same-domain
lexical substitute list (`VOCAB_SUB[query_domain]`). Family 9 still uses the
disjoint analogy domain. Structure is unchanged. A regression test forbids
label equality between the two families.

This is a gold-construction fix before freeze completion, not a silent
relabel to make an engine pass.

## F2. Analogical gold is template-isomorphic (approved with limit)

Family 9 candidates are the query skeleton with swapped domain labels and an
identity node/edge map. That is a valid analogical fixture: disjoint words,
preserved directed typed system. It is not independently drawn human analogy.
The mapping is reviewable because it is the generator's explicit correspondence
order.

Battery `n0` problem "high cell heat" ↔ software "request burst", `n4` method
prevents `n5` outcome, and the rest of the ten-edge skeleton match. Approved.

## F3. Same-domain structural match is paraphrase-adjacent (approved with limit)

Family 6 only prefixes query labels with `variant`. It is an isomorphic
same-domain positive, not a separately authored variant. Still a legal
direct-class identity mapping. Approved.

## F4. Intent / global-conflict / generic negatives are usable (approved with limits)

- Family 11 flips the governing intervention `n4 → n5` from `prevents` to
  `causes` and retargets the constraint edge. Same words, opposite intent.
- Family 12 reverses the main outcome edge `n2 ↔ n5` and also flips `n4 → n5`
  to `causes`. Local `n0 → n1 → n2` survives. This is a 2-edge global
  conflict, not a higher-order reification test.
- Family 13 uses generic role labels and edits two relations. It is a
  generic-label hard negative, not H's identical path-bag collision.
- Family 14 keeps query labels and rewires endpoints. This is the cleanest
  same-words/wrong-structure sibling outside family 10.

All four remain gold_class `negative` with empty correspondences. Approved.

## F5. Complementary bridges are explicit (approved)

Family 15 bridges query `n5.requires` to candidate `n0.about` on
`local:{pack}:continuation`. Family 16 bridges query `n4.requires` to
candidate `n0.about` on `local:{pack}:method-input`. No fake isomorphism.
Approved.

## F6. Extraction pair is tautological (approved with limit)

The two extraction observations per pack share the same source text, spans,
roles, and relations; only extractor version strings differ. Duplicate-extract
F1 on this pair is 1.0 by construction. It is a valid exact-span reference
floor, not a realistic extraction-noise measurement. Family 8 remains the
noise model. Approved as reference observations.

## F7. Family 10 anti-invariance allocation is correct (generated, checked)

Gate packs: two polarity flips (G01, G02), two direction reversals (G03, G04),
two broader rewires (G05, G06). Calibration uses rewires. Not in the manual
ledger; verified against the contract.

# Approvals

Reviewer: `parshkov-xai-grok46-k3e8`

- 64/64 required pair cases approved
- 16/16 extraction-reference observations approved
- freeze_state → `independent_review_complete`
- `gate_execution_ready` → true after regenerate

# Residual limits (do not overclaim)

1. Analogies and same-domain variants are template copies, not independently
   authored thoughts.
2. Duplicate-extract self-match is currently tautological.
3. Family 13 is not a full E1/H motif-collision replica.
4. Family 12 does not test relation-as-argument / higher-order binding.
5. Same human sponsor as the author; a later reviewer from another sponsor
   may still challenge individual mappings.

# Recommended architecture consequence

Keep r0-v0.1. Do not treat this review as a production-solver or million-corpus
claim. R3 must still emit real E1/scale measurements. R2 should not treat the
extraction references as a noisy self-match dataset.

# Confidence

**HIGH** that family 2/9 were identical and that the analogical identity map
matches the shared skeleton.

**MEDIUM** on the analogical *content* of the eight domain pairs: they are
role-aligned by construction, not independently judged as the best possible
battery↔software analogy.

**LOW** that two extraction runs of real text would reproduce these graphs.
