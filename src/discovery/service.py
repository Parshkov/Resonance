"""Discovery service: joins ACCEPTED engine results with consented metadata
into a strict, versioned, visualization-ready DTO.

Architectural rule (issue #73 / contract section 7), enforced here and by
tests: no new retrieval heuristics, no reranking, no scoring compensation.
Match ORDER is exactly the engine's find() order with non-consented entries
REMOVED (removal preserves relative order); every score is copied from the
accepted VerifierResult; evidence is derived from its mappings verbatim.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Sequence

from src.engine import ENGINE_VERSION, ResonanceEngine
from src.graph import ThoughtGraph
from src.interfaces import INTERFACE_VERSION, ResonanceHit, require_mode

from .metadata import METADATA_SCHEMA_VERSION, ConsentRegistry

DISCOVERY_CONTRACT_VERSION = "resonance-discovery/0.1"
ACTIONS = ("compare", "explain", "request_intro")
MAX_EVIDENCE_ITEMS = 5


def _sha(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


class DiscoveryService:
    def __init__(self, engine: ResonanceEngine, registry: ConsentRegistry):
        self.engine = engine
        self.registry = registry
        self._intro_events: list[dict[str, Any]] = []
        self._match_targets: dict[str, str] = {}

    # -- identity -----------------------------------------------------------
    def provenance(self) -> dict[str, Any]:
        return {"engine_version": ENGINE_VERSION,
                "interface_version": INTERFACE_VERSION,
                "discovery_contract_version": DISCOVERY_CONTRACT_VERSION,
                "metadata_schema_version": METADATA_SCHEMA_VERSION,
                "verifier_config_hash": self.engine.verifier.config_hash,
                "corpus_snapshot": self.engine.candidate_index.corpus_snapshot}

    # -- discovery ----------------------------------------------------------
    def discover(self, graph: ThoughtGraph, *, mode: str, k: int = 8) -> dict[str, Any]:
        require_mode(mode)
        hits = self.engine.find(graph, mode=mode, k=k)
        matches, rejected = [], []
        for hit in hits:                       # engine order; filter-only pass
            profile = self.registry.get(hit.candidate.candidate_id)
            if profile is None or profile.share_state != "discoverable":
                continue                       # hidden/unknown: absent entirely
            entry = self._match(graph, hit, profile)
            # Segregation is driven by the ENGINE's own hard boundary, never
            # by a score threshold: a hard-rejected correspondence must be
            # surfaced as a contradiction, not reported as resonance
            # (ADR-0003 / R6-E2E scenario 5). Order within each list remains
            # the engine's.
            (rejected if hit.verification.hard_rejection else matches).append(entry)
        response = {
            "contract_version": DISCOVERY_CONTRACT_VERSION,
            "query": {"thought_id": graph.thought_id, "mode": mode,
                      "provenance": self.provenance()},
            "matches": matches,
            "rejected": rejected,
            "aggregation": self._aggregation(matches),
            "unsupported_fields": ["realtime_presence", "exact_location",
                                   "contact_details"],
        }
        return response

    def _match(self, graph: ThoughtGraph, hit: ResonanceHit, profile) -> dict[str, Any]:
        v = hit.verification
        wire = v.components.to_wire()
        match_id = _sha(["match", graph.thought_id, v.candidate_id,
                         v.candidate_config])[:24]
        self._match_targets[match_id] = v.candidate_id
        mapping_pairs = [(m.query_node, m.candidate_node) for m in v.mapping]
        label = {n.id: n.label for n in graph.nodes}
        target = self.engine.get(v.candidate_id)
        clabel = {n.id: n.label for n in target.nodes} if target else {}
        correspondences = [
            {"query_node": q, "candidate_node": c,
             "query_label": label.get(q, q), "candidate_label": clabel.get(c, c)}
            for q, c in mapping_pairs[:MAX_EVIDENCE_ITEMS]]
        preserved = [{"query_relation": m.query_relation,
                      "candidate_relation": m.candidate_relation}
                     for m in v.matched_relations[:MAX_EVIDENCE_ITEMS]]
        display: dict[str, Any] = {"share_state": profile.share_state,
                                   "cluster_id": _sha(["cluster",
                                                       profile.person_pseudonym])[:12]}
        if profile.location_shareable and profile.location_bucket:
            display["location_bucket"] = profile.location_bucket
        return {
            "match_id": match_id,
            "person_pseudonym": profile.person_pseudonym,
            "session_id": profile.session_id,
            "mode_classification": v.classification,
            "hard_rejection": v.hard_rejection,
            "scores": {"structural": wire["structural_score"],
                       "semantic": wire["S_semantic"],
                       "r_direct": wire["R_direct"],
                       "y_systematicity": wire["Y_systematicity"],
                       "coverage_containment": wire["Q_containment"],
                       "contradiction": wire["X_contradiction"],
                       "h_sign_conflict": wire["H_sign_conflict"]},
            "confidence": v.confidence,
            "evidence": {"mapped_node_count": len(mapping_pairs),
                         "preserved_relation_count": len(v.matched_relations),
                         "contradiction_count": len(v.contradictions),
                         "top_correspondences": correspondences,
                         "preserved_relations": preserved},
            "display": display,
            "actions": list(ACTIONS),
        }

    @staticmethod
    def _aggregation(matches: Sequence[dict[str, Any]]) -> dict[str, Any]:
        """Map/heat buckets over DISCOVERABLE matches only. Hidden sessions
        never reach this function, so no count can reveal them."""
        buckets: dict[str, int] = {}
        for match in matches:
            bucket = match["display"].get("location_bucket")
            if bucket:
                buckets[bucket] = buckets.get(bucket, 0) + 1
        total = sum(buckets.values())
        return {"basis": "discoverable_matches_with_shareable_location_only",
                "buckets": [{"bucket_id": b, "count": n,
                             "intensity": round(n / total, 4) if total else 0.0}
                            for b, n in sorted(buckets.items())]}

    # -- consent workflow (service capability; MCP exposure deferred) -------
    def request_intro(self, match_id: str, message: str | None = None) -> dict[str, Any]:
        target_session = self._match_targets.get(match_id)
        if target_session is None:
            raise ValueError(f"unknown match_id: {match_id!r}")
        event = {"event_id": _sha(["intro", match_id, len(self._intro_events)])[:24],
                 "match_id": match_id,
                 "state": "pending_target_acceptance",
                 "message_attached": bool(message),
                 "disclosure": "none_until_target_accepts"}
        # audit record keeps the target INTERNALLY only; the returned event
        # never carries it.
        self._intro_events.append({**event, "_target_session": target_session,
                                   "_message": message})
        return event

    def audit_log(self) -> list[dict[str, Any]]:
        return [{k: v for k, v in e.items() if not k.startswith("_")}
                for e in self._intro_events]
