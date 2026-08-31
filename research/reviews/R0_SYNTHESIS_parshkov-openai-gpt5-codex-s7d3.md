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
revision_assists:
  - agent_id: parshkov-xai-grok46-k3e8
    run_id: R0-SYNTHESIS-REV37
    consumes: "PR #37 / C-REVIEW2 bake-off (c2f48e2 / 3f30b58) plus PR #48 review map"
    note: >
      Assist patch into the reserved canonical run. Does not replace
      parshkov-openai-gpt5-codex-s7d3 as the canonical synthesis author
      and is not a second CLAIM on issue #13.
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

The revised result is a **PROVISIONAL GO** for an extraction, benchmark, a
multi-scale structural-retrieval prototype behind the R0-G gate, and a
three-stage verifier whose v0.1 **prototype default** is multi-relational FGW
(per-type + transpose). It remains a **NO-GO** for claiming million-corpus,
real-distribution cross-domain recall before that gate and a corpus-scale
replay pass, and a **NO-GO** for freezing the production proposal solver from
the 8-node stipulated-oracle bake-off. Both ADRs are `proposed`, not accepted;
this submission does not silently open the core implementation gate.

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
| R0-B E1 post-submit evidence | [#36](https://github.com/Parshkov/Resonance/pull/36) | `0c48babb20c5829bfce5f4a7e6c796cbf1e9d661` (merged as `33bce16e75d5d5f8583ebf15caa6f2e50f7b4cac`) | executes the B review's structural-retrieval kill test |
| C-REVIEW2 shared-testbed bake-off | [#37](https://github.com/Parshkov/Resonance/pull/37) | `3f30b58` (merged as `c2f48e2d5ef8217347feadf09f01485554377c63`) | executes E-C1 on one scorer; default prototype vs co-equal fallback |
| Synthesis review of this PR | [#48](https://github.com/Parshkov/Resonance/pull/48) | review input | maps the #37 gap and the semantic pair-pruning hole |

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

After the first synthesis `SUBMIT`, PR #36 supplied the previously open E1
experiment and triggered a formal `REVISION_REQUESTED`. Its exact stdlib script
was rerun locally. MULTI passed 12 reproduced world/size/seed configurations;
at `N=30000` in the rich world, `org_noisy` ranked 4, the best generic chain
ranked 5, and 1,834 postings were touched. The polarity-flipped near-duplicate
ranked 3 above the true noisy analogue throughout. Local build/query timings
differed from the contributor's machine and are treated as machine-specific,
not as an SLA. E1's toy role/relation inventories are not identical to Thought
DNA v0.1 (`increases`, `enables`, and `precedes` appear in E1), so the run
validates the retrieval machinery rather than freezing the extraction schema.

After the E1 revision (`beda225`), maintainer `REVISION_INPUT` required this
run to consume merged PR #37. That review plus
`research/experiments/R0_C_REVIEW2_bakeoff.py` executed a shared-testbed
comparison of semantic Hungarian, C1-style RRWM with and without semantic
`top_d=3`, C2-style single shortest-path FGW, and C3 multi-relational FGW.
C3's published table reproduced. This second revision records that bake-off
as **partially executed**, names a v0.1 prototype default, and keeps the
production freeze behind the DNA-native / pygmtools / real-encoder follow-ups.
The pre-#37 wording that the solver choice was unrun is preserved only as
superseded history. PR #48 (same assist identity as PR #37) is review input,
not a second independent vote on the ranking.

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

**Initial submitted resolution (`7864446`):** content/knowledge retrieval was
the default v0.1 generator and the complete structural design remained an
unblended shadow experiment. That was the correct state before E1 existed, but
it is preserved here as superseded evidence history rather than silently erased.

**Post-submit E1 evidence:** PR #36 runs the full descriptor + typed path +
distance + DF/IDF + injective-consensus design against full constellations in a
rich-random world and an 80%-bare-chain world. MULTI passes the kill rule across
the tested sizes and four seeds. Role-only D0 fails systematically at `N=10000`
in the rich world; D1 survives but is brittle under graph edits, so combining D0
and D1 is mandatory. Touched postings grow 216 -> 819 -> 1,834 as the rich
corpus grows `10^3 -> 10^4 -> 3*10^4`. The rich-world positive margin is thin,
and one `causes -> prevents` near-duplicate still outranks the true analogue.

**Revised resolution:** include the unblended **multi-scale structural channel
in v0.1 behind the R0-G architecture gate**, alongside content and knowledge
channels. It returns candidates and optional seeds, never a final resonance
decision. Its output is explicitly polarity-unreliable and MUST pass through a
verifier-side sign/direction rejection before user-visible acceptance. E1
refutes H's NO-GO as stated while preserving H's entropy, extraction, generic
motif, and polarity warnings. Real-corpus distribution and million-scale recall
remain open.

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

**Initial submitted resolution (`7864446` / `beda225`):** adopt the shared
typed-directed `soft proposal -> structural consistency -> discrete partial
mapping -> exact rescore` pattern, and leave QAP-RRWM versus multi-relational
FGW-CG as co-equal gate candidates until a one-machine bake-off. That was
correct while C1 and C3 used different toys and C2 was unexecuted. It is
preserved here as superseded evidence history.

**Post-submit C-REVIEW2 evidence (PR #37, merged `c2f48e2`):** on one shared
scorer, C1-style RRWM-all and C3 multi-rel FGW `α=0.7` both pass 8/8 combined
kill rules; C3's published table reproduces; C2-style single shortest-path FGW
fails the analogical struct/accuracy floors (6/8); C1-style semantic `top_d=3`
kills the analogical case (`S_struct` 1.000 → 0.024); equal-weight
`(S_struct+S_sem)/2` inverts analog vs rewired on C3's winning numbers.
Qualifications remain: numpy RRWM ≠ pygmtools; stipulated 1.00/0.85/0.05
oracle; 4–11 node graphs; no real encoder.

**Revised resolution:** keep the three-stage hybrid. v0.1 **prototype default**
is C3 multi-relational FGW (one matrix per relation type plus transpose,
`α≈0.7` on this testbed). Typed QAP/RRWM remains a **co-equal gate candidate /
fallback**, with **no semantic top-d pair pruning**. Single-matrix /
path-distance FGW is not a primary encoding. Partial/ε-padded FGW variants
remain unmatched-mass alternatives of the FGW family, not a third judge.
Blended-only public APIs are rejected. Production primary is still selected
only by the frozen DNA-native gate, not by this toy. If retrieval seeds are
used, at least one unseeded restart is mandatory because C3 shows seeds can
improve stability while reducing mapping accuracy.

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
| Retrieval | B1/B2 design convergence; H warning; E1 full-design pass with corrections | content, knowledge, and mandatory MULTI structural candidates; unblended scores; structural output polarity-unreliable | R0-G gate plus real-distribution scale replay | medium for v0.1, low for million-scale claim |
| Candidate hand-off | B1/B2/C1 agree | ranked IDs plus per-channel scores and optional seed correspondences | deterministic replay | high |
| Verification | C1 typed QAP; C2 pFGW; C3 multi-rel FGW; PR #37 bake-off | three-stage hybrid; prototype default = multi-rel FGW α≈0.7; QAP/RRWM co-equal fallback; no semantic pair-pruning; no blended-only API | DNA-native gate + pygmtools/real-encoder follow-up; ≤2 s/pair | medium for prototype, low for production freeze |
| Granularity | D versus generic coarsening | reversible guarded suppression plus bounded edge-to-path matching | zero false contraction in gate cases | medium-high |
| Knowledge | E and H agree it is not analogical identity | optional `about`/`requires` IDs; same-domain and complementary side-channel only | generic-ID, polysemy, and direction tests | medium |
| Scoring | A/C/E/G converge on inspectability | structural score plus semantic, knowledge, coverage, contradiction, and evidence fields; no cross-mode scalar | calibration-only thresholds; family reports | medium |
| Benchmark | G design, H adversarial additions | 8 packs × 16 cases; 2 calibration and 6 immutable gate packs; separate stage metrics | all mandatory gates, no averaging away failures | high for architecture testing |
| Scale claim | B1 analytic feasibility; B2/H entropy risk; G warns 136 graphs cannot establish scale | no 1M-scale claim until synthetic collision/latency replay | p95, index size, recall, and skew report | high |

# Assumption Matrix

| Assumption | Current evidence | If false | Required experiment |
|---|---|---|---|
| Closed roles/relations repeat across extraction | literature-backed, not measured on Resonance text | all structural features drift | duplicate greedy extraction with span-aligned node/edge F1 |
| Generic motifs can be suppressed without losing analogical recall | E1 passes two synthetic worlds and four seeds; rich margin is thin | structural channel fails the R0-G gate or remains corpus-specific | margin distribution on reviewed fixtures and real-like corpus skew |
| E1 discrimination transfers to Thought DNA v0.1's vocabulary | machinery passes, but E1 uses different role/relation enums | rare branch entropy may disappear under the canonical extraction schema | DNA-native companion of the exact E1 matrix |
| Candidate pruning retains cross-domain correspondences | **falsified for semantic top-d** (C1 failure mode 2; C3 analogical sim ~0.05; PR #37 `top_d=3` drops analog `S_struct` 1.000→0.024) | analogical pairs never enter the proposal | DNA-native bake-off must keep semantic pair-pruning as a required failing control |
| One proposal solver dominates after identical exact rescore | PR #37: both typed QAP-RRWM and multi-rel FGW pass 8/8; FGW has higher noisy recall on this numpy RRWM; pygmtools/real-encoder unrun | keep FGW as prototype default and QAP as fallback, or invert after library-faithful replay | DNA-native one-machine bake-off with pygmtools RRWM and a real encoder |
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
3. **Oracle-pair verifier bake-off:** **partially executed** by PR #37 on a
   stipulated-oracle toy. Remaining work is not “run any bake-off”; it is
   pygmtools / exact-library RRWM on the same harness, a real encoder instead
   of 1.00/0.85/0.05, DNA-native relation enums (no `increases`), C3's
   relation-pattern IDF ablation, and cross-size normalisation of `S_struct`.
   Path-distance FGW and semantic Hungarian stay as diagnostic controls.
   Semantic `top_d` pair-pruning stays as a required failing control.
4. **Structural retrieval gate extension:** retain E1 as a regression, then
   measure MULTI recall, positive-minus-generic margin distribution, polarity
   inversions, and postings skew across all R0-G packs and real-like fillers;
   run a companion using the exact Thought DNA v0.1 enums.
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
  -> unblended content + Knowledge DNA + MULTI structural retrieval
       (structural candidates require polarity-aware verification)
  -> top-K graphs (+ optional seed correspondences; never semantic pair-pruning)
  -> canonical + guarded coarse graph views
  -> typed-directed soft proposal
       default prototype: multi-relational FGW (per-type + transpose, α≈0.7)
       co-equal gate candidate: typed QAP / RRWM, no semantic top-d
  -> partial injective rounding + exact structural rescore
  -> score vector, class, correspondence, contradictions, provenance
```

Do not advertise cross-domain analogical recall at corpus scale from E1 alone.
The channel is an explicit v0.1 architecture component, but its claims remain
bounded by R0-G and a future real-distribution scale replay.

# Confidence

**MEDIUM.** Confidence is high in the contracts, the three-stage verifier
shape, typed/directed encoding, the no-semantic-pair-prune rule, and the
falsification order; medium in naming multi-rel FGW as the v0.1 prototype
default (PR #37 numpy RRWM is not pygmtools); and low-to-medium in global
structural retrieval and any production solver freeze. This is exactly why
the outputs remain proposed and benchmark-gated.

# Open Questions

1. Can explicit binary relations support enough systematicity, or must v0.2
   accept grounded relation-as-argument statements?
2. What corpus-derived relation compatibility and composition table preserves
   recall without collapsing `causes`, `prevents`, and `requires`?
3. Does MULTI retain its E1 margin across all R0-G packs and real-distribution
   motif skew, rather than one synthetic constellation family?
4. Does pygmtools RRWM close C3's noisy-recall gap on the shared harness, and
   does a real encoder shrink the safe FGW `α` interval? (The shared-testbed
   bake-off has been run; this is the remaining library/oracle question, not
   an unrun comparison.)
5. Can two human reviewers agree on the six gate analogies and mappings?
6. What is the minimum evidence floor that rejects tiny generic motifs without
   suppressing genuinely small thoughts?
