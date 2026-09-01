#!/usr/bin/env python3
"""Deterministic Benchmark v0.2 contraction-audit evaluator.

False contractions are derived from preservation gold and submitted edge/path
mappings. A prediction-supplied false_contractions integer is ignored.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parents[1]
V01_ROOT = ROOT.parent / "r0-v0.1"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.graph import ThoughtDNAValidationError, validate_thought  # noqa: E402


class BenchmarkError(ValueError):
    """Raised when fixtures or predictions are malformed."""


@dataclass(frozen=True)
class FixtureBundle:
    graphs: tuple[dict[str, Any], ...]
    pairs: tuple[dict[str, Any], ...]
    config: dict[str, Any]
    manifest: dict[str, Any]
    manifest_sha256: str
    config_sha256: str
    graph_by_id: dict[str, dict[str, Any]]
    pair_by_id: dict[str, dict[str, Any]]


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
        records.append(json.loads(line))
    return records


def require_exact_fields(record: Mapping[str, Any], fields: set[str], context: str) -> None:
    missing = sorted(fields - set(record))
    extra = sorted(set(record) - fields)
    if missing or extra:
        raise BenchmarkError(f"{context}: closed record mismatch; missing={missing}, extra={extra}")


def _path_key(query_relation: str, candidate_relations: Sequence[str]) -> tuple[str, tuple[str, ...]]:
    return (query_relation, tuple(candidate_relations))


def _gold_path_key(item: Sequence[Any]) -> tuple[str, tuple[str, ...]] | None:
    if not isinstance(item, list) or len(item) != 2 or not isinstance(item[0], str):
        raise BenchmarkError(f"path gold must be [query_rel, candidate_rels]: {item!r}")
    if isinstance(item[1], list) and item[1] and all(isinstance(part, str) for part in item[1]):
        return (item[0], tuple(item[1]))
    return None


def interior_nodes_from_path(thought: Mapping[str, Any], rel_ids: Sequence[str]) -> list[str]:
    by_id = {rel["id"]: rel for rel in thought["relations"]}
    ordered = []
    for rel_id in rel_ids:
        if rel_id not in by_id:
            raise BenchmarkError(f"predicted path relation {rel_id} is not in the candidate graph")
        ordered.append(by_id[rel_id])
    interiors: list[str] = []
    for left, right in zip(ordered, ordered[1:]):
        if left["target"] != right["source"]:
            raise BenchmarkError(f"path is not connected: {left['id']} -> {right['id']}")
        interiors.append(left["target"])
    return interiors


def derived_false_contractions(
    pair: Mapping[str, Any],
    candidate_thought: Mapping[str, Any],
    prediction: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Count unlicensed contractions from mappings, never from a self-reported integer."""
    allowed = {key for item in pair["gold_edge_pairs"] if (key := _gold_path_key(item)) is not None and len(key[1]) >= 2}
    forbidden = {key for item in pair["forbidden_edge_path_matches"] if (key := _gold_path_key(item)) is not None}
    must_preserve = set(pair["must_preserve_nodes"]) | set(pair["meaningful_nodes"])

    matches = list(prediction["verification"].get("edge_path_matches") or [])
    for item in prediction["verification"].get("edge_mapping") or []:
        key = _gold_path_key(item)
        if key is not None and len(key[1]) >= 2:
            matches.append({
                "query_relation": key[0],
                "candidate_relations": list(key[1]),
                "realizes_nodes": [],
            })

    violations: list[dict[str, Any]] = []
    seen: set[tuple[str, tuple[str, ...]]] = set()
    for match in matches:
        if not isinstance(match, Mapping):
            raise BenchmarkError(f"{pair['case_id']}: edge_path_match must be an object")
        query_rel = match["query_relation"]
        cand_rels = list(match["candidate_relations"])
        if len(cand_rels) < 2:
            continue
        key = _path_key(query_rel, cand_rels)
        if key in seen:
            continue
        seen.add(key)
        realized = list(match.get("realizes_nodes") or [])
        inferred = interior_nodes_from_path(candidate_thought, cand_rels)
        if realized and realized != inferred:
            raise BenchmarkError(
                f"{pair['case_id']}: realizes_nodes {realized} != path interiors {inferred}"
            )
        realized = inferred
        reasons = []
        if key in forbidden:
            reasons.append("forbidden_edge_path_match")
        contracted = sorted(set(realized) & must_preserve)
        if contracted:
            reasons.append("preserved_node_contracted")
        if key not in allowed:
            reasons.append("unlicensed_contraction")
        if reasons:
            violations.append({
                "query_relation": query_rel,
                "candidate_relations": cand_rels,
                "realizes_nodes": realized,
                "reasons": reasons,
                "stage": "verifier_mapping",
            })
    return violations


