"""Executable falsifier for benchmark-owned contraction judgments.

This experiment models the minimum v0.2 contract needed to make the
``false_meaningful_contractions == 0`` gate auditable.  A candidate emits
canonical edge-to-path mappings.  The evaluator reconstructs each realized
path, checks independently reviewed preservation gold, and derives the count;
the candidate's legacy self-reported counter is retained only to demonstrate
that it cannot grant PASS.

The frozen v0.1 bundle is inspected read-only and is never rewritten.

Run:
    python3 research/experiments/R0_G_repeat_benchmark_audit.py

Dependencies: Python 3.11+ standard library only.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable


ROOT = Path(__file__).resolve().parents[2]
V01 = ROOT / "benchmark" / "r0-v0.1"


@dataclass(frozen=True)
class Relation:
    relation_id: str
    source: str
    target: str
    relation_type: str = "causes"
    assertion: str = "asserted"
    modality: str = "actual"


@dataclass(frozen=True)
class ContractionCase:
    case_id: str
    family: str
    expected_match: bool
    candidate_relations: tuple[Relation, ...]
    allowed_edge_path_matches: tuple[tuple[str, tuple[str, ...]], ...] = ()
    forbidden_edge_path_matches: tuple[tuple[str, tuple[str, ...]], ...] = ()
    must_preserve_nodes: tuple[str, ...] = ()


@dataclass(frozen=True)
class EdgePathPrediction:
    query_relation_id: str
    candidate_relation_ids: tuple[str, ...]
    realized_candidate_nodes: tuple[str, ...]


@dataclass(frozen=True)
class Prediction:
    case_id: str
    edge_path_matches: tuple[EdgePathPrediction, ...]
    reported_false_contractions: int


def chain(
    case_id: str,
    family: str,
    *,
    relation_count: int = 2,
    expected_match: bool = False,
    preserve: bool = False,
    relation_types: tuple[str, ...] | None = None,
    assertions: tuple[str, ...] | None = None,
    modalities: tuple[str, ...] | None = None,
) -> ContractionCase:
    node_ids = ("c-a",) + tuple(f"c-x{i}" for i in range(relation_count - 1)) + ("c-b",)
    relation_types = relation_types or ("causes",) * relation_count
    assertions = assertions or ("asserted",) * relation_count
    modalities = modalities or ("actual",) * relation_count
    relations = tuple(
        Relation(
            relation_id=f"c-r{index}",
            source=node_ids[index],
            target=node_ids[index + 1],
            relation_type=relation_types[index],
            assertion=assertions[index],
            modality=modalities[index],
        )
        for index in range(relation_count)
    )
    match = ("q-r0", tuple(relation.relation_id for relation in relations))
    intermediate = node_ids[1:-1]
    return ContractionCase(
        case_id=case_id,
        family=family,
        expected_match=expected_match,
        candidate_relations=relations,
        allowed_edge_path_matches=(match,) if expected_match else (),
        forbidden_edge_path_matches=() if expected_match else (match,),
        must_preserve_nodes=intermediate if preserve else (),
    )


CASES = (
    chain("T01", "transparent_mediator", expected_match=True),
    chain("T02", "transparent_longer", relation_count=3, expected_match=True),
    chain("N01", "meaningful_mediator", preserve=True),
    chain("N02", "atomic_mediator", preserve=True),
    chain("N03", "branching_mediator", preserve=True),
    chain("N04", "merging_mediator", preserve=True),
    chain("N05", "mixed_relation", relation_types=("causes", "supports")),
    chain("N06", "sign_boundary", relation_types=("causes", "prevents")),
    chain("N07", "modality_boundary", modalities=("actual", "conditional")),
    chain("N08", "assertion_boundary", assertions=("asserted", "negated")),
    chain("N09", "path_length_limit", relation_count=5),
)


def canonical_path(case: ContractionCase) -> EdgePathPrediction:
    relations = case.candidate_relations
    return EdgePathPrediction(
        query_relation_id="q-r0",
        candidate_relation_ids=tuple(relation.relation_id for relation in relations),
        realized_candidate_nodes=(relations[0].source,) + tuple(relation.target for relation in relations),
    )


def predict_none(case: ContractionCase) -> Prediction:
    return Prediction(case.case_id, (), 0)


def predict_everything_report_zero(case: ContractionCase) -> Prediction:
    return Prediction(case.case_id, (canonical_path(case),), 0)


def predict_everything_report_honestly(case: ContractionCase) -> Prediction:
    return Prediction(case.case_id, (canonical_path(case),), int(not case.expected_match))


def predict_gold_compliant(case: ContractionCase) -> Prediction:
    matches = (canonical_path(case),) if case.expected_match else ()
    return Prediction(case.case_id, matches, 0)


def realized_path_nodes(case: ContractionCase, relation_ids: tuple[str, ...]) -> tuple[str, ...] | None:
    relations_by_id = {relation.relation_id: relation for relation in case.candidate_relations}
    try:
        relations = tuple(relations_by_id[relation_id] for relation_id in relation_ids)
    except KeyError:
        return None
    if not relations:
        return None
    for left, right in zip(relations, relations[1:]):
        if left.target != right.source:
            return None
    return (relations[0].source,) + tuple(relation.target for relation in relations)


def evaluate(policy: Callable[[ContractionCase], Prediction]) -> dict[str, object]:
    expected_positive = sum(case.expected_match for case in CASES)
    matched_positive = 0
    derived_false_contractions: list[str] = []
    malformed_outputs: list[str] = []
    reported_false_contractions = 0

    for case in CASES:
        prediction = policy(case)
        reported_false_contractions += prediction.reported_false_contractions
        case_matched = False
        seen: set[tuple[str, tuple[str, ...]]] = set()
        for match in prediction.edge_path_matches:
            key = (match.query_relation_id, match.candidate_relation_ids)
            derived_nodes = realized_path_nodes(case, match.candidate_relation_ids)
            if key in seen or derived_nodes is None or match.realized_candidate_nodes != derived_nodes:
                malformed_outputs.append(case.case_id)
                continue
            seen.add(key)
            intermediate_nodes = set(derived_nodes[1:-1])
            forbidden = key in set(case.forbidden_edge_path_matches)
            destroys_preserved_node = bool(intermediate_nodes & set(case.must_preserve_nodes))
            allowed = key in set(case.allowed_edge_path_matches)
            if forbidden or destroys_preserved_node or not allowed:
                derived_false_contractions.append(case.case_id)
            elif case.expected_match:
                case_matched = True
        matched_positive += int(case.expected_match and case_matched)

    transparent_recall = matched_positive / expected_positive
    passed = (
        transparent_recall == 1.0
        and not derived_false_contractions
        and not malformed_outputs
    )
    return {
        "transparent_recall": transparent_recall,
        "reported_false_contractions": reported_false_contractions,
        "derived_false_contractions": len(derived_false_contractions),
        "derived_false_contraction_cases": sorted(set(derived_false_contractions)),
        "malformed_output_cases": sorted(set(malformed_outputs)),
        "gate_status": "pass" if passed else "fail",
    }


def audit_frozen_v01() -> dict[str, object]:
    pairs = [json.loads(line) for line in (V01 / "pairs.jsonl").read_text().splitlines() if line]
    pair_schema = json.loads((V01 / "schema" / "pair.schema.json").read_text())
    prediction_schema = json.loads((V01 / "schema" / "prediction.schema.json").read_text())
    runner_text = (V01 / "runner.py").read_text()
    gold_properties = set(pair_schema["properties"])
    verification = prediction_schema["$defs"]["verification"]
    return {
        "transparent_positive_cases": sum(pair["family"] == "transparent_granularity" for pair in pairs),
        "explicit_negative_contraction_cases": sum(
            pair.get("transform_manifest", {}).get("operation")
            in {"meaningful_subdivision", "forbidden_contraction", "atomic_mediator"}
            for pair in pairs
        ),
        "preservation_gold_fields": sorted(
            gold_properties & {"must_preserve_nodes", "forbidden_edge_path_matches", "meaningful_nodes"}
        ),
        "prediction_has_structured_edge_path_matches": "edge_path_matches" in verification["properties"],
        "prediction_requires_self_reported_counter": "false_contractions" in verification["required"],
        "runner_sums_self_reported_counter": (
            'sum(row["false_contractions"] for row in gate_rows)' in runner_text
        ),
    }


def fixture_digest() -> str:
    payload = json.dumps([asdict(case) for case in CASES], sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def main() -> None:
    results = {
        "exact_only": evaluate(predict_none),
        "cheating_self_report_zero": evaluate(predict_everything_report_zero),
        "naive_honest_self_report": evaluate(predict_everything_report_honestly),
        "gold_compliant": evaluate(predict_gold_compliant),
    }

    assert results["exact_only"]["gate_status"] == "fail"
    assert results["exact_only"]["derived_false_contractions"] == 0
    assert results["cheating_self_report_zero"]["reported_false_contractions"] == 0
    assert results["cheating_self_report_zero"]["derived_false_contractions"] == 9
    assert results["cheating_self_report_zero"]["gate_status"] == "fail"
    assert results["gold_compliant"]["gate_status"] == "pass"

    output = {
        "experiment": "R0-G-REPEAT-F6A9 benchmark-owned contraction oracle",
        "fixture_sha256": fixture_digest(),
        "case_count": len(CASES),
        "families": [case.family for case in CASES],
        "policies": results,
        "frozen_v01_read_only_audit": audit_frozen_v01(),
        "conclusion": (
            "A candidate that maps every path and self-reports zero is rejected; "
            "only evaluator-derived preservation checks can grant PASS."
        ),
    }
    print(json.dumps(output, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
