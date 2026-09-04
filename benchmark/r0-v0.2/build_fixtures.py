#!/usr/bin/env python3
"""Build the deterministic Benchmark v0.2 corpus (graphs.jsonl, pairs.jsonl, manifest).

v0.2 replaces the single-template v0.1 corpus: eight distinct skeletons, four
domain instantiations each with genuinely different vocabulary, two new hard
negatives (polarity_flip, template_coincidence) and a partial cross-domain
analogy. Skeletons S1-S4 are the calibration split (thresholds may be tuned
on them); S5-S8 are the gate split and must not be used for tuning.

The generator contains no engine code and no expected scores.
"""

from __future__ import annotations

import hashlib
import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from skeletons import FAMILIES, SKELETONS  # noqa: E402

BENCHMARK_VERSION = "r0-v0.2"
SCHEMA_VERSION = "thought-dna/0.1"
AUTHOR = "parshkov-anthropic-fable51-uutj4x"
QUALIFIERS = (" in the second unit", " at the other site", " during the night shift", " on the new line",
              " in the pilot", " last quarter", " in the north wing")
ROLE_NEIGHBOUR = {"state": "mechanism", "mechanism": "state", "problem": "state", "outcome": "state",
                  "method": "mechanism", "constraint": "problem", "evidence": "state", "resource": "state",
                  "agent": "resource"}


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def node(i: int | str, label: str, role: str, *, atomic: bool = True, knowledge: dict | None = None) -> dict:
    out = {"id": f"n{i}" if isinstance(i, int) else i, "label": label, "role": role, "spans": [],
           "extract_conf": 1.0, "atomic": atomic, "assertion": "asserted", "modality": "actual"}
    if knowledge:
        out["knowledge"] = knowledge
    return out


def rel(rid: str, s: str, t: str, typ: str) -> dict:
    return {"id": rid, "source": s, "target": t, "type": typ, "extract_conf": 1.0, "spans": [],
            "assertion": "asserted", "modality": "actual"}


def skeleton_relations(sk: dict) -> list[dict]:
    return [rel(f"r{i}", f"n{s}", f"n{t}", typ) for i, (s, t, typ) in enumerate(sk["edges"])]


def graph(graph_id: str, nodes: list[dict], relations: list[dict], *, reverse: bool = False) -> dict:
    nodes = deepcopy(nodes)
    relations = deepcopy(relations)
    if reverse:
        nodes.reverse()
        relations.reverse()
    text = f"Benchmark v0.2 graph {graph_id}."
    return {"benchmark_graph_id": graph_id,
            "thought_dna": {"schema_version": SCHEMA_VERSION, "thought_id": graph_id,
                            "source": {"text": text, "sha256": sha(text.encode())},
                            "provenance": {"kind": "manual", "extractor": None, "human_id": AUTHOR},
                            "nodes": nodes, "relations": relations}}


def first_slot(sk: dict, role: str) -> int:
    return sk["roles"].index(role)


def causes_index(sk: dict) -> int:
    for i, (_s, _t, typ) in enumerate(sk["edges"]):
        if typ == "causes":
            return i
    raise AssertionError(sk["id"] + " has no causes edge")


def bridge_slot(sk: dict) -> int:
    """Slot carrying the method-input knowledge bridge: method, else mechanism, else constraint."""
    for role in ("method", "mechanism", "constraint"):
        if role in sk["roles"]:
            return sk["roles"].index(role)
    return 0


def base_nodes(sk: dict, labels: list[str]) -> list[dict]:
    out = []
    for i, (label, role) in enumerate(zip(labels, sk["roles"], strict=True)):
        knowledge = None
        if i == bridge_slot(sk):
            knowledge = {"about": [], "requires": [{"id": f"local:{sk['id']}:method-input", "conf": 1.0, "via": "benchmark"}]}
        if role == "outcome" and i == first_slot(sk, "outcome"):
            knowledge = {"about": [], "requires": [{"id": f"local:{sk['id']}:continuation", "conf": 1.0, "via": "benchmark"}]}
        out.append(node(i, label, role, knowledge=knowledge))
    return out


