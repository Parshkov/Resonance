"""ResonanceEngine: the accepted components composed behind EngineFacade.

context/manual graph -> Thought DNA -> validate/canonicalize -> index ->
retrieve -> verify -> score -> explain. Pure Python; no MCP anywhere.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Sequence

from src.graph import ThoughtGraph, validate_thought
from src.interfaces import (
    CandidateResult,
    EngineFacade,
    ResonanceHit,
    VerifierResult,
    require_mode,
)
from src.extraction.cue import CueExtractor
from src.index.store import InvertedCandidateIndex
from src.alignment import MultiRelFGWVerifier

ENGINE_VERSION = "resonance-engine/0.1"


class InMemoryThoughtStore:
    """Minimal ThoughtStore: canonical dicts in memory, JSON persistence."""

    def __init__(self) -> None:
        self._graphs: dict[str, ThoughtGraph] = {}

    def put(self, graph: ThoughtGraph) -> None:
        validate_thought(graph.to_dict())
        self._graphs[graph.thought_id] = graph

    def get(self, thought_id: str) -> ThoughtGraph | None:
        return self._graphs.get(thought_id)

    def contains(self, thought_id: str) -> bool:
        return thought_id in self._graphs

    def thought_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._graphs))

    def dump(self, path: Path) -> None:
        payload = {tid: g.to_dict() for tid, g in sorted(self._graphs.items())}
        Path(path).write_text(
            json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "InMemoryThoughtStore":
        store = cls()
        for _tid, data in json.loads(Path(path).read_text(encoding="utf-8")).items():
            store.put(ThoughtGraph.from_dict(data))
        return store


class ResonanceEngine:
    """EngineFacade over the accepted R2/R3/R4 components."""

    def __init__(self, *, extractor: CueExtractor | None = None,
                 index: InvertedCandidateIndex | None = None,
                 verifier: MultiRelFGWVerifier | None = None,
                 store: InMemoryThoughtStore | None = None) -> None:
        self.extractor = extractor or CueExtractor()
        self.candidate_index = index or InvertedCandidateIndex()
        self.verifier = verifier or MultiRelFGWVerifier()
        self.store = store or InMemoryThoughtStore()
        self._explanations: dict[tuple[str, str], VerifierResult] = {}

    # -- EngineFacade -------------------------------------------------------
    def ingest(self, context: str, *, source_id: str | None = None) -> ThoughtGraph:
        result = self.extractor.extract(context, source_id=source_id)
        return result.graph

    def ingest_manual(self, payload: dict) -> ThoughtGraph:
        """Manual bypass: same validator/model, no extractor involved."""
        graph = ThoughtGraph.from_dict(payload)
        if graph.provenance.kind != "manual":
            raise ValueError("manual ingest requires provenance.kind == 'manual'")
        return graph

    def index(self, graph: ThoughtGraph) -> None:
        self.store.put(graph)
        self.candidate_index.upsert(graph)

    def find(self, graph: ThoughtGraph, *, mode: str, k: int = 20) -> Sequence[ResonanceHit]:
        require_mode(mode)
        hits: list[ResonanceHit] = []
        for candidate in self.candidate_index.query(graph, mode=mode, k=k):
            target = self.store.get(candidate.candidate_id)
            if target is None:
                continue
            verification = self.verifier.verify(
                graph, target, seeds=candidate.seed_correspondences)
            self._explanations[(graph.thought_id, candidate.candidate_id)] = verification
            hits.append(ResonanceHit(candidate=self._flag_synced(candidate, verification),
                                     verification=verification))
        return tuple(hits)

    def compare(self, a: ThoughtGraph, b: ThoughtGraph, *, mode: str) -> VerifierResult:
        require_mode(mode)
        result = self.verifier.verify(a, b)
        self._explanations[(a.thought_id, b.thought_id)] = result
        return result

    def explain(self, a_id: str, b_id: str) -> VerifierResult | None:
        return self._explanations.get((a_id, b_id))

    def get(self, thought_id: str) -> ThoughtGraph | None:
        return self.store.get(thought_id)

    # -- helpers ------------------------------------------------------------
    @staticmethod
    def _flag_synced(candidate: CandidateResult, verification: VerifierResult) -> CandidateResult:
        flags = verification.retrieval_flags
        if (candidate.requires_structural_verification == flags.requires_structural_verification
                and candidate.polarity_reliable == flags.polarity_reliable):
            return candidate
        raise ValueError("retrieval flags drifted between index and verifier")
