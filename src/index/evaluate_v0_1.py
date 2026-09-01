"""Measure shipping retrieval against frozen Benchmark v0.1 graphs.

Does not mutate frozen gold. Uses public ``build()``.
"""

from __future__ import annotations

import hashlib
import json
import random
import time
from pathlib import Path

from src.graph import ThoughtGraph
from src.index import QUERY_BUDGET, InvertedCandidateIndex

EMPTY_SHA = hashlib.sha256(b"").hexdigest()
ROLES = (
    "problem", "mechanism", "state", "outcome", "constraint",
    "method", "evidence", "resource", "agent",
)
REL_TYPES = (
    "causes", "prevents", "requires", "part_of", "constrains", "supports", "contradicts",
)

REPO = Path(__file__).resolve().parents[2]
BENCHMARK = REPO / "benchmark" / "r0-v0.1"
REPORT = Path(__file__).resolve().parent / "reports" / "r0-v0.1-retrieval.json"
GATE_ANALOGY = [
    ("G01-09", "G01-Q", "G01-C09"),
    ("G02-09", "G02-Q", "G02-C09"),
    ("G03-09", "G03-Q", "G03-C09"),
    ("G04-09", "G04-Q", "G04-C09"),
    ("G05-09", "G05-Q", "G05-C09"),
    ("G06-09", "G06-Q", "G06-C09"),
]


def _load_graphs() -> dict[str, ThoughtGraph]:
    graphs: dict[str, ThoughtGraph] = {}
    for line in (BENCHMARK / "graphs.jsonl").read_text(encoding="utf-8").splitlines():
        record = json.loads(line)
        graph = ThoughtGraph.from_dict(record["thought_dna"])
        graphs[record["benchmark_graph_id"]] = graph
    return graphs


def _filler(rng: random.Random, index: int) -> ThoughtGraph:
    n = rng.randint(4, 8)
    nodes = []
    for i in range(n):
        nodes.append(
            {
                "id": f"n{i}",
                "label": f"syn-{index}-{i}",
                "role": ROLES[rng.randrange(len(ROLES))],
                "spans": [],
                "extract_conf": 1.0,
                "atomic": True,
                "assertion": "asserted",
                "modality": "actual",
            }
        )
    relations = []
    for i in range(n - 1):
        relations.append(
            {
                "id": f"r{i}",
                "source": f"n{i}",
                "target": f"n{i + 1}",
                "type": REL_TYPES[rng.randrange(len(REL_TYPES))],
                "extract_conf": 1.0,
                "spans": [],
                "assertion": "asserted",
                "modality": "actual",
            }
        )
    return ThoughtGraph.from_dict(
        {
            "schema_version": "thought-dna/0.1",
            "thought_id": f"syn-{index}",
            "source": {"text": "", "sha256": EMPTY_SHA},
            "provenance": {"kind": "manual", "extractor": None, "human_id": "r3-e1-synthetic"},
            "nodes": nodes,
            "relations": relations,
        }
    )


def measure_e1_companion(graphs: dict[str, ThoughtGraph], *, n_fillers: int = 1000, seed: int = 1729) -> dict[str, object]:
    """DNA-native MULTI companion: analogue vs generic distractors in a synthetic world."""
    query = graphs["G01-Q"]
    analogue = graphs["G01-C09"]
    generics = [graphs["G01-C13"], graphs["G02-C13"], graphs["G03-C13"]]
    polarity = graphs["G01-C10"]
    rng = random.Random(seed)
    fillers = [_filler(rng, i) for i in range(n_fillers)]
    index = InvertedCandidateIndex()
    started = time.perf_counter()
    index.build([analogue, polarity, *generics, *fillers])
    build_seconds = time.perf_counter() - started
    hits = index.query(query, mode="structural", k=max(50, n_fillers))
    ranks = {hit.candidate_id: hit.channel_ranks["structural"] for hit in hits}
    scores = {hit.candidate_id: hit.channel_scores["structural"] for hit in hits}
    analogue_rank = ranks.get(analogue.thought_id)
    analogue_score = scores.get(analogue.thought_id, 0.0)
    generic_ranks = {g.thought_id: ranks.get(g.thought_id) for g in generics}
    generic_scores = {g.thought_id: scores.get(g.thought_id, 0.0) for g in generics}
    best_generic_rank = min((rank for rank in generic_ranks.values() if rank is not None), default=10**9)
    best_generic_score = max(generic_scores.values()) if generic_scores else 0.0
    polarity_rank = ranks.get(polarity.thought_id)
    multi_pass = (
        analogue_rank is not None
        and analogue_rank < best_generic_rank
        and analogue_score > best_generic_score
    )
    diag = index.last_query
    return {
        "world": "rich_random_dna_native",
        "corpus_size": n_fillers + 1 + 1 + len(generics),
        "seed": seed,
        "synthetic": True,
        "multi_true_rank": analogue_rank,
        "multi_true_score": analogue_score,
        "best_generic_rank": best_generic_rank if best_generic_rank < 10**9 else None,
        "best_generic_score": best_generic_score,
        "polarity_flip_rank": polarity_rank,
        "polarity_reliable": False,
        "multi_pass": multi_pass,
        "build_seconds": build_seconds,
        "postings_touched": diag.postings_touched if diag else None,
        "query_latency_seconds": diag.latency_seconds if diag else None,
        "cutoff": index._cutoff_value,
        "dead_keys": len(index._structural_dead),
        "live_keys": len(index._structural_df) - len(index._structural_dead),
        "notes": "N=1000 DNA-native companion only; 10^4/10^5 scale replay is not claimed.",
    }


