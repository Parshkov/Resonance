#!/usr/bin/env python3
"""Deterministic validator and non-compensating Benchmark v0.1 evaluator.

This module evaluates external engine predictions. It deliberately contains no
retrieval, extraction, alignment, scoring, or threshold-tuning algorithm.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.graph import ThoughtDNAValidationError, validate_thought  # noqa: E402


class BenchmarkError(ValueError):
    """Raised when frozen fixtures or submitted predictions are malformed."""


@dataclass(frozen=True)
class FixtureBundle:
    graphs: tuple[dict[str, Any], ...]
    pairs: tuple[dict[str, Any], ...]
    extraction_runs: tuple[dict[str, Any], ...]
    e1_cases: tuple[dict[str, Any], ...]
    config: dict[str, Any]
    manifest: dict[str, Any]
    manifest_sha256: str
    config_sha256: str
    summary: dict[str, Any]


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    records = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            raise BenchmarkError(f"{path.name}:{line_number}: blank JSONL records are forbidden")
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise BenchmarkError(f"{path.name}:{line_number}: {exc}") from exc
        if not isinstance(value, dict):
            raise BenchmarkError(f"{path.name}:{line_number}: record must be an object")
        records.append(value)
    return records


def require_exact_fields(record: Mapping[str, Any], fields: set[str], context: str) -> None:
    missing = sorted(fields - set(record))
    extra = sorted(set(record) - fields)
    if missing or extra:
        raise BenchmarkError(f"{context}: closed record mismatch; missing={missing}, extra={extra}")


def ensure_pair_list(value: Any, context: str, *, edge: bool = False) -> None:
    if not isinstance(value, list):
        raise BenchmarkError(f"{context}: must be a list")
    for index, pair in enumerate(value):
        if not isinstance(pair, list) or len(pair) != 2 or not isinstance(pair[0], str):
            raise BenchmarkError(f"{context}[{index}]: must be a two-item pair")
        if edge and isinstance(pair[1], list):
            if not pair[1] or not all(isinstance(item, str) for item in pair[1]):
                raise BenchmarkError(f"{context}[{index}][1]: edge path must be non-empty strings")
        elif not isinstance(pair[1], str):
            raise BenchmarkError(f"{context}[{index}][1]: must be a string")


def _forbidden_gold_key(value: Any) -> str | None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if key.startswith("gold_") or key in {"relevant", "rationale", "review", "family"}:
                return key
            found = _forbidden_gold_key(child)
            if found:
                return found
    elif isinstance(value, list):
        for child in value:
            found = _forbidden_gold_key(child)
            if found:
                return found
    return None


def _verify_manifest(manifest: dict[str, Any]) -> str:
    for relative, expected in manifest.get("files", {}).items():
        path = ROOT / relative
        if not path.is_file():
            raise BenchmarkError(f"manifest file is missing: {relative}")
        payload = path.read_bytes()
        actual = hashlib.sha256(payload).hexdigest()
        if actual != expected.get("sha256"):
            raise BenchmarkError(f"manifest hash mismatch for {relative}: {actual} != {expected.get('sha256')}")
        if len(payload) != expected.get("bytes"):
            raise BenchmarkError(f"manifest byte count mismatch for {relative}")
    digest = canonical_sha256(manifest)
    recorded = (ROOT / "manifest.sha256").read_text(encoding="utf-8").strip()
    if digest != recorded:
        raise BenchmarkError(f"manifest.sha256 mismatch: {digest} != {recorded}")
    return digest


def _verify_generated_assets() -> None:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from build_fixtures import build_records, jsonl_bytes

    for relative, records in build_records().items():
        expected = jsonl_bytes(records)
        actual = (ROOT / relative).read_bytes()
        if actual != expected:
            raise BenchmarkError(f"{relative} differs from deterministic build_fixtures.py output")


def validate_fixtures() -> FixtureBundle:
    """Validate hashes, closed records, Thought DNA, split topology and E1 matrix."""
    graphs = read_jsonl(ROOT / "graphs.jsonl")
    pairs = read_jsonl(ROOT / "pairs.jsonl")
    extraction_runs = read_jsonl(ROOT / "extraction_runs.jsonl")
    e1_cases = read_jsonl(ROOT / "e1_cases.jsonl")
    config = json.loads((ROOT / "config/evaluation-v0.1.json").read_text(encoding="utf-8"))
    manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))

    expected_counts = {"graphs": 136, "pairs": 128, "extraction_runs": 16, "e1_matrix_cases": 12}
    actual_counts = {
        "graphs": len(graphs),
        "pairs": len(pairs),
        "extraction_runs": len(extraction_runs),
        "e1_matrix_cases": len(e1_cases),
    }
    if actual_counts != expected_counts:
        raise BenchmarkError(f"fixture counts changed: {actual_counts} != {expected_counts}")

    graph_by_id: dict[str, dict[str, Any]] = {}
    for index, wrapper in enumerate(graphs):
        require_exact_fields(wrapper, {"benchmark_graph_id", "thought_dna"}, f"graphs[{index}]")
        graph_id = wrapper["benchmark_graph_id"]
        if not isinstance(graph_id, str) or graph_id in graph_by_id:
            raise BenchmarkError(f"graphs[{index}]: duplicate or invalid benchmark_graph_id")
        thought = wrapper["thought_dna"]
        if _forbidden_gold_key(thought):
            raise BenchmarkError(f"{graph_id}: benchmark gold leaked into engine graph input")
        try:
            validate_thought(thought)
        except ThoughtDNAValidationError as exc:
            raise BenchmarkError(f"{graph_id}: invalid Thought DNA: {exc}") from exc
        if thought["thought_id"] != graph_id:
            raise BenchmarkError(f"{graph_id}: thought_id must equal benchmark_graph_id")
        graph_by_id[graph_id] = wrapper

    pair_fields = {
        "case_id", "pack_id", "split", "family", "query_graph", "candidate_graph",
        "gold_class", "evaluation_mode", "relevant", "gold_node_pairs", "gold_edge_pairs",
        "equivalent_mapping_sets", "bridge_pairs", "transform_manifest", "rationale", "review",
    }
    pair_ids: set[str] = set()
    pack_families: dict[str, set[str]] = defaultdict(set)
    manual_unapproved = 0
    for index, pair in enumerate(pairs):
        context = f"pairs[{index}]"
        require_exact_fields(pair, pair_fields, context)
        case_id = pair["case_id"]
        if case_id in pair_ids:
            raise BenchmarkError(f"{context}: duplicate case_id {case_id}")
        pair_ids.add(case_id)
        if pair["query_graph"] not in graph_by_id or pair["candidate_graph"] not in graph_by_id:
            raise BenchmarkError(f"{case_id}: graph reference does not resolve")
        if pair["relevant"] != (pair["gold_class"] != "negative"):
            raise BenchmarkError(f"{case_id}: relevant disagrees with gold_class")
        ensure_pair_list(pair["gold_node_pairs"], f"{case_id}.gold_node_pairs")
        ensure_pair_list(pair["gold_edge_pairs"], f"{case_id}.gold_edge_pairs", edge=True)
        ensure_pair_list(pair["bridge_pairs"], f"{case_id}.bridge_pairs")
        if not isinstance(pair["equivalent_mapping_sets"], list):
            raise BenchmarkError(f"{case_id}.equivalent_mapping_sets must be a list")
        review = pair["review"]
        require_exact_fields(review, {"required", "status", "reviewer"}, f"{case_id}.review")
        if review["required"] and review["status"] != "approved":
            manual_unapproved += 1
        if review["required"] and review["status"] == "generated":
            raise BenchmarkError(f"{case_id}: required human judgment cannot be self-approved as generated")
        if review["status"] == "approved" and (not review["reviewer"] or review["reviewer"] == "parshkov-openai-gpt5-codex-s7d3"):
            raise BenchmarkError(f"{case_id}: approval must name an independent public reviewer")
        pack_families[pair["pack_id"]].add(pair["family"])

    if set(pack_families) != {"C01", "C02", "G01", "G02", "G03", "G04", "G05", "G06"}:
        raise BenchmarkError("pack IDs changed")
    family_reference = set(next(iter(pack_families.values())))
    if len(family_reference) != 16 or any(families != family_reference for families in pack_families.values()):
        raise BenchmarkError("each pack must contain the same sixteen families")
    split_counts = Counter(pair["split"] for pair in pairs)
    if split_counts != Counter({"gate": 96, "calibration": 32}):
        raise BenchmarkError(f"split counts changed: {split_counts}")

    gate_wrong_structure = [
        pair for pair in pairs if pair["split"] == "gate" and pair["family"] == "same_vocabulary_wrong_structure"
    ]
    subtypes = Counter(pair["transform_manifest"].get("negative_subtype") for pair in gate_wrong_structure)
    if subtypes != Counter({"polarity_flip": 2, "direction_reversal": 2, "broader_rewire": 2}):
        raise BenchmarkError(f"family-10 gate subtype allocation changed: {subtypes}")

    extraction_ids: set[str] = set()
    extraction_unapproved = 0
    for index, record in enumerate(extraction_runs):
        fields = {"extraction_case_id", "pack_id", "split", "run_index", "input", "reference_thought_dna", "review"}
        require_exact_fields(record, fields, f"extraction_runs[{index}]")
        case_id = record["extraction_case_id"]
        if case_id in extraction_ids:
            raise BenchmarkError(f"duplicate extraction_case_id: {case_id}")
        extraction_ids.add(case_id)
        thought = record["reference_thought_dna"]
        try:
            validate_thought(thought)
        except ThoughtDNAValidationError as exc:
            raise BenchmarkError(f"{case_id}: invalid reference extraction: {exc}") from exc
        if record["input"] != thought["source"]:
            raise BenchmarkError(f"{case_id}: extraction input must exactly equal reference source")
        if record["review"]["required"] and record["review"]["status"] != "approved":
            extraction_unapproved += 1
        if record["review"]["status"] == "approved" and (not record["review"]["reviewer"] or record["review"]["reviewer"] == "parshkov-openai-gpt5-codex-s7d3"):
            raise BenchmarkError(f"{case_id}: extraction approval must name an independent public reviewer")
    if Counter(record["pack_id"] for record in extraction_runs) != Counter({pack: 2 for pack in pack_families}):
        raise BenchmarkError("each pack must contain exactly two extraction observations")

    thought_schema = json.loads((REPO_ROOT / "schemas/thought-dna-0.1.schema.json").read_text(encoding="utf-8"))
    exact_relations = set(thought_schema["$defs"]["relation"]["properties"]["type"]["enum"])
    matrix_keys: set[tuple[str, int, int]] = set()
    for case in e1_cases:
        require_exact_fields(
            case,
            {"case_id", "world", "corpus_size", "seed", "descriptors", "query_graph", "true_analogue", "generic_distractors", "polarity_flip", "direction_negative", "relation_vocabulary", "filler_recipe", "kill_rule"},
            case.get("case_id", "e1"),
        )
        for graph_id in [case["query_graph"], case["true_analogue"], case["polarity_flip"], case["direction_negative"], *case["generic_distractors"]]:
            if graph_id not in graph_by_id:
                raise BenchmarkError(f"{case['case_id']}: unresolved graph {graph_id}")
        if case["descriptors"] != ["D0", "D1", "MULTI"]:
            raise BenchmarkError(f"{case['case_id']}: D0/D1/MULTI are mandatory")
        if set(case["relation_vocabulary"]) != exact_relations:
            raise BenchmarkError(f"{case['case_id']}: E1 companion must use exact Thought DNA relation enums")
        matrix_keys.add((case["world"], case["corpus_size"], case["seed"]))
    expected_matrix = {
        (world, size, 1729) for world in ("rich_random", "zipf_chains") for size in (1_000, 10_000, 30_000)
    } | {
        (world, 10_000, seed) for world in ("rich_random", "zipf_chains") for seed in (7, 17, 31)
    }
    if matrix_keys != expected_matrix:
        raise BenchmarkError("E1 12-case world/size/seed matrix changed")

    for schema_path in sorted((ROOT / "schema").glob("*.json")):
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
            raise BenchmarkError(f"{schema_path.name}: unsupported or missing JSON Schema dialect")

    _verify_generated_assets()
    manifest_sha = _verify_manifest(manifest)
    if manifest.get("counts") != {"packs": 8, "calibration_packs": 2, "gate_packs": 6, **actual_counts}:
        raise BenchmarkError("manifest counts do not match validated fixtures")
    config_sha = canonical_sha256(config)
    summary = {
        "benchmark_version": "r0-v0.1",
        "manifest_sha256": manifest_sha,
        "config_sha256": config_sha,
        "counts": manifest["counts"],
        "manual_pair_reviews_unapproved": manual_unapproved,
        "extraction_reviews_unapproved": extraction_unapproved,
        "gate_execution_ready": manual_unapproved == 0 and extraction_unapproved == 0,
        "engine_input_projection": {
            "graph_fields": ["benchmark_graph_id", "thought_dna"],
            "extraction_fields": ["extraction_case_id", "input"],
            "gold_in_engine_input": False,
        },
    }
    return FixtureBundle(
        tuple(graphs), tuple(pairs), tuple(extraction_runs), tuple(e1_cases), config,
        manifest, manifest_sha, config_sha, summary,
    )


def _normalize_pairs(value: Sequence[Sequence[Any]], *, edge: bool = False) -> set[tuple[str, Any]]:
    out: set[tuple[str, Any]] = set()
    for pair in value:
        right: Any = tuple(pair[1]) if edge and isinstance(pair[1], list) else pair[1]
        out.add((str(pair[0]), right))
    return out


def _f1(predicted: set[Any], gold: set[Any]) -> float:
    if not predicted and not gold:
        return 1.0
    if not predicted or not gold:
        return 0.0
    overlap = len(predicted & gold)
    precision = overlap / len(predicted)
    recall = overlap / len(gold)
    return 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)


def _percentile(values: Sequence[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, math.ceil(percentile * len(ordered)) - 1)
    return ordered[index]


def _validate_prediction(record: dict[str, Any], case_id: str) -> None:
    require_exact_fields(record, {"case_id", "retrieval", "verification", "replay"}, case_id)
    if record["case_id"] != case_id:
        raise BenchmarkError(f"prediction key {case_id} disagrees with record case_id")
    retrieval = record["retrieval"]
    require_exact_fields(
        retrieval,
        {"candidate_rank", "channel_scores", "requires_structural_verification", "polarity_reliable", "latency_seconds", "postings_touched"},
        f"{case_id}.retrieval",
    )
    if not isinstance(retrieval["candidate_rank"], int) or retrieval["candidate_rank"] < 1:
        raise BenchmarkError(f"{case_id}: candidate_rank must be a positive integer")
    if not isinstance(retrieval["channel_scores"], dict) or "structural" not in retrieval["channel_scores"]:
        raise BenchmarkError(f"{case_id}: channel_scores.structural is required")
    if retrieval["polarity_reliable"] is not False or retrieval["requires_structural_verification"] is not True:
        raise BenchmarkError(f"{case_id}: structural retrieval must be marked polarity-unreliable and verifier-required")
    verification = record["verification"]
    require_exact_fields(
        verification,
        {"predicted_class", "node_mapping", "edge_mapping", "bridge_mapping", "hard_rejection", "false_contractions", "components", "latency_seconds"},
        f"{case_id}.verification",
    )
    for field in ("node_mapping", "bridge_mapping"):
        ensure_pair_list(verification[field], f"{case_id}.verification.{field}")
    ensure_pair_list(verification["edge_mapping"], f"{case_id}.verification.edge_mapping", edge=True)
    if "structural_score" not in verification["components"]:
        raise BenchmarkError(f"{case_id}: components.structural_score is required")
    replay = record["replay"]
    require_exact_fields(
        replay,
        {"candidate_rank", "predicted_class", "node_mapping", "edge_mapping", "bridge_mapping", "hard_rejection", "components"},
        f"{case_id}.replay",
    )
    for field in ("node_mapping", "bridge_mapping"):
        ensure_pair_list(replay[field], f"{case_id}.replay.{field}")
    ensure_pair_list(replay["edge_mapping"], f"{case_id}.replay.edge_mapping", edge=True)


def _deterministic_match(prediction: dict[str, Any]) -> tuple[bool, float]:
    retrieval = prediction["retrieval"]
    verification = prediction["verification"]
    replay = prediction["replay"]
    same = (
        retrieval["candidate_rank"] == replay["candidate_rank"]
        and verification["predicted_class"] == replay["predicted_class"]
        and _normalize_pairs(verification["node_mapping"]) == _normalize_pairs(replay["node_mapping"])
        and _normalize_pairs(verification["edge_mapping"], edge=True) == _normalize_pairs(replay["edge_mapping"], edge=True)
        and _normalize_pairs(verification["bridge_mapping"]) == _normalize_pairs(replay["bridge_mapping"])
        and verification["hard_rejection"] == replay["hard_rejection"]
    )
    keys = set(verification["components"]) | set(replay["components"])
    deltas = []
    for key in keys:
        left, right = verification["components"].get(key), replay["components"].get(key)
        if isinstance(left, bool) or isinstance(right, bool):
            deltas.append(0.0 if left is right else 1.0)
        elif isinstance(left, (int, float)) and isinstance(right, (int, float)):
            deltas.append(abs(float(left) - float(right)))
        else:
            deltas.append(1.0)
    delta = max(deltas, default=0.0)
    return same and delta == 0.0, delta


def _node_signature(node: Mapping[str, Any]) -> tuple[Any, ...]:
    spans = tuple(sorted((span["start"], span["end"], span["text"]) for span in node.get("spans", [])))
    return node.get("role"), spans, node.get("assertion", "asserted"), node.get("modality", "actual")


def _extraction_sets(thought: Mapping[str, Any]) -> tuple[set[Any], set[Any]]:
    node_by_id = {node["id"]: _node_signature(node) for node in thought.get("nodes", []) if isinstance(node, Mapping) and "id" in node}
    node_set = set(node_by_id.values())
    relation_set = set()
    for relation in thought.get("relations", []):
        if not isinstance(relation, Mapping):
            continue
        source = node_by_id.get(relation.get("source"))
        target = node_by_id.get(relation.get("target"))
        if source is None or target is None:
            continue
        relation_set.add((source, relation.get("type"), target, relation.get("assertion", "asserted"), relation.get("modality", "actual")))
    return node_set, relation_set


def evaluate_extraction(bundle: FixtureBundle, records: list[dict[str, Any]] | None) -> dict[str, Any] | None:
    if records is None:
        return None
    by_id = {record.get("extraction_case_id"): record for record in records}
    expected_ids = {record["extraction_case_id"] for record in bundle.extraction_runs}
    if set(by_id) != expected_ids or None in by_id:
        raise BenchmarkError("extraction predictions must contain exactly all sixteen extraction_case_id values")
    valid_count = 0
    ungrounded_objects = 0
    node_f1_to_reference = []
    edge_f1_to_reference = []
    predicted_by_pack: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    prediction_fields = {"extraction_case_id", "thought_dna"}
    fixture_by_id = {record["extraction_case_id"]: record for record in bundle.extraction_runs}
    for case_id, prediction in by_id.items():
        require_exact_fields(prediction, prediction_fields, f"extraction prediction {case_id}")
        thought = prediction["thought_dna"]
        fixture = fixture_by_id[case_id]
        try:
            validate_thought(thought)
            valid = thought.get("source") == fixture["input"] and thought.get("provenance", {}).get("kind") == "extracted"
        except (ThoughtDNAValidationError, AttributeError):
            valid = False
        if valid:
            valid_count += 1
        else:
            for node in thought.get("nodes", []) if isinstance(thought, Mapping) else []:
                if not node.get("spans"):
                    ungrounded_objects += 1
            for relation in thought.get("relations", []) if isinstance(thought, Mapping) else []:
                if not relation.get("spans"):
                    ungrounded_objects += 1
        predicted_nodes, predicted_edges = _extraction_sets(thought if isinstance(thought, Mapping) else {})
        reference_nodes, reference_edges = _extraction_sets(fixture["reference_thought_dna"])
        node_f1_to_reference.append(_f1(predicted_nodes, reference_nodes))
        edge_f1_to_reference.append(_f1(predicted_edges, reference_edges))
        predicted_by_pack[fixture["pack_id"]].append(thought)
    duplicate_node_f1 = []
    duplicate_edge_f1 = []
    for thoughts in predicted_by_pack.values():
        if len(thoughts) != 2:
            raise BenchmarkError("each pack needs two extraction predictions")
        left_nodes, left_edges = _extraction_sets(thoughts[0])
        right_nodes, right_edges = _extraction_sets(thoughts[1])
        duplicate_node_f1.append(_f1(left_nodes, right_nodes))
        duplicate_edge_f1.append(_f1(left_edges, right_edges))
    return {
        "span_hash_schema_rate": valid_count / len(bundle.extraction_runs),
        "duplicate_node_f1": sum(duplicate_node_f1) / len(duplicate_node_f1),
        "duplicate_edge_f1": sum(duplicate_edge_f1) / len(duplicate_edge_f1),
        "node_f1_to_reference": sum(node_f1_to_reference) / len(node_f1_to_reference),
        "edge_f1_to_reference": sum(edge_f1_to_reference) / len(edge_f1_to_reference),
        "ungrounded_extracted_objects": ungrounded_objects,
    }


def _gate(status: str, observed: Any, required: str) -> dict[str, Any]:
    return {"status": status, "observed": observed, "required": required}


def evaluate_structural_retrieval(
    bundle: FixtureBundle,
    e1_predictions: list[dict[str, Any]] | None,
    scale_predictions: list[dict[str, Any]] | None,
) -> tuple[dict[str, Any] | None, dict[str, Any], dict[str, Any]]:
    """Evaluate the DNA-native E1 matrix and the synthetic 10^3..10^5 replay."""
    if e1_predictions is None:
        e1_metrics = None
        e1_gate = _gate("not_evaluated", None, "all 12 DNA-native E1 cases must pass MULTI and polarity rejection")
    else:
        by_id = {record.get("case_id"): record for record in e1_predictions}
        expected_ids = {case["case_id"] for case in bundle.e1_cases}
        if set(by_id) != expected_ids or None in by_id or len(by_id) != len(e1_predictions):
            raise BenchmarkError("E1 predictions must contain exactly the twelve frozen case_id values")
        fields = {
            "case_id", "descriptor_results", "polarity_flip_rank", "polarity_flip_score",
            "polarity_rejected_end_to_end", "polarity_reliable", "postings_touched",
            "build_seconds", "query_seconds", "live_keys", "dead_keys", "replay_hash", "rerun_hash",
        }
        margins = []
        failed_cases = []
        d0_control_failures = 0
        deterministic_failures = 0
        polarity_failures = 0
        touched: dict[str, int] = {}
        measurements: dict[str, Any] = {}
        for case_id in sorted(expected_ids):
            record = by_id[case_id]
            require_exact_fields(record, fields, f"E1 prediction {case_id}")
            descriptor_results = record["descriptor_results"]
            if set(descriptor_results) != {"D0", "D1", "MULTI"}:
                raise BenchmarkError(f"{case_id}: descriptor_results must contain exactly D0, D1 and MULTI")
            descriptor_fields = {"true_rank", "true_score", "best_generic_rank", "best_generic_score"}
            for name, result in descriptor_results.items():
                require_exact_fields(result, descriptor_fields, f"{case_id}.{name}")
            multi = descriptor_results["MULTI"]
            margin = float(multi["true_score"]) - float(multi["best_generic_score"])
            margins.append(margin)
            multi_pass = margin > 0 and int(multi["true_rank"]) < int(multi["best_generic_rank"])
            polarity_pass = record["polarity_reliable"] is False and record["polarity_rejected_end_to_end"] is True
            deterministic = record["replay_hash"] == record["rerun_hash"]
            if not multi_pass or not polarity_pass or not deterministic:
                failed_cases.append(case_id)
            polarity_failures += int(not polarity_pass)
            deterministic_failures += int(not deterministic)
            d0 = descriptor_results["D0"]
            d0_control_failures += int(
                float(d0["true_score"]) <= float(d0["best_generic_score"])
                or int(d0["true_rank"]) >= int(d0["best_generic_rank"])
            )
            touched[case_id] = int(record["postings_touched"])
            measurements[case_id] = {
                "multi_true_rank": multi["true_rank"],
                "multi_best_generic_rank": multi["best_generic_rank"],
                "multi_margin": margin,
                "polarity_flip_rank": record["polarity_flip_rank"],
                "polarity_flip_score": record["polarity_flip_score"],
                "postings_touched": record["postings_touched"],
                "build_seconds": record["build_seconds"],
                "query_seconds": record["query_seconds"],
                "live_keys": record["live_keys"],
                "dead_keys": record["dead_keys"],
            }
        e1_metrics = {
            "cases": len(expected_ids),
            "failed_cases": failed_cases,
            "minimum_multi_margin": min(margins),
            "multi_margin_distribution": sorted(margins),
            "d0_control_failures": d0_control_failures,
            "polarity_failures": polarity_failures,
            "deterministic_failures": deterministic_failures,
            "postings_touched": touched,
            "case_measurements": measurements,
        }
        e1_gate = _gate(
            "pass" if not failed_cases else "fail",
            e1_metrics,
            "MULTI true analogue strictly above all generic distractors in 12/12; polarity rejected; replay hashes equal",
        )

    if scale_predictions is None:
        scale_metrics = None
        scale_gate = _gate("not_evaluated", None, "both synthetic worlds at 10^3, 10^4 and 10^5 with sublinear touched postings and Recall@20 >= 0.50")
    else:
        fields = {
            "case_id", "world", "corpus_size", "seed", "synthetic", "feature_distribution",
            "build_seconds", "index_bytes", "posting_length", "postings_touched",
            "query_latency_seconds", "recall_at_5", "recall_at_20", "peak_memory_bytes",
            "replay_hash", "rerun_hash",
        }
        ids: set[str] = set()
        by_world_size: dict[tuple[str, int], dict[str, Any]] = {}
        for record in scale_predictions:
            case_id = record.get("case_id")
            if not isinstance(case_id, str) or case_id in ids:
                raise BenchmarkError("scale predictions require unique string case_id values")
            ids.add(case_id)
            require_exact_fields(record, fields, f"scale prediction {case_id}")
            if record["world"] in {"rich_random", "zipf_chains"} and record["seed"] == 1729:
                key = (record["world"], int(record["corpus_size"]))
                if key in by_world_size:
                    raise BenchmarkError(f"duplicate required scale replay point {key}")
                by_world_size[key] = record
        required_keys = {
            (world, size) for world in ("rich_random", "zipf_chains") for size in (1_000, 10_000, 100_000)
        }
        missing = sorted(required_keys - set(by_world_size))
        failures = []
        growth: dict[str, list[float]] = {}
        for world in ("rich_random", "zipf_chains"):
            world_growth = []
            for smaller, larger in ((1_000, 10_000), (10_000, 100_000)):
                left = by_world_size.get((world, smaller))
                right = by_world_size.get((world, larger))
                if left is None or right is None:
                    continue
                left_touched = int(left["postings_touched"])
                right_touched = int(right["postings_touched"])
                ratio = math.inf if left_touched == 0 else right_touched / left_touched
                world_growth.append(ratio)
                if ratio >= larger / smaller:
                    failures.append(f"{world}:{smaller}->{larger}:postings_not_sublinear")
            growth[world] = world_growth
        for key in sorted(required_keys & set(by_world_size)):
            record = by_world_size[key]
            if record["synthetic"] is not True:
                failures.append(f"{key}:synthetic_flag")
            if float(record["recall_at_20"]) < 0.5:
                failures.append(f"{key}:recall_at_20")
            if record["replay_hash"] != record["rerun_hash"]:
                failures.append(f"{key}:replay_hash")
        million_worlds = {
            record["world"] for record in scale_predictions
            if record["corpus_size"] == 1_000_000 and record["world"] in {"rich_random", "zipf_chains"}
        }
        scale_metrics = {
            "required_points_missing": [list(key) for key in missing],
            "failures": failures,
            "postings_growth_ratios": growth,
            "million_scale_worlds_reported": sorted(million_worlds),
            "real_distribution_reported": any(record["world"] == "extracted_fixture_distribution" for record in scale_predictions),
            "points": {
                record["case_id"]: {
                    key: record[key]
                    for key in (
                        "world", "corpus_size", "seed", "synthetic", "feature_distribution",
                        "build_seconds", "index_bytes", "posting_length", "postings_touched",
                        "query_latency_seconds", "recall_at_5", "recall_at_20", "peak_memory_bytes",
                    )
                }
                for record in sorted(scale_predictions, key=lambda item: item["case_id"])
            },
        }
        scale_gate = _gate(
            "pass" if not missing and not failures else "fail",
            scale_metrics,
            "both synthetic worlds at 10^3, 10^4 and 10^5; touched-posting growth < corpus growth; Recall@20 >= 0.50; deterministic replay",
        )
    return {"e1": e1_metrics, "scale": scale_metrics}, e1_gate, scale_gate


def evaluate(
    bundle: FixtureBundle,
    predictions: list[dict[str, Any]],
    extraction_predictions: list[dict[str, Any]] | None = None,
    e1_predictions: list[dict[str, Any]] | None = None,
    scale_predictions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Evaluate complete predictions without allowing aggregate compensation."""
    by_id = {record.get("case_id"): record for record in predictions}
    expected_ids = {pair["case_id"] for pair in bundle.pairs}
    if set(by_id) != expected_ids or None in by_id or len(by_id) != len(predictions):
        raise BenchmarkError("pair predictions must contain exactly all 128 unique case_id values")
    pair_by_id = {pair["case_id"]: pair for pair in bundle.pairs}
    for case_id, prediction in by_id.items():
        _validate_prediction(prediction, case_id)

    rows: list[dict[str, Any]] = []
    deterministic_failures = 0
    max_replay_delta = 0.0
    for case_id in sorted(expected_ids):
        pair = pair_by_id[case_id]
        prediction = by_id[case_id]
        verification = prediction["verification"]
        node_gold_sets = [_normalize_pairs(pair["gold_node_pairs"])] + [
            _normalize_pairs(alternative) for alternative in pair["equivalent_mapping_sets"]
        ]
        node_f1 = max((_f1(_normalize_pairs(verification["node_mapping"]), gold) for gold in node_gold_sets), default=1.0) if pair["gold_node_pairs"] else None
        edge_f1 = _f1(
            _normalize_pairs(verification["edge_mapping"], edge=True),
            _normalize_pairs(pair["gold_edge_pairs"], edge=True),
        ) if pair["gold_edge_pairs"] else None
        bridge_f1 = _f1(_normalize_pairs(verification["bridge_mapping"]), _normalize_pairs(pair["bridge_pairs"])) if pair["bridge_pairs"] else None
        deterministic, delta = _deterministic_match(prediction)
        deterministic_failures += int(not deterministic)
        max_replay_delta = max(max_replay_delta, delta)
        rows.append(
            {
                "case_id": case_id,
                "pack_id": pair["pack_id"],
                "split": pair["split"],
                "family": pair["family"],
                "gold_class": pair["gold_class"],
                "relevant": pair["relevant"],
                "rank": prediction["retrieval"]["candidate_rank"],
                "retrieved_at_5": prediction["retrieval"]["candidate_rank"] <= 5,
                "predicted_class": verification["predicted_class"],
                "class_correct": verification["predicted_class"] == pair["gold_class"],
                "predicted_positive": verification["predicted_class"] not in {"negative", "unsupported"},
                "node_f1": node_f1,
                "edge_f1": edge_f1,
                "bridge_f1": bridge_f1,
                "structural_score": float(verification["components"]["structural_score"]),
                "hard_rejection": verification["hard_rejection"],
                "false_contractions": verification["false_contractions"],
                "latency_seconds": float(verification["latency_seconds"]),
                "deterministic": deterministic,
                "negative_subtype": pair["transform_manifest"].get("negative_subtype"),
            }
        )

    gate_rows = [row for row in rows if row["split"] == "gate"]
    relevant_rows = [row for row in gate_rows if row["relevant"]]
    negative_rows = [row for row in gate_rows if not row["relevant"]]
    overall_recall = sum(row["retrieved_at_5"] for row in relevant_rows) / len(relevant_rows)
    predicted_positive = [row for row in gate_rows if row["predicted_positive"]]
    precision = sum(row["relevant"] for row in predicted_positive) / len(predicted_positive) if predicted_positive else 0.0
    negative_fpr = sum(row["predicted_positive"] for row in negative_rows) / len(negative_rows)
    mapping_rows = [row for row in relevant_rows if pair_by_id[row["case_id"]]["gold_node_pairs"]]
    edge_rows = [row for row in relevant_rows if pair_by_id[row["case_id"]]["gold_edge_pairs"]]
    bridge_rows = [row for row in relevant_rows if pair_by_id[row["case_id"]]["bridge_pairs"]]
    node_f1 = sum(row["node_f1"] for row in mapping_rows) / len(mapping_rows)
    edge_accuracy = sum(row["edge_f1"] for row in edge_rows) / len(edge_rows)
    bridge_f1 = sum(row["bridge_f1"] for row in bridge_rows) / len(bridge_rows)
    p95_latency = _percentile([row["latency_seconds"] for row in gate_rows], 0.95)

    per_family: dict[str, Any] = {}
    for family in sorted({row["family"] for row in rows}):
        family_rows = [row for row in gate_rows if row["family"] == family]
        family_node_rows = [row for row in family_rows if row["node_f1"] is not None]
        family_edge_rows = [row for row in family_rows if row["edge_f1"] is not None]
        family_bridge_rows = [row for row in family_rows if row["bridge_f1"] is not None]
        per_family[family] = {
            "gate_count": len(family_rows),
            "retrieval_hits_at_5": sum(row["retrieved_at_5"] for row in family_rows),
            "recall_at_5": sum(row["retrieved_at_5"] for row in family_rows) / len(family_rows),
            "classification_accuracy": sum(row["class_correct"] for row in family_rows) / len(family_rows),
            "false_positives": sum(row["predicted_positive"] and not row["relevant"] for row in family_rows),
            "mean_node_f1": (sum(row["node_f1"] for row in family_node_rows) / len(family_node_rows)) if family_node_rows else None,
            "mean_edge_f1": (sum(row["edge_f1"] for row in family_edge_rows) / len(family_edge_rows)) if family_edge_rows else None,
            "mean_bridge_f1": (sum(row["bridge_f1"] for row in family_bridge_rows) / len(family_bridge_rows)) if family_bridge_rows else None,
        }

    sow_passes = 0
    by_pack_family = {(row["pack_id"], row["family"]): row for row in gate_rows}
    for pack in ("G01", "G02", "G03", "G04", "G05", "G06"):
        negative_score = by_pack_family[(pack, "same_vocabulary_wrong_structure")]["structural_score"]
        sow_passes += int(by_pack_family[(pack, "vocabulary_substitution")]["structural_score"] > negative_score)
        sow_passes += int(by_pack_family[(pack, "cross_domain_analogy")]["structural_score"] > negative_score)

    polarity_rows = [row for row in gate_rows if row["negative_subtype"] == "polarity_flip"]
    polarity_rejections = sum(
        row["predicted_class"] == "negative" and bool(row["hard_rejection"]) for row in polarity_rows
    )
    polarity_rate = polarity_rejections / len(polarity_rows)

    attribution = Counter()
    threshold = bundle.config["thresholds"]["node_pair_f1_min"]
    for row in gate_rows:
        if row["relevant"] and not row["retrieved_at_5"]:
            attribution["retrieval_miss"] += 1
        elif row["relevant"] and not row["class_correct"]:
            attribution["verifier_classification_failure"] += 1
        elif row["relevant"] and pair_by_id[row["case_id"]]["gold_node_pairs"] and row["node_f1"] < threshold:
            attribution["mapping_failure"] += 1
        elif row["negative_subtype"] == "polarity_flip" and (row["predicted_positive"] or not row["hard_rejection"]):
            attribution["polarity_rejection_failure"] += 1
        elif not row["relevant"] and row["predicted_positive"]:
            attribution["verifier_false_positive"] += 1
        elif not row["deterministic"]:
            attribution["deterministic_replay_failure"] += 1
        else:
            attribution["pass"] += 1

    extraction = evaluate_extraction(bundle, extraction_predictions)
    thresholds = bundle.config["thresholds"]
    positive_family_checks = {
        family: per_family[family]["retrieval_hits_at_5"] >= thresholds["positive_family_gate_hits_min"]
        for family in bundle.config["positive_families"]
    }
    negative_family_checks = {
        family: per_family[family]["false_positives"] <= thresholds["negative_family_false_positives_max"]
        for family in bundle.config["negative_families"]
    }
    structural_metrics, e1_gate, scale_gate = evaluate_structural_retrieval(bundle, e1_predictions, scale_predictions)
    gates: dict[str, Any] = {
        "independent_gold_review": _gate(
            "pass" if bundle.summary["gate_execution_ready"] else "fail",
            {
                "pair_reviews_unapproved": bundle.summary["manual_pair_reviews_unapproved"],
                "extraction_reviews_unapproved": bundle.summary["extraction_reviews_unapproved"],
            },
            "all required manual judgments approved by an independent reviewer",
        ),
        "sow": _gate("pass" if sow_passes >= thresholds["sow_min_passes"] else "fail", sow_passes, ">= 10/12; ties fail"),
        "overall_recall_at_5": _gate("pass" if overall_recall >= thresholds["overall_recall_at_5_min"] else "fail", overall_recall, ">= 0.85"),
        "positive_family_recall": _gate("pass" if all(positive_family_checks.values()) else "fail", positive_family_checks, "every family >= 4/6"),
        "resonance_precision": _gate("pass" if precision >= thresholds["resonance_precision_min"] else "fail", precision, ">= 0.80"),
        "overall_negative_fpr": _gate("pass" if negative_fpr <= thresholds["overall_negative_fpr_max"] else "fail", negative_fpr, "<= 0.10"),
        "negative_family_fpr": _gate("pass" if all(negative_family_checks.values()) else "fail", negative_family_checks, "each family <= 1/6 false positives"),
        "node_pair_f1": _gate("pass" if node_f1 >= thresholds["node_pair_f1_min"] else "fail", node_f1, ">= 0.70"),
        "directed_typed_edge_accuracy": _gate("pass" if edge_accuracy >= thresholds["directed_typed_edge_accuracy_min"] else "fail", edge_accuracy, ">= 0.75"),
        "false_meaningful_contractions": _gate("pass" if sum(row["false_contractions"] for row in gate_rows) == 0 else "fail", sum(row["false_contractions"] for row in gate_rows), "== 0"),
        "deterministic_replay": _gate("pass" if deterministic_failures == 0 and max_replay_delta == 0 else "fail", {"failures": deterministic_failures, "max_score_vector_delta": max_replay_delta}, "zero mapping/class/rank differences and score-vector delta == 0"),
        "verifier_p95_seconds": _gate("pass" if p95_latency <= thresholds["verifier_p95_seconds_max"] else "fail", p95_latency, "<= 2.0 on declared reference CPU"),
        "polarity_rejection": _gate("pass" if polarity_rate == 1.0 else "fail", polarity_rate, "== 1.0 end-to-end"),
        "structural_e1_matrix": e1_gate,
        "structural_scale_replay": scale_gate,
    }
    if extraction is None:
        gates["extraction_prerequisite"] = _gate("not_evaluated", None, "all extraction gates must pass")
    else:
        extraction_pass = (
            extraction["span_hash_schema_rate"] >= thresholds["extraction_span_hash_schema_rate_min"]
            and extraction["duplicate_node_f1"] >= thresholds["duplicate_extract_node_f1_min"]
            and extraction["duplicate_edge_f1"] >= thresholds["duplicate_extract_edge_f1_min"]
            and extraction["ungrounded_extracted_objects"] <= thresholds["ungrounded_extracted_objects_max"]
        )
        gates["extraction_prerequisite"] = _gate("pass" if extraction_pass else "fail", extraction, "span/hash/schema=100%; node F1>=0.70; edge F1>=0.60; ungrounded=0")

    report: dict[str, Any] = {
        "report_version": "resonance-benchmark-report/0.1",
        "benchmark_version": "r0-v0.1",
        "manifest_sha256": bundle.manifest_sha256,
        "config_sha256": bundle.config_sha256,
        "prediction_sha256": canonical_sha256({
            "pairs": sorted(predictions, key=lambda item: item["case_id"]),
            "extraction": sorted(extraction_predictions, key=lambda item: item["extraction_case_id"]) if extraction_predictions else None,
            "e1": sorted(e1_predictions, key=lambda item: item["case_id"]) if e1_predictions else None,
            "scale": sorted(scale_predictions, key=lambda item: item["case_id"]) if scale_predictions else None,
        }),
        "fixture_readiness": bundle.summary,
        "metrics": {
            "overall_gate_recall_at_5": overall_recall,
            "resonance_precision": precision,
            "overall_negative_fpr": negative_fpr,
            "node_pair_f1": node_f1,
            "directed_typed_edge_accuracy": edge_accuracy,
            "bridge_mapping_f1": bridge_f1,
            "sow_passes": sow_passes,
            "sow_total": 12,
            "polarity_rejection_rate": polarity_rate,
            "verifier_p95_seconds": p95_latency,
            "extraction": extraction,
            "structural_retrieval": structural_metrics,
        },
        "per_family": per_family,
        "pipeline_attribution": dict(sorted(attribution.items())),
        "gates": gates,
        "overall_status": "pass" if all(item["status"] == "pass" for item in gates.values()) else "fail",
    }
    report["report_sha256"] = canonical_sha256(report)
    return report


