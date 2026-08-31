#!/usr/bin/env python3
"""Build the deterministic, authored Benchmark v0.1 fixture corpus.

The generator is the reviewable source for the JSONL assets. It contains no
engine implementation and no expected numeric model scores.
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
AGENT_ID = "parshkov-openai-gpt5-codex-s7d3"
SCHEMA_VERSION = "thought-dna/0.1"
APPROVALS = json.loads((ROOT / "review_approvals.json").read_text(encoding="utf-8"))
NODE_ROLES = (
    "problem",
    "mechanism",
    "state",
    "constraint",
    "method",
    "outcome",
    "evidence",
    "resource",
    "agent",
    "mechanism",
)
RELATION_TYPES = (
    "causes",
    "causes",
    "causes",
    "constrains",
    "prevents",
    "requires",
    "supports",
    "part_of",
    "causes",
    "supports",
)
BASE_EDGES = (
    (0, 1),
    (1, 2),
    (2, 5),
    (3, 4),
    (4, 5),
    (4, 7),
    (6, 4),
    (9, 1),
    (9, 2),
    (8, 4),
)
FAMILIES = (
    "paraphrase",
    "vocabulary_substitution",
    "irrelevant_branch",
    "partial_graph",
    "transparent_granularity",
    "same_domain_structural_match",
    "serialization_permutation",
    "modest_extraction_error",
    "cross_domain_analogy",
    "same_vocabulary_wrong_structure",
    "same_topic_different_intent",
    "local_match_global_conflict",
    "generic_motif_distractor",
    "accidental_semantic_similarity",
    "branch_continuation",
    "method_knowledge_bridge",
)
GOLD_CLASSES = (
    "direct",
    "approximate",
    "approximate",
    "approximate",
    "approximate",
    "direct",
    "direct",
    "approximate",
    "analogical",
    "negative",
    "negative",
    "negative",
    "negative",
    "negative",
    "complementary",
    "complementary",
)
REVIEW_REQUIRED = frozenset(
    {
        "same_domain_structural_match",
        "cross_domain_analogy",
        "same_topic_different_intent",
        "local_match_global_conflict",
        "generic_motif_distractor",
        "accidental_semantic_similarity",
        "branch_continuation",
        "method_knowledge_bridge",
    }
)

DOMAINS = {
    "battery": (
        "high cell heat",
        "electrolyte breakdown",
        "rising resistance",
        "charging speed limit",
        "thermal control",
        "capacity loss",
        "impedance readings",
        "cooling hardware",
        "battery controller",
        "side-reaction loop",
    ),
    "software": (
        "request burst",
        "retry amplification",
        "queue saturation",
        "response deadline",
        "exponential backoff",
        "service outage",
        "latency trace",
        "jitter budget",
        "service operator",
        "timeout cascade",
    ),
    "organization": (
        "ambiguous ownership",
        "coordination churn",
        "decision backlog",
        "staffing limit",
        "clear delegation",
        "missed launch",
        "handoff audit",
        "review capacity",
        "program lead",
        "approval loop",
    ),
    "eutrophication": (
        "nutrient runoff",
        "algal bloom",
        "oxygen depletion",
        "watershed limit",
        "buffer restoration",
        "fish mortality",
        "oxygen survey",
        "wetland area",
        "watershed council",
        "decomposition loop",
    ),
    "medicine": (
        "tumor burden",
        "resistance pathway",
        "disease persistence",
        "toxicity ceiling",
        "combination therapy",
        "clinical decline",
        "biomarker evidence",
        "treatment capacity",
        "care team",
        "escape mechanism",
    ),
    "liquidity": (
        "asset selloff",
        "margin-call cascade",
        "market illiquidity",
        "capital constraint",
        "liquidity facility",
        "institution failure",
        "spread evidence",
        "cash reserve",
        "risk committee",
        "fire-sale loop",
    ),
    "learning": (
        "missing prerequisite",
        "misconception reinforcement",
        "learning plateau",
        "time constraint",
        "scaffolded practice",
        "assessment failure",
        "error evidence",
        "worked examples",
        "instructor",
        "feedback loop",
    ),
    "supply": (
        "supplier disruption",
        "order amplification",
        "inventory shortage",
        "warehouse limit",
        "demand smoothing",
        "delivery failure",
        "stockout evidence",
        "safety inventory",
        "planner",
        "expediting loop",
    ),
}

PACKS = (
    ("C01", "calibration", "battery", "software"),
    ("C02", "calibration", "organization", "eutrophication"),
    ("G01", "gate", "software", "liquidity"),
    ("G02", "gate", "eutrophication", "learning"),
    ("G03", "gate", "medicine", "supply"),
    ("G04", "gate", "liquidity", "battery"),
    ("G05", "gate", "learning", "organization"),
    ("G06", "gate", "supply", "medicine"),
)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def source_record(text: str) -> dict[str, str]:
    return {"text": text, "sha256": sha256_bytes(text.encode("utf-8"))}


def relation_records(edges: tuple[tuple[int, int], ...] = BASE_EDGES) -> list[dict[str, Any]]:
    return [
        {
            "id": f"r{i}",
            "source": f"n{source}",
            "target": f"n{target}",
            "type": RELATION_TYPES[i],
            "extract_conf": 1.0,
            "spans": [],
            "assertion": "asserted",
            "modality": "actual",
        }
        for i, (source, target) in enumerate(edges)
    ]


def make_graph(
    graph_id: str,
    labels: tuple[str, ...] | list[str],
    pack_id: str,
    *,
    relations: list[dict[str, Any]] | None = None,
    extra_nodes: list[dict[str, Any]] | None = None,
    reverse_serialization: bool = False,
) -> dict[str, Any]:
    nodes = []
    for i, (label, role) in enumerate(zip(labels, NODE_ROLES, strict=True)):
        node: dict[str, Any] = {
            "id": f"n{i}",
            "label": label,
            "role": role,
            "spans": [],
            "extract_conf": 1.0,
            "atomic": True,
            "assertion": "asserted",
            "modality": "actual",
        }
        if i == 4:
            node["knowledge"] = {
                "about": [],
                "requires": [{"id": f"local:{pack_id}:method-input", "conf": 1.0, "via": "benchmark"}],
            }
        elif i == 5:
            node["knowledge"] = {
                "about": [],
                "requires": [{"id": f"local:{pack_id}:continuation", "conf": 1.0, "via": "benchmark"}],
            }
        nodes.append(node)
    nodes.extend(deepcopy(extra_nodes or []))
    rels = deepcopy(relations if relations is not None else relation_records())
    if reverse_serialization:
        nodes.reverse()
        rels.reverse()
    text = f"Manual benchmark graph {graph_id}."
    thought = {
        "schema_version": SCHEMA_VERSION,
        "thought_id": graph_id,
        "source": source_record(text),
        "provenance": {"kind": "manual", "extractor": None, "human_id": AGENT_ID},
        "nodes": nodes,
        "relations": rels,
    }
    return {"benchmark_graph_id": graph_id, "thought_dna": thought}


def all_node_pairs(indices: set[int] | None = None) -> list[list[str]]:
    use = indices if indices is not None else set(range(10))
    return [[f"n{i}", f"n{i}"] for i in sorted(use)]


def all_edge_pairs(relations: list[dict[str, Any]]) -> list[list[Any]]:
    return [[rel["id"], rel["id"]] for rel in relations]


def review_record(family: str, case_id: str) -> dict[str, Any]:
    required = family in REVIEW_REQUIRED
    reviewer = APPROVALS["pair_approvals"].get(case_id) if required else None
    return {
        "required": required,
        "status": ("approved" if reviewer else "pending") if required else "generated",
        "reviewer": reviewer,
    }


def build_pack(pack_id: str, split: str, query_domain: str, analogy_domain: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    query_labels = DOMAINS[query_domain]
    analogy_labels = DOMAINS[analogy_domain]
    query_id = f"{pack_id}-Q"
    graphs = [make_graph(query_id, query_labels, pack_id)]
    pairs: list[dict[str, Any]] = []

    for family_index, (family, gold_class) in enumerate(zip(FAMILIES, GOLD_CLASSES, strict=True), start=1):
        candidate_id = f"{pack_id}-C{family_index:02d}"
        labels: tuple[str, ...] | list[str] = query_labels
        relations = relation_records()
        extra_nodes: list[dict[str, Any]] = []
        node_pairs = all_node_pairs()
        edge_pairs: list[list[Any]] = all_edge_pairs(relations)
        bridge_pairs: list[list[str]] = []
        transform: dict[str, Any] = {"operation": family}
        reverse = False

        if family == "paraphrase":
            labels = tuple(f"rephrased {label}" for label in query_labels)
        elif family in {"vocabulary_substitution", "cross_domain_analogy"}:
            labels = analogy_labels
        elif family == "irrelevant_branch":
            extra_nodes = [
                {"id": "x0", "label": "unrelated observation", "role": "evidence", "spans": [], "extract_conf": 1.0, "atomic": True, "assertion": "asserted", "modality": "actual"},
                {"id": "x1", "label": "unrelated side outcome", "role": "outcome", "spans": [], "extract_conf": 1.0, "atomic": True, "assertion": "asserted", "modality": "actual"},
            ]
            relations.extend(
                [{"id": "rx0", "source": "x0", "target": "x1", "type": "supports", "extract_conf": 1.0, "spans": [], "assertion": "asserted", "modality": "actual"}]
            )
        elif family == "partial_graph":
            kept = set(range(10)) - {6, 7}
            node_pairs = all_node_pairs(kept)
            relations = [r for r in relations if int(r["source"][1:]) in kept and int(r["target"][1:]) in kept]
            edge_pairs = all_edge_pairs(relations)
        elif family == "transparent_granularity":
            extra_nodes = [
                {"id": "x0", "label": "transparent causal step", "role": "mechanism", "spans": [], "extract_conf": 1.0, "atomic": False, "assertion": "asserted", "modality": "actual"}
            ]
            relations = [r for r in relations if r["id"] != "r0"]
            relations.extend(
                [
                    {"id": "r0a", "source": "n0", "target": "x0", "type": "causes", "extract_conf": 1.0, "spans": [], "assertion": "asserted", "modality": "actual"},
                    {"id": "r0b", "source": "x0", "target": "n1", "type": "causes", "extract_conf": 1.0, "spans": [], "assertion": "asserted", "modality": "actual"},
                ]
            )
            edge_pairs = [["r0", ["r0a", "r0b"]]] + [[f"r{i}", f"r{i}"] for i in range(1, 10)]
        elif family == "same_domain_structural_match":
            labels = tuple(f"variant {label}" for label in query_labels)
        elif family == "serialization_permutation":
            reverse = True
        elif family == "modest_extraction_error":
            extra_nodes = [
                {"id": "x0", "label": "spurious extraction", "role": "state", "spans": [], "extract_conf": 0.55, "atomic": True, "assertion": "asserted", "modality": "possible"}
            ]
            relations[8]["type"] = "supports"
            edge_pairs = [[f"r{i}", f"r{i}"] for i in range(10) if i != 8]
        elif family == "same_vocabulary_wrong_structure":
            if pack_id in {"G01", "G02"}:
                relations[0]["type"] = "prevents"
                transform["negative_subtype"] = "polarity_flip"
            elif pack_id in {"G03", "G04"}:
                relations[0]["source"], relations[0]["target"] = relations[0]["target"], relations[0]["source"]
                transform["negative_subtype"] = "direction_reversal"
            else:
                relations[0]["target"] = "n5"
                relations[2]["target"] = "n1"
                transform["negative_subtype"] = "broader_rewire"
            node_pairs = []
            edge_pairs = []
        elif family == "same_topic_different_intent":
            relations[4]["type"] = "causes"
            relations[3]["target"] = "n5"
            node_pairs = []
            edge_pairs = []
        elif family == "local_match_global_conflict":
            relations[2]["source"], relations[2]["target"] = "n5", "n2"
            relations[4]["type"] = "causes"
            node_pairs = []
            edge_pairs = []
        elif family == "generic_motif_distractor":
            labels = tuple(f"generic {role}" for role in NODE_ROLES)
            relations[3]["type"] = "causes"
            relations[5]["target"] = "n5"
            node_pairs = []
            edge_pairs = []
        elif family == "accidental_semantic_similarity":
            relations = relation_records(((0, 5), (5, 1), (7, 2), (4, 3), (5, 4), (7, 4), (4, 6), (1, 9), (2, 9), (4, 8)))
            node_pairs = []
            edge_pairs = []
        elif family == "branch_continuation":
            labels = tuple(f"continuation {label}" for label in analogy_labels)
            node_pairs = []
            edge_pairs = []
            bridge_pairs = [["n5", "n0"]]
        elif family == "method_knowledge_bridge":
            labels = tuple(f"knowledge bridge {label}" for label in analogy_labels)
            node_pairs = []
            edge_pairs = []
            bridge_pairs = [["n4", "n0"]]

        candidate = make_graph(
            candidate_id,
            labels,
            pack_id,
            relations=relations,
            extra_nodes=extra_nodes,
            reverse_serialization=reverse,
        )
        if family == "partial_graph":
            candidate["thought_dna"]["nodes"] = [
                node for node in candidate["thought_dna"]["nodes"] if node["id"] not in {"n6", "n7"}
            ]
        if family == "modest_extraction_error":
            next(node for node in candidate["thought_dna"]["nodes"] if node["id"] == "n2")["role"] = "mechanism"
        if family == "branch_continuation":
            next(node for node in candidate["thought_dna"]["nodes"] if node["id"] == "n0")["knowledge"] = {
                "about": [{"id": f"local:{pack_id}:continuation", "conf": 1.0, "via": "benchmark"}],
                "requires": [],
            }
        if family == "method_knowledge_bridge":
            next(node for node in candidate["thought_dna"]["nodes"] if node["id"] == "n0")["knowledge"] = {
                "about": [{"id": f"local:{pack_id}:method-input", "conf": 1.0, "via": "benchmark"}],
                "requires": [],
            }
        graphs.append(candidate)

        rationale = {
            "paraphrase": "Surface wording changes while the directed typed system is preserved.",
            "vocabulary_substitution": "Concept vocabulary changes while roles and relations are preserved.",
            "irrelevant_branch": "A disconnected grounded branch is unmatched evidence, not a contradiction.",
            "partial_graph": "A twenty-percent partial observation preserves the surviving correspondence.",
            "transparent_granularity": "One causes edge is reversibly subdivided through an atomic=false mechanism.",
            "same_domain_structural_match": "A reviewed same-domain variant preserves the complete relation system.",
            "serialization_permutation": "Only node and relation list order changes.",
            "modest_extraction_error": "One role, one relation and one low-confidence spurious node model extraction noise.",
            "cross_domain_analogy": "Disjoint domain labels instantiate the same connected directed typed system.",
            "same_vocabulary_wrong_structure": "Labels are retained while a required anti-invariant changes.",
            "same_topic_different_intent": "Topic words remain but the governing intervention has the opposite intent.",
            "local_match_global_conflict": "Local chains survive while governing outcome relations conflict globally.",
            "generic_motif_distractor": "A common causal constellation lacks the intended role/relation binding.",
            "accidental_semantic_similarity": "Concept labels overlap but relation endpoints are systematically rewired.",
            "branch_continuation": "Candidate knowledge begins at the query's explicitly open outcome branch.",
            "method_knowledge_bridge": "Query method requires the concept marked about on the candidate start node.",
        }[family]
        pair = {
            "case_id": f"{pack_id}-{family_index:02d}",
            "pack_id": pack_id,
            "split": split,
            "family": family,
            "query_graph": query_id,
            "candidate_graph": candidate_id,
            "gold_class": gold_class,
            "evaluation_mode": "complementary" if gold_class == "complementary" else ("analogical" if gold_class == "analogical" else "structural"),
            "relevant": gold_class != "negative",
            "gold_node_pairs": node_pairs,
            "gold_edge_pairs": edge_pairs,
            "equivalent_mapping_sets": [],
            "bridge_pairs": bridge_pairs,
            "transform_manifest": transform,
            "rationale": rationale,
            "review": review_record(family, f"{pack_id}-{family_index:02d}"),
        }
        pairs.append(pair)
    return graphs, pairs


def extracted_reference(pack_id: str, split: str, labels: tuple[str, ...], run_index: int) -> dict[str, Any]:
    pieces: list[str] = []
    spans: list[dict[str, Any]] = []
    offset = 0
    for label in labels:
        if pieces:
            offset += 1
        pieces.append(label)
        spans.append({"start": offset, "end": offset + len(label), "text": label})
        offset += len(label)
    text = " ".join(pieces)
    nodes = [
        {
            "id": f"n{i}",
            "label": label,
            "role": NODE_ROLES[i],
            "spans": [spans[i]],
            "extract_conf": 1.0,
            "atomic": True,
            "assertion": "asserted",
            "modality": "actual",
        }
        for i, label in enumerate(labels)
    ]
    full_span = {"start": 0, "end": len(text), "text": text}
    relations = relation_records()
    for relation in relations:
        relation["spans"] = [full_span]
    thought = {
        "schema_version": SCHEMA_VERSION,
        "thought_id": f"{pack_id}-X{run_index}",
        "source": source_record(text),
        "provenance": {
            "kind": "extracted",
            "extractor": {"id": "benchmark-reference", "version": f"0.1-run-{run_index}"},
        },
        "nodes": nodes,
        "relations": relations,
    }
    case_id = f"{pack_id}-X{run_index}"
    reviewer = APPROVALS["extraction_approvals"].get(case_id)
    return {
        "extraction_case_id": case_id,
        "pack_id": pack_id,
        "split": split,
        "run_index": run_index,
        "input": source_record(text),
        "reference_thought_dna": thought,
        "review": {"required": True, "status": "approved" if reviewer else "pending", "reviewer": reviewer},
    }


def build_e1_cases() -> list[dict[str, Any]]:
    matrix: list[tuple[str, int, int]] = []
    for world in ("rich_random", "zipf_chains"):
        matrix.extend((world, size, 1729) for size in (1_000, 10_000, 30_000))
        matrix.extend((world, 10_000, seed) for seed in (7, 17, 31))
    out = []
    for world, size, seed in matrix:
        short = "R" if world == "rich_random" else "Z"
        out.append(
            {
                "case_id": f"E1-{short}-{size}-{seed}",
                "world": world,
                "corpus_size": size,
                "seed": seed,
                "descriptors": ["D0", "D1", "MULTI"],
                "query_graph": "G01-Q",
                "true_analogue": "G01-C09",
                "generic_distractors": ["G01-C13", "G02-C13", "G03-C13"],
                "polarity_flip": "G01-C10",
                "direction_negative": "G01-C12",
                "relation_vocabulary": [
                    "causes",
                    "prevents",
                    "requires",
                    "part_of",
                    "constrains",
                    "supports",
                    "contradicts",
                ],
                "filler_recipe": {
                    "distribution": world,
                    "bare_chain_fraction": 0.8 if world == "zipf_chains" else 0.0,
                    "synthetic": True,
                },
                "kill_rule": {
                    "multi_true_above_all_generic": True,
                    "positive_margin_required": True,
                    "polarity_rank_not_constrained": True,
                    "polarity_must_be_rejected_end_to_end": True,
                    "d0_shipping_allowed": False,
                },
            }
        )
    return out


def jsonl_bytes(records: list[dict[str, Any]]) -> bytes:
    return b"".join(canonical_bytes(record) + b"\n" for record in records)


def build_records() -> dict[str, list[dict[str, Any]]]:
    graphs: list[dict[str, Any]] = []
    pairs: list[dict[str, Any]] = []
    extraction_runs: list[dict[str, Any]] = []
    for pack_id, split, query_domain, analogy_domain in PACKS:
        pack_graphs, pack_pairs = build_pack(pack_id, split, query_domain, analogy_domain)
        graphs.extend(pack_graphs)
        pairs.extend(pack_pairs)
        for run_index in (1, 2):
            extraction_runs.append(extracted_reference(pack_id, split, DOMAINS[query_domain], run_index))
    return {
        "graphs.jsonl": graphs,
        "pairs.jsonl": pairs,
        "extraction_runs.jsonl": extraction_runs,
        "e1_cases.jsonl": build_e1_cases(),
    }


def build_manifest() -> dict[str, Any]:
    tracked = [
        "graphs.jsonl",
        "pairs.jsonl",
        "extraction_runs.jsonl",
        "e1_cases.jsonl",
        "config/evaluation-v0.1.json",
        "schema/graph.schema.json",
        "schema/pair.schema.json",
        "schema/extraction-run.schema.json",
        "schema/e1-case.schema.json",
        "schema/e1-prediction.schema.json",
        "schema/scale-prediction.schema.json",
        "schema/prediction.schema.json",
        "schema/extraction-prediction.schema.json",
        "schema/report.schema.json",
        "review_approvals.json",
    ]
    records = build_records()
    files: dict[str, Any] = {}
    for relative in tracked:
        payload = jsonl_bytes(records[relative]) if relative in records else (ROOT / relative).read_bytes()
        item: dict[str, Any] = {"sha256": sha256_bytes(payload), "bytes": len(payload)}
        if relative in records:
            item["records"] = len(records[relative])
        files[relative] = item
    return {
        "manifest_version": "resonance-benchmark-manifest/0.1",
        "benchmark_version": "r0-v0.1",
        "thought_dna_schema": SCHEMA_VERSION,
        "freeze_state": "candidate_frozen_pending_independent_review",
        "counts": {
            "packs": 8,
            "calibration_packs": 2,
            "gate_packs": 6,
            "graphs": 136,
            "pairs": 128,
            "extraction_runs": 16,
            "e1_matrix_cases": 12,
        },
        "files": files,
        "provenance": {
            "agent_id": AGENT_ID,
            "human_sponsor": "Parshkov",
            "provider": "OpenAI",
            "model": "GPT-5-based Codex (exact deployed model/version not exposed to this run)",
            "runtime": "Python 3.12 stdlib; src.graph Thought DNA validator",
            "source_commit": "set by git; content hash is authoritative",
        },
    }


def main() -> None:
    records = build_records()
    for relative, rows in records.items():
        (ROOT / relative).write_bytes(jsonl_bytes(rows))
    manifest = build_manifest()
    manifest_payload = json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8") + b"\n"
    (ROOT / "manifest.json").write_bytes(manifest_payload)
    (ROOT / "manifest.sha256").write_text(sha256_bytes(canonical_bytes(manifest)) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
