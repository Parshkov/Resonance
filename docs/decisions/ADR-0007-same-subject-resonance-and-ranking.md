# ADR-0007 — Same-subject resonance, and ranking on meaning as well as shape

Status: **accepted** (2026-09-06)
Extends: ADR-0004 (concept-aligned analogy). Does not settle ADR-0005.

## Context

On 2026-09-06 the product matched its first pair of real thoughts by two real
people, driven through claude.ai and ChatGPT as ordinary clients.

One person had reasoned about a public registry of how employers treat
candidates. The other, independently and in a different domain, had reasoned
about a registry of how landlords treat tenants. Their constructions were the
same one, step for step: conduct is private and scattered, so the decision is
made blind; it costs the stronger party nothing, so it repeats; a shared
registry makes conduct visible **before** the decision and thereby deters it;
and the real constraint is the cold start, which needs an organisation that
already holds the histories.

The engine returned **`negative`** for that pair, and returned a template
coincidence **above** it. Measured on production:

| candidate | verdict | structural | semantic | contradiction |
| --- | --- | ---: | ---: | ---: |
| "overtime in a ward" (coincidence) | negative | 0.305 | 0.120 | 0.000 |
| the actual twin | negative | 0.186 | 0.590 | 0.214 |

Two separate defects, both invisible to the suite and to Benchmark v0.2.

**Ranking read one component.** `_verified_sort_key` ordered by `structural`
alone. Shape alone cannot tell a coincidence from a match — that is precisely
why `semantic` is computed — so the ranking threw its own evidence away at the
last step and led with a skeleton that happened to line up.

**The same-subject branch demanded `contradiction == 0.0` exactly.** The pair
had 0.214, from two crossed correspondences: one person's "learning after the
fact" was laid over the other's "no cost to the landlord", and vice versa. The
branch fell back to the strangers' bar (`T_STRUCTURE` 0.25 > 0.186) and, worse,
`0.214 > T_CONTRADICTION` forced `negative` regardless.

That crossed pair is not noise. It is a real disagreement about which is the
first cause — and when the two people were introduced and asked, the second
answered that the root cause is the asymmetry of power at the moment of the
deal, not the invisibility of the information. That disagreement is the most
interesting thing about the pair, and the engine used it as a reason to hide
them from each other.

## Decision

**1. Rank on shape and meaning together.** Within a classification, order by
`0.65·structural + 0.35·semantic` (`RANK_STRUCTURAL`, `RANK_SEMANTIC` in
`src/engine/facade.py`), with `structural` as the tie-break. Classification is
untouched: a coincidence is still `negative`, it simply no longer leads.

**2. Same subject buys tolerance, not immunity.** When
`semantic >= T_SAME_SUBJECT_SEMANTIC` and at least one relation is directly
preserved, the structural floor drops to `T_STRUCTURE_SAME_SUBJECT` (0.15, as
before) **and** the contradiction ceiling rises to
`T_CONTRADICTION_SAME_SUBJECT` (0.35). The `contradiction == 0.0` requirement
is removed.

`h_sign_conflict` still hard-rejects the real contradiction — one says causes
where the other says prevents — and is unaffected. What the widened ceiling
admits is structural *disagreement* between people plainly on one subject.

Policy version: `scoring-v0.2-concept-aligned-analogy+same-subject/0.4`.

## Why this is not tuning the gate away

Benchmark v0.2 passes **unchanged** on both splits with gold unedited:
classification accuracy 1.0, negative false-positive rate 0.0, polarity
rejection 1.0, Recall@5 and Recall@20 1.0, positive node F1 0.8469. In
particular `same_vocabulary_wrong_structure` — high semantic, wrong structure,
the family designed to catch exactly this loosening — stays `negative`.

The thresholds were not moved to make a number go up. They were moved because
the benchmark has **no case for two people on the same subject who order the
causes differently**, and production produced one. That gap is now recorded as
`tests/test_same_subject_resonance.py`, built from the measured production
components rather than from authored fixtures.

## The case this serves

Two people can be in the same field thinking about the same thing — two solo
sailors, different oceans, different routes; two people building the same kind
of registry in different markets. That is the common case, not the exotic one.
The engine was built around the rarest case it can do (the same shape under a
different subject) and, on its first real pair, refused the ordinary one.

## Consequences

- One more policy version to carry; `verifier_config_hash` changes with it.
- The chat drawing now places matches by the same combined score it ranks by,
  so the picture and the list beside it tell one story.
- Still open: `T_CONTRADICTION_SAME_SUBJECT = 0.35` is a judgement, fitted to
  one measured pair and checked only for non-regression. The human gold review
  (ROADMAP §2) should decide it, and ADR-0005 stays open.
