"""Cue-grounded Thought Graph extraction.

Only explicit lexical relation cues become edges. Implicit causation is
abstained. No live-network Knowledge DNA lookups.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from src.graph import Node, Relation, ThoughtGraph, make_node_id, make_relation_id, make_thought_id, validate_thought
from src.interfaces import ConfigRef, ExtractionResult

EXTRACTOR_ID = "resonance-cue-extractor"
EXTRACTOR_VERSION = "0.1.1"
DROP_THRESHOLD = 0.35
IOU_MERGE = 0.5
FROZEN_EXTRACTION_RUNS = Path(__file__).resolve().parents[2] / "benchmark" / "r0-v0.1" / "extraction_runs.jsonl"

CUES: tuple[tuple[str, str, float, int], ...] = (
    (r"\bcaused by\b", "causes", 0.86, 1),
    (r"\bcauses\b", "causes", 0.92, 0),
    (r"\bcause\b", "causes", 0.84, 0),
    (r"\bleads to\b", "causes", 0.8, 0),
    (r"\bprevents\b", "prevents", 0.9, 0),
    (r"\bprevent\b", "prevents", 0.82, 0),
    (r"\brequires\b", "requires", 0.88, 0),
    (r"\brequire\b", "requires", 0.8, 0),
    (r"\bpart of\b", "part_of", 0.84, 0),
    (r"\bconstrains\b", "constrains", 0.84, 0),
    (r"\bsupports\b", "supports", 0.72, 0),
    (r"\bcontradicts\b", "contradicts", 0.78, 0),
)
BOUNDARY = re.compile(r"\b(?:but|and|however|although|while|because|so|then)\b|[.;:!?]", re.I)
WORD = re.compile(r"\S+")
# Cue-attached verbal negation only. Bare "no" is too wide (no doubt, no wonder).
CUE_NEGATION = re.compile(
    r"(?:do\s+not|does\s+not|did\s+not|cannot|can(?:no)?t|will\s+not|won'?t|never|not)\s+$",
    re.I,
)
ROLE_HINTS = (
    ("constraint", ("constraint", "limit", "budget", "must not")),
    ("evidence", ("evidence", "observation", "measured")),
    ("method", ("method", "protocol", "procedure")),
    ("agent", ("agent", "team", "person")),
    ("resource", ("resource", "data", "tool")),
    ("mechanism", ("mechanism", "process", "cooling", "heating")),
    ("outcome", ("failure", "degradation", "collapse", "success", "outcome")),
    ("problem", ("problem", "issue", "fault")),
    ("state", ("heat", "state", "accumulation", "pressure")),
)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _span(text: str, start: int, end: int) -> dict[str, object]:
    return {"start": start, "end": end, "text": text[start:end]}


def _iou(a: Mapping[str, object], b: Mapping[str, object]) -> float:
    left, right = max(int(a["start"]), int(b["start"])), min(int(a["end"]), int(b["end"]))
    inter = max(0, right - left)
    union = int(a["end"]) - int(a["start"]) + int(b["end"]) - int(b["start"]) - inter
    return inter / union if union else 0.0


def _window(text: str, cue_start: int, cue_end: int, side: str) -> dict[str, object] | None:
    if side == "left":
        region = text[:cue_start]
        parts = list(BOUNDARY.finditer(region))
        start = parts[-1].end() if parts else 0
        chunk = region[start:]
        tokens = list(WORD.finditer(chunk))
        if not tokens:
            return None
        chosen = tokens[-4:]
        abs_start = start + chosen[0].start()
        abs_end = start + chosen[-1].end()
    else:
        region = text[cue_end:]
        bound = BOUNDARY.search(region)
        stop = bound.start() if bound else len(region)
        chunk = region[:stop]
        tokens = list(WORD.finditer(chunk))
        if not tokens:
            return None
        chosen = tokens[:4]
        abs_start = cue_end + chosen[0].start()
        abs_end = cue_end + chosen[-1].end()
    while abs_start < abs_end and text[abs_start].isspace():
        abs_start += 1
    while abs_end > abs_start and text[abs_end - 1] in ",;:":
        abs_end -= 1
    if abs_end <= abs_start:
        return None
    return _span(text, abs_start, abs_end)


def _role(label: str) -> tuple[str, float]:
    lowered = label.lower()
    for role, hints in ROLE_HINTS:
        if any(hint in lowered for hint in hints):
            return role, 0.8
    return "state", 0.55


def _slug(label: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")
    return slug or "concept"


def _modality(text: str, start: int, end: int) -> str:
    window = text[max(0, start - 24) : min(len(text), end + 24)].lower()
    if re.search(r"\b(if|unless)\b", window):
        return "conditional"
    if re.search(r"\b(may|might|could|possible)\b", window):
        return "possible"
    return "actual"


def _assertion(text: str, start: int, end: int) -> str:
    """Negate only when a verbal negator immediately precedes the cue."""
    prefix = text[max(0, start - 32) : start]
    if CUE_NEGATION.search(prefix):
        return "negated"
    return "asserted"


def _require_drop_threshold(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("drop_threshold must be a finite number in [0, 1]")
    number = float(value)
    if not math.isfinite(number) or not 0.0 <= number <= 1.0:
        raise ValueError("drop_threshold must be a finite number in [0, 1]")
    return number


def _node_signature(node: Node) -> tuple[object, ...]:
    spans = tuple(sorted((span.start, span.end, span.text) for span in node.spans))
    return (node.role, spans, node.assertion, node.modality)


def _edge_signature(graph: ThoughtGraph, relation: Relation) -> tuple[object, ...] | None:
    by_id = {node.id: node for node in graph.nodes}
    source = by_id.get(relation.source)
    target = by_id.get(relation.target)
    if source is None or target is None:
        return None
    return (
        _node_signature(source),
        relation.type,
        _node_signature(target),
        relation.assertion,
        relation.modality,
    )


def _f1(predicted: set[object], gold: set[object]) -> float:
    if not predicted and not gold:
        return 1.0
    if not predicted or not gold:
        return 0.0
    overlap = len(predicted & gold)
    precision = overlap / len(predicted)
    recall = overlap / len(gold)
    return 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)


@dataclass(frozen=True)
class CueExtractor:
    drop_threshold: float = DROP_THRESHOLD

    def __post_init__(self) -> None:
        object.__setattr__(self, "drop_threshold", _require_drop_threshold(self.drop_threshold))

    def extract(self, context: str, *, source_id: str | None = None) -> ExtractionResult:
        if not isinstance(context, str) or not context.strip():
            raise ValueError("context must be a non-empty string")
        warnings: list[str] = []
        abstentions: list[str] = []
        thought_id = make_thought_id(context, namespace=source_id or "")
        nodes: dict[str, dict[str, object]] = {}
        relations: list[dict[str, object]] = []

        def add_node(span: dict[str, object]) -> str | None:
            label = str(span["text"]).strip()
            if not label:
                return None
            role, conf = _role(label)
            if conf < self.drop_threshold:
                abstentions.append(f"dropped node {label!r} below threshold")
                return None
            for existing in nodes.values():
                if _iou(span, existing["spans"][0]) >= IOU_MERGE:
                    if conf > float(existing["extract_conf"]):
                        existing["label"] = label
                        existing["role"] = role
                        existing["spans"] = [span]
                        existing["extract_conf"] = conf
                    return str(existing["id"])
            node_id = make_node_id(role, spans=[span], namespace=thought_id)
            nodes[node_id] = {
                "id": node_id,
                "label": label,
                "role": role,
                "spans": [span],
                "extract_conf": conf,
                "atomic": True,
                "assertion": "asserted",
                "modality": "actual",
            }
            return node_id

        for pattern, rel_type, conf, reverse in CUES:
            for match in re.finditer(pattern, context, flags=re.I):
                if conf < self.drop_threshold:
                    abstentions.append(f"dropped {rel_type} cue {match.group(0)!r}")
                    continue
                left = _window(context, match.start(), match.end(), "left")
                right = _window(context, match.start(), match.end(), "right")
                if left is None or right is None:
                    abstentions.append(f"incomplete arguments for cue {match.group(0)!r}")
                    continue
                src_span, dst_span = (right, left) if reverse else (left, right)
                src = add_node(src_span)
                dst = add_node(dst_span)
                if src is None or dst is None or src == dst:
                    abstentions.append(f"could not ground both ends of {match.group(0)!r}")
                    continue
                cue = _span(context, match.start(), match.end())
                assertion = _assertion(context, match.start(), match.end())
                modality = _modality(context, match.start(), match.end())
                rel_id = make_relation_id(
                    src,
                    dst,
                    rel_type,
                    spans=[cue],
                    assertion=assertion,
                    modality=modality,
                    namespace=thought_id,
                )
                relation: dict[str, object] = {
                    "id": rel_id,
                    "source": src,
                    "target": dst,
                    "type": rel_type,
                    "extract_conf": conf,
                    "spans": [cue],
                    "cue": cue,
                    "assertion": assertion,
                    "modality": modality,
                }
                if rel_type == "requires":
                    dst_node = nodes[dst]
                    dst_node["knowledge"] = {
                        "about": [{"id": f"local:{_slug(str(dst_node['label']))}", "conf": max(conf, 0.5), "via": "extractor"}],
                        "requires": [],
                    }
                    src_node = nodes[src]
                    src_node["knowledge"] = {
                        "about": [],
                        "requires": [{"id": f"local:{_slug(str(dst_node['label']))}", "conf": max(conf, 0.5), "via": "extractor"}],
                    }
                relations.append(relation)

        if not relations:
            abstentions.append("no explicit relation cues; implicit structure not emitted")

        raw = {
            "schema_version": "thought-dna/0.1",
            "thought_id": thought_id,
            "source": {"text": context, "sha256": _sha256(context)},
            "provenance": {"kind": "extracted", "extractor": {"id": EXTRACTOR_ID, "version": EXTRACTOR_VERSION}},
            "nodes": list(nodes.values()),
            "relations": relations,
        }
        graph = ThoughtGraph.from_dict(raw)
        config = ConfigRef(
            component="extraction",
            component_version=EXTRACTOR_VERSION,
            config_hash=_sha256(f"{EXTRACTOR_ID}:{EXTRACTOR_VERSION}:{self.drop_threshold}"),
        )
        return ExtractionResult(graph=graph, config=config, warnings=tuple(warnings), abstentions=tuple(abstentions))


class ManualIngest:
    """Non-LLM bypass: the same validator/model, extractor=null."""

    def ingest(self, payload: dict) -> ThoughtGraph:
        data = dict(payload)
        provenance = dict(data.get("provenance") or {})
        provenance.setdefault("kind", "manual")
        provenance["extractor"] = None
        data["provenance"] = provenance
        graph = ThoughtGraph.from_dict(data)
        validate_thought(graph.to_dict())
        return graph


def repeat_extraction_f1(first: ThoughtGraph, second: ThoughtGraph) -> dict[str, float]:
    """Node/edge F1 after span/role/assertion/modality alignment, not local IDs.

    Matches Benchmark v0.1 `runner._extraction_sets`: Thought DNA does not
    promise run-identical IDs, so typed-edge agreement is computed through
    aligned node signatures.
    """
    a_nodes = {_node_signature(node) for node in first.nodes}
    b_nodes = {_node_signature(node) for node in second.nodes}
    a_edges = {sig for rel in first.relations if (sig := _edge_signature(first, rel)) is not None}
    b_edges = {sig for rel in second.relations if (sig := _edge_signature(second, rel)) is not None}
    return {"node_f1": _f1(a_nodes, b_nodes), "edge_f1": _f1(a_edges, b_edges)}


def frozen_v0_1_predictions(
    extractor: CueExtractor | None = None,
    *,
    path: Path = FROZEN_EXTRACTION_RUNS,
) -> list[dict[str, object]]:
    """Adapter: CueExtractor over the frozen 16 extraction observations."""
    extractor = extractor or CueExtractor()
    predictions: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        case_id = str(record["extraction_case_id"])
        text = str(record["input"]["text"])
        graph = extractor.extract(text, source_id=case_id).graph
        predictions.append({"extraction_case_id": case_id, "thought_dna": graph.to_dict()})
    return predictions


def frozen_v0_1_coverage(predictions: list[dict[str, object]]) -> dict[str, float | int]:
    """Honest coverage for cue-only extraction. Empty graphs are not hidden."""
    node_counts = [len(item["thought_dna"]["nodes"]) for item in predictions]
    rel_counts = [len(item["thought_dna"]["relations"]) for item in predictions]
    n = len(predictions) or 1
    nonempty = sum(1 for nodes, rels in zip(node_counts, rel_counts) if nodes or rels)
    return {
        "n_records": len(predictions),
        "mean_nodes": sum(node_counts) / n,
        "mean_relations": sum(rel_counts) / n,
        "nonempty_graph_rate": nonempty / n,
        "total_nodes": sum(node_counts),
        "total_relations": sum(rel_counts),
    }
