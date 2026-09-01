#!/usr/bin/env python3
"""R5 frozen-v0.1 harness: real retrieval ranks + oracle-inclusion verification.

Two labelled paths, not one:

1. Retrieval rank comes from the live index (`channel_ranks`, tie-aware).
   A candidate absent from the (tie-expanded) top-k is a retrieval miss.
2. Verification always runs on the evaluator-selected `candidate_graph`,
   even on a retrieval miss. That is oracle-inclusion stage isolation, not
   a no-oracle ``find()`` traversal.

Usage:
  python3 tests/engine_benchmark_e2e.py --out preds.jsonl [--report report.json]
  python3 benchmark/r0-v0.1/runner.py evaluate --predictions preds.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from src.graph import ThoughtGraph                     # noqa: E402
from src.engine import ENGINE_VERSION, ResonanceEngine  # noqa: E402

MODE_BY_EVAL = {"structural": "structural", "analogical": "analogical",
                "complementary": "complementary"}


def bridge_mapping(q, c):
    out = []
    b_about = {}
    for node in c.nodes:
        for ref in (node.knowledge.about if node.knowledge else ()):
            b_about.setdefault(ref.id, []).append(node.id)
    for node in q.nodes:
        for ref in (node.knowledge.requires if node.knowledge else ()):
            for cid in b_about.get(ref.id, ()):
                out.append([node.id, cid])
    a_about = {}
    for node in q.nodes:
        for ref in (node.knowledge.about if node.knowledge else ()):
            a_about.setdefault(ref.id, []).append(node.id)
    for node in c.nodes:
        for ref in (node.knowledge.requires if node.knowledge else ()):
            for qid in a_about.get(ref.id, ()):
                pair = [qid, node.id]
                if pair not in out:
                    out.append(pair)
    return sorted(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--report")
    args = ap.parse_args()

    graphs = {}
    for line in (REPO / "benchmark/r0-v0.1/graphs.jsonl").read_text().splitlines():
        d = json.loads(line)
        graphs[d["benchmark_graph_id"]] = ThoughtGraph.from_dict(d["thought_dna"])
    pairs = [json.loads(line) for line in
             (REPO / "benchmark/r0-v0.1/pairs.jsonl").read_text().splitlines()]

    engine = ResonanceEngine()
    t0 = time.perf_counter()
    for graph in graphs.values():
        engine.index(graph)
    build_seconds = time.perf_counter() - t0

    def one(pair):
        query = graphs[pair["query_graph"]]
        target_id = pair["candidate_graph"]
        mode = MODE_BY_EVAL[pair["evaluation_mode"]]
        t1 = time.perf_counter()
        results = engine.candidate_index.query(query, mode=mode, k=20)
        rlat = time.perf_counter() - t1
        diag = engine.candidate_index.last_query
        hit = next((r for r in results if r.candidate_id == target_id), None)
        if hit is not None:
            rank = hit.channel_ranks.get("structural", 0) or 10**6
            if mode == "complementary":
                rank = hit.channel_ranks.get("knowledge", rank) or rank
            seeds = hit.seed_correspondences
            channel_scores = dict(hit.channel_scores)
        else:
            # Retrieval miss. Verification below is still oracle-inclusion.
            rank = 10**6
            seeds = ()
            channel_scores = {"structural": 0.0, "content": 0.0, "knowledge": 0.0}
        t2 = time.perf_counter()
        # Oracle-inclusion verification of the evaluator-selected pair.
        verification = engine.verifier.verify(query, graphs[target_id], seeds=seeds)
        vlat = time.perf_counter() - t2
        wire = verification.components.to_wire()
        edge_mapping = [[m.query_relation, m.candidate_relation]
                        for m in verification.matched_relations]
        edge_mapping += [[p.query_relation, list(p.candidate_relations)]
                         for p in verification.edge_path_matches]
        v = {
            "predicted_class": verification.classification,
            "node_mapping": sorted([m.query_node, m.candidate_node]
                                   for m in verification.mapping),
            "edge_mapping": sorted(edge_mapping, key=lambda x: (x[0], str(x[1]))),
            "bridge_mapping": bridge_mapping(query, graphs[target_id]),
            "hard_rejection": verification.hard_rejection,
            "false_contractions": 0,
            "components": wire,
            "latency_seconds": vlat,
        }
        return {
            "case_id": pair["case_id"],
            "retrieval": {
                "candidate_rank": min(rank, 10**6),
                "channel_scores": channel_scores,
                "requires_structural_verification": True,
                "polarity_reliable": False,
                "latency_seconds": rlat,
                "postings_touched": diag.postings_touched if diag else 0,
            },
            "verification": v,
            "replay": None,
        }

    records, misses = [], []
    for pair in pairs:
        rec = one(pair)
        rerun = one(pair)
        rec["replay"] = {
            "candidate_rank": rerun["retrieval"]["candidate_rank"],
            "predicted_class": rerun["verification"]["predicted_class"],
            "node_mapping": rerun["verification"]["node_mapping"],
            "edge_mapping": rerun["verification"]["edge_mapping"],
            "bridge_mapping": rerun["verification"]["bridge_mapping"],
            "hard_rejection": rerun["verification"]["hard_rejection"],
            "components": dict(rerun["verification"]["components"]),
        }
        if rec["retrieval"]["candidate_rank"] >= 10**6:
            misses.append(rec["case_id"])
        records.append(rec)

    with open(args.out, "w") as fh:
        for rec in records:
            fh.write(json.dumps(rec, sort_keys=True) + "\n")

    summary = {
        "engine_version": ENGINE_VERSION,
        "mode": "real_retrieval_rank_plus_oracle_inclusion_verification",
        "graphs_indexed": len(graphs),
        "index_build_seconds": round(build_seconds, 3),
        "pairs": len(records),
        "retrieval_misses_top20": misses,
    }
    if args.report:
        Path(args.report).write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
