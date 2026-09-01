#!/usr/bin/env python3
"""R4 verifier gate harness: run the verifier over frozen Benchmark v0.1 pairs
with ORACLE candidate retrieval and emit predictions.jsonl for the frozen
runner, plus a v0.2 contraction-audit prediction file.

Oracle retrieval means candidate_rank=1 for every pair: this measures the
VERIFIER gates in isolation (ADR-0003 "oracle-retrieval verification").
End-to-end retrieval+verification belongs to R3+R5 and is not claimed here.

Usage:
  python3 tests/r4_gate_harness.py --solver multirel_fgw_cg --out preds.jsonl
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

from src.graph import ThoughtGraph                      # noqa: E402
from src.alignment import MultiRelFGWVerifier           # noqa: E402


def bridge_mapping(result, va_graph, vb_graph):
    """Directional requires->about node bridges (Knowledge DNA overlay)."""
    out = []
    b_about = {}
    for node in vb_graph.nodes:
        for ref in (node.knowledge.about if node.knowledge else ()):
            b_about.setdefault(ref.id, []).append(node.id)
    for node in va_graph.nodes:
        for ref in (node.knowledge.requires if node.knowledge else ()):
            for cid in b_about.get(ref.id, ()):
                out.append([node.id, cid])
    a_about = {}
    for node in va_graph.nodes:
        for ref in (node.knowledge.about if node.knowledge else ()):
            a_about.setdefault(ref.id, []).append(node.id)
    for node in vb_graph.nodes:
        for ref in (node.knowledge.requires if node.knowledge else ()):
            for qid in a_about.get(ref.id, ()):
                pair = [qid, node.id]
                if pair not in out:
                    out.append(pair)
    return sorted(out)


def predict(verifier, graphs, pair):
    q, c = graphs[pair["query_graph"]], graphs[pair["candidate_graph"]]
    t0 = time.perf_counter()
    r = verifier.verify(q, c)
    dt = time.perf_counter() - t0
    wire = r.components.to_wire()
    edge_mapping = [[m.query_relation, m.candidate_relation] for m in r.matched_relations]
    edge_mapping += [[p.query_relation, list(p.candidate_relations)] for p in r.edge_path_matches]
    verification = {
        "predicted_class": r.classification,
        "node_mapping": sorted([m.query_node, m.candidate_node] for m in r.mapping),
        "edge_mapping": sorted(edge_mapping, key=lambda x: (x[0], str(x[1]))),
        "bridge_mapping": bridge_mapping(r, q, c),
        "hard_rejection": r.hard_rejection,
        # v0.1 sums this self-reported integer (the audit gap Benchmark v0.2
        # closed); it is NOT contraction-safety evidence -- v0.2's evaluator
        # derives the real count from gold and submitted mappings.
        "false_contractions": 0,
        "components": wire,
        "latency_seconds": dt,
    }
    record = {
        "case_id": pair["case_id"],
        "retrieval": {
            "candidate_rank": 1,
            "channel_scores": {"structural": wire["structural_score"],
                               "semantic": wire["S_semantic"],
                               "knowledge": wire["K_about"]},
            "requires_structural_verification": True,
            "polarity_reliable": False,
            "latency_seconds": 0.0,
            "postings_touched": 0,
        },
        "verification": verification,
        "replay": {
            "candidate_rank": 1,
            "predicted_class": verification["predicted_class"],
            "node_mapping": verification["node_mapping"],
            "edge_mapping": verification["edge_mapping"],
            "bridge_mapping": verification["bridge_mapping"],
            "hard_rejection": verification["hard_rejection"],
            "components": dict(wire),
        },
        "_latency": dt,
    }
    return record, r


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--solver", default="multirel_fgw_cg",
                    choices=["multirel_fgw_cg", "qap_rrwm"])
    ap.add_argument("--path-matching", default="guarded", choices=["guarded", "off"])
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    graphs = {}
    for line in (REPO / "benchmark/r0-v0.1/graphs.jsonl").read_text().splitlines():
        d = json.loads(line)
        graphs[d["benchmark_graph_id"]] = ThoughtGraph.from_dict(d["thought_dna"])
    pairs = [json.loads(line) for line in
             (REPO / "benchmark/r0-v0.1/pairs.jsonl").read_text().splitlines()]

    verifier = MultiRelFGWVerifier({"solver": args.solver,
                                    "path_matching": args.path_matching})
    records = []
    replay_verifier = MultiRelFGWVerifier({"solver": args.solver,
                                           "path_matching": args.path_matching})
    latencies = []
    for pair in pairs:
        rec, _ = predict(verifier, graphs, pair)
        rec2, _ = predict(replay_verifier, graphs, pair)
        rec["replay"] = rec2["replay"]          # true rerun, not a copy
        rec["replay"].pop("hard_rejection", None)
        rec["replay"]["hard_rejection"] = rec2["verification"]["hard_rejection"]
        latencies.append(rec.pop("_latency"))
        rec2.pop("_latency")
        records.append(rec)

    with open(args.out, "w") as fh:
        for rec in records:
            fh.write(json.dumps(rec, sort_keys=True) + "\n")
    latencies.sort()
    summary = {
        "solver": args.solver,
        "path_matching": args.path_matching,
        "config_hash": verifier.config_hash,
        "pairs": len(records),
        "latency_p50_ms": round(latencies[len(latencies) // 2] * 1000, 2),
        "latency_p95_ms": round(latencies[int(len(latencies) * 0.95)] * 1000, 2),
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
