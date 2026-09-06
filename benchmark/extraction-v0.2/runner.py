#!/usr/bin/env python3
"""Evaluate the cue extractor on the prose cases (no LLM anywhere).

Node match: gold label vs predicted label by stem containment/Jaccard >= 0.5.
Edge match: both endpoints matched and same type; assertion/modality scored
separately on matched edges. Roles scored on matched nodes.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(ROOT))

from cases import CASES  # noqa: E402
from src.extraction import CueExtractor  # noqa: E402
from src.semantics import stems  # noqa: E402

GATES = {"nonempty_rate": 1.0, "node_f1": 0.70, "edge_f1": 0.60, "role_accuracy": 0.60,
         "assertion_accuracy": 0.90, "modality_accuracy": 0.80, "determinism": 1.0, "pii_leaks": 0}


def _match(gold: str, pred: str) -> bool:
    g, p = set(stems(gold)), set(stems(pred))
    if not g or not p:
        return False
    inter = len(g & p)
    if inter == 0:
        return False
    if g <= p or p <= g:
        return True
    return inter / len(g | p) >= 0.5


def evaluate(extractor: CueExtractor | None = None) -> dict:
    extractor = extractor or CueExtractor()
    rows = []
    tn = tp_n = fp_n = fn_n = 0
    tp_e = fp_e = fn_e = 0
    role_ok = role_n = 0
    asr_ok = mod_ok = matched_edges = 0
    nonempty_ok = 0
    deterministic = 0
    pii_leaks = 0
    for case in CASES:
        r1 = extractor.extract(case["text"], source_id=case["id"])
        r2 = extractor.extract(case["text"], source_id=case["id"])
        deterministic += int(r1.graph.to_dict() == r2.graph.to_dict())
        g = r1.graph
        by = {n.id: n for n in g.nodes}
        pred_nodes = [(n.label, n.role) for n in g.nodes]
        pred_edges = [(by[e.source].label, e.type, by[e.target].label, e.assertion, e.modality) for e in g.relations]
        expect_empty = not case["nodes"]
        nonempty_ok += int((not g.relations) if expect_empty else bool(g.relations))
        # node alignment (greedy, gold-first)
        used = set()
        node_map = {}
        for gl, grole in case["nodes"]:
            for j, (pl, prole) in enumerate(pred_nodes):
                if j in used:
                    continue
                if _match(gl, pl):
                    used.add(j)
                    node_map[gl] = pl
                    role_n += 1
                    role_ok += int(grole == prole)
                    break
        tp_n += len(node_map)
        fn_n += len(case["nodes"]) - len(node_map)
        fp_n += len(pred_nodes) - len(used)
        # edges
        pred_set = list(pred_edges)
        hit = 0
        for gs_, gt, gd, ga, gm in case["edges"]:
            found = None
            for k, (ps, pt, pd, pa, pm) in enumerate(pred_set):
                if pt == gt and _match(gs_, ps) and _match(gd, pd):
                    found = k
                    break
            if found is not None:
                ps, pt, pd, pa, pm = pred_set.pop(found)
                hit += 1
                matched_edges += 1
                asr_ok += int(pa == ga)
                mod_ok += int(pm == gm)
        tp_e += hit
        fn_e += len(case["edges"]) - hit
        fp_e += len(pred_set)
        for forbidden in case.get("forbidden_label_text", ()):
            if any(forbidden.lower() in n.label.lower() for n in g.nodes):
                pii_leaks += 1
        rows.append({"id": case["id"], "pred_nodes": pred_nodes, "pred_edges": pred_edges,
                     "gold_edges": len(case["edges"]), "matched_edges": hit,
                     "abstentions": list(r1.abstentions)})

    def prf(tp, fp, fn):
        p = tp / (tp + fp) if tp + fp else 0.0
        r = tp / (tp + fn) if tp + fn else 0.0
        f = 2 * p * r / (p + r) if p + r else 0.0
        return round(p, 4), round(r, 4), round(f, 4)

    np_, nr, nf = prf(tp_n, fp_n, fn_n)
    ep, er, ef = prf(tp_e, fp_e, fn_e)
    n = len(CASES)
    metrics = {
        "cases": n,
        "nonempty_rate": round(nonempty_ok / n, 4),
        "node_precision": np_, "node_recall": nr, "node_f1": nf,
        "edge_precision": ep, "edge_recall": er, "edge_f1": ef,
        "role_accuracy": round(role_ok / role_n, 4) if role_n else 0.0,
        "assertion_accuracy": round(asr_ok / matched_edges, 4) if matched_edges else 0.0,
        "modality_accuracy": round(mod_ok / matched_edges, 4) if matched_edges else 0.0,
        "determinism": round(deterministic / n, 4),
        "pii_leaks": pii_leaks,
    }
    gates = {}
    for k, req in GATES.items():
        obs = metrics[k]
        ok = obs <= req if k == "pii_leaks" else obs >= req
        gates[k] = {"observed": obs, "required": req, "status": "pass" if ok else "fail"}
    from src.extraction import EXTRACTOR_ID, EXTRACTOR_VERSION
    return {"extractor": {"id": EXTRACTOR_ID, "version": EXTRACTOR_VERSION}, "metrics": metrics, "gates": gates,
            "overall_status": "pass" if all(g["status"] == "pass" for g in gates.values()) else "fail", "rows": rows}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", type=Path)
    ap.add_argument("--rows", action="store_true")
    args = ap.parse_args(argv)
    report = evaluate()
    if args.output:
        args.output.write_text(json.dumps(report, indent=1, sort_keys=True) + "\n")
    out = dict(report)
    if not args.rows:
        out.pop("rows")
    print(json.dumps(out, indent=1, sort_keys=True))
    return 0 if report["overall_status"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
