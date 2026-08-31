"""R0-D repeat: audit guarded edge-to-path matching and its benchmark gate.

The synthetic cases compare three policies against one direct ``causes`` edge:

* exact-only: no edge-to-path match;
* naive: any homogeneous causes path of length 2..4;
* guarded: the machine-checkable v0.1 invariance rules.

The final pair is deliberately observationally equal to a transparent path but
has a meaningful mediator in its source interpretation.  It demonstrates that
the guard is only as sound as the ``atomic=false`` annotation.

The benchmark audit is read-only.  It does not modify frozen fixtures.

Run:
    python3 research/experiments/R0_D_repeat_contraction_audit.py

Dependencies: Python standard library only.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable


ROOT = Path(__file__).resolve().parents[2]
BENCHMARK = ROOT / "benchmark" / "r0-v0.1"
SAFE_INTERMEDIATE_ROLES = frozenset({"mechanism", "state"})
MAX_PATH_RELATIONS = 4


@dataclass(frozen=True)
class Node:
    id: str
    role: str = "mechanism"
    atomic: bool = False
    assertion: str = "asserted"
    modality: str = "actual"


@dataclass(frozen=True)
class Relation:
    id: str
    source: str
    target: str
    type: str = "causes"
    assertion: str = "asserted"
    modality: str = "actual"
    confidence: float = 1.0


@dataclass(frozen=True)
class Case:
    name: str
    nodes: tuple[Node, ...]
    path: tuple[Relation, ...]
    extra_relations: tuple[Relation, ...] = field(default_factory=tuple)
    expected_match: bool = False
    note: str = ""


def chain_case(
    name: str,
    *,
    intermediate_count: int = 1,
    expected: bool,
    role: str = "mechanism",
    atomic: bool = False,
    relation_types: tuple[str, ...] | None = None,
    edge_assertions: tuple[str, ...] | None = None,
    edge_modalities: tuple[str, ...] | None = None,
    node_modality: str = "actual",
    extra_relations: tuple[Relation, ...] = (),
    note: str = "",
) -> Case:
    ids = ("a",) + tuple(f"x{i}" for i in range(intermediate_count)) + ("b",)
    nodes = (
        Node("a", role="state", atomic=True),
        *(Node(node_id, role=role, atomic=atomic, modality=node_modality) for node_id in ids[1:-1]),
        Node("b", role="outcome", atomic=True),
    )
    edge_count = len(ids) - 1
    relation_types = relation_types or ("causes",) * edge_count
    edge_assertions = edge_assertions or ("asserted",) * edge_count
    edge_modalities = edge_modalities or ("actual",) * edge_count
    path = tuple(
        Relation(f"r{index}", ids[index], ids[index + 1], relation_types[index], edge_assertions[index], edge_modalities[index])
        for index in range(edge_count)
    )
    return Case(name, tuple(nodes), path, extra_relations, expected, note)


CASES = (
    chain_case("transparent_one_step", expected=True),
    chain_case("transparent_three_steps", intermediate_count=3, expected=True),
    chain_case("too_long", intermediate_count=4, expected=False),
    chain_case("atomic_mediator", expected=False, atomic=True),
    chain_case("outcome_mediator", expected=False, role="outcome"),
    chain_case("constraint_mediator", expected=False, role="constraint"),
    chain_case("evidence_mediator", expected=False, role="evidence"),
    chain_case(
        "branch_at_mediator",
        expected=False,
        extra_relations=(Relation("branch", "x0", "z"),),
    ),
    chain_case(
        "merge_at_mediator",
        expected=False,
        extra_relations=(Relation("merge", "z", "x0"),),
    ),
    chain_case(
        "sign_flip",
        expected=False,
        relation_types=("causes", "prevents"),
    ),
    chain_case(
        "relation_mixture",
        expected=False,
        relation_types=("causes", "supports"),
    ),
    chain_case(
        "negated_edge",
        expected=False,
        edge_assertions=("asserted", "negated"),
    ),
    chain_case(
        "modal_boundary",
        expected=False,
        edge_modalities=("actual", "conditional"),
    ),
    chain_case(
        "modal_intermediate_node",
        expected=False,
        node_modality="conditional",
    ),
    chain_case(
        "meaningful_but_misannotated",
        expected=False,
        note="All v0.1 machine fields equal transparent_one_step; only source interpretation says the mediator is meaningful.",
    ),
)


def exact_only(_case: Case) -> bool:
    return False


def naive_path(case: Case) -> bool:
    return 2 <= len(case.path) <= MAX_PATH_RELATIONS and all(edge.type == "causes" for edge in case.path)


def guarded_path(case: Case) -> bool:
    if not naive_path(case):
        return False
    if len({edge.source for edge in case.path} | {case.path[-1].target}) != len(case.path) + 1:
        return False
    nodes = {node.id: node for node in case.nodes}
    all_relations = case.path + case.extra_relations
    indegree = {node_id: 0 for node_id in nodes}
    outdegree = {node_id: 0 for node_id in nodes}
    for edge in all_relations:
        if edge.source in outdegree:
            outdegree[edge.source] += 1
        if edge.target in indegree:
            indegree[edge.target] += 1
    for node_id in tuple(edge.target for edge in case.path[:-1]):
        node = nodes[node_id]
        if node.atomic or node.role not in SAFE_INTERMEDIATE_ROLES:
            return False
        if node.assertion != "asserted" or node.modality != "actual":
            return False
        if indegree[node_id] != 1 or outdegree[node_id] != 1:
            return False
    return all(edge.assertion == "asserted" and edge.modality == "actual" for edge in case.path)


def metrics(policy: Callable[[Case], bool]) -> dict[str, object]:
    rows = [(case, policy(case)) for case in CASES]
    tp = sum(predicted and case.expected_match for case, predicted in rows)
    fp = sum(predicted and not case.expected_match for case, predicted in rows)
    fn = sum(not predicted and case.expected_match for case, predicted in rows)
    tn = sum(not predicted and not case.expected_match for case, predicted in rows)
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "precision": round(tp / (tp + fp), 4) if tp + fp else None,
        "recall": round(tp / (tp + fn), 4) if tp + fn else None,
        "false_positive_cases": [case.name for case, predicted in rows if predicted and not case.expected_match],
        "false_negative_cases": [case.name for case, predicted in rows if not predicted and case.expected_match],
    }


def audit_benchmark() -> dict[str, object]:
    pairs = [json.loads(line) for line in (BENCHMARK / "pairs.jsonl").read_text().splitlines() if line]
    transparent = [pair for pair in pairs if pair["family"] == "transparent_granularity"]
    negative_ops = {
        "meaningful_subdivision",
        "forbidden_contraction",
        "atomic_mediator",
        "modal_boundary_subdivision",
    }
    explicit_negative_contractions = [
        pair for pair in pairs if pair.get("transform_manifest", {}).get("operation") in negative_ops
    ]
    runner = (BENCHMARK / "runner.py").read_text()
    prediction_schema = json.loads((BENCHMARK / "schema" / "prediction.schema.json").read_text())
    verification = prediction_schema["$defs"]["verification"]
    return {
        "transparent_positive_cases": len(transparent),
        "transparent_review_statuses": sorted({pair["review"]["status"] for pair in transparent}),
        "explicit_negative_contraction_cases": len(explicit_negative_contractions),
        "gold_fields_for_forbidden_contractions": sorted(
            set(pairs[0]) & {"must_preserve_nodes", "forbidden_edge_path_matches", "meaningful_nodes"}
        ),
        "prediction_requires_self_reported_false_contractions": "false_contractions" in verification["required"],
        "runner_sums_prediction_false_contractions": 'sum(row["false_contractions"] for row in gate_rows)' in runner,
    }


if __name__ == "__main__":
    output = {
        "experiment": "R0-D-REPEAT-S7D3 contraction audit",
        "policies": {
            "exact_only": metrics(exact_only),
            "naive_path": metrics(naive_path),
            "guarded_path": metrics(guarded_path),
        },
        "machine_indistinguishable_pair": {
            "left": "transparent_one_step",
            "right": "meaningful_but_misannotated",
            "guard_results_equal": guarded_path(CASES[0]) == guarded_path(CASES[-1]),
            "gold_labels_equal": CASES[0].expected_match == CASES[-1].expected_match,
        },
        "frozen_benchmark_read_only_audit": audit_benchmark(),
    }
    print(json.dumps(output, indent=2, sort_keys=True))
