# Benchmark v0.2 — multi-skeleton, multi-domain, hard negatives

v0.1 (`../r0-v0.1`) instantiates **one** 10-node template with eight label sets, so
every "cross-domain analogy" is a relabelling of the query and every structural
metric is a tautology (see `src/engine/reports/r0-v0.2-baseline-engine-0.1.json`
for what the v0.1 engine scores on this corpus: Recall@5 = 0.08, template
coincidences accepted as analogies 4/4).

v0.2 fixes the instrument:

| property | v0.1 | v0.2 |
|---|---|---|
| distinct skeletons (topologies) | 1 | 8 (5–7 nodes, chains, cycles, forks, requires/supports/contradicts) |
| domain instantiations per skeleton | 8 label tuples | 4 hand-authored domains with different vocabulary |
| cross-domain analogy | relabelling | different domain, concept-aligned per slot (`skeletons.py`) |
| template coincidence negative | absent | same skeleton, labels with no abstract concept |
| polarity flip negative | subtype of family 10 | own family, `causes -> prevents` on the first causal edge |
| partial cross-domain analogy | absent | one slot dropped + irrelevant branch |
| tuning / test separation | same template both splits | S1–S4 calibration, S5–S8 gate (different skeletons) |
| corpus size for retrieval | 136 | 176 |

Families (18): paraphrase, vocabulary_substitution, irrelevant_branch, partial_graph,
transparent_granularity, same_domain_structural_match, serialization_permutation,
modest_extraction_error, cross_domain_analogy, cross_domain_analogy_partial,
same_vocabulary_wrong_structure, polarity_flip, template_coincidence,
generic_motif_distractor, same_topic_different_intent, accidental_semantic_similarity,
branch_continuation, method_knowledge_bridge.

Gold classes are **structural**: `direct` = complete isomorphism in the same domain
(paraphrase, vocabulary substitution, permutation, same-domain variant);
`approximate` = partial/perturbed structure; `analogical` = different domain with
concept-aligned slots; `complementary` = knowledge bridge; `negative` otherwise.

## Reproduce

```bash
python3 benchmark/r0-v0.2/build_fixtures.py          # regenerates graphs/pairs/manifest
python3 benchmark/r0-v0.2/runner.py                  # evaluates the current engine, exit 1 on gate failure
python3 benchmark/r0-v0.2/runner.py --rows           # per-family detail
```

## Provenance and limits

Skeletons, labels and gold were authored by the agent `parshkov-anthropic-fable51-uutj4x`
(Claude Fable 5.1) and checked mechanically against the lexicon
(`src/semantics/lexicon.py`). Independent human review of the 8 analogy families and
the 8 template-coincidence negatives is still required before any external claim;
until then the manifest marks gold review as pending. Labels are English prose
phrases, not extracted text: extraction quality is measured separately
(`benchmark/extraction-v0.2`).
