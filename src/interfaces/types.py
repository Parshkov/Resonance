"""Pure data contracts shared by Resonance engine components.

These types contain no implementation logic and no MCP transport types.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping

from src.graph import Span, ThoughtGraph

SCORE_CONTRACT_VERSION = "resonance-score/0.1"
INTERFACE_VERSION = "resonance-interfaces/0.1"


def frozen_mapping(values: Mapping[str, float | int | str | bool] | None = None) -> Mapping[str, float | int | str | bool]:
    return MappingProxyType(dict(values or {}))


@dataclass(frozen=True, slots=True)
class ConfigRef:
    """Version/config identity carried across every component boundary."""

    component: str
    component_version: str
    config_hash: str
    schema_version: str = "thought-dna/0.1"


@dataclass(frozen=True, slots=True)
class ExtractionResult:
    graph: ThoughtGraph
    config: ConfigRef
    warnings: tuple[str, ...] = ()
    abstentions: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SeedCorrespondence:
    query_node: str
    candidate_node: str
    support: float
    channel: str


@dataclass(frozen=True, slots=True)
class CandidateResult:
    candidate_id: str
    channel_scores: Mapping[str, float]
    channel_ranks: Mapping[str, int]
    seed_correspondences: tuple[SeedCorrespondence, ...]
    usable_query_evidence: float
    requires_structural_verification: bool
    polarity_reliable: bool
    index_version: str
    feature_version: str
    corpus_snapshot: str
    config: ConfigRef


@dataclass(frozen=True, slots=True)
class ItemProvenance:
    thought_id: str
    item_id: str
    provenance_kind: str
    spans: tuple[Span, ...] = ()


@dataclass(frozen=True, slots=True)
class NodeMatch:
    query_node: str
    candidate_node: str
    support: float
    query_provenance: ItemProvenance
    candidate_provenance: ItemProvenance


@dataclass(frozen=True, slots=True)
class RelationMatch:
    query_relation: str
    candidate_relation: str
    support: float
    query_provenance: ItemProvenance
    candidate_provenance: ItemProvenance


@dataclass(frozen=True, slots=True)
class EdgePathMatch:
    query_relation: str
    candidate_relations: tuple[str, ...]
    realizes_nodes: tuple[str, ...]
    support: float


@dataclass(frozen=True, slots=True)
class Contradiction:
    kind: str
    query_item: str
    candidate_item: str
    contribution: float
    rule_version: str
    query_provenance: ItemProvenance
    candidate_provenance: ItemProvenance


@dataclass(frozen=True, slots=True)
class ScoreVector:
    """Observable score vector. A blended-only public result is non-conforming."""

    structural: float
    semantic: float
    knowledge_about: float
    knowledge_requires: float
    complement_query_to_candidate: float
    complement_candidate_to_query: float
    coverage_containment: float
    coverage_symmetric: float
    contradiction: float
    evidence_gate: float
    retrieval_content: float = 0.0
    retrieval_knowledge: float = 0.0
    retrieval_structural: float = 0.0
    extras: Mapping[str, float] = field(default_factory=lambda: MappingProxyType({}))


@dataclass(frozen=True, slots=True)
class Explanation:
    mapping: tuple[NodeMatch, ...]
    matched_relations: tuple[RelationMatch, ...]
    edge_path_matches: tuple[EdgePathMatch, ...]
    unmatched_query_nodes: tuple[str, ...]
    unmatched_candidate_nodes: tuple[str, ...]
    contradictions: tuple[Contradiction, ...]
    retrieval_channels: tuple[str, ...]
    systematicity_systems: tuple[tuple[str, ...], ...]
    score_model_version: str
    schema_version: str
    config_hash: str


@dataclass(frozen=True, slots=True)
class VerifierResult:
    contract_version: str
    query_id: str
    candidate_id: str
    candidate_config: str
    mapping: tuple[NodeMatch, ...]
    matched_relations: tuple[RelationMatch, ...]
    edge_path_matches: tuple[EdgePathMatch, ...]
    unmatched_query_nodes: tuple[str, ...]
    unmatched_candidate_nodes: tuple[str, ...]
    contradictions: tuple[Contradiction, ...]
    hard_rejection: str | None
    components: ScoreVector
    classification: str
    confidence: str
    explanation: Explanation
    solver_config: ConfigRef

    def __post_init__(self) -> None:
        if self.contract_version != SCORE_CONTRACT_VERSION:
            raise ValueError(f"unsupported score contract: {self.contract_version}")


@dataclass(frozen=True, slots=True)
class ResonanceHit:
    candidate: CandidateResult
    verification: VerifierResult
