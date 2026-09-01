"""Cue-grounded Thought Graph extraction.

Only explicit lexical relation cues become edges. Implicit causation is
abstained. No live-network Knowledge DNA lookups.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from src.graph import ThoughtGraph, make_node_id, make_relation_id, make_thought_id, validate_thought
from src.interfaces import ConfigRef, ExtractionResult

EXTRACTOR_ID = "resonance-cue-extractor"
EXTRACTOR_VERSION = "0.1"
DROP_THRESHOLD = 0.35
IOU_MERGE = 0.5

CUES: tuple[tuple[str, str, float, int], ...] = (
    (r"\bcaused by\b", "causes", 0.86, 1),
    (r"\bcauses\b", "causes", 0.92, 0),
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


def _iou(a: dict[str, object], b: dict[str, object]) -> float:
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
    window = text[max(0, start - 16) : end].lower()
    if re.search(r"\b(not|never|no)\b", window):
        return "negated"
    return "asserted"


@dataclass(frozen=True)
class CueExtractor:
    drop_threshold: float = DROP_THRESHOLD

    def extract(self, context: str, *, source_id: str | None = None) -> ExtractionResult:
        if not isinstance(context, str) or not context.strip():
            raise ValueError("context must be a non-empty string")
        warnings: list[str] = []
        abstentions: list[str] = []
        thought_id = make_thought_id(context, namespace=source_id or "")
        nodes: dict[tuple[int, int], dict[str, object]] = {}
        relations: list[dict[str, object]] = []

        def add_node(span: dict[str, object]) -> str | None:
            label = str(span["text"]).strip()
            if not label:
                return None
            role, conf = _role(label)
            if conf < self.drop_threshold:
                abstentions.append(f"dropped node {label!r} below threshold")
                return None
            key = (int(span["start"]), int(span["end"]))
            for existing_key, existing in list(nodes.items()):
                if _iou(span, existing["spans"][0]) >= IOU_MERGE:
                    if conf > float(existing["extract_conf"]):
                        nodes.pop(existing_key)
                        break
                    return str(existing["id"])
            node_id = make_node_id(role, spans=[span], namespace=thought_id)
            payload: dict[str, object] = {
                "id": node_id,
                "label": label,
                "role": role,
                "spans": [span],
                "extract_conf": conf,
                "atomic": True,
                "assertion": "asserted",
                "modality": "actual",
            }
            nodes[key] = payload
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
                    dst_node = next(item for item in nodes.values() if item["id"] == dst)
                    dst_node["knowledge"] = {
                        "about": [{"id": f"local:{_slug(str(dst_node['label']))}", "conf": max(conf, 0.5), "via": "extractor"}],
                        "requires": [],
                    }
                    src_node = next(item for item in nodes.values() if item["id"] == src)
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
    def node_spans(graph: ThoughtGraph) -> list[dict[str, object]]:
        return [span.to_dict() for node in graph.nodes for span in node.spans]

    def edge_keys(graph: ThoughtGraph) -> set[tuple[str, str, str]]:
        return {(rel.source, rel.type, rel.target) for rel in graph.relations}

    a, b = node_spans(first), node_spans(second)
    matched = 0
    used: set[int] = set()
    for span in a:
        for index, other in enumerate(b):
            if index in used:
                continue
            if _iou(span, other) >= IOU_MERGE:
                matched += 1
                used.add(index)
                break
    node_p = matched / len(a) if a else 1.0
    node_r = matched / len(b) if b else 1.0
    node_f1 = 0.0 if node_p + node_r == 0 else 2 * node_p * node_r / (node_p + node_r)
    ea, eb = edge_keys(first), edge_keys(second)
    inter = len(ea & eb)
    edge_p = inter / len(ea) if ea else 1.0
    edge_r = inter / len(eb) if eb else 1.0
    edge_f1 = 0.0 if edge_p + edge_r == 0 else 2 * edge_p * edge_r / (edge_p + edge_r)
    return {"node_f1": node_f1, "edge_f1": edge_f1}
