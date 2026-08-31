---
mission: R0-SYNTHESIS
run: R0-SYNTHESIS
contributor: Parshkov
agent_id: parshkov-openai-gpt5-codex-s7d3
agent_or_model: GPT-5-based Codex (exact deployed model/version not exposed to this run)
execution_environment: Codex
date: 2026-08-31
mission_modified: false
web_research_used: false
code_execution_used: true
additional_agents_used: false
tools_used:
  - Git and GitHub CLI for immutable PR-head inspection and coordination
  - local Python validation
  - temporary Python 3.12 environment with numpy 2.0.2 and scipy 1.13.1 for C3 reproduction
blind_constraints_preserved: true
---

# Scope

This review closes the R0 architecture-synthesis gate without starting core
implementation. It reconciles the submitted primary R0-A through R0-H research,
including the formerly blind B1/B2 and C1/C2 pairs, into seven proposed outputs:

1. this decision matrix;
2. [Invariance Specification v0.1](../../docs/INVARIANCE_SPECIFICATION_v0.1.md);
3. [Retrieval ADR](../../docs/decisions/ADR-0002-retrieval-candidate-generation.md);
4. [Verification ADR](../../docs/decisions/ADR-0003-structural-verification.md);
5. [Thought DNA v0.1](../../docs/THOUGHT_DNA_v0.1.md);
6. [Benchmark v0.1](../../benchmark/R0_BENCHMARK_v0.1.md); and
7. [Resonance Scoring and Explanation Contract v0.1](../../docs/RESONANCE_SCORING_v0.1.md).

The overall result is a **PROVISIONAL GO** for an extraction and benchmark
prototype, and a **NO-GO** for claiming million-corpus cross-domain analogical
retrieval before the structural channel passes its explicit gates. Both ADRs are
`proposed`, not accepted; this submission does not silently open the core
implementation gate.

# Inputs Reviewed

The table records the exact immutable PR head inspected. Open/merged describes
GitHub state at synthesis time on 2026-08-31, not review acceptance.