def identity_pairs(n: int, drop: set[int] = frozenset()) -> list[list[str]]:
    return [[f"n{i}", f"n{i}"] for i in range(n) if i not in drop]


def edge_pairs(relations: list[dict], drop: set[str] = frozenset()) -> list[list[Any]]:
    return [[r["id"], r["id"]] for r in relations if r["id"] not in drop]


def derange(n: int) -> list[int]:
    """Deterministic derangement that breaks every edge: rotate by n//2 + 1 (coprime-ish) and swap ends."""
    shift = max(2, n // 2)
    perm = [(i + shift) % n for i in range(n)]
    if any(perm[i] == i for i in range(n)):
        perm = [(i + 1) % n for i in range(n)]
    return perm


def build_skeleton(sk: dict) -> tuple[list[dict], list[dict]]:
    sid = sk["id"]
    n = len(sk["roles"])
    domains = list(sk["domains"].items())
    q_domain, q_labels = domains[0]
    q_nodes = base_nodes(sk, q_labels)
    q_rels = skeleton_relations(sk)
    graphs = [graph(f"{sid}-Q", q_nodes, q_rels)]
    pairs: list[dict] = []
    split = sk["split"]
    # analogy domains also enter the corpus as plain graphs (three per skeleton)
    for d_name, d_labels in domains[1:]:
        graphs.append(graph(f"{sid}-A-{d_name}", base_nodes(sk, d_labels), q_rels))

    for fam_index, (family, gold_class, relevant) in enumerate(FAMILIES, start=1):
        cid = f"{sid}-C{fam_index:02d}"
        nodes = deepcopy(q_nodes)
        rels = deepcopy(q_rels)
        node_pairs = identity_pairs(n)
        e_pairs = edge_pairs(rels)
        bridge: list[list[str]] = []
        manifest: dict[str, Any] = {"operation": family}
        reverse = False
        candidate_id = cid

        if family == "paraphrase":
            for i in range(n):
                if i % 2 == 0:
                    nodes[i]["label"] = sk["alt"][i]
        elif family == "vocabulary_substitution":
            for i in range(n):
                nodes[i]["label"] = sk["alt"][i]
        elif family == "irrelevant_branch":
            nodes += [node("x0", "office plant watering rota", "evidence"), node("x1", "parking lot repainting", "outcome")]
            rels += [rel("rx0", "x0", "x1", "supports"), rel("rx1", "x0", f"n{n-1}", "supports")]
        elif family == "partial_graph":
            keep = set(range(n - 2))
            nodes = [nd for nd in nodes if int(nd["id"][1:]) in keep]
            rels = [r for r in rels if int(r["source"][1:]) in keep and int(r["target"][1:]) in keep]
            node_pairs = identity_pairs(n, drop=set(range(n)) - keep)
            e_pairs = edge_pairs(rels)
            manifest["dropped_nodes"] = sorted(set(range(n)) - keep)
        elif family == "transparent_granularity":
            ci = causes_index(sk)
            s0, t0, _typ0 = sk["edges"][ci]
            rid = f"r{ci}"
            nodes.append(node("x0", "gradual transfer step", "mechanism", atomic=False))
            rels = [r for r in rels if r["id"] != rid]
            rels += [rel(rid + "a", f"n{s0}", "x0", "causes"), rel(rid + "b", "x0", f"n{t0}", "causes")]
            e_pairs = [[rid, [rid + "a", rid + "b"]]] + [[r["id"], r["id"]] for r in q_rels if r["id"] != rid]
            manifest["expanded_relation"] = rid
        elif family == "same_domain_structural_match":
            for i in range(n):
                nodes[i]["label"] = q_labels[i] + QUALIFIERS[i % len(QUALIFIERS)]
        elif family == "serialization_permutation":
            reverse = True
        elif family == "modest_extraction_error":
            # one role drifts to a neighbouring role, one label truncated, one non-chain edge retyped
            nodes[1]["role"] = ROLE_NEIGHBOUR[nodes[1]["role"]]
            nodes[1]["extract_conf"] = 0.7
            nodes[n - 1]["label"] = " ".join(q_labels[n - 1].split()[:2])
            for r in rels:
                if r["type"] == "supports":
                    r["type"] = "part_of"
                    r["extract_conf"] = 0.6
                    break
            manifest["role_drift"] = ["n1"]
        elif family == "cross_domain_analogy":
            d_name, d_labels = domains[1]
            nodes = base_nodes(sk, d_labels)
            manifest["analogy_domain"] = d_name
        elif family == "cross_domain_analogy_partial":
            d_name, d_labels = domains[2]
            nodes = base_nodes(sk, d_labels)[: n - 1]
            rels = [r for r in rels if int(r["source"][1:]) < n - 1 and int(r["target"][1:]) < n - 1]
            nodes += [node("x0", "annual budget review meeting", "evidence")]
            rels += [rel("rx0", "x0", "n0", "supports")]
            node_pairs = identity_pairs(n, drop={n - 1})
            e_pairs = edge_pairs(rels, drop={"rx0"})
            manifest["analogy_domain"] = d_name
        elif family == "same_vocabulary_wrong_structure":
            perm = derange(n)
            rels = [rel(f"r{i}", f"n{perm[s]}", f"n{perm[t]}", typ) for i, (s, t, typ) in enumerate(sk["edges"])]
            node_pairs, e_pairs = [], []
            manifest["permutation"] = perm
        elif family == "polarity_flip":
            ci = causes_index(sk)
            rels[ci]["type"] = "prevents"
            manifest["flipped_relation"] = f"r{ci}"
            node_pairs, e_pairs = [], []
            manifest["negative_subtype"] = "polarity_flip"
        elif family == "template_coincidence":
            for i in range(n):
                nodes[i]["label"] = sk["coincidence"][i]
                nodes[i].pop("knowledge", None)
            node_pairs, e_pairs = [], []
            manifest["negative_subtype"] = "template_coincidence"
        elif family == "generic_motif_distractor":
            nodes = [node(0, "something happens", "problem"), node(1, "some condition follows", "state"),
                     node(2, "some result appears", "outcome")]
            rels = [rel("r0", "n0", "n1", "causes"), rel("r1", "n1", "n2", "causes")]
            node_pairs, e_pairs = [], []
        elif family == "same_topic_different_intent":
            hub = f"n{first_slot(sk, 'outcome') if 'outcome' in sk['roles'] else 0}"
            rels = []
            k = 0
            for i in range(n):
                nid = f"n{i}"
                if nid == hub:
                    continue
                rels.append(rel(f"r{k}", nid, hub, "part_of" if k % 2 == 0 else "supports"))
                k += 1
            node_pairs, e_pairs = [], []
        elif family == "accidental_semantic_similarity":
            other = SKELETONS[(SKELETONS.index(sk) + 1) % len(SKELETONS)]
            o_domains = other["domains"]
            o_name = q_domain if q_domain in o_domains else next(iter(o_domains))
            nodes = base_nodes(other, o_domains[o_name])
            rels = skeleton_relations(other)
            for nd in nodes:
                nd.pop("knowledge", None)
            node_pairs, e_pairs = [], []
            manifest["source_skeleton"] = other["id"]
        elif family == "branch_continuation":
            out_slot = first_slot(sk, "outcome") if "outcome" in sk["roles"] else n - 1
            keep = {out_slot}
            base = [nd for nd in nodes if int(nd["id"][1:]) in keep]
            base[0].pop("knowledge", None)
            base[0]["knowledge"] = {"about": [{"id": f"local:{sid}:continuation", "conf": 1.0, "via": "benchmark"}], "requires": []}
            nodes = base + [node("x0", "second-order consequences downstream", "state"),
                            node("x1", "recovery playbook for the aftermath", "method")]
            rels = [rel("rx0", f"n{out_slot}", "x0", "causes"), rel("rx1", "x0", "x1", "requires")]
            node_pairs = [[f"n{out_slot}", f"n{out_slot}"]]
            e_pairs = []
            bridge = [[f"n{out_slot}", f"n{out_slot}"]]
        elif family == "method_knowledge_bridge":
            m_slot = bridge_slot(sk)
            m_label = q_labels[m_slot]
            nodes = [node("x0", f"how to run {m_label}", "method",
                          knowledge={"about": [{"id": f"local:{sid}:method-input", "conf": 1.0, "via": "benchmark"}], "requires": []}),
                     node("x1", "required inputs and preparation", "resource"),
                     node("x2", "expected side effects", "state")]
            rels = [rel("rx0", "x0", "x1", "requires"), rel("rx1", "x0", "x2", "causes")]
            node_pairs, e_pairs = [], []
            bridge = [[f"n{m_slot}", "x0"]]
        else:
            raise AssertionError(family)

        graphs.append(graph(candidate_id, nodes, rels, reverse=reverse))
        pairs.append({
            "case_id": cid, "skeleton": sid, "split": split, "family": family,
            "gold_class": gold_class, "relevant": relevant,
            "query_graph": f"{sid}-Q", "candidate_graph": candidate_id,
            "gold_node_pairs": node_pairs, "gold_edge_pairs": e_pairs, "bridge_pairs": bridge,
            "transform_manifest": manifest,
        })
    return graphs, pairs


def build() -> dict[str, Any]:
    graphs: list[dict] = []
    pairs: list[dict] = []
    for sk in SKELETONS:
        g, p = build_skeleton(sk)
        graphs += g
        pairs += p
    ids = [g["benchmark_graph_id"] for g in graphs]
    assert len(ids) == len(set(ids)), "duplicate graph ids"
    return {"graphs": graphs, "pairs": pairs}


def jsonl(records: list[dict]) -> bytes:
    return b"".join(canonical_bytes(r) + b"\n" for r in records)


def main() -> None:
    from src.graph import validate_thought  # noqa: WPS433 -- validation only
    data = build()
    for g in data["graphs"]:
        validate_thought(g["thought_dna"])
    files = {"graphs.jsonl": jsonl(data["graphs"]), "pairs.jsonl": jsonl(data["pairs"])}
    for name, payload in files.items():
        (ROOT / name).write_bytes(payload)
    skeleton_bytes = (ROOT / "skeletons.py").read_bytes()
    manifest = {
        "benchmark_version": BENCHMARK_VERSION,
        "author": AUTHOR,
        "counts": {"graphs": len(data["graphs"]), "pairs": len(data["pairs"]),
                   "skeletons": len(SKELETONS), "families": len(FAMILIES),
                   "calibration_pairs": sum(p["split"] == "calibration" for p in data["pairs"]),
                   "gate_pairs": sum(p["split"] == "gate" for p in data["pairs"])},
        "files": {name: sha(payload) for name, payload in files.items()},
        "skeletons_sha256": sha(skeleton_bytes),
        "splits": {"calibration": [s["id"] for s in SKELETONS if s["split"] == "calibration"],
                   "gate": [s["id"] for s in SKELETONS if s["split"] == "gate"]},
        "policy": {
            "gate_split_tuning": "forbidden",
            "gold_review": "AI-authored; independent human review pending (see README)",
            "direct_vs_approximate": "structural: direct = complete isomorphism; approximate = partial/perturbed",
        },
    }
    (ROOT / "manifest.json").write_bytes(canonical_bytes(manifest) + b"\n")
    print(json.dumps(manifest["counts"]))


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT.parents[1]))
    main()
