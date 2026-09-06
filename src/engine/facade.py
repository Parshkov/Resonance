"""ResonanceEngine: the accepted components composed behind EngineFacade.

context/manual graph -> Thought DNA -> validate/canonicalize -> index ->
retrieve -> verify -> score -> explain. Pure Python; no MCP anywhere.
"""

from __future__ import annotations

import hashlib
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
from src.extraction.cue import EXTRACTOR_VERSION, CueExtractor
from src.index.store import INDEX_VERSION, InvertedCandidateIndex
from src.alignment import MultiRelFGWVerifier
from src import scoring as _scoring
from src.alignment.verifier import COMPONENT_VERSION as VERIFIER_VERSION, _config_hash
from src.interfaces import INTERFACE_VERSION

ENGINE_VERSION = "resonance-engine/0.2"


CLASS_RANK = {"direct": 0, "approximate": 1, "analogical": 2, "complementary": 3, "negative": 4}
# Retrieval proposes, verification ranks (ADR-0004): fetch a larger candidate
# pool than the caller asked for, verify all of it, and return the best k by
# verified score. Hard-rejected candidates that sat inside the caller's
# retrieval window are returned too, after the kept rows, as contradiction
# evidence rather than silently dropped.
RETRIEVAL_OVERFETCH = 4
MIN_VERIFY_POOL = 24


def _tie_key(hit: ResonanceHit):
    """Boundary ties are decided on the verified score alone: candidates whose
    structural score equals the k-th one are all returned (retrieval score is
    only a stable order inside the tie, never a truncation key)."""
    return (hit.verification.classification == "negative",
            round(hit.verification.components.structural, 6))


def _verified_sort_key(hit: ResonanceHit):
    v = hit.verification
    rejected = 1 if v.hard_rejection else 0
    negative = 1 if v.classification == "negative" else 0
    primary = hit.candidate.channel_scores.get("primary", 0.0)
    return (rejected, negative, -round(v.components.structural, 6), -round(primary, 6), hit.candidate.candidate_id)