| Mission | Artifact | PR | Head inspected | State | Role in synthesis |
|---|---|---|---|---|---|
| R0-A | `R0_A_structure_mapping_veronicagedd-dev-openai-gpt5-codex-8cf4.md` | [#27](https://github.com/Parshkov/Resonance/pull/27) | `cffbb424ac916a7a9a0907f0e916472da3516c52` | merged | proposition identity, systematicity, SME-lite |
| R0-B1 | `R0_B1_fingerprinting_parshkov-openai-gpt56sol-b1-r7m4.md` | [#24](https://github.com/Parshkov/Resonance/pull/24) | `7df83b27702891fa41d87207ccba37b7c7ea8eb8` | open | relational constellation fingerprints |
| R0-B2 | `R0_B2_fingerprinting_dima2010-anthropic-opus5-f5ae.md` | [#28](https://github.com/Parshkov/Resonance/pull/28) | `126a4cae2db316bdf16045c74657e83084792e5d` | merged | two-channel index and entropy bound |
| R0-C1 | `R0_C1_alignment_parshkov-openai-gpt5-codex-c914.md` | [#30](https://github.com/Parshkov/Resonance/pull/30) | `8c73b2e3d56b0f1b099dfecb5feaff9c14cf51a5` | open | typed sparse QAP hybrid |
| R0-C2 | `R0_C2_alignment_julianadamsciv-blip-openai-gpt56sol-8f2c.md` | [#26](https://github.com/Parshkov/Resonance/pull/26) | `01ad949611dba2c5b6f039d2560dcdd89cff0c98` | merged | partial FGW with discrete rescore |
| R0-D | `R0_D_multiscale_andy82-openai-gpt56sol-01a05419.md` | [#25](https://github.com/Parshkov/Resonance/pull/25) | `eef9053a57ec28c645705b5d84befd96dac41ec6` | merged | guarded chain suppression and edge-to-path matching |
| R0-E | `R0_E_knowledge_parshkov-xai-grok46-k3e8.md` | [#23](https://github.com/Parshkov/Resonance/pull/23) | `9d0ce3f27dc9a35aad22a268312638f65faa7152` | open | `about`/`requires` concept side-channel |
| R0-F | `R0_F_extraction_parshkov-xai-grok46-k3e8.md` | [#31](https://github.com/Parshkov/Resonance/pull/31) | `aa6982af359c37345e346b756dc9612876c4016c` | open | span-grounded staged extraction |
| R0-G | `R0_G_benchmark_parshkov-openai-gpt5-codex-a6f2.md` | [#21](https://github.com/Parshkov/Resonance/pull/21) | `d61774dd1aad84c5165e153752c21603a8ea18a7` | open | contrastive metamorphic gate |
| R0-H | `R0_H_redteam_parshkov-xai-grok46-k3e8.md` | [#29](https://github.com/Parshkov/Resonance/pull/29) | `560c19372a923bbaf87b0184439166db663150ca` | open | generic-motif and entropy attack |

Supporting evidence received while the coordinator lease was active was also
inspected:

| Input | PR | Head inspected | Use |
|---|---|---|---|
| R0-F2 independent repeat | [#32](https://github.com/Parshkov/Resonance/pull/32) | `cfc0e8ea5391930da5487626c927be6c937abc31` | corroborates exact spans, abstention, manual bypass |
| R0-C3 independent repeat + executed experiment | [#33](https://github.com/Parshkov/Resonance/pull/33) | `5f4b5aca36cb10a098a162128ae826c798a9a683` | multi-relational FGW, restart/seed and generic-motif evidence |
| B/C comparative `REVIEW_INPUT` | [#34](https://github.com/Parshkov/Resonance/pull/34) | `1ffe6518d1d4f5babdfbc0b5743ada2f6c12493b` | conflict-disclosed review of B1/B2/H and C1/C2/C3 |

These repeats and reviews do not replace the canonical primary runs. The PR #34
reviewer discloses that the same human sponsor authored B2 and C3; its
adjudications were checked against the underlying artifacts rather than treated
as independent votes. No blind sibling was read before its own submission;
B1/B2 and C1/C2/C3 were opened together only during synthesis.

The exact C3 experiment script at PR #33's head was rerun locally with its
declared NumPy/SciPy versions. Its reported score and seed tables reproduced,
including clean cross-domain `1.000`, noisy cross-domain `0.740`, generic long
chain `0.512`, and seed accuracy `0.896 -> 0.750`. Runtime is machine-dependent:
this run measured 13.7 ms for 50×50 versus C3's 8.7 ms. No other submission's
analytic estimate or toy result was relabeled as a synthesis-run measurement.

# Independent Convergence

The strongest evidence is not any single algorithm recommendation but the
constraints that independent runs reached by different routes:

- Thought graphs must preserve stable local IDs, functional roles, directed
  typed relations, relation identity, confidence, and provenance.
- Semantic/content evidence and structural evidence must remain separately
  inspectable. A blended score cannot diagnose the defining hard negative.
- Retrieval and verification are different stages. Verification runs only on a
  small candidate set and must return an explicit partial correspondence.
- Direction, relation type, polarity, and meaningful intermediate mechanisms
  are anti-invariances: changing them must be visible, not normalized away.
- Unmatched nodes are a valid outcome. Different sizes, noise, and irrelevant
  branches cannot be represented as forced full assignment.
- Exact GED/MCS/isomorphism, whole-graph embedding cosine, LLM-as-judge, learned
  GNN matching, and a universal ontology are all out of R0 scope.
- The representation/extraction loop is the primary risk. Matcher results are
  not credible until two independent extractions of the same text self-match.
- Any first result must expose component scores, contradictions, coverage, and
  matched/unmatched branches; one opaque scalar is insufficient.

# Material Disagreements

## B1 versus B2, then H

B1 gives a high-confidence GO to multiscale WL/path landmark pairs. B2 agrees on
the inverted-index shape and seed-correspondence hand-off but calculates only
about 15 bits for the lexicon-free structural channel, versus about 30 bits for
the semantic channel, and makes global structural retrieval conditional. H then
constructs a five-domain generic-causal-motif collision where role-path Jaccard
is 1.0 and intended versus spurious analogues tie. The B comparative review
correctly limits that attack: H's minimal chains omit B1/B2 landmark descriptors,
distance buckets, and correspondence-consensus voting, so it falsifies a naive
path bag rather than the complete constellation design.

**Resolution:** content/knowledge retrieval is the default v0.1 candidate
generator. The complete structural relational-fingerprint design may be built
only as an unblended shadow experiment and promoted only after passing
self-match, full-constellation generic-motif precision, cross-domain recall, and
posting-skew gates. Seed correspondences are retained as optional hints if it is
promoted. This preserves B1's falsifiable proposal, B2's entropy accounting, and
H's valid entropy/motif warning without overstating H's toy as a test of the
complete design.

## C1 versus C2 versus C3

C1 selects typed Lawler QAP with RRWM, partial Hungarian rounding, and exact
discrete local rescoring; C2 selects pFGW with partial transport, Hungarian
rounding, and typed directed-edge rescoring. C3 independently executes a
multi-relational FGW using one matrix per relation type plus its transpose,
followed by structural consistency and Hungarian extraction. It recovers the
small clean cross-domain mapping and shows conditional-gradient feasibility,
but also measures non-convex relabeling variance, seed-induced accuracy loss,
cross-size score incomparability, and only a 0.23 noisy-positive/generic-chain
margin. All three disagree on proposal optimization, not the decision object.

**Resolution:** adopt the shared typed-directed `soft proposal -> structural
consistency -> discrete partial mapping -> exact rescore` pattern. Do not select
a production proposal solver before one-machine head-to-head evidence. Typed
QAP-RRWM and multi-relational FGW-CG are co-equal gate candidates; partial FGW
variants cover unmatched-mass alternatives. All terminate in the same mapping
and scorer. If retrieval seeds are used, at least one unseeded restart is
mandatory because C3 shows seeds can improve stability while reducing mapping
accuracy.

## Reified propositions versus extractable binary relations

A argues that statements, including higher-order statements, are the correct
unit of structural matching. F finds nested predicates unreliable at ingest,
and G does not yet justify hyperedges/reification in the gate fixtures.

**Resolution:** canonical v0.1 stores each binary relation as a uniquely
identified, source-grounded proposition record. A deterministic derived view may
reify those records as statement nodes and compile connected chains for
systematicity; it may not invent higher-order source claims. Explicit
relation-as-argument syntax is deferred until extracted evidence and benchmark
cases require it. This is reification-ready without making the extractor assert
what it cannot reliably ground.

## Granularity invariance

C1 correctly reports direct QAP as non-invariant to edge subdivision; C2 expects
shortest-path costs to help partially; D defines a much narrower safe rule.

**Resolution:** use D's guarded, reversible chain suppression and bounded
edge-to-path verification. Only transparent nodes explicitly marked
`atomic=false` may be suppressed. General granularity invariance is rejected.

# Decision Matrix

| Decision surface | Evidence / alternatives | Proposed v0.1 decision | Gate | Confidence |
|---|---|---|---|---|
| Canonical graph | A prefers proposition graph; C/D/F/G converge on directed typed graph | Source-grounded directed typed property multigraph with unique proposition IDs; reified derived view | schema/example validation and self-match | medium-high |
| Extraction | F and F2 converge; H identifies relation instability | staged span → role → closed relation → validate; abstain; manual bypass | duplicate-extract node F1 ≥0.70 and edge F1 ≥0.60 on calibration set | medium |
| Relation vocabulary | A/B need direction and polarity; F limits reliable types | `causes`, `prevents`, `requires`, `part_of`, `constrains`, `supports`, `contradicts`; versioned compatibility table | explicit-cue and polarity tests | medium |
| Higher-order structure | A needs systematicity; F rejects nested extraction | compile a derived statement/chain view; never treat it as new source truth | improves hard-negative ranking without provenance loss | medium |
| Retrieval | B1 GO; B2 qualified GO; H qualified NO-GO | content + specific concept postings by default; structural fingerprints shadow-only | promotion gates in retrieval ADR | medium-low for global analogy |
| Candidate hand-off | B1/B2/C1 agree | ranked IDs plus per-channel scores and optional seed correspondences | deterministic replay | high |
| Verification | C1 typed QAP; C2 pFGW; C3 multi-relational FGW | typed-directed soft proposal → consistency → partial Hungarian → exact scorer; solver selected by bake-off | benchmark thresholds and ≤2 s/pair target | medium |
| Granularity | D versus generic coarsening | reversible guarded suppression plus bounded edge-to-path matching | zero false contraction in gate cases | medium-high |
| Knowledge | E and H agree it is not analogical identity | optional `about`/`requires` IDs; same-domain and complementary side-channel only | generic-ID, polysemy, and direction tests | medium |
| Scoring | A/C/E/G converge on inspectability | structural score plus semantic, knowledge, coverage, contradiction, and evidence fields; no cross-mode scalar | calibration-only thresholds; family reports | medium |
| Benchmark | G design, H adversarial additions | 8 packs × 16 cases; 2 calibration and 6 immutable gate packs; separate stage metrics | all mandatory gates, no averaging away failures | high for architecture testing |
| Scale claim | B1 analytic feasibility; B2/H entropy risk; G warns 136 graphs cannot establish scale | no 1M-scale claim until synthetic collision/latency replay | p95, index size, recall, and skew report | high |

# Assumption Matrix

| Assumption | Current evidence | If false | Required experiment |
|---|---|---|---|
| Closed roles/relations repeat across extraction | literature-backed, not measured on Resonance text | all structural features drift | duplicate greedy extraction with span-aligned node/edge F1 |
| Generic motifs can be suppressed without losing analogical recall | disputed by B1/B2/H | structural channel cannot be global retrieval | generic-motif pack plus corpus-skew scaling |
| Candidate pruning retains cross-domain correspondences | unmeasured | QAP cannot recover a pair it never sees | seeded/unseeded oracle-candidate verification |
| One proposal solver dominates after identical exact rescore | C1 and C3 executed different toys/machines; C2 unexecuted | retain the simpler winner or SME-lite | frozen one-machine QAP/FGW/SME-lite bake-off |
| `atomic=false` can be assigned conservatively | D hypothesis | false contractions erase mechanisms | meaningful-versus-transparent subdivision cases |
| Knowledge IDs are sufficiently precise | E hand-linked only; H cites linker risk | optional channel creates false matches | polysemy and abstention audit with second annotator |
| Hand-authored analogies have useful gold mappings | G design only | gate measures author theory | independent human review of manual gate cases |

# Experiments Needed

Run them in this order; later results are uninterpretable if an earlier gate
fails.

1. **Extraction self-match:** two greedy runs per calibration text, exact span
   validation, span-IoU node alignment, typed-edge F1, hallucination rate.
2. **Benchmark fixture audit:** second-human review of the six manually authored
   gate analogies and complementary bridges; schema validation and permutation
   invariance.
3. **Oracle-pair verifier bake-off:** semantic Hungarian, SME-lite greedy, typed
   QAP hybrid, pFGW+rescore, and C3's per-relation-plus-transpose FGW-CG on the
   same pairs and machine, with seeded and unseeded restarts.
4. **Structural retrieval shadow test:** B1-style pair fingerprints and B2-style
   monotone path shingles, measured against H's generic-motif pack and the
   benchmark's cross-domain positives.
5. **Scale replay:** fixed queries against increasing synthetic distractor IDs;
   report posting-list distribution, touched postings, build size, p50/p95, and
   recall rather than extrapolating from 136 graphs.

# Consequences for Thought DNA

Thought DNA v0.1 is deliberately smaller than the union of all proposals. It
contains source-grounded nodes and proposition records, closed roles/relations,
direction, assertion/modality, confidence, optional Knowledge DNA, and enough
metadata to reproduce extraction. It excludes embeddings, semantic buckets, WL
colors, fingerprints, global IDs, solver matrices, and ungrounded nested claims.
Those are versioned derived artifacts.

# Recommended Architecture Decision

Adopt the contracts in the linked documents for review:

```text
source text / manual graph
  -> staged grounded Thought DNA
  -> content + Knowledge DNA candidate retrieval
       + optional shadow structural retrieval
  -> top-K candidates (+ optional seed correspondences)
  -> canonical + guarded coarse graph views
  -> typed-directed soft proposal (QAP and multi-relational FGW candidates)
  -> partial injective rounding + exact structural rescore
  -> score vector, class, correspondence, contradictions, provenance
```

Do not advertise cross-domain analogical recall at corpus scale in v0.1. The
verifier may validate a supplied/retrieved cross-domain pair; discovering that
pair globally remains an experiment.

# Confidence

**MEDIUM.** Confidence is high in the contracts and falsification order, medium
in the schema and verifier choice, and low-to-medium in global structural
retrieval. This is exactly why the outputs remain proposed and benchmark-gated.

# Open Questions

1. Can explicit binary relations support enough systematicity, or must v0.2
   accept grounded relation-as-argument statements?
2. What corpus-derived relation compatibility and composition table preserves
   recall without collapsing `causes`, `prevents`, and `requires`?
3. Does any structural fingerprint family promote out of shadow mode after the
   generic-motif and extraction-self-match gates?
4. Which typed proposal solver wins the one-machine bake-off, and can its
   candidate mask/transport preserve cross-domain pairs without unstable cost?
5. Can two human reviewers agree on the six gate analogies and mappings?
6. What is the minimum evidence floor that rejects tiny generic motifs without
   suppressing genuinely small thoughts?
