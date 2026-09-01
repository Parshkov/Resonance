#!/usr/bin/env python3
"""Reproducible R3 repeat gate, legacy-E1, and synthetic-scale evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from research.experiments.R0_E1_fingerprint_discrimination import run_world
from src.graph import ThoughtGraph
from src.index import CandidateRetrievalIndex, IndexConfig


AGENT_ID = "parshkov-openai-gpt5-codex-r3r-m8k4"
RUN_ID = "R3-RETRIEVAL-REPEAT-M8K4"


def _load_benchmark() -> dict[str, ThoughtGraph]:
    rows = [
        json.loads(line)
        for line in (ROOT / "benchmark/r0-v0.1/graphs.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    return {
        row["benchmark_graph_id"]: ThoughtGraph.from_dict(row["thought_dna"])
        for row in rows
    }


def frozen_gate() -> dict[str, object]:
    graphs = _load_benchmark()
    index = CandidateRetrievalIndex(IndexConfig(enabled_channels=("structural",)))
    index.extend(
        graph
        for graph_id, graph in graphs.items()
        if graph_id.startswith("G") and not graph_id.endswith("-Q")
    )
    packs = []
    replay_stable = True
    for offset in range(1, 7):
        pack = f"G{offset:02d}"
        query = graphs[f"{pack}-Q"]
        outcome = index.query_with_diagnostics(query, mode="analogical", k=96)
        replay = index.query_with_diagnostics(query, mode="analogical", k=96)
        replay_stable &= outcome.diagnostics.replay_sha256 == replay.diagnostics.replay_sha256
        ranks = {result.candidate_id: rank for rank, result in enumerate(outcome.results, 1)}
        scores = {result.candidate_id: result.channel_scores["structural"] for result in outcome.results}
        target = f"{pack}-C09"
        vocabulary = f"{pack}-C02"
        wrong_words = f"{pack}-C10"
        generic = f"{pack}-C13"
        packs.append(
            {
                "pack": pack,
                "target_rank": ranks[target],
                "target_score": scores[target],
                "vocabulary_score": scores[vocabulary],
                "wrong_words_score": scores[wrong_words],
                "generic_score": scores[generic],
                "generic_margin": scores[target] - scores[generic],
                "sow_passes": int(scores[vocabulary] > scores[wrong_words])
                + int(scores[target] > scores[wrong_words]),
                "perfect_score_tie_count": sum(value == 1.0 for value in scores.values()),
                "selected_features": outcome.diagnostics.selected_structural_features,
                "postings_touched": outcome.diagnostics.postings_touched_by_channel["structural"],
                "query_latency_ms": outcome.diagnostics.total_latency_ms,
                "replay_sha256": outcome.diagnostics.replay_sha256,
            }
        )
    recall_at_20 = sum(item["target_rank"] <= 20 for item in packs) / len(packs)
    recall_at_5 = sum(item["target_rank"] <= 5 for item in packs) / len(packs)
    sow = sum(item["sow_passes"] for item in packs)
    stats = index.stats()
    return {
        "benchmark_version": "r0-v0.1",
        "scope": "gate packs only; structural channel only",
        "config_hash": index.config.config_hash,
        "feature_version": index.feature_version,
        "corpus_snapshot": index.corpus_snapshot,
        "pack_results": packs,
        "metrics": {
            "structural_cross_domain_recall_at_20": recall_at_20,
            "cross_domain_recall_at_5": recall_at_5,
            "sow": sow,
            "sow_total": 12,
            "all_generic_margins_positive": all(item["generic_margin"] > 0 for item in packs),
            "deterministic_replay": replay_stable,
            "perfect_score_candidates_per_query": packs[0]["perfect_score_tie_count"],
        },
        "gate_status": "NO_GO_OBSERVATIONAL_COLLISION",
        "attribution": (
            "All six gate query graphs have the same D0 roles and D1 typed/directed neighborhoods. "
            "Forty-eight gate candidates score 1.0 for every query. Pack-local target identity is "
            "not observable to a structural-only index without forbidden semantic or benchmark-ID leakage."
        ),
        "index_stats": {
            "corpus_size": stats.corpus_size,
            "structural_keys": stats.structural_keys,
            "structural_postings": stats.structural_postings,
            "max_posting_length": stats.max_posting_length,
            "index_bytes_estimate": stats.index_bytes_estimate,
        },
    }


def legacy_e1(full: bool) -> dict[str, object]:
    if full:
        matrix = []
        for world in ("R", "Z"):
            for size in (1_000, 10_000, 30_000):
                matrix.append(run_world(world, size, "MULTI", seed=20260831))
            for seed in (20260832, 20260833, 20260834):
                matrix.append(run_world(world, 10_000, "MULTI", seed=seed))
    else:
        matrix = [
            run_world(world, 1_000, "MULTI", seed=20260831)
            for world in ("R", "Z")
        ]
    d0_control = run_world("R", 10_000 if full else 1_000, "D0", seed=20260831)
    return {
        "matrix_kind": "full_12_case" if full else "smoke_2_case",
        "matrix": matrix,
        "all_multi_kill_rules_pass": all(item["kill_pass"] for item in matrix),
        "required_d0_control": d0_control,
        "d0_control_fails": not d0_control["kill_pass"],
        "note": "Legacy toy enums are provenance only; frozen Thought DNA evidence is reported separately.",
    }


def _scale_graph(thought_id: str, *, full: bool) -> ThoughtGraph:
    text = f"Synthetic scale graph {thought_id}."
    if full:
        roles = ("problem", "mechanism", "outcome", "method")
        edges = ((0, 1, "causes"), (1, 2, "causes"), (3, 2, "prevents"))
    else:
        roles = ("problem", "mechanism", "outcome")
        edges = ((0, 1, "causes"), (1, 2, "causes"))
    return ThoughtGraph.from_dict(
        {
            "schema_version": "thought-dna/0.1",
            "thought_id": thought_id,
            "source": {
                "text": text,
                "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            },
            "provenance": {"kind": "manual", "extractor": None, "human_id": AGENT_ID},
            "nodes": [
                {
                    "id": f"n{offset}",
                    "label": f"synthetic label {offset}",
                    "role": role,
                    "spans": [],
                    "extract_conf": 1.0,
                    "atomic": True,
                }
                for offset, role in enumerate(roles)
            ],
            "relations": [
                {
                    "id": f"r{offset}",
                    "source": f"n{source}",
                    "target": f"n{target}",
                    "type": kind,
                    "extract_conf": 1.0,
                    "spans": [],
                }
                for offset, (source, target, kind) in enumerate(edges)
            ],
        }
    )


def scale_replay(sizes: tuple[int, ...]) -> dict[str, object]:
    index = CandidateRetrievalIndex(IndexConfig(enabled_channels=("structural",)))
    query = _scale_graph("scale-query", full=True)
    index.upsert(_scale_graph("intended-analogue", full=True))
    rows = []
    inserted = 1
    build_started = time.perf_counter()
    for target_size in sizes:
        while inserted < target_size:
            index.upsert(_scale_graph(f"filler-{inserted:07d}", full=False))
            inserted += 1
        latencies = []
        outcome = None
        for _ in range(5):
            outcome = index.query_with_diagnostics(query, mode="analogical", k=20)
            latencies.append(outcome.diagnostics.total_latency_ms)
        assert outcome is not None
        ranks = {result.candidate_id: rank for rank, result in enumerate(outcome.results, 1)}
        stats = index.stats()
        ordered_latency = sorted(latencies)
        rows.append(
            {
                "corpus_size": target_size,
                "build_seconds_cumulative": time.perf_counter() - build_started,
                "target_rank": ranks.get("intended-analogue"),
                "recall_at_20": int("intended-analogue" in ranks),
                "postings_touched": outcome.diagnostics.postings_touched_by_channel["structural"],
                "skipped_evidence_fraction": outcome.diagnostics.skipped_evidence_fraction,
                "query_latency_p50_ms": statistics.median(latencies),
                "query_latency_p95_ms": ordered_latency[-1],
                "max_posting_length": stats.max_posting_length,
                "index_bytes_estimate": stats.index_bytes_estimate,
                "replay_sha256": outcome.diagnostics.replay_sha256,
            }
        )
    base = rows[0]
    final = rows[-1]
    corpus_growth = final["corpus_size"] / base["corpus_size"]
    touched_growth = final["postings_touched"] / max(base["postings_touched"], 1)
    return {
        "distribution": "synthetic repeated three-node causal chains; not a real-distribution claim",
        "rows": rows,
        "postings_touched_sublinear": touched_growth < corpus_growth,
        "real_distribution_scale_supported": False,
        "limitation": "No extracted real-distribution 10^5/10^6 replay exists yet.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--full", action="store_true", help="run the full 12-case legacy E1 matrix")
    parser.add_argument(
        "--scale-sizes",
        default="1000,10000",
        help="comma-separated cumulative synthetic corpus sizes",
    )
    parser.add_argument("--skip-scale", action="store_true")
    args = parser.parse_args()
    sizes = tuple(int(item) for item in args.scale_sizes.split(",") if item)
    if not sizes or tuple(sorted(set(sizes))) != sizes or sizes[0] < 1:
        raise SystemExit("--scale-sizes must be unique increasing positive integers")
    report = {
        "run_id": RUN_ID,
        "agent_id": AGENT_ID,
        "python": __import__("sys").version,
        "frozen_gate": frozen_gate(),
        "legacy_e1": legacy_e1(args.full),
        "scale_replay": None if args.skip_scale else scale_replay(sizes),
    }
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