class EngineIntegrityError(RuntimeError):
    """Store/index composition is inconsistent; fail closed, never skip."""


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

    def snapshot(self) -> str:
        """Same recipe as the index corpus snapshot: sha256 over sorted
        (thought_id, canonical graph hash) pairs, so store/index binding is a
        string-equality check."""
        from src.graph import canonical_sha256
        items = sorted((tid, canonical_sha256(g.to_dict()))
                       for tid, g in self._graphs.items())
        blob = json.dumps(items, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(blob).hexdigest()

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

    def _require_bound(self) -> None:
        """Use-time integrity: catches in-memory store/index drift that never
        went through dump/load (R5-ASSIST 5b1a9f2's addition, adopted).
        Full-recompute by design so direct mutation cannot hide behind a
        cache; O(corpus) canonical hashing is milliseconds at v0.1 scale."""
        if self.store.snapshot() != self.candidate_index.corpus_snapshot:
            raise EngineIntegrityError(
                "store and index corpus snapshots diverge; refuse to serve")

    def find(self, graph: ThoughtGraph, *, mode: str, k: int = 20) -> Sequence[ResonanceHit]:
        require_mode(mode)
        self._require_bound()
        hits: list[ResonanceHit] = []
        rarity = self.candidate_index.motif_rarity(graph)
        pool = max(k * RETRIEVAL_OVERFETCH, MIN_VERIFY_POOL)
        retrieval_position: dict[str, int] = {}
        for position, candidate in enumerate(self.candidate_index.query(graph, mode=mode, k=pool), start=1):
            retrieval_position[candidate.candidate_id] = position
            target = self.store.get(candidate.candidate_id)
            if target is None:
                raise EngineIntegrityError(
                    f"index returned {candidate.candidate_id!r} which is absent "
                    "from the thought store; store/index snapshots have diverged")
            verification = self.verifier.verify(
                graph, target, seeds=candidate.seed_correspondences, rarity=rarity)
            self._explanations[(graph.thought_id, candidate.candidate_id)] = verification
            hits.append(ResonanceHit(candidate=self._flag_synced(candidate, verification),
                                     verification=verification))
        ordered = sorted(hits, key=_verified_sort_key)
        accepted = [h for h in ordered if not h.verification.hard_rejection]
        kept = accepted[:k]
        # Competition ties at the k boundary are not truncated by name or by
        # retrieval score: every candidate whose verified score equals the
        # k-th one is returned too (same policy as the index's TIE_POLICY).
        if len(accepted) > k:
            boundary = _tie_key(kept[-1])
            for extra in accepted[k:]:
                if _tie_key(extra) != boundary:
                    break
                kept.append(extra)
        rejected = [h for h in ordered if h.verification.hard_rejection
                    and retrieval_position.get(h.candidate.candidate_id, pool + 1) <= k]
        return tuple(kept + rejected)

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


    # -- bound persistence --------------------------------------------------
    def dump(self, directory: Path) -> None:
        """Persist store+index as ONE verified snapshot: a manifest binds the
        two payloads by hash and by the shared corpus snapshot."""
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        store_path = directory / "store.json"
        index_path = directory / "index.json"
        self.store.dump(store_path)
        self.candidate_index.dump(index_path)
        store_snapshot = self.store.snapshot()
        index_snapshot = self.candidate_index.corpus_snapshot
        if store_snapshot != index_snapshot:
            raise EngineIntegrityError(
                "refusing to dump: store and index disagree on corpus snapshot")
        manifest = {
            "engine_version": ENGINE_VERSION,
            "interface_version": INTERFACE_VERSION,
            "schema_version": "thought-dna/0.1",
            "verifier_version": VERIFIER_VERSION,
            "index_version": INDEX_VERSION,
            "extractor_version": EXTRACTOR_VERSION,
            "scoring_version": _scoring.SCORE_MODEL_VERSION,
            "components": {
                "extractor": {
                    "config": {"drop_threshold": self.extractor.drop_threshold},
                    "config_hash": _config_hash(
                        {"drop_threshold": self.extractor.drop_threshold}),
                },
                "verifier": {"config": dict(self.verifier.config),
                             "config_hash": self.verifier.config_hash},
            },
            "corpus_snapshot": index_snapshot,
            "thought_ids": list(self.store.thought_ids()),
            "files": {
                "store.json": hashlib.sha256(store_path.read_bytes()).hexdigest(),
                "index.json": hashlib.sha256(index_path.read_bytes()).hexdigest(),
            },
        }
        (directory / "manifest.json").write_text(
            json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8")

    @classmethod
    def load(cls, directory: Path, **kwargs) -> "ResonanceEngine":
        """Load a snapshot; any hash, version, snapshot, or component-config
        mismatch fails closed. Extractor and verifier are RECONSTRUCTED from
        the persisted configs, so the loaded engine behaves exactly like the
        one that dumped; overriding them via kwargs is rejected."""
        if "extractor" in kwargs or "verifier" in kwargs:
            raise EngineIntegrityError(
                "load() reconstructs extractor/verifier from the snapshot; "
                "overrides would silently change behavior")
        directory = Path(directory)
        manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
        declared = {
            "engine_version": ENGINE_VERSION,
            "scoring_version": _scoring.SCORE_MODEL_VERSION,
            "interface_version": INTERFACE_VERSION,
            "schema_version": "thought-dna/0.1",
            "verifier_version": VERIFIER_VERSION,
            "index_version": INDEX_VERSION,
            "extractor_version": EXTRACTOR_VERSION,
        }
        for key, expected in declared.items():
            if manifest.get(key) != expected:
                raise EngineIntegrityError(
                    f"snapshot {key} mismatch: {manifest.get(key)!r} != {expected!r}")
        for name, expected in manifest["files"].items():
            actual = hashlib.sha256((directory / name).read_bytes()).hexdigest()
            if actual != expected:
                raise EngineIntegrityError(f"snapshot file hash mismatch: {name}")
        from src.index.store import InvertedCandidateIndex
        store = InMemoryThoughtStore.load(directory / "store.json")
        index = InvertedCandidateIndex.load(directory / "index.json")
        if store.snapshot() != index.corpus_snapshot:
            raise EngineIntegrityError(
                "store and index snapshots diverge inside the manifest-verified payloads")
        if list(store.thought_ids()) != list(manifest.get("thought_ids") or []):
            raise EngineIntegrityError("manifest thought_ids do not match the store")
        if manifest["corpus_snapshot"] != index.corpus_snapshot:
            raise EngineIntegrityError("manifest corpus_snapshot mismatch")
        components = manifest.get("components") or {}
        ext_cfg = components.get("extractor") or {}
        if _config_hash(dict(ext_cfg.get("config") or {})) != ext_cfg.get("config_hash"):
            raise EngineIntegrityError(
                "persisted extractor config does not reproduce its recorded hash")
        try:
            extractor = CueExtractor(
                drop_threshold=ext_cfg["config"]["drop_threshold"])
        except (KeyError, TypeError, ValueError) as exc:
            raise EngineIntegrityError(f"invalid persisted extractor config: {exc}")
        verifier_cfg = components.get("verifier") or {}
        persisted_v = dict(verifier_cfg.get("config") or {})
        runtime_identity = {
            "score_model": _scoring.SCORE_MODEL_VERSION,
            "classify_policy": _scoring.CLASSIFY_POLICY,
        }
        for key, expected in runtime_identity.items():
            if persisted_v.get(key) != expected:
                raise EngineIntegrityError(
                    f"persisted verifier {key} does not match the runtime "
                    f"value {expected!r}; the adjudicator would silently use "
                    "runtime behavior")
        verifier = MultiRelFGWVerifier(persisted_v)
        if verifier.config_hash != verifier_cfg.get("config_hash"):
            raise EngineIntegrityError(
                "persisted verifier config does not reproduce its recorded hash")
        return cls(store=store, index=index, extractor=extractor,
                   verifier=verifier, **kwargs)