def _verify_manifest(manifest: dict[str, Any]) -> str:
    for relative, expected in manifest.get("files", {}).items():
        path = ROOT / relative
        payload = path.read_bytes()
        actual = hashlib.sha256(payload).hexdigest()
        if actual != expected.get("sha256"):
            raise BenchmarkError(f"manifest hash mismatch for {relative}")
        if len(payload) != expected.get("bytes"):
            raise BenchmarkError(f"manifest byte count mismatch for {relative}")
    digest = canonical_sha256(manifest)
    recorded = (ROOT / "manifest.sha256").read_text(encoding="utf-8").strip()
    if digest != recorded:
        raise BenchmarkError(f"manifest.sha256 mismatch: {digest} != {recorded}")
    return digest


def _verify_generated_assets() -> None:
    spec = importlib.util.spec_from_file_location(
        "resonance_benchmark_v02_builder", ROOT / "build_fixtures.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    for relative, records in module.build_records().items():
        if (ROOT / relative).read_bytes() != module.jsonl_bytes(records):
            raise BenchmarkError(f"{relative} differs from deterministic build_fixtures.py output")


def validate_fixtures() -> FixtureBundle:
    graphs = read_jsonl(ROOT / "graphs.jsonl")
    pairs = read_jsonl(ROOT / "pairs.jsonl")
    config = json.loads((ROOT / "config/evaluation-v0.2.json").read_text(encoding="utf-8"))
    manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
    _verify_generated_assets()
    digest = _verify_manifest(manifest)

    pair_fields = {
        "case_id", "pack_id", "split", "family", "query_graph", "candidate_graph",
        "gold_class", "evaluation_mode", "relevant", "gold_node_pairs", "gold_edge_pairs",
        "meaningful_nodes", "must_preserve_nodes", "forbidden_edge_path_matches",
        "transform_manifest", "rationale", "review",
    }
    graph_by_id: dict[str, dict[str, Any]] = {}
    for wrapper in graphs:
        require_exact_fields(wrapper, {"benchmark_graph_id", "thought_dna"}, wrapper.get("benchmark_graph_id", "graph"))
        graph_id = wrapper["benchmark_graph_id"]
        try:
            validate_thought(wrapper["thought_dna"])
        except ThoughtDNAValidationError as exc:
            raise BenchmarkError(f"{graph_id}: invalid Thought DNA: {exc}") from exc
        graph_by_id[graph_id] = wrapper

    pair_by_id: dict[str, dict[str, Any]] = {}
    for pair in pairs:
        require_exact_fields(pair, pair_fields, pair.get("case_id", "pair"))
        if pair["query_graph"] not in graph_by_id or pair["candidate_graph"] not in graph_by_id:
            raise BenchmarkError(f"{pair['case_id']}: graph reference does not resolve")
        if pair["relevant"] != (pair["gold_class"] != "negative"):
            raise BenchmarkError(f"{pair['case_id']}: relevant disagrees with gold_class")
        if pair["relevant"] and not pair["gold_edge_pairs"]:
            raise BenchmarkError(f"{pair['case_id']}: positive contraction case needs licensed gold_edge_pairs")
        if not pair["relevant"] and not pair["forbidden_edge_path_matches"]:
            raise BenchmarkError(f"{pair['case_id']}: negative contraction case needs forbidden_edge_path_matches")
        pair_by_id[pair["case_id"]] = pair

    return FixtureBundle(
        graphs=tuple(graphs),
        pairs=tuple(pairs),
        config=config,
        manifest=manifest,
        manifest_sha256=digest,
        config_sha256=hashlib.sha256((ROOT / "config/evaluation-v0.2.json").read_bytes()).hexdigest(),
        graph_by_id=graph_by_id,
        pair_by_id=pair_by_id,
    )


def _gate(status: str, value: Any, rule: str) -> dict[str, Any]:
    return {"status": status, "value": value, "rule": rule}


def evaluate(bundle: FixtureBundle, predictions: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    by_id = {item["case_id"]: item for item in predictions}
    missing = sorted(set(bundle.pair_by_id) - set(by_id))
    extra = sorted(set(by_id) - set(bundle.pair_by_id))
    if missing or extra:
        raise BenchmarkError(f"prediction case_id mismatch; missing={missing}, extra={extra}")

    rows = []
    for case_id, pair in bundle.pair_by_id.items():
        prediction = by_id[case_id]
        retrieval = prediction["retrieval"]
        if retrieval.get("polarity_reliable") is not False:
            raise BenchmarkError(f"{case_id}: structural retrieval must declare polarity_reliable=false")
        if retrieval.get("requires_structural_verification") is not True:
            raise BenchmarkError(f"{case_id}: requires_structural_verification must be true")
        verification = prediction["verification"]
        required = {"predicted_class", "node_mapping", "edge_mapping", "edge_path_matches"}
        missing = sorted(required - set(verification))
        extra = sorted(set(verification) - required - {"false_contractions"})
        if missing or extra:
            raise BenchmarkError(f"{case_id}.verification: missing={missing}, extra={extra}")
        candidate = bundle.graph_by_id[pair["candidate_graph"]]["thought_dna"]
        violations = derived_false_contractions(pair, candidate, prediction)
        self_reported = verification.get("false_contractions")
        rows.append({
            "case_id": case_id,
            "family": pair["family"],
            "split": pair["split"],
            "relevant": pair["relevant"],
            "predicted_class": verification["predicted_class"],
            "derived_false_contractions": len(violations),
            "self_reported_false_contractions": self_reported,
            "violations": violations,
            "stage": "verifier_mapping" if violations else "pass",
        })

    derived_total = sum(row["derived_false_contractions"] for row in rows)
    positive_ok = all(row["derived_false_contractions"] == 0 for row in rows if row["relevant"])
    pending = bundle.manifest["counts"]["manual_reviews_pending"]
    gates = {
        "false_meaningful_contractions": _gate(
            "pass" if derived_total == 0 else "fail",
            derived_total,
            "evaluator-derived count == 0; self-reported false_contractions is ignored",
        ),
        "transparent_positives_pass": _gate(
            "pass" if positive_ok else "fail",
            {
                "positives": [row["case_id"] for row in rows if row["relevant"]],
                "failed": [row["case_id"] for row in rows if row["relevant"] and row["derived_false_contractions"]],
            },
            "licensed transparent-granularity paths still derive zero false contractions",
        ),
        "self_report_ignored": _gate(
            "pass",
            True,
            "v0.2 never uses verification.false_contractions for the gate",
        ),
        "independent_gold_review": _gate(
            "pass" if pending == 0 else "fail",
            {"manual_reviews_pending": pending, "freeze_state": bundle.manifest["freeze_state"]},
            "required manual gold approved by an independent reviewer",
        ),
    }
    measured = {name: gate for name, gate in gates.items() if name != "independent_gold_review"}
    overall = "pass" if all(gate["status"] == "pass" for gate in measured.values()) else "fail"
    report = {
        "report_version": "resonance-benchmark-report/0.2",
        "benchmark_version": "r0-v0.2",
        "manifest_sha256": bundle.manifest_sha256,
        "config_sha256": bundle.config_sha256,
        "overall_status": overall,
        "freeze_state": bundle.manifest["freeze_state"],
        "gates": gates,
        "pipeline_attribution": {
            "verifier_mapping": sum(row["stage"] == "verifier_mapping" for row in rows),
            "pass": sum(row["stage"] == "pass" for row in rows),
        },
        "cases": rows,
    }
    report["report_sha256"] = canonical_sha256({k: v for k, v in report.items() if k != "report_sha256"})
    return report


def evaluate_v0_1_transparent_positives(predictions_by_case: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    """Read-only overlay: v0.1 transparent_granularity gold paths still derive zero.

    v0.1 has no preservation gold, so this overlay cannot catch cheaters on the
    frozen bundle. It only checks that licensed v0.1 paths remain legal.
    """
    pairs = [json.loads(line) for line in (V01_ROOT / "pairs.jsonl").read_text(encoding="utf-8").splitlines()]
    graphs = {item["benchmark_graph_id"]: item["thought_dna"] for item in (
        json.loads(line) for line in (V01_ROOT / "graphs.jsonl").read_text(encoding="utf-8").splitlines()
    )}
    transparent = [pair for pair in pairs if pair["family"] == "transparent_granularity"]
    results = []
    for pair in transparent:
        overlay = {
            **pair,
            "meaningful_nodes": [],
            "must_preserve_nodes": [],
            "forbidden_edge_path_matches": [],
        }
        prediction = predictions_by_case[pair["case_id"]]
        violations = derived_false_contractions(overlay, graphs[pair["candidate_graph"]], prediction)
        results.append({"case_id": pair["case_id"], "derived_false_contractions": len(violations), "violations": violations})
    total = sum(item["derived_false_contractions"] for item in results)
    return {
        "source": "benchmark/r0-v0.1 (read-only)",
        "transparent_cases": len(results),
        "derived_false_contractions": total,
        "status": "pass" if total == 0 else "fail",
        "cases": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark v0.2 contraction-audit runner")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate")
    evaluate_cmd = sub.add_parser("evaluate")
    evaluate_cmd.add_argument("--predictions", required=True)
    evaluate_cmd.add_argument("--output")
    args = parser.parse_args()
    bundle = validate_fixtures()
    if args.command == "validate":
        summary = {
            "benchmark_version": "r0-v0.2",
            "manifest_sha256": bundle.manifest_sha256,
            "freeze_state": bundle.manifest["freeze_state"],
            "counts": bundle.manifest["counts"],
            "gate_execution_ready": bundle.manifest["counts"]["manual_reviews_pending"] == 0,
        }
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0
    predictions = read_jsonl(Path(args.predictions))
    report = evaluate(bundle, predictions)
    text = json.dumps(report, indent=2, sort_keys=True)
    if args.output:
        Path(args.output).write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0 if report["overall_status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