def measure() -> dict[str, object]:
    graphs = _load_graphs()
    index = InvertedCandidateIndex()
    started = time.perf_counter()
    index.build(graphs.values())
    build_seconds = time.perf_counter() - started
    rows = []
    in_top20 = 0
    in_tied_best = 0
    for case_id, query_id, analogue_id in GATE_ANALOGY:
        hits = index.query(graphs[query_id], mode="structural", k=20)
        diag = index.last_query
        scores = {hit.candidate_id: hit.channel_scores["structural"] for hit in hits}
        ranks = {hit.candidate_id: hit.channel_ranks["structural"] for hit in hits}
        analogue_score = scores.get(analogue_id, 0.0)
        best = max(scores.values()) if scores else 0.0
        rank = ranks.get(analogue_id)
        tied = analogue_score == best and analogue_id in scores
        if rank is not None and rank <= 20:
            in_top20 += 1
        if tied:
            in_tied_best += 1
        rows.append(
            {
                "case_id": case_id,
                "analogue_rank": rank,
                "analogue_score": analogue_score,
                "best_score": best,
                "tied_best": tied,
                "returned": diag.returned if diag else None,
                "tie_group_expanded": diag.tie_group_expanded if diag else None,
                "postings_touched": diag.postings_touched if diag else None,
                "latency_seconds": diag.latency_seconds if diag else None,
                "budget_used": diag.budget_used if diag else None,
                "skipped_dead_keys": diag.skipped_dead_keys if diag else None,
                "content_scanned": diag.content_scanned if diag else None,
            }
        )
    report = {
        "index_version": index.config.component_version,
        "feature_version": index.query(graphs["G01-Q"], mode="structural", k=1)[0].feature_version,
        "config_hash": index.config.config_hash,
        "corpus_n": len(graphs),
        "query_budget": QUERY_BUDGET,
        "cutoff": index._cutoff_value,
        "dead_keys": len(index._structural_dead),
        "live_keys": len(index._structural_df) - len(index._structural_dead),
        "build_seconds": build_seconds,
        "gate_cross_domain_analogy": rows,
        "recall_at_20": in_top20 / len(GATE_ANALOGY),
        "tied_best_rate": in_tied_best / len(GATE_ANALOGY),
        "tie_policy": index.last_query.tie_policy if index.last_query else None,
        "structural_recall_at_20_claimed": in_top20 == len(GATE_ANALOGY),
        "e1_companion_n1000": measure_e1_companion(graphs, n_fillers=1000, seed=1729),
        "notes": (
            "Tie policy is competition min-rank; query(k) includes the full "
            "boundary tie group. Frozen Recall@20 uses channel_ranks, not list "
            "position. 72 MULTI-identical graphs share rank 1; that is disclosed "
            "as the tie group, not as 72 distinct scores. Shipping DF policy for "
            "n<1000 uses small_corpus_max_df_frac=0.90. E1 companion is DNA-native "
            "MULTI at N=1000 only; 10^4/10^5 is not claimed."
        ),
    }
    return report


def main() -> None:
    report = measure()
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
