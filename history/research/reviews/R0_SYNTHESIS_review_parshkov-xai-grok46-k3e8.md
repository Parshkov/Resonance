---
mission: R0-SYNTHESIS
run: R0-SYNTHESIS-REVIEW
review_type: independent review of a reserved canonical synthesis revision
contributor: Parshkov
agent_id: parshkov-xai-grok46-k3e8
agent_or_model: Grok 4.6 (Grok Build TUI; exact mode not exposed)
date: 2026-08-31
mission_modified: false
web_research_used: false
code_execution_used: false
blind_constraints_preserved: not-applicable
notes: >
  Non-exclusive review input. Does not claim canonical R0-SYNTHESIS
  (REVISION_REQUESTED, reserved for parshkov-openai-gpt5-codex-s7d3 / PR #35)
  and does not claim any R1+ mission (all BLOCKED until #13 is ACCEPTED).
  Inspected PR #35 head beda2251ac125e37345e346b756dc9612876c4016c against
  merged main df2e1be38f7da41e4eccc9d0718619e6691106be.
conflict_of_interest: >
  This identity authored R0-E (PR #23), R0-H (PR #29), R0-F (PR #31), and
  R0-C-REVIEW2 (PR #37). E1 / PR #36 is not this identity's work and is checked
  independently. Findings that depend on PR #37 are labelled as such. This
  review is not a second independent vote on the C solver ranking.
---

# Scope

Independent review of the current R0-SYNTHESIS revision (PR #35, head
`beda225`) against the live gate on issue #13.

The question is not “should another agent rewrite the ADRs?” The canonical
slot is reserved. The question is whether this revision is ready to become
the accepted architecture gate that unblocks R1-SCHEMA.

It is not.

The E1 / PR #36 retrieval revision is materially correct and should be kept.
The merged C-REVIEW2 / PR #37 bake-off is still treated as an unrun experiment.
Maintainer `REVISION_REQUESTED` / `REVISION_INPUT` on issue #13 already named
that gap. This review maps it onto specific files and adds a smaller set of
independent findings that do not require adopting this identity's solver
ranking.

# Inputs Reviewed

| Artifact | Location | Head / state | Role |
|---|---|---|---|
| Canonical synthesis | `research/reviews/R0_SYNTHESIS_parshkov-openai-gpt5-codex-s7d3.md` | PR #35 `beda225` | object of review |
| Retrieval ADR | `docs/decisions/ADR-0002-retrieval-candidate-generation.md` | PR #35 `beda225` | E1 consumption |
| Verification ADR | `docs/decisions/ADR-0003-structural-verification.md` | PR #35 `beda225` | solver / pruning / polarity |
| Thought DNA v0.1 | `docs/THOUGHT_DNA_v0.1.md` | PR #35 `beda225` | representation contract |
| Invariance Spec v0.1 | `docs/INVARIANCE_SPECIFICATION_v0.1.md` | PR #35 `beda225` | A–I and anti-invariances |
| Scoring contract v0.1 | `docs/RESONANCE_SCORING_v0.1.md` | PR #35 `beda225` | vector vs blend, polarity hard reject |
| Benchmark v0.1 | `benchmark/R0_BENCHMARK_v0.1.md` | PR #35 `beda225` | gates, E1 regression, bake-off |
| E1 evidence | `research/submissions/R0_B_E1_evidence_dima2010-anthropic-fable5-7328.md` | merged `0c48bab` / `33bce16` | independent check of retrieval revision |
| C-REVIEW2 | `research/reviews/R0_C_structural_verifier_review_parshkov-xai-grok46-k3e8.md` | merged `3f30b58` / `c2f48e2` | evidence the revision must consume |
| C1 | `research/submissions/R0_C1_alignment_parshkov-openai-gpt5-codex-c914.md` | merged PR #30 | independent source of the pruning failure mode |
| C3 | `research/submissions/R0_C3_alignment_dima2010-anthropic-opus5-f5ae.md` | merged PR #33 | independent analogical-sim and vector-API evidence |
| Issue #13 + PR #35 | GitHub event stream | through 2026-08-31T21:15Z | live canonical state |

Primary R0-A through R0-H submissions, F2, C3, the B/C reviews in PR #34, and
the implementation-queue merge (PR #47) were used only as coordination context.
This is a review of the synthesis contracts, not a second comparative B or C
review.

# Independent Convergence

The contracts already freeze several constraints that independent R0 runs had
already converged on. Those should survive the next revision:

1. Canonical Thought DNA is a source-grounded directed typed property
   multigraph. Fingerprints, WL colors, solver matrices, and embeddings are
   derived, versioned, and disposable.
2. Retrieval and verification are different stages. Retrieval returns
   candidates and optional seeds; verification returns a partial injective
   mapping plus unmatched items plus a score vector.
3. Semantic/content, knowledge, and structural scores stay unblended at
   retrieval. A blended hash cannot diagnose the project's paired hard
   negative.
4. Direction, relation type, polarity, assertion, and meaningful mediators
   are anti-invariances.
5. Exact GED/MCS/isomorphism, whole-graph cosine, LLM-as-judge, and a
   universal ontology are out of v0.1.
6. Extraction self-match is a prerequisite. Matcher numbers are diagnostic
   if duplicate-extract F1 fails.
7. Unmatched nodes are first-class. Forced full assignment is rejected.
8. Granularity is D's guarded, reversible contraction, not an edit-cost trick
   inside the 1–1 verifier.

On the post-submit E1 revision specifically, the synthesis and the E1 artifact
also converge, and that convergence is **independent of this identity**:

- MULTI is the minimum structural key (D0+D1). Role-only D0 is a required
  failing control at rich-world `N=10^4`.
- Structural retrieval is included in v0.1 behind the R0-G gate, not as a
  user-visible decision.
- Structural retrieval is polarity-unreliable. `prevents_flip` outranks the
  noisy analogue; the verifier is the polarity boundary.
- Thin rich-world margin and toy-enum mismatch with Thought DNA v0.1 are
  preserved rather than laundered into a million-corpus claim.

That is a successful evidence revision. Do not revert it.

# Material Disagreements

## D1. Has the verifier bake-off been run? **(blocking; depends on PR #37)**

**PR #35 still says no.** The synthesis report, ADR-0003, Benchmark v0.1's
solver section, the Decision Matrix verification row, Open Question 4, and
the PR body all treat typed QAP-RRWM vs multi-relational FGW as an unrun
one-machine experiment.

**Merged main says yes, with stated limits.** PR #37 (`c2f48e2`) executed a
shared-testbed bake-off of semantic Hungarian, C1-style RRWM, C1-style RRWM
with semantic `top_d=3`, C2-style single shortest-path FGW, and C3
multi-relational FGW. Maintainer comments on issue #13 and PR #35 already
asked the reserved run to consume that evidence before merge.

This is not a scientific disagreement. It is a stale-evidence disagreement.
The next revision must record that the bake-off happened, what it measured,
and which qualifications remain (numpy RRWM ≠ pygmtools; stipulated
similarity oracle; 4–11 node toys; no real encoder). Leaving the question
marked “unresolved / unrun” after `c2f48e2` is factually wrong even if the
solver ranking is later changed.

## D2. What may prune verifier node pairs? **(blocking; only partly dependent on PR #37)**

ADR-0003's Decision starts from “compatible candidate node pairs” and
prohibits dense unpruned 100×100 QAP, while Known Failure Mode 1 is
“Candidate pruning removes the true cross-domain node pair.”

C1's own pseudocode uses `compatible_pairs(..., top_d=10, keep=seeds)` and
lists that exact failure as mode 2. C3 independently measured cross-domain
semantic support at `S_struct=0.083` / accuracy 0.156 under a stipulated
oracle. Those two facts are in merged canonical C runs. PR #37 additionally
measured C1-style `top_d=3` dropping analogical `S_struct` from 1.000 to
0.024.

The contract currently names the risk and still permits the C1 shortcut.
That is the hole an implementation agent would drive through.

**Independent of this identity's solver ranking:** v0.1 MUST NOT prune
candidate node pairs by semantic top-d. Semantic support may weight; it may
not gate analogical pairs. Retrieval top-K of *graphs* remains allowed.
Dense 100×100 QAP remains a scaling NO-GO and must be solved by sparsity,
typed structure, or FGW — not by semantic shortlisting.

Role-identity as an exclusive candidate mask is untested and should not be
silently equated with “compatible pairs.” Role compatibility as a score
component (`N_role`) is a different, weaker claim and can stay.

## D3. Prototype solver vs production freeze **(blocking wording; ranking depends on PR #37)**

ADR-0003 currently refuses to name a prototype default and waits for the
frozen gate. That was correct *before* a shared-testbed result existed.

The reserved-run maintainer request is: name multi-relational FGW
(per-type + transpose, `α≈0.7` on that testbed) as the **v0.1 prototype
default**; keep typed QAP/RRWM as a **co-equal gate candidate / fallback**;
do not freeze production until the DNA-native benchmark confirms it.

This review does **not** recast that ranking as independently re-derived
here. It only requires the contracts to stop saying the comparison is
unrun, and to keep the qualifications that would let pygmtools RRWM or a
real encoder flip the noisy-recall comparison later.

Single-matrix / path-distance FGW is already prohibited as a primary
encoding in ADR-0003. Keep that prohibition. Mark the path-FGW row in the
benchmark bake-off as a **diagnostic control expected to fail the analogical
gate**, not as a shipping candidate.

## D4. Blended-only scoring API **(mostly already fixed; needs an explicit NO-GO)**

The scoring contract already computes `structural_score` without
`S_semantic`, classifies from the structural threshold plus contradiction
policy, and requires a vector plus mapping. That is the right API and it
does not depend on PR #37 (C3 already refused a blend).

C1 and C2 still proposed weighted scalars. ADR-0003 Alternatives should
explicitly reject a blended-only public API. Equal-weight
`(S_struct + S_sem) / 2` is a documented hard-negative inversion on C3's
own winning analog/rewired pair; C1's structure-heavy weights would still
separate that pair. The surviving rule is: emit the vector; if a scalar is
needed internally, structure must dominate; never ship a blended-only API.

## D5. Nothing material on the E1 revision **(non-blocking; independent)**

Checked against the E1 write-up, not against this identity's H report:

| E1 claim | PR #35 consumption | Verdict |
|---|---|---|
| MULTI 12/12 kill-rule pass | included; R0-G gated | correct |
| D0 fail at rich `N=10^4`, 4/4 seeds | D0-only rejected; required failing control | correct |
| `prevents_flip` rank 3 above `org_noisy` | `polarity_reliable=false`; verifier hard reject | correct |
| postings 216 → 819 → 1834 | reproduced and labelled machine-specific for timings | correct |
| rich margin ~0.152 vs 0.143 | thin-margin distribution required | correct |
| toy enums `increases` / `enables` / `precedes` | DNA-native companion required | correct |
| one constellation, synthetic fillers | no million-corpus claim | correct |
| H NO-GO as stated vs as warning | naive path-bag falsified; entropy risk retained | correct |

Do not reopen the shadow-only retrieval decision. The history paragraph in
the synthesis report is the right way to preserve the pre-E1 state.

# Assumption Matrix

| Assumption in PR #35 | Status after this review | If handled wrongly |
|---|---|---|
| E1 MULTI pass transfers to DNA v0.1 enums | still open; companion gate is the right control | rare-branch entropy disappears under the closed relation set |
| One-machine QAP vs FGW bake-off has not been run | **false as of `c2f48e2`**; remaining uncertainty is library/oracle/size | R1-VERIFIER implements an unresolved fork that is already partially measured |
| Semantic pair pruning is a known risk, not a prohibition | **too weak**; C1 named it, C3 showed analogical sim is tiny, #37 measured the kill | analogical pairs never enter the proposal |
| Functional-role compatibility is a safe verifier input | underspecified (score vs exclusive mask) | noisy cross-domain role labels drop true pairs |
| Equal-weight blend is already avoided by the scoring contract | true for the formula; not explicit in ADR-0003 | an implementer ships C1/C2's scalar as the API |
| `Q_containment` / evidence-gate can wait on a size sweep | correctly marked provisional | global thresholds punish fragments |
| Seeds improve verification | C3 measured the opposite for accuracy; ADR-0003 already requires an unseeded restart | keep that restart; do not treat seeds as accuracy evidence |

# Experiments Needed

Reorder against current evidence. Later items remain uninterpretable if
earlier gates fail.

1. **Extraction self-match** — unchanged; still first.
2. **Benchmark fixture audit** — unchanged; still required before the gate
   is used.
3. **Verifier bake-off** — mark **partially executed** by PR #37. Remaining
   work is not “run any bake-off”; it is:
   - pygmtools / exact-library RRWM on the same harness;
   - a real encoder instead of the 1.00 / 0.85 / 0.05 oracle;
   - DNA-native relation enums (no `increases`);
   - C3's idf-on-relational-patterns ablation for generic-chain collapse;
   - cross-size normalisation of `S_struct` / `Q_*`.
4. **Structural retrieval DNA-native companion + R0-G pack margins** —
   unchanged; E1 is a regression, not the architecture gate.
5. **Scale replay** — unchanged; synthetic Zipfian/skewed, not uniform.

# File-level revision map

These are the edits the reserved run should make on PR #35. They do not
authorise a second canonical synthesis.

### Must change before acceptance

| File | Change |
|---|---|
| `research/reviews/R0_SYNTHESIS_parshkov-openai-gpt5-codex-s7d3.md` | Add PR #37 (`c2f48e2` / review `3f30b58`) to supporting inputs. Rewrite the C disagreement resolution, Decision Matrix verification row, assumption “one proposal solver dominates…”, Experiments Needed item 3, Open Question 4, and confidence note so they no longer call the bake-off unrun. Preserve the pygmtools / real-encoder / size qualifications. |
| `docs/decisions/ADR-0003-structural-verification.md` | Name multi-rel FGW as v0.1 **prototype default** and typed QAP/RRWM as **co-equal gate candidate / fallback**. Explicit NO-GO: semantic top-d node-pair pruning; blended-only public API; single-matrix/path-distance FGW as primary encoding (already present — keep). Clarify that “compatible candidate node pairs” must not mean semantic shortlisting. Keep unseeded restart and polarity hard reject. |
| `benchmark/R0_BENCHMARK_v0.1.md` | Record PR #37 as executed shared-testbed evidence. Keep path-FGW and semantic-Hungarian as diagnostic controls. Do not let the bake-off section imply the primary encoding question is still open. Retain the DNA-native / real-encoder / pygmtools follow-ups. |
| PR #35 description | Delete “the verifier proposal-solver choice remains unresolved … require the frozen one-machine E-C1 bake-off.” Replace with the prototype-default-plus-qualifications wording and a revised SUBMIT on issue #13. |

### Should change

| File | Change |
|---|---|
| `docs/RESONANCE_SCORING_v0.1.md` | Already vector-first and polarity-hard. Add one sentence that a blended-only API is non-conforming. Keep `N_role` as a component, not a candidate mask. |
| `docs/INVARIANCE_SPECIFICATION_v0.1.md` | Already correct on polarity-as-anti-invariance vs retrieval-rank. No required change. |
| `docs/THOUGHT_DNA_v0.1.md` | Keep roles in the canonical graph (they are required for MULTI D0). Do not add fingerprints, embeddings, or solver costs. Optional: note that verify-time matching consumes a node-pair similarity function and must not require role identity as a hard gate. |
| `docs/decisions/ADR-0002-retrieval-candidate-generation.md` | No E1 correction required. Optional: state that retrieval must not emit a semantic node-pair shortlist that the verifier then treats as the candidate mask. |

### Must not change

- Do not revert MULTI from v0.1 back to shadow-only.
- Do not erase the pre-E1 history paragraph.
- Do not freeze a production solver from the 8-node stipulated-oracle toy.
- Do not rewrite E1's script or gold to match Thought DNA enums; add the
  companion matrix instead.
- Do not start `src/` implementation from this review.

# Consequences for Thought DNA

No schema enlargement is required for the missing revision.

- Directed typed signed relations, stable IDs, closed roles, and provenance
  stay.
- Node-pair similarity remains an interface, not a DNA field.
- Functional roles stay on nodes because retrieval MULTI D0 needs them.
  They are not a verify-time exclusive mask.
- Relation-pattern IDF, fingerprints, and FGW/QAP matrices stay derived.
- The closed relation set remaining smaller than E1's toy set is a
  **feature of the companion experiment**, not a reason to add `increases`
  / `enables` / `precedes` just to make the legacy script look native.

# Recommended Architecture Decision

**PROVISIONAL GO on the E1 retrieval revision. NO-GO on accepting PR #35
at `beda225`.**

Recommended state after the reserved run's next commit, not a replacement
canonical synthesis:

```text
source text / manual graph
  -> staged grounded Thought DNA
  -> unblended content + Knowledge DNA + MULTI structural retrieval
       (structural candidates are polarity-unreliable)
  -> top-K graphs (+ optional seed correspondences; never semantic pair-pruning)
  -> canonical + guarded coarse views
  -> typed-directed soft proposal
       default prototype: multi-relational FGW (per-type + transpose, α≈0.7)
       co-equal gate candidate: typed QAP / RRWM, no semantic top-d
  -> partial injective rounding + exact typed-edge rescore
  -> score vector, class, correspondence, contradictions, provenance
```

R1-SCHEMA should not start until this issue records `REVIEW_STATUS status:
accepted`. A merged-but-unaccepted synthesis is still BLOCKED for
engineering missions.

# Confidence

**HIGH** that E1 was consumed correctly, that PR #37 is absent from the
current revision, and that semantic pair-pruning is an implementation
hazard even from C1+C3 alone.

**MEDIUM** on naming multi-rel FGW as the prototype default. That ranking
comes from PR #37 plus the maintainer revision request. This review
discloses authorship and does not treat it as independently re-measured
here.

**LOW** on any global numeric threshold, million-corpus recall, or
production solver freeze.

# Open Questions

1. Does pygmtools RRWM close C3's noisy-recall gap on the shared harness?
2. Does a real R0-E / R0-F similarity function shrink the safe FGW `α`
   interval?
3. Does MULTI's E1 margin survive Thought DNA v0.1's closed relation set
   and real-like motif skew?
4. What replaces `max(|E1|,|E2|)` / raw containment so fragments and
   wholes can share a threshold?
5. Should retrieval emit seeds at all, given C3's accuracy-versus-
   determinism measurement?

Questions 1–2 are why the solver remains a prototype default, not a
production freeze. They are not reasons to keep calling the bake-off
unrun.

# Sources

1. PR #35 head `beda2251ac125e37345e346b756dc9612876c4016c` — synthesis
   report and the seven proposed contracts.
2. Issue #13 event stream, including `REVISION_REQUESTED` after PR #36,
   `REVISION_INPUT` after PR #37, and `IMPLEMENTATION_QUEUE_READY`.
3. E1 evidence `research/submissions/R0_B_E1_evidence_dima2010-anthropic-fable5-7328.md`
   and `research/experiments/R0_E1_fingerprint_discrimination.py`.
4. C1 submission, failure mode 2 and `top_d=10` pseudocode.
5. C3 submission and executed experiment, analogical semantic floor and
   unblended vector API.
6. C-REVIEW2 `research/reviews/R0_C_structural_verifier_review_parshkov-xai-grok46-k3e8.md`
   plus `research/experiments/R0_C_REVIEW2_bakeoff.py` (authored by this
   identity; used as evidence-to-be-consumed, not as a second vote).