def _write_or_print(value: dict[str, Any], output: Path | None) -> None:
    rendered = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if output is None:
        print(rendered, end="")
    else:
        output.write_text(rendered, encoding="utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate_parser = subparsers.add_parser("validate", help="validate fixtures, schemas and hashes")
    validate_parser.add_argument("--output", type=Path)
    evaluate_parser = subparsers.add_parser("evaluate", help="evaluate complete external predictions")
    evaluate_parser.add_argument("--predictions", type=Path, required=True)
    evaluate_parser.add_argument("--extraction-predictions", type=Path)
    evaluate_parser.add_argument("--e1-predictions", type=Path)
    evaluate_parser.add_argument("--scale-predictions", type=Path)
    evaluate_parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        bundle = validate_fixtures()
        if args.command == "validate":
            _write_or_print(bundle.summary, args.output)
        else:
            predictions = read_jsonl(args.predictions)
            extraction = read_jsonl(args.extraction_predictions) if args.extraction_predictions else None
            e1 = read_jsonl(args.e1_predictions) if args.e1_predictions else None
            scale = read_jsonl(args.scale_predictions) if args.scale_predictions else None
            _write_or_print(evaluate(bundle, predictions, extraction, e1, scale), args.output)
    except BenchmarkError as exc:
        print(f"benchmark error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
