"""ResonanceEngine: the accepted components composed behind EngineFacade.

context/manual graph -> Thought DNA -> validate/canonicalize -> index ->
retrieve -> verify -> score -> explain. Pure Python; no MCP anywhere.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Sequence

from src.graph import ThoughtGraph, canonical_sha256, validate_thought
from src.graph.versioning import SCHEMA_VERSION
from src.interfaces import (
    INTERFACE_VERSION,
    CandidateResult,
    EngineFacade,
    ResonanceHit,
    VerifierResult,
    require_mode,
)
from src.extraction.cue import EXTRACTOR_ID, EXTRACTOR_VERSION, CueExtractor
from src.index.store import INDEX_VERSION, InvertedCandidateIndex
from src.fingerprint.keys import FEATURE_VERSION
from src.alignment import MultiRelFGWVerifier
from src.alignment.verifier import COMPONENT_VERSION

ENGINE_VERSION = "resonance-engine/0.1.1"
MANIFEST_VERSION = "resonance-engine-manifest/0.1"


def _canonical_sha(value: object) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def store_corpus_snapshot(store: "InMemoryThoughtStore") -> str:
    """Same snapshot function the inverted index uses for corpus_snapshot."""
    return _canonical_sha(
        sorted((tid, canonical_sha256(store.get(tid).to_dict())) for tid in store.thought_ids())
    )


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
        self._require_bound()

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
        self._require_bound()
        for candidate in self.candidate_index.query(graph, mode=mode, k=k):
            target = self.store.get(candidate.candidate_id)
            if target is None:
                raise ValueError(
                    f"index candidate {candidate.candidate_id!r} is absent from the bound store"
                )
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

    def manifest(self) -> dict[str, object]:
        self._require_bound()
        return {
            "manifest_version": MANIFEST_VERSION,
            "engine_version": ENGINE_VERSION,
            "interface_version": INTERFACE_VERSION,
            "schema_version": SCHEMA_VERSION,
            "extractor_id": EXTRACTOR_ID,
            "extractor_version": EXTRACTOR_VERSION,
            "index_version": INDEX_VERSION,
            "feature_version": FEATURE_VERSION,
            "verifier_version": COMPONENT_VERSION,
            "index_config_hash": self.candidate_index.config.config_hash,
            "verifier_config_hash": self.verifier.config_hash,
            "corpus_snapshot": self.candidate_index.corpus_snapshot,
            "thought_ids": list(self.store.thought_ids()),
        }

    def dump(self, path: str | Path) -> None:
        """Write a bound engine snapshot: store + index + manifest."""
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)
        self._require_bound()
        self.store.dump(path / "store.json")
        self.candidate_index.dump(path / "index.json")
        (path / "manifest.json").write_text(
            json.dumps(self.manifest(), ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )

    @classmethod
    def load(cls, path: str | Path) -> "ResonanceEngine":
        """Restore a bound snapshot. Rejects mixed store/index and tampered versions."""
        path = Path(path)
        manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
        if manifest.get("manifest_version") != MANIFEST_VERSION:
            raise ValueError(
                f"persisted manifest_version {manifest.get('manifest_version')!r} != {MANIFEST_VERSION!r}"
            )
        if manifest.get("engine_version") != ENGINE_VERSION:
            raise ValueError(
                f"persisted engine_version {manifest.get('engine_version')!r} != {ENGINE_VERSION!r}"
            )
        store = InMemoryThoughtStore.load(path / "store.json")
        index = InvertedCandidateIndex.load(path / "index.json")
        if list(store.thought_ids()) != list(manifest.get("thought_ids") or []):
            raise ValueError("manifest thought_ids do not match store")
        if index.corpus_snapshot != manifest.get("corpus_snapshot"):
            raise ValueError("manifest corpus_snapshot does not match index")
        if store_corpus_snapshot(store) != index.corpus_snapshot:
            raise ValueError("store and index corpus snapshots diverge")
        return cls(store=store, index=index)

    # -- helpers ------------------------------------------------------------
    def _require_bound(self) -> None:
        store_snap = store_corpus_snapshot(self.store)
        if store_snap != self.candidate_index.corpus_snapshot:
            raise ValueError("store and index corpus snapshots diverge")
    @staticmethod
    def _flag_synced(candidate: CandidateResult, verification: VerifierResult) -> CandidateResult:
        flags = verification.retrieval_flags
        if (candidate.requires_structural_verification == flags.requires_structural_verification
                and candidate.polarity_reliable == flags.polarity_reliable):
            return candidate
        raise ValueError("retrieval flags drifted between index and verifier")
