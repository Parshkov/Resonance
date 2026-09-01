"""D0+D1 landmark-pair fingerprints from canonical Thought DNA.

The feature layer is disposable derived state. Keys never enter Thought DNA and
never include labels, node IDs, relation IDs, or list order. Relation IDs are
also not used to choose one of several equal paths: every simple typed path up
to the configured bound contributes a deterministic feature.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Iterable

from src.graph import ThoughtGraph

FEATURE_ALGORITHM_VERSION = "resonance-relational-fingerprint/0.1"
_SCALES = ("D0", "D1")
_TOKEN_RE = re.compile(r"[a-z0-9]+")
_STOP_TOKENS = frozenset(
    {
        "a",
        "an",
        "and",
        "as",
        "at",
        "by",
        "for",
        "from",
        "in",
        "is",
        "of",
        "on",
        "or",
        "the",
        "to",
        "with",
    }
)


def _stable_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _digest(value: object) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class FingerprintConfig:
    """Frozen feature policy; MULTI is the only shipping configuration."""

    max_path_length: int = 3
    scales: tuple[str, ...] = _SCALES
    query_budget: int = 64
    allow_nonshipping_ablation: bool = False

    def __post_init__(self) -> None:
        if (
            isinstance(self.max_path_length, bool)
            or not isinstance(self.max_path_length, int)
            or not 1 <= self.max_path_length <= 3
        ):
            raise ValueError("max_path_length must be an integer in [1,3]")
        if isinstance(self.query_budget, bool) or not isinstance(self.query_budget, int) or self.query_budget < 2:
            raise ValueError("query_budget must be an integer >= 2")
        if not isinstance(self.scales, tuple) or not all(isinstance(scale, str) for scale in self.scales):
            raise ValueError("scales must be a tuple of strings")
        if not self.scales or len(set(self.scales)) != len(self.scales):
            raise ValueError("scales must be a non-empty unique tuple")
        if any(scale not in _SCALES for scale in self.scales):
            raise ValueError(f"scales must contain only {_SCALES}")
        if self.scales != _SCALES and not self.allow_nonshipping_ablation:
            raise ValueError("shipping fingerprints require D0+D1; set allow_nonshipping_ablation for a control")
        if not isinstance(self.allow_nonshipping_ablation, bool):
            raise ValueError("allow_nonshipping_ablation must be boolean")

    def to_dict(self) -> dict[str, object]:
        return {
            "max_path_length": self.max_path_length,
            "scales": list(self.scales),
            "query_budget": self.query_budget,
            "allow_nonshipping_ablation": self.allow_nonshipping_ablation,
        }

    @classmethod
    def from_dict(cls, value: dict[str, object]) -> "FingerprintConfig":
        expected = {"max_path_length", "scales", "query_budget", "allow_nonshipping_ablation"}
        if set(value) != expected:
            raise ValueError(f"fingerprint config fields must be exactly {sorted(expected)}")
        scales = value["scales"]
        if not isinstance(scales, list) or not all(isinstance(item, str) for item in scales):
            raise ValueError("fingerprint config scales must be a list of strings")
        return cls(
            max_path_length=value["max_path_length"],  # type: ignore[arg-type]
            scales=tuple(scales),
            query_budget=value["query_budget"],  # type: ignore[arg-type]
            allow_nonshipping_ablation=value["allow_nonshipping_ablation"],  # type: ignore[arg-type]
        )

    @property
    def config_hash(self) -> str:
        return _digest({"algorithm": FEATURE_ALGORITHM_VERSION, **self.to_dict()})

    @property
    def feature_version(self) -> str:
        return f"{FEATURE_ALGORITHM_VERSION}+{self.config_hash[:16]}"


@dataclass(frozen=True, slots=True)
class LandmarkFingerprint:
    key: str
    scale: str
    endpoint_a: str
    endpoint_b: str
    distance: int
    path_signature: tuple[tuple[str, str, str, str], ...]


@dataclass(frozen=True, slots=True)
class _Step:
    neighbor: str
    direction: str
    relation_type: str
    assertion: str
    modality: str

    @property
    def signature(self) -> tuple[str, str, str, str]:
        return (self.direction, self.relation_type, self.assertion, self.modality)


def _adjacency(graph: ThoughtGraph) -> dict[str, tuple[_Step, ...]]:
    adjacency: dict[str, list[_Step]] = {node.id: [] for node in graph.nodes}
    for relation in graph.relations:
        adjacency[relation.source].append(
            _Step(relation.target, ">", relation.type, relation.assertion, relation.modality)
        )
        adjacency[relation.target].append(
            _Step(relation.source, "<", relation.type, relation.assertion, relation.modality)
        )
    return {
        node_id: tuple(
            sorted(
                steps,
                key=lambda item: (
                    item.direction,
                    item.relation_type,
                    item.assertion,
                    item.modality,
                    item.neighbor,
                ),
            )
        )
        for node_id, steps in adjacency.items()
    }


def _descriptors(graph: ThoughtGraph, adjacency: dict[str, tuple[_Step, ...]], scale: str) -> dict[str, str]:
    nodes = {node.id: node for node in graph.nodes}
    if scale == "D0":
        return {node_id: node.role for node_id, node in nodes.items()}
    if scale != "D1":
        raise ValueError(f"unsupported descriptor scale: {scale}")
    out: dict[str, str] = {}
    for node_id, node in nodes.items():
        neighborhood = sorted(
            (
                step.direction,
                step.relation_type,
                step.assertion,
                step.modality,
                nodes[step.neighbor].role,
            )
            for step in adjacency[node_id]
        )
        out[node_id] = _digest(
            ["D1", node.role, node.assertion, node.modality, neighborhood]
        )
    return out


def _simple_paths(
    adjacency: dict[str, tuple[_Step, ...]],
    start: str,
    max_length: int,
) -> Iterable[tuple[str, tuple[tuple[str, str, str, str], ...]]]:
    """Yield all simple paths, retaining equal alternatives without ID tie-breaking."""

    stack: list[tuple[str, frozenset[str], tuple[tuple[str, str, str, str], ...]]] = [
        (start, frozenset({start}), ())
    ]
    while stack:
        current, visited, signature = stack.pop()
        if signature:
            yield current, signature
        if len(signature) >= max_length:
            continue
        # Reversal only affects traversal order. The emitted set and key do not
        # depend on relation IDs or serialized relation order.
        for step in reversed(adjacency[current]):
            if step.neighbor in visited:
                continue
            stack.append(
                (
                    step.neighbor,
                    visited | {step.neighbor},
                    signature + (step.signature,),
                )
            )


def structural_fingerprints(
    graph: ThoughtGraph,
    config: FingerprintConfig | None = None,
) -> tuple[LandmarkFingerprint, ...]:
    """Return order-invariant D0+D1 typed/directed path fingerprints."""

    policy = config or FingerprintConfig()
    adjacency = _adjacency(graph)
    seen: set[tuple[str, str, str]] = set()
    records: list[LandmarkFingerprint] = []
    landmarks = sorted(node_id for node_id, steps in adjacency.items() if steps)
    for scale in policy.scales:
        descriptors = _descriptors(graph, adjacency, scale)
        for endpoint_a in landmarks:
            for endpoint_b, path_signature in _simple_paths(
                adjacency, endpoint_a, policy.max_path_length
            ):
                key = _digest(
                    [
                        FEATURE_ALGORITHM_VERSION,
                        scale,
                        descriptors[endpoint_a],
                        descriptors[endpoint_b],
                        list(path_signature),
                        len(path_signature),
                    ]
                )
                identity = (key, endpoint_a, endpoint_b)
                if identity in seen:
                    continue
                seen.add(identity)
                records.append(
                    LandmarkFingerprint(
                        key=key,
                        scale=scale,
                        endpoint_a=endpoint_a,
                        endpoint_b=endpoint_b,
                        distance=len(path_signature),
                        path_signature=path_signature,
                    )
                )
    return tuple(
        sorted(
            records,
            key=lambda item: (
                item.scale,
                item.key,
                item.endpoint_a,
                item.endpoint_b,
                item.path_signature,
            ),
        )
    )


def content_tokens(graph: ThoughtGraph, *, include_source_text: bool = False) -> tuple[str, ...]:
    """Return deterministic content tokens; lookup uses an inverted index."""

    text = " ".join(node.label for node in graph.nodes)
    if include_source_text:
        text += " " + graph.source.text
    return tuple(
        sorted(
            token
            for token in _TOKEN_RE.findall(text.lower())
            if len(token) > 1 and token not in _STOP_TOKENS
        )
    )
