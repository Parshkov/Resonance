"""Pure data contracts shared by Resonance engine components.

These types contain no implementation logic and no MCP transport types.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping

from src.graph import Span, ThoughtGraph

SCORE_CONTRACT_VERSION = "resonance-score/0.1"
INTERFACE_VERSION = "resonance-interfaces/0.1"

# Python field -> Scoring v0.1 wire name. Required components stay typed;
# extras is only for non-contract diagnostics.
SCORE_WIRE_NAMES: Mapping[str, str] = MappingProxyType(
    {
        "n_role": "N_role",
        "r_direct": "R_direct",
        "r_path": "R_path",
        "y_systematicity": "Y_systematicity",
        "coverage_containment": "Q_containment",
        "coverage_symmetric": "Q_symmetric",
        "contradiction": "X_contradiction",
        "h_sign_conflict": "H_sign_conflict",
        "e_nodes": "E_nodes",
        "e_relations": "E_relations",
        "evidence_gate": "evidence_gate",
        "structural": "structural_score",
        "semantic": "S_semantic",
        "knowledge_about": "K_about",
        "knowledge_requires": "K_requires",
        "complement_query_to_candidate": "K_comp_q_to_c",
        "complement_candidate_to_query": "K_comp_c_to_q",
        "retrieval_content": "retrieval_semantic",
        "retrieval_knowledge": "retrieval_knowledge",
        "retrieval_structural": "retrieval_structural",
    }
)


def frozen_str_float_mapping(values: Mapping[str, float] | None = None) -> Mapping[str, float]:
    return MappingProxyType({str(key): float(val) for key, val in dict(values or {}).items()})


def frozen_str_int_mapping(values: Mapping[str, int] | None = None) -> Mapping[str, int]:
    return MappingProxyType({str(key): int(val) for key, val in dict(values or {}).items()})


@dataclass(frozen=True, slots=True)
class ConfigRef:
    """Version/config identity carried across every component boundary."""

    component: str
    component_version: str
    config_hash: str
    schema_version: str = "thought-dna/0.1"


@dataclass(frozen=True, slots=True)
class RetrievalFlags:
    """Scoring v0.1 retrieval_flags. Fail closed: polarity is never assumed reliable."""

    requires_structural_verification: bool = True
    polarity_reliable: bool = False

    def to_wire(self) -> dict[str, bool]:
        return {
            "requires_structural_verification": self.requires_structural_verification,
            "polarity_reliable": self.polarity_reliable,
        }

    @classmethod
    def from_candidate(cls, candidate: CandidateResult) -> RetrievalFlags:
        return cls(
            requires_structural_verification=candidate.requires_structural_verification,
            polarity_reliable=candidate.polarity_reliable,
        )


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

    def __post_init__(self) -> None:
        object.__setattr__(self, "channel_scores", frozen_str_float_mapping(self.channel_scores))
        object.__setattr__(self, "channel_ranks", frozen_str_int_mapping(self.channel_ranks))


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
    query_provenance: ItemProvenance
    candidate_provenances: tuple[ItemProvenance, ...]

    def __post_init__(self) -> None:
        if len(self.candidate_relations) != len(self.candidate_provenances):
            raise ValueError("edge-path candidate relation IDs and provenances must be parallel")


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
    n_role: float = 0.0
    r_direct: float = 0.0
    r_path: float = 0.0
    y_systematicity: float = 0.0
    h_sign_conflict: bool = False
    e_nodes: float = 0.0
    e_relations: float = 0.0
    retrieval_content: float = 0.0
    retrieval_knowledge: float = 0.0
    retrieval_structural: float = 0.0
    extras: Mapping[str, float] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        object.__setattr__(self, "extras", frozen_str_float_mapping(self.extras))

    @property
    def q_containment(self) -> float:
        return self.coverage_containment

    @property
    def q_symmetric(self) -> float:
        return self.coverage_symmetric

    @property
    def x_contradiction(self) -> float:
        return self.contradiction

    def to_wire(self) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        for field_name, wire_name in SCORE_WIRE_NAMES.items():
            payload[wire_name] = getattr(self, field_name)
        if self.extras:
            payload["extras"] = dict(self.extras)
        return payload

    @classmethod
    def from_wire(cls, payload: Mapping[str, Any]) -> ScoreVector:
        kwargs: dict[str, Any] = {}
        extras: dict[str, float] = {}
        inverse = {wire: field_name for field_name, wire in SCORE_WIRE_NAMES.items()}
        for key, value in payload.items():
            if key == "extras":
                extras.update({str(item): float(item_value) for item, item_value in dict(value).items()})
            elif key in inverse:
                field_name = inverse[key]
                kwargs[field_name] = bool(value) if field_name == "h_sign_conflict" else value
            else:
                extras[str(key)] = float(value)
        return cls(**kwargs, extras=extras)


@dataclass(frozen=True, slots=True)
class Explanation:
    mapping: tuple[NodeMatch, ...]
    matched_relations: tuple[RelationMatch, ...]
    edge_path_matches: tuple[EdgePathMatch, ...]
    unmatched_query_nodes: tuple[str, ...]
    unmatched_candidate_nodes: tuple[str, ...]
    unmatched_query_relations: tuple[str, ...]
    unmatched_candidate_relations: tuple[str, ...]
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
    unmatched_query_relations: tuple[str, ...]
    unmatched_candidate_relations: tuple[str, ...]
    contradictions: tuple[Contradiction, ...]
    hard_rejection: str | None
    components: ScoreVector
    classification: str
    confidence: str
    explanation: Explanation
    solver_config: ConfigRef
    retrieval_flags: RetrievalFlags = field(default_factory=RetrievalFlags)

    def __post_init__(self) -> None:
        if self.contract_version != SCORE_CONTRACT_VERSION:
            raise ValueError(f"unsupported score contract: {self.contract_version}")
        explanation = self.explanation
        pairs = (
            ("mapping", self.mapping, explanation.mapping),
            ("matched_relations", self.matched_relations, explanation.matched_relations),
            ("edge_path_matches", self.edge_path_matches, explanation.edge_path_matches),
            ("unmatched_query_nodes", self.unmatched_query_nodes, explanation.unmatched_query_nodes),
            ("unmatched_candidate_nodes", self.unmatched_candidate_nodes, explanation.unmatched_candidate_nodes),
            ("unmatched_query_relations", self.unmatched_query_relations, explanation.unmatched_query_relations),
            ("unmatched_candidate_relations", self.unmatched_candidate_relations, explanation.unmatched_candidate_relations),
            ("contradictions", self.contradictions, explanation.contradictions),
        )
        for name, left, right in pairs:
            if left != right:
                raise ValueError(f"VerifierResult.{name} must equal Explanation.{name}")
        if explanation.score_model_version != self.contract_version:
            raise ValueError("explanation score_model_version must match contract_version")
        if explanation.config_hash != self.solver_config.config_hash:
            raise ValueError("explanation config_hash must match solver_config.config_hash")


@dataclass(frozen=True, slots=True)
class ResonanceHit:
    candidate: CandidateResult
    verification: VerifierResult

    def __post_init__(self) -> None:
        flags = self.verification.retrieval_flags
        if flags.requires_structural_verification != self.candidate.requires_structural_verification:
            raise ValueError("hit retrieval_flags.requires_structural_verification must match the candidate")
        if flags.polarity_reliable != self.candidate.polarity_reliable:
            raise ValueError("hit retrieval_flags.polarity_reliable must match the candidate")
