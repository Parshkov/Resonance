# Same-Vocabulary Cross-Domain Pairs: `approximate` vs `analogical`

Status: **proposed (open)** — raises a scoring-policy question for the human
gold review. Nothing in this ADR is implemented; the v0.2 classification policy
of ADR-0004 stands unchanged until this record is accepted or rejected.

Date: 2026-09-04

## Context

`ops/TEST_READINESS.md` and `submission/evidence/public-origin-c66951b/SUMMARY.md`
recorded an open question from the first engine 0.2 production run: the classical
A/A' pair — *"Irrigation retry storms after pressure drops"* against *"Retry storm
overloads delivery queue"* — is `approximate` on production, where engine 0.1
called it `analogical`. The evidence summary attributed the change to a single
contradicting relation demoting an otherwise systematic mapping.

**That attribution is wrong, and this ADR corrects the record.** Reproducing the
pair against the engine (`src/scoring/classify`) shows:

| component | value |
|---|---|
| `surface_semantic` | 0.44 |
| `domain_overlap` | 0.00 |
| `concept_alignment` | 0.57 |
| `structural` | 0.91 |
| `r_direct` | 0.86 |

`classify()` reaches `analogical` only through the branch guarded by
`surface < T_SAME_WORDS (0.30) and domain < T_SAME_DOMAIN (0.30)`. This pair's
surface similarity is 0.44 — the two thoughts genuinely share vocabulary
("retry", "overload", "fixed retry budget", "synchronized … retries"). It
therefore takes the *same-subject-matter* branch, `_direct_or_approximate`, where
the only possible outcomes are `direct` and `approximate`. **`analogical` was
never reachable for this pair under v0.2, with or without a contradiction.**
Within that branch it is `approximate` rather than `direct` because
`r_direct = 0.86 < 0.999`: one query relation has no counterpart in the candidate.

A separate implementation defect *did* also fire on this pair and is fixed
outside this ADR (see below); removing it changed the reported contradiction mass
from 0.071 to 0.0 and confidence from `medium` to `high`, and left the verdict
`approximate`.

## Decision

**No decision is taken here.** The question put to the human gold review is:

> When two thoughts share vocabulary but sit in different domains — the same
> *named* mechanism instantiated in two worlds (a retry storm in an irrigation
> network and a retry storm in a delivery queue) — is the correct verdict
> `approximate` ("the same subject matter, imperfectly matched") or `analogical`
> ("different subject matter, the same structure")?

The v0.2 policy answers `approximate`, because `surface >= 0.30` is read as
evidence of shared subject matter and the analogy branch is reserved for pairs
that agree *despite* different words. An alternative reading is that shared
vocabulary with `domain_overlap = 0.0` is precisely a cross-domain analogy whose
mechanism happens to have a portable name, and that the analogy branch should be
gated on domain overlap alone.

Two candidate policies, neither adopted:

- **P1 (status quo).** Any surface similarity ≥ `T_SAME_WORDS` means the same
  subject matter. Simple, and it makes `analogical` a strong claim.
- **P2.** Enter the analogy branch when `domain_overlap < T_SAME_DOMAIN` *and*
  `concept_alignment >= T_CONCEPT_ANALOGY`, regardless of surface similarity;
  keep `surface` only as a confidence input.

P2 would relabel an unknown number of same-vocabulary cross-domain pairs from
`approximate` to `analogical`. Its risk is the failure mode ADR-0004 exists to
prevent: two thoughts that share words *and* structure because they are about the
same thing would be advertised to people as analogies.

## Evidence

The reproduction is `tests/test_r4_verifier.ParallelRelationTests` plus the
component table above. Benchmark v0.2 does not decide the question: its
`cross_domain_analogy` family substitutes vocabulary as well as domain, so no
gold case exercises "same words, different domain, same structure". **This is
the gap that makes the question a policy question rather than a measurement.**

Deciding it therefore requires new gold, which must be human-authored:
Benchmark v0.2 gold is AI-authored and already awaiting human review
(ADR-0004, "Known Failure Modes"). This ADR must not be resolved by adding
agent-written cases and re-running the gate.

## Alternatives Considered

- **Tuning `T_SAME_WORDS` upward until the observed pair is called
  `analogical`.** Rejected outright. It fits a threshold to one production
  observation, has no gold behind it, and is the exact move the mission
  contract forbids.
- **Treating the verdict as a bug and patching `classify()`.** Rejected: the
  branch behaves as ADR-0004 specifies. Changing it is a policy change and
  needs this record.

## Consequences

While this ADR is open:

- production continues to return `approximate` for same-vocabulary
  cross-domain pairs, and that is the documented, intended behaviour, not a
  known defect;
- `ops/TEST_READINESS.md` and the c66951b evidence summary carry a corrected
  explanation of *why*, so the next reader does not re-diagnose it as a
  contradiction effect;
- no threshold in `src/scoring` is changed.

## Benchmark / Validation

Unchanged: `python3 benchmark/r0-v0.2/runner.py` and
`python3 benchmark/extraction-v0.2/runner.py` must exit 0, as they do on the
commit that adds this record. If P2 is ever adopted, it needs human-authored
gold for the same-vocabulary/different-domain family *before* any threshold or
branch is touched.

## Known Failure Modes

- The question is stated from a single production pair plus a synthetic
  reproduction. How often the situation occurs in a real corpus is unmeasured.
- `surface_semantic` is lexicon-derived; a lexicon change moves the 0.44 that
  motivates this record.

## Conditions for Reconsideration

- Human-reviewed gold containing same-vocabulary / different-domain pairs with
  an agreed label.
- Pilot evidence that people receiving `approximate` for such pairs read the
  verdict as wrong.

## Related Research

- ADR-0004 — concept-aligned analogy, multi-skeleton benchmark, verified ranking
  (the policy this record questions, and which stands).
- `submission/evidence/public-origin-c66951b/SUMMARY.md` — the production
  observation, whose stated cause this record corrects.
