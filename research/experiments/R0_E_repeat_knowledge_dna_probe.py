#!/usr/bin/env python3
"""Deterministic falsification probe for R0-E-REPEAT-V9K2.

The probe compares role-blind topic overlap with the proposed v0.1 channels:
required-knowledge overlap and directional requires->about supply.  It is a
small contract test, not evidence that automatic knowledge annotation works.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from math import sqrt


@dataclass(frozen=True)
class Ref:
    id: str
    conf: float = 1.0


@dataclass(frozen=True)
class Case:
    name: str
    about_a: tuple[Ref, ...] = ()
    requires_a: tuple[Ref, ...] = ()
    about_b: tuple[Ref, ...] = ()
    requires_b: tuple[Ref, ...] = ()


GENERIC = {"local:engineering", "local:science"}
EXACT = {frozenset(("local:graph-algorithms", "acmccs:graph-algorithms"))}
CLOSE = {frozenset(("local:bayesian-filtering", "local:kalman-filtering"))}
BROADER = {frozenset(("local:heat-transfer", "local:thermodynamics"))}


def concept_similarity(left: str, right: str) -> float:
    """Allowlisted, snapshot-like resolver behavior for the v0.1 probe."""
    if left in GENERIC or right in GENERIC:
        return 0.0
    if left == right:
        return 1.0
    pair = frozenset((left, right))
    if pair in EXACT:
        return 1.0
    if pair in CLOSE:
        return 0.75
    if pair in BROADER:
        return 0.45
    return 0.0


def _best_matching(left: tuple[Ref, ...], right: tuple[Ref, ...]) -> float:
    """Maximum one-to-one match, exhaustive because Knowledge DNA caps at 8."""
    best = 0.0

    def visit(index: int, used: frozenset[int], total: float) -> None:
        nonlocal best
        if index == len(left):
            best = max(best, total)
            return
        visit(index + 1, used, total)
        for right_index, right_ref in enumerate(right):
            if right_index in used:
                continue
            similarity = concept_similarity(left[index].id, right_ref.id)
            weight = similarity * sqrt(left[index].conf * right_ref.conf)
            if weight:
                visit(index + 1, used | {right_index}, total + weight)

    visit(0, frozenset(), 0.0)
    return best


def knowledge_score(left: tuple[Ref, ...], right: tuple[Ref, ...]) -> float | None:
    """Confidence-weighted soft Dice; missing evidence abstains instead of failing."""
    left = tuple(ref for ref in left if ref.id not in GENERIC)
    right = tuple(ref for ref in right if ref.id not in GENERIC)
    if not left or not right:
        return None
    denominator = sum(ref.conf for ref in left) + sum(ref.conf for ref in right)
    return round(2.0 * _best_matching(left, right) / denominator, 3)


def role_blind_jaccard(case: Case) -> float:
    left = {ref.id for ref in case.about_a + case.requires_a}
    right = {ref.id for ref in case.about_b + case.requires_b}
    union = left | right
    return round(len(left & right) / len(union), 3) if union else 0.0


CASES = (
    Case("same-topic-different-requirements",
         (Ref("local:batteries"),), (Ref("local:heat-transfer"),),
         (Ref("local:batteries"),), (Ref("local:supply-chain-accounting"),)),
    Case("different-words-same-requirement",
         (Ref("local:battery-cooling"),), (Ref("local:heat-transfer"),),
         (Ref("local:server-cooling"),), (Ref("local:heat-transfer"),)),
    Case("cross-domain-structural-analogy",
         (Ref("local:batteries"),), (Ref("local:heat-transfer"),),
         (Ref("local:organizations"),), (Ref("local:organization-design"),)),
    Case("generic-hub-only",
         requires_a=(Ref("local:engineering"),),
         requires_b=(Ref("local:engineering"),)),
    Case("cross-scheme-exact-map",
         requires_a=(Ref("local:graph-algorithms"),),
         requires_b=(Ref("acmccs:graph-algorithms"),)),
    Case("near-not-identical",
         requires_a=(Ref("local:bayesian-filtering"),),
         requires_b=(Ref("local:kalman-filtering"),)),
    Case("hierarchy-is-weak-evidence",
         requires_a=(Ref("local:heat-transfer"),),
         requires_b=(Ref("local:thermodynamics"),)),
    Case("directional-complement",
         requires_a=(Ref("local:kalman-filtering"),),
         about_b=(Ref("local:kalman-filtering"),)),
    Case("reverse-direction-does-not-supply",
         about_a=(Ref("local:kalman-filtering"),),
         requires_b=(Ref("local:kalman-filtering"),)),
    Case("missing-annotations",
         requires_a=(Ref("local:heat-transfer"),)),
    Case("partial-overlap",
         requires_a=(Ref("local:heat-transfer"), Ref("local:fluid-dynamics")),
         requires_b=(Ref("local:heat-transfer"), Ref("local:control-theory"))),
    Case("duplicate-anchor-cannot-double-count",
         requires_a=(Ref("local:heat-transfer"), Ref("local:heat-transfer")),
         requires_b=(Ref("local:heat-transfer"),)),
)


def main() -> int:
    rows = []
    for case in CASES:
        rows.append({
            "case": case.name,
            "role_blind_jaccard": role_blind_jaccard(case),
            "required_overlap": knowledge_score(case.requires_a, case.requires_b),
            "a_requires_b_about": knowledge_score(case.requires_a, case.about_b),
            "b_requires_a_about": knowledge_score(case.requires_b, case.about_a),
        })

    by_name = {row["case"]: row for row in rows}
    assert by_name["same-topic-different-requirements"]["role_blind_jaccard"] > 0
    assert by_name["same-topic-different-requirements"]["required_overlap"] == 0.0
    assert by_name["different-words-same-requirement"]["required_overlap"] == 1.0
    assert by_name["cross-domain-structural-analogy"]["required_overlap"] == 0.0
    assert by_name["generic-hub-only"]["required_overlap"] is None
    assert by_name["cross-scheme-exact-map"]["required_overlap"] == 1.0
    assert 0.0 < by_name["hierarchy-is-weak-evidence"]["required_overlap"] < 0.5
    assert by_name["directional-complement"]["a_requires_b_about"] == 1.0
    assert by_name["directional-complement"]["b_requires_a_about"] is None
    assert by_name["missing-annotations"]["required_overlap"] is None
    assert 0.0 < by_name["partial-overlap"]["required_overlap"] < 1.0
    assert by_name["duplicate-anchor-cannot-double-count"]["required_overlap"] < 1.0

    print(json.dumps({"run": "R0-E-REPEAT-V9K2", "cases": rows}, indent=2))
    print("PROBE_STATUS: PASS (12/12 contract assertions)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
