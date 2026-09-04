#!/usr/bin/env python3
"""End-to-end Benchmark v0.2 evaluation of the Resonance engine.

Unlike the v0.1 runner (an external evaluator of submitted predictions) this
harness drives the engine directly so every number is reproducible from a
clean checkout:

    python3 benchmark/r0-v0.2/runner.py --output src/engine/reports/r0-v0.2-e2e.json

Gold never enters engine inputs. Retrieval ranks are measured against the
whole 176-graph corpus (8 skeletons x 4 domains x 18 families), so a rank is
earned against distractors that share roles, skeletons or vocabulary.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from src.engine import ResonanceEngine  # noqa: E402
from src.graph import ThoughtGraph  # noqa: E402

RETRIEVAL_K = (5, 20)
GATES = {
    "positive_recall_at_5": 0.85,
    "positive_recall_at_20": 0.95,
    "negative_false_positive_rate": 0.10,
    "polarity_rejection": 1.0,
    "classification_accuracy": 0.70,
    "positive_node_f1": 0.80,
    "analogy_over_coincidence": 1.0,
    "analogy_over_generic_motif": 1.0,
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def f1(pred: set, gold: set) -> float:
    if not pred and not gold:
        return 1.0
    if not pred or not gold:
        return 0.0
    tp = len(pred & gold)
    p = tp / len(pred)
    r = tp / len(gold)
    return 0.0 if p + r == 0 else 2 * p * r / (p + r)


def evaluate(engine_factory=ResonanceEngine, *, split: str | None = None, k_retrieval: int = 50) -> dict[str, Any]:
    graphs = {g["benchmark_graph_id"]: ThoughtGraph.from_dict(g["thought_dna"]) for g in read_jsonl(ROOT / "graphs.jsonl")}
    pairs = read_jsonl(ROOT / "pairs.jsonl")
    if split:
        pairs = [p for p in pairs if p["split"] == split]
    manifest = json.loads((ROOT / "manifest.json").read_text())
    engine = engine_factory()
    t0 = time.perf_counter()
    for g in graphs.values():
        engine.store.put(g)
    engine.candidate_index.build(graphs.values())
    build_seconds = time.perf_counter() - t0

    # retrieval: one query per skeleton. A positive's rank is counted among
    # DISTRACTORS only (1 + number of non-relevant graphs ranked above it):
    # twelve relevant candidates per query cannot all fit in a top-5, and a
    # relevant graph outranking another relevant graph is not a retrieval error.
    ranks: dict[str, dict[str, int]] = {}
    verified_order: dict[str, list[tuple[str, float, str]]] = {}
    relevant_for: dict[str, set[str]] = defaultdict(set)
    for p in pairs:
        if p["relevant"]:
            relevant_for[p["query_graph"]].add(p["candidate_graph"])
    for p in read_jsonl(ROOT / "pairs.jsonl"):
        if p["relevant"]:
            relevant_for[p["query_graph"]].add(p["candidate_graph"])
    for g in graphs:                       # plain analogy-domain graphs are relevant too
        if g.split("-A-")[0] + "-Q" in relevant_for and "-A-" in g:
            relevant_for[g.split("-A-")[0] + "-Q"].add(g)
    query_ids = sorted({p["query_graph"] for p in pairs})
    latencies = []
    comp_ranks: dict[str, dict[str, int]] = {}
    for qid in query_ids:
        t1 = time.perf_counter()
        hits = engine.find(graphs[qid], mode="analogical", k=k_retrieval)
        latencies.append(time.perf_counter() - t1)
        ranks[qid] = distractor_ranks(hits, relevant_for[qid])
        verified_order[qid] = [(h.candidate.candidate_id, h.verification.components.structural,
                                h.verification.classification) for h in hits]
        comp_hits = engine.find(graphs[qid], mode="complementary", k=k_retrieval)
        comp_ranks[qid] = distractor_ranks(comp_hits, relevant_for[qid])

    rows = []
    for p in pairs:
        q, c = graphs[p["query_graph"]], graphs[p["candidate_graph"]]
        res = engine.compare(q, c, mode="analogical")
        pred_nodes = {(m.query_node, m.candidate_node) for m in res.mapping}
        gold_nodes = {tuple(x) for x in p["gold_node_pairs"]}
        node_f1 = f1(pred_nodes, gold_nodes) if p["relevant"] else None
        rank_table = comp_ranks if p["gold_class"] == "complementary" else ranks
        rank = rank_table[p["query_graph"]].get(p["candidate_graph"])
        predicted_relevant = res.classification != "negative" and res.hard_rejection is None
        rows.append({
            "case_id": p["case_id"], "skeleton": p["skeleton"], "split": p["split"], "family": p["family"],
            "gold_class": p["gold_class"], "relevant": p["relevant"],
            "predicted_class": res.classification, "hard_rejection": res.hard_rejection,
            "confidence": res.confidence,
            "structural": round(res.components.structural, 4), "semantic": round(res.components.semantic, 4),
            "contradiction": round(res.components.contradiction, 4),
            "node_f1": None if node_f1 is None else round(node_f1, 4),
            "retrieval_rank": rank, "predicted_relevant": predicted_relevant,
            "class_correct": res.classification == p["gold_class"],
        })

    def summarize(subset: list[dict]) -> dict[str, Any]:
        pos = [r for r in subset if r["relevant"]]
        neg = [r for r in subset if not r["relevant"]]
        fam: dict[str, dict[str, Any]] = {}
        for r in subset:
            f = fam.setdefault(r["family"], {"n": 0, "class_correct": 0, "retrieved_at_5": 0, "retrieved_at_20": 0,
                                             "false_positive": 0, "node_f1_sum": 0.0, "hard_rejected": 0})
            f["n"] += 1
            f["class_correct"] += r["class_correct"]
            if r["retrieval_rank"] is not None and r["retrieval_rank"] <= 5:
                f["retrieved_at_5"] += 1
            if r["retrieval_rank"] is not None and r["retrieval_rank"] <= 20:
                f["retrieved_at_20"] += 1
            if not r["relevant"] and r["predicted_relevant"]:
                f["false_positive"] += 1
            if r["node_f1"] is not None:
                f["node_f1_sum"] += r["node_f1"]
            if r["hard_rejection"]:
                f["hard_rejected"] += 1
        for f in fam.values():
            f["node_f1"] = round(f["node_f1_sum"] / f["n"], 4)
            del f["node_f1_sum"]
        polarity = [r for r in neg if r["family"] == "polarity_flip"]
        # analogy ranking: verified structural score of the analogy must beat coincidence/generic per skeleton
        by_sk: dict[str, dict[str, float]] = defaultdict(dict)
        for r in subset:
            by_sk[r["skeleton"]][r["family"]] = (r["structural"], r["predicted_relevant"])
        a_over_c = a_over_g = 0
        n_sk = 0
        for sk, fams in by_sk.items():
            if "cross_domain_analogy" not in fams:
                continue
            n_sk += 1
            a = fams["cross_domain_analogy"]
            c = fams.get("template_coincidence", (0.0, False))
            g = fams.get("generic_motif_distractor", (0.0, False))
            a_over_c += int(a[1] and not c[1])
            a_over_g += int(a[1] and not g[1])
        metrics = {
            "pairs": len(subset),
            "positive_recall_at_5": round(sum(1 for r in pos if r["retrieval_rank"] and r["retrieval_rank"] <= 5) / max(len(pos), 1), 4),
            "positive_recall_at_20": round(sum(1 for r in pos if r["retrieval_rank"] and r["retrieval_rank"] <= 20) / max(len(pos), 1), 4),
            "negative_false_positive_rate": round(sum(1 for r in neg if r["predicted_relevant"]) / max(len(neg), 1), 4),
            "polarity_rejection": round(sum(1 for r in polarity if r["hard_rejection"]) / max(len(polarity), 1), 4),
            "classification_accuracy": round(sum(r["class_correct"] for r in subset) / max(len(subset), 1), 4),
            "positive_node_f1": round(sum(r["node_f1"] for r in pos) / max(len(pos), 1), 4),
            "analogy_over_coincidence": round(a_over_c / max(n_sk, 1), 4),
            "analogy_over_generic_motif": round(a_over_g / max(n_sk, 1), 4),
            "families": fam,
        }
        return metrics

    report: dict[str, Any] = {
        "benchmark_version": manifest["benchmark_version"],
        "fixture_files": manifest["files"],
        "engine": engine_identity(engine),
        "corpus_n": len(graphs), "build_seconds": round(build_seconds, 4),
        "query_latency_mean_seconds": round(sum(latencies) / max(len(latencies), 1), 4),
        "calibration": summarize([r for r in rows if r["split"] == "calibration"]),
        "gate": summarize([r for r in rows if r["split"] == "gate"]),
        "rows": rows,
    }
    gate = report["gate"]
    statuses = {}
    for name, required in GATES.items():
        observed = gate[name]
        ok = observed <= required if name == "negative_false_positive_rate" else observed >= required
        statuses[name] = {"observed": observed, "required": required, "status": "pass" if ok else "fail"}
    report["gates"] = statuses
    report["overall_status"] = "pass" if all(s["status"] == "pass" for s in statuses.values()) else "fail"
    return report


def distractor_ranks(hits, relevant: set[str]) -> dict[str, int]:
    ordered = sorted(hits, key=lambda h: (h.candidate.channel_ranks.get("primary", 10**9), h.candidate.candidate_id))
    out: dict[str, int] = {}
    distractors_above = 0
    for h in ordered:
        cid = h.candidate.candidate_id
        out[cid] = distractors_above + 1
        if cid not in relevant:
            distractors_above += 1
    return out


def engine_identity(engine: ResonanceEngine) -> dict[str, str]:
    from src.engine import ENGINE_VERSION
    return {"engine_version": ENGINE_VERSION,
            "verifier_config_hash": engine.verifier.config_hash,
            "index_config_hash": engine.candidate_index.config.config_hash}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", type=Path)
    ap.add_argument("--split", choices=("calibration", "gate"))
    ap.add_argument("--rows", action="store_true", help="print per-pair rows")
    args = ap.parse_args(argv)
    report = evaluate(split=args.split)
    if args.output:
        args.output.write_text(json.dumps(report, indent=1, sort_keys=True) + "\n")
    summary = dict(report)
    if not args.rows:
        summary.pop("rows")
        for split in ("calibration", "gate"):
            summary[split] = {k: v for k, v in summary[split].items() if k != "families"}
    print(json.dumps(summary, indent=1, sort_keys=True))
    return 0 if report["overall_status"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
