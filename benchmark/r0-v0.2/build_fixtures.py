#!/usr/bin/env python3
"""Build the deterministic Benchmark v0.2 contraction-audit corpus.

Frozen v0.1 assets are never written. This generator is the reviewable source
for v0.2 JSONL gold.
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
AGENT_ID = "parshkov-xai-grok46-k3e8"
SCHEMA_VERSION = "thought-dna/0.1"
APPROVALS = json.loads((ROOT / "review_approvals.json").read_text(encoding="utf-8"))
MAX_PATH_RELATIONS = 4


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def jsonl_bytes(records: list[dict[str, Any]]) -> bytes:
    return b"".join(canonical_bytes(record) + b"\n" for record in records)


def source_record(text: str) -> dict[str, str]:
    return {"text": text, "sha256": sha256_bytes(text.encode("utf-8"))}


def node(
    node_id: str,
    label: str,
    role: str,
    *,
    atomic: bool,
    assertion: str = "asserted",
    modality: str = "actual",
) -> dict[str, Any]:
    return {
        "id": node_id,
        "label": label,
        "role": role,
        "spans": [],
        "extract_conf": 1.0,
        "atomic": atomic,
        "assertion": assertion,
        "modality": modality,
    }


def relation(
    rel_id: str,
    source: str,
    target: str,
    rel_type: str = "causes",
    *,
    assertion: str = "asserted",
    modality: str = "actual",
) -> dict[str, Any]:
    return {
        "id": rel_id,
        "source": source,
        "target": target,
        "type": rel_type,
        "extract_conf": 1.0,
        "spans": [],
        "assertion": assertion,
        "modality": modality,
    }


def make_graph(graph_id: str, nodes: list[dict[str, Any]], relations: list[dict[str, Any]]) -> dict[str, Any]:
    text = f"Manual benchmark graph {graph_id}."
    return {
        "benchmark_graph_id": graph_id,
        "thought_dna": {
            "schema_version": SCHEMA_VERSION,
            "thought_id": graph_id,
            "source": source_record(text),
            "provenance": {"kind": "manual", "extractor": None, "human_id": AGENT_ID},
            "nodes": deepcopy(nodes),
            "relations": deepcopy(relations),
        },
    }


def chain(
    *,
    intermediate_count: int,
    role: str = "mechanism",
    atomic: bool = False,
    types: tuple[str, ...] | None = None,
    edge_assertions: tuple[str, ...] | None = None,
    edge_modalities: tuple[str, ...] | None = None,
    node_modality: str = "actual",
    labels: tuple[str, ...] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str], list[str]]:
    interiors = [f"x{i}" for i in range(intermediate_count)]
    ids = ["n0", *interiors, "n1"]
    default_labels = tuple(f"transparent step {i}" for i in range(intermediate_count))
    labels = labels or default_labels
    nodes = [node("n0", "heat accumulation", "state", atomic=True), node("n1", "failure", "outcome", atomic=True)]
    for interior_id, label in zip(interiors, labels, strict=True):
        nodes.append(node(interior_id, label, role, atomic=atomic, modality=node_modality))
    edge_count = len(ids) - 1
    types = types or ("causes",) * edge_count
    edge_assertions = edge_assertions or ("asserted",) * edge_count
    edge_modalities = edge_modalities or ("actual",) * edge_count
    rel_ids = [f"r{i}" for i in range(edge_count)]
    rels = [
        relation(rel_ids[i], ids[i], ids[i + 1], types[i], assertion=edge_assertions[i], modality=edge_modalities[i])
        for i in range(edge_count)
    ]
    return nodes, rels, rel_ids, interiors


QUERY = make_graph(
    "V02-Q",
    [node("n0", "heat accumulation", "state", atomic=True), node("n1", "failure", "outcome", atomic=True)],
    [relation("rq", "n0", "n1")],
)


def _case(
    index: int,
    family: str,
    *,
    relevant: bool,
    nodes: list[dict[str, Any]],
    rels: list[dict[str, Any]],
    path_rel_ids: list[str],
    interiors: list[str],
    extra_nodes: list[dict[str, Any]] | None = None,
    extra_relations: list[dict[str, Any]] | None = None,
    licensed: bool = False,
    must_preserve: list[str] | None = None,
    meaningful: list[str] | None = None,
    review_required: bool = False,
    rationale: str,
    note: str = "",
    split: str = "gate",
) -> tuple[dict[str, Any], dict[str, Any]]:
    candidate_id = f"V02-C{index:02d}"
    all_nodes = nodes + list(extra_nodes or [])
    all_rels = rels + list(extra_relations or [])
    graph = make_graph(candidate_id, all_nodes, all_rels)
    path_pair = ["rq", path_rel_ids]
    if review_required:
        reviewer = APPROVALS["pair_approvals"].get(f"V02-{index:02d}")
        review = {
            "required": True,
            "status": "approved" if reviewer else "pending",
            "reviewer": reviewer,
        }
    else:
        review = {"required": False, "status": "generated", "reviewer": None}
    pair = {
        "case_id": f"V02-{index:02d}",
        "pack_id": "V02",
        "split": split,
        "family": family,
        "query_graph": "V02-Q",
        "candidate_graph": candidate_id,
        "gold_class": "approximate" if relevant else "negative",
        "evaluation_mode": "structural",
        "relevant": relevant,
        "gold_node_pairs": [["n0", "n0"], ["n1", "n1"]],
        "gold_edge_pairs": [path_pair] if licensed else [],
        "meaningful_nodes": list(meaningful or []),
        "must_preserve_nodes": list(must_preserve if must_preserve is not None else ([] if licensed else interiors)),
        "forbidden_edge_path_matches": [] if licensed else [path_pair],
        "transform_manifest": {
            "operation": family,
            "path_relation_ids": path_rel_ids,
            "interior_nodes": interiors,
            "max_path_relations": MAX_PATH_RELATIONS,
            "note": note,
        },
        "rationale": rationale,
        "review": review,
    }
    return graph, pair


def build_records() -> dict[str, list[dict[str, Any]]]:
    graphs = [QUERY]
    pairs: list[dict[str, Any]] = []

    specs: list[dict[str, Any]] = []

    n, r, ids, interiors = chain(intermediate_count=1)
    specs.append(dict(
        family="transparent_one_step", relevant=True, nodes=n, rels=r, path_rel_ids=ids,
        interiors=interiors, licensed=True, split="calibration",
        rationale="A single causes edge is reversibly subdivided through an atomic=false mechanism of degree one.",
    ))
    n, r, ids, interiors = chain(intermediate_count=3)
    specs.append(dict(
        family="transparent_three_steps", relevant=True, nodes=n, rels=r, path_rel_ids=ids,
        interiors=interiors, licensed=True,
        rationale="A homogeneous causes path of length four through atomic=false mechanisms remains a licensed contraction.",
    ))
    n, r, ids, interiors = chain(intermediate_count=1, atomic=True, labels=("atomic mechanism",))
    specs.append(dict(
        family="atomic_mediator", relevant=False, nodes=n, rels=r, path_rel_ids=ids, interiors=interiors,
        rationale="An atomic=true mediator is independently meaningful and must not be contracted.",
    ))
    n, r, ids, interiors = chain(intermediate_count=1, labels=("insulin secretion",))
    specs.append(dict(
        family="meaningful_mediator", relevant=False, nodes=n, rels=r, path_rel_ids=ids, interiors=interiors,
        meaningful=["x0"], must_preserve=["x0"], review_required=True,
        note="Machine fields equal transparent_one_step; gold, not atomic=false, marks the mediator meaningful.",
        rationale="Gold records the mediator as independently meaningful even though atomic=false. Contracting it is a false contraction.",
    ))
    n, r, ids, interiors = chain(intermediate_count=1, role="outcome", labels=("intermediate outcome",))
    specs.append(dict(
        family="outcome_mediator", relevant=False, nodes=n, rels=r, path_rel_ids=ids, interiors=interiors,
        rationale="An outcome-role mediator is not a licensed transparent elaboration.",
    ))
    n, r, ids, interiors = chain(intermediate_count=1, role="constraint", labels=("budget constraint",))
    specs.append(dict(
        family="constraint_mediator", relevant=False, nodes=n, rels=r, path_rel_ids=ids, interiors=interiors,
        rationale="A constraint mediator must be preserved; contraction would erase a governing restriction.",
    ))
    n, r, ids, interiors = chain(intermediate_count=1, role="evidence", labels=("observational evidence",))
    specs.append(dict(
        family="evidence_mediator", relevant=False, nodes=n, rels=r, path_rel_ids=ids, interiors=interiors,
        rationale="Evidence nodes are provenance anchors and are not licensed intermediates.",
    ))
    n, r, ids, interiors = chain(intermediate_count=1, labels=("branching mediator",))
    specs.append(dict(
        family="branch_at_mediator", relevant=False, nodes=n, rels=r, path_rel_ids=ids, interiors=interiors,
        extra_nodes=[node("z0", "side branch", "outcome", atomic=True)],
        extra_relations=[relation("rb", "x0", "z0")],
        rationale="A branch at the mediator makes degree>1; contraction is forbidden.",
    ))
    n, r, ids, interiors = chain(intermediate_count=1, labels=("merging mediator",))
    specs.append(dict(
        family="merge_at_mediator", relevant=False, nodes=n, rels=r, path_rel_ids=ids, interiors=interiors,
        extra_nodes=[node("z0", "alternate cause", "mechanism", atomic=True)],
        extra_relations=[relation("rm", "z0", "x0")],
        rationale="A merge into the mediator makes degree>1; contraction is forbidden.",
    ))
    n, r, ids, interiors = chain(intermediate_count=1, types=("causes", "prevents"), labels=("sign-flipped step",))
    specs.append(dict(
        family="sign_flip", relevant=False, nodes=n, rels=r, path_rel_ids=ids, interiors=interiors,
        rationale="causes then prevents is not a licensed homogeneous causes path.",
    ))
    n, r, ids, interiors = chain(intermediate_count=1, types=("causes", "supports"), labels=("type-mixed step",))
    specs.append(dict(
        family="relation_mixture", relevant=False, nodes=n, rels=r, path_rel_ids=ids, interiors=interiors,
        rationale="Unknown relation composition does not contract.",
    ))
    n, r, ids, interiors = chain(intermediate_count=1, edge_assertions=("asserted", "negated"), labels=("negated step",))
    specs.append(dict(
        family="assertion_boundary", relevant=False, nodes=n, rels=r, path_rel_ids=ids, interiors=interiors,
        rationale="An asserted/negated boundary is an anti-invariance, not a granularity change.",
    ))
    n, r, ids, interiors = chain(intermediate_count=1, edge_modalities=("actual", "conditional"), labels=("modal edge",))
    specs.append(dict(
        family="modality_boundary", relevant=False, nodes=n, rels=r, path_rel_ids=ids, interiors=interiors,
        rationale="An actual/conditional edge boundary forbids contraction.",
    ))
    n, r, ids, interiors = chain(intermediate_count=1, node_modality="conditional", labels=("modal node",))
    specs.append(dict(
        family="modal_intermediate_node", relevant=False, nodes=n, rels=r, path_rel_ids=ids, interiors=interiors,
        rationale="A non-actual intermediate node is a modal boundary.",
    ))
    n, r, ids, interiors = chain(intermediate_count=4)
    specs.append(dict(
        family="path_too_long", relevant=False, nodes=n, rels=r, path_rel_ids=ids, interiors=interiors,
        rationale="Five relations exceed the v0.1 max licensed path length of four.",
    ))

    for index, spec in enumerate(specs, start=1):
        graph, pair = _case(index, **spec)
        graphs.append(graph)
        pairs.append(pair)
    return {"graphs.jsonl": graphs, "pairs.jsonl": pairs}


TRACKED = [
    "graphs.jsonl",
    "pairs.jsonl",
    "config/evaluation-v0.2.json",
    "schema/graph.schema.json",
    "schema/pair.schema.json",
    "schema/prediction.schema.json",
    "schema/report.schema.json",
    "review_approvals.json",
]


def build_manifest() -> dict[str, Any]:
    records = build_records()
    files: dict[str, Any] = {}
    for relative in TRACKED:
        payload = jsonl_bytes(records[relative]) if relative in records else (ROOT / relative).read_bytes()
        item: dict[str, Any] = {"sha256": sha256_bytes(payload), "bytes": len(payload)}
        if relative in records:
            item["records"] = len(records[relative])
        files[relative] = item
    pending = sum(1 for pair in records["pairs.jsonl"] if pair["review"]["required"] and pair["review"]["status"] != "approved")
    return {
        "benchmark_version": "r0-v0.2",
        "manifest_version": "resonance-benchmark-manifest/0.2",
        "thought_dna_schema": SCHEMA_VERSION,
        "freeze_state": "candidate_frozen_pending_independent_review" if pending else "independent_review_complete",
        "counts": {
            "graphs": len(records["graphs.jsonl"]),
            "pairs": len(records["pairs.jsonl"]),
            "positives": sum(pair["relevant"] for pair in records["pairs.jsonl"]),
            "negatives": sum(not pair["relevant"] for pair in records["pairs.jsonl"]),
            "manual_reviews_pending": pending,
        },
        "files": files,
        "extends": "r0-v0.1",
        "does_not_mutate": "benchmark/r0-v0.1",
        "provenance": {
            "agent_id": AGENT_ID,
            "human_sponsor": "Parshkov",
            "provider": "xAI",
            "model": "Grok 4.6",
            "runtime": "Python 3.12 stdlib; src.graph Thought DNA validator",
            "source_issue": 56,
        },
    }


def write_corpus() -> None:
    records = build_records()
    for relative, items in records.items():
        (ROOT / relative).write_bytes(jsonl_bytes(items))
    manifest = build_manifest()
    (ROOT / "manifest.json").write_bytes(canonical_bytes(manifest) + b"\n")
    (ROOT / "manifest.sha256").write_text(sha256_bytes(canonical_bytes(manifest)) + "\n", encoding="utf-8")


if __name__ == "__main__":
    write_corpus()
    print(json.dumps(build_manifest()["counts"], indent=2, sort_keys=True))
