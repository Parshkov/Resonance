"""Inverted multi-channel CandidateIndex (v0.2).

Channels, all deterministic and model-free:

* ``structural`` -- label-free D0/D1 landmark-pair keys (same skeleton).
* ``concept``    -- (role, abstract concept) landmark keys from the lexicon
                    (same abstract notions in the same arrangement).
* ``content``    -- BM25-style stem overlap over node labels
                    (same words).
* ``knowledge``  -- Knowledge DNA ``about``/``requires`` overlap.

Every key is IDF-weighted. A key is a *stop key* (skipped) only when more
than ``stop_df_frac`` of the corpus carries it; generic motifs are therefore
down-weighted, never made unretrievable. The primary rank for the
``analogical`` mode fuses structural, concept and content evidence; the
``structural`` mode stays label-free by contract (the ablation path).
"""

from __future__ import annotations

import hashlib
import json
import math
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from src.fingerprint.keys import FEATURE_VERSION, DescriptorVariant, concept_fingerprints, fingerprints
from src.graph import ThoughtGraph, canonical_sha256
from src.interfaces import (
    CandidateResult,
    ConfigRef,
    SeedCorrespondence,
    require_mode,
)
from src.semantics import stems as _stems

INDEX_VERSION = "resonance-index/0.2.0"
QUERY_BUDGET = 96
STOP_DF_FRAC = 0.5
MIN_CORPUS_FOR_STOP = 20
TIE_POLICY = "competition_min_rank_include_boundary_ties"
FUSION_WEIGHTS = {"structural": 0.45, "concept": 0.40, "content": 0.15}


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _tokens(*texts: str) -> list[str]:
    out: list[str] = []
    for text in texts:
        out.extend(_stems(text))
    return out


@dataclass(frozen=True)
class QueryDiagnostics:
    """Observable postings/latency for the last query(). Not a CandidateResult field."""

    postings_touched: int
    latency_seconds: float
    live_query_keys: int
    skipped_dead_keys: int
    budget_used: int
    usable_query_evidence: float
    content_scanned: bool
    requested_k: int = 0
    returned: int = 0
    tie_group_expanded: bool = False
    tie_policy: str = TIE_POLICY


class _KeyChannel:
    """One inverted key channel with IDF weights and stop keys."""

    def __init__(self) -> None:
        self.postings: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
        self.df: Counter[str] = Counter()
        self.idf: dict[str, float] = {}
        self.stop: set[str] = set()
        self.per_graph: dict[str, list[tuple[str, str, str]]] = {}

    def add(self, thought_id: str, records: list[tuple[str, str, str]]) -> None:
        self.per_graph[thought_id] = records
        seen: set[str] = set()
        for key, left, right in records:
            self.postings[key].append((thought_id, left, right))
            if key not in seen:
                self.df[key] += 1
                seen.add(key)

    def finalize(self, n: int, stop_cutoff: float) -> None:
        self.idf = {key: math.log((n + 1) / (df + 1)) + 1e-9 for key, df in self.df.items()}
        self.stop = {key for key, df in self.df.items() if df > stop_cutoff}


class InvertedCandidateIndex:
    """Deterministic CandidateIndex. Default structural path is MULTI."""

    def __init__(
        self,
        *,
        query_budget: int = QUERY_BUDGET,
        stop_df_frac: float = STOP_DF_FRAC,
        min_corpus_for_stop: int = MIN_CORPUS_FOR_STOP,
        fusion_weights: Mapping[str, float] | None = None,
    ) -> None:
        if query_budget < 1:
            raise ValueError("query_budget must be >= 1")
        self.query_budget = int(query_budget)
        self.stop_df_frac = float(stop_df_frac)
        self.min_corpus_for_stop = int(min_corpus_for_stop)
        self.fusion_weights = dict(fusion_weights or FUSION_WEIGHTS)
        self._graphs: dict[str, ThoughtGraph] = {}
        self.last_query: QueryDiagnostics | None = None
        self._rebuild()

    def _policy(self) -> dict[str, object]:
        return {
            "index_version": INDEX_VERSION,
            "feature_version": FEATURE_VERSION,
            "query_budget": self.query_budget,
            "stop_df_frac": self.stop_df_frac,
            "min_corpus_for_stop": self.min_corpus_for_stop,
            "fusion_weights": self.fusion_weights,
            "default_variant": "MULTI",
            "tie_policy": TIE_POLICY,
        }

    def _cutoff(self, n: int) -> float:
        if n < self.min_corpus_for_stop:
            return float(n)            # nothing is a stop key in a tiny corpus
        return self.stop_df_frac * n

    def _rebuild(self) -> None:
        graphs = self._graphs
        n = max(len(graphs), 1)
        cutoff = self._cutoff(len(graphs))
        structural = _KeyChannel()
        concept = _KeyChannel()
        content_tf: dict[str, Counter[str]] = {}
        content_postings: dict[str, dict[str, int]] = defaultdict(dict)
        content_df: Counter[str] = Counter()
        content_len: dict[str, int] = {}
        about: dict[str, list[str]] = defaultdict(list)
        about_df: Counter[str] = Counter()
        requires: dict[str, set[str]] = defaultdict(set)
        for thought_id, graph in graphs.items():
            structural.add(thought_id, fingerprints(graph, "MULTI"))
            concept.add(thought_id, concept_fingerprints(graph))
            # Labels only: shared user graphs never carry source text (it is
            # removed on share), so scoring source text would favour seeded
            # fixtures over people.
            bag: Counter[str] = Counter(_tokens(*(node.label for node in graph.nodes)))
            content_tf[thought_id] = bag
            content_len[thought_id] = sum(bag.values())
            for term, tf in bag.items():
                content_postings[term][thought_id] = tf
                content_df[term] += 1
            seen_about: set[str] = set()
            for node in graph.nodes:
                knowledge = node.knowledge
                if knowledge is None:
                    continue
                for ref in knowledge.about:
                    about[ref.id].append(thought_id)
                    if ref.id not in seen_about:
                        about_df[ref.id] += 1
                        seen_about.add(ref.id)
                for ref in knowledge.requires:
                    requires[thought_id].add(ref.id)
        structural.finalize(n, cutoff)
        concept.finalize(n, cutoff)
        self._structural = structural
        self._concept = concept
        self._content = content_tf
        self._content_postings = content_postings
        self._content_df = content_df
        self._content_len = content_len
        self._avg_len = (sum(content_len.values()) / n) if content_len else 1.0
        self._content_idf = {term: math.log((n + 1) / (df + 0.5)) for term, df in content_df.items()}
        self._about = about
        self._about_df = about_df
        self._about_idf = {concept_id: math.log((n + 1) / (df + 1)) for concept_id, df in about_df.items()}
        self._requires = requires
        self._corpus_n = n
        self._cutoff_value = cutoff
        snapshot = _sha(sorted((thought_id, canonical_sha256(graph.to_dict())) for thought_id, graph in graphs.items()))
        self.corpus_snapshot = snapshot
        self.config = ConfigRef(
            component="retrieval",
            component_version=INDEX_VERSION,
            config_hash=_sha({**self._policy(), "corpus_snapshot": snapshot}),
        )

    # -- corpus management ----------------------------------------------------
    def build(self, graphs: Iterable[ThoughtGraph]) -> None:
        """Replace the corpus and rebuild once. Public non-quadratic bulk path."""
        self._graphs = {graph.thought_id: graph for graph in graphs}
        self._rebuild()

    def upsert(self, graph: ThoughtGraph) -> None:
        self._graphs[graph.thought_id] = graph
        self._rebuild()

    def remove(self, thought_id: str) -> None:
        self._graphs.pop(thought_id, None)
        self._rebuild()

    # -- key channels -----------------------------------------------------------
    def _key_query(
        self,
        channel: _KeyChannel,
        records: list[tuple[str, str, str]],
        query_id: str,
        *,
        apply_budget: bool = True,
        seed_channel: str = "structural",
    ) -> tuple[dict[str, float], dict[str, list[SeedCorrespondence]], float, int, int, int]:
        by_key: dict[str, list[tuple[str, str]]] = defaultdict(list)
        for key, qa, qb in records:
            by_key[key].append((qa, qb))
        skipped = 0
        live: list[tuple[str, float, list[tuple[str, str]]]] = []
        for key, pairs in by_key.items():
            if key in channel.stop or key not in channel.idf:
                skipped += 1
                continue
            live.append((key, channel.idf[key], pairs))
        live.sort(key=lambda item: (-item[1], item[0]))
        budget = self.query_budget if apply_budget else len(live)
        selected = live[:budget]
        support: dict[str, dict[tuple[str, str], float]] = defaultdict(lambda: defaultdict(float))
        contrib: dict[str, list[tuple[float, str, str, str, str]]] = defaultdict(list)
        touched = 0
        usable = 0.0
        for key, weight, pairs in selected:
            usable += weight
            posts = channel.postings.get(key, ())
            touched += len(posts)
            for qa, qb in pairs:
                for thought_id, ca, cb in posts:
                    if thought_id == query_id:
                        continue
                    support[thought_id][(qa, ca)] += weight
                    if qb != qa:
                        support[thought_id][(qb, cb)] += weight
                    contrib[thought_id].append((weight, qa, qb, ca, cb))
        scores: dict[str, float] = {}
        seeds: dict[str, list[SeedCorrespondence]] = {}
        for thought_id, pair_weights in support.items():
            ordered = sorted(pair_weights.items(), key=lambda item: (-item[1], item[0][0], item[0][1]))
            mapping: dict[str, str] = {}
            used_q: set[str] = set()
            used_c: set[str] = set()
            for (qn, cn), _weight in ordered:
                if qn in used_q or cn in used_c:
                    continue
                mapping[qn] = cn
                used_q.add(qn)
                used_c.add(cn)
            coherent = sum(
                weight
                for weight, qa, qb, ca, cb in contrib[thought_id]
                if mapping.get(qa) == ca and mapping.get(qb) == cb
            )
            scores[thought_id] = min(1.0, coherent / usable) if usable > 0 else 0.0
            seeds[thought_id] = [
                SeedCorrespondence(query_node=qn, candidate_node=cn, support=min(1.0, pair_weights[(qn, cn)] / max(usable, 1e-9) * 4.0), channel=seed_channel)
                for qn, cn in mapping.items()
            ]
        return scores, seeds, usable, touched, skipped, len(selected)

    def _structural_query(self, graph: ThoughtGraph, *, variant: DescriptorVariant = "MULTI", apply_budget: bool = True):
        return self._key_query(self._structural, fingerprints(graph, variant), graph.thought_id,
                               apply_budget=apply_budget, seed_channel="structural")

    def _concept_query(self, graph: ThoughtGraph):
        return self._key_query(self._concept, concept_fingerprints(graph, expand=True), graph.thought_id,
                               seed_channel="concept")

    def _content_query(self, graph: ThoughtGraph) -> dict[str, float]:
        """BM25 over stems, normalised by the query's self-score so values lie in [0, 1]."""
        query_bag = Counter(_tokens(*(node.label for node in graph.nodes)))
        k1, b = 1.2, 0.75
        scores: dict[str, float] = defaultdict(float)

        def bm25(tf: int, dl: int) -> float:
            return tf * (k1 + 1) / (tf + k1 * (1 - b + b * dl / max(self._avg_len, 1e-9)))

        self_score = 0.0
        q_len = sum(query_bag.values())
        for term, qf in query_bag.items():
            idf = self._content_idf.get(term)
            if not idf:
                continue
            self_score += idf * bm25(qf, q_len)
            for thought_id, tf in self._content_postings.get(term, {}).items():
                if thought_id == graph.thought_id:
                    continue
                scores[thought_id] += idf * bm25(tf, self._content_len[thought_id])
        if self_score <= 0:
            return {}
        return {key: min(1.0, value / self_score) for key, value in scores.items() if value}

    def _knowledge_query(self, graph: ThoughtGraph) -> tuple[dict[str, float], dict[str, float]]:
        about_ids = {ref.id for node in graph.nodes if node.knowledge for ref in node.knowledge.about}
        require_ids = {ref.id for node in graph.nodes if node.knowledge for ref in node.knowledge.requires}
        about_scores: dict[str, float] = defaultdict(float)
        complement_scores: dict[str, float] = defaultdict(float)
        for concept_id in about_ids:
            weight = self._about_idf.get(concept_id, 0.0)
            if not weight:
                continue
            for thought_id in self._about.get(concept_id, ()):
                if thought_id != graph.thought_id:
                    about_scores[thought_id] += weight
        for concept_id in require_ids:
            weight = self._about_idf.get(concept_id, 0.0)
            if not weight:
                continue
            for thought_id in self._about.get(concept_id, ()):
                if thought_id != graph.thought_id:
                    complement_scores[thought_id] += weight
        return dict(about_scores), dict(complement_scores)

    def _ranks(self, scores: Mapping[str, float]) -> dict[str, int]:
        """Competition ranking: equal scores share the minimum rank."""
        ordered = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
        ranks: dict[str, int] = {}
        last_score: float | None = None
        last_rank = 0
        for index, (thought_id, score) in enumerate(ordered, start=1):
            if last_score is None or score != last_score:
                last_rank = index
                last_score = score
            ranks[thought_id] = last_rank
        return ranks

    # -- rarity -----------------------------------------------------------------
    def motif_rarity(self, graph: ThoughtGraph) -> float:
        """Corpus-relative rarity of the graph's label-free skeleton in [0, 1].

        Mean IDF of its structural keys over log(n+1). 1.0 = every key is unique
        in the corpus; 0.0 = every key is carried by the whole corpus. Used by
        scoring to demand more semantic support for common skeletons.
        """
        keys = {key for key, _, _ in fingerprints(graph, "MULTI")}
        if not keys or self._corpus_n <= 1:
            return 1.0
        denom = math.log(self._corpus_n + 1)
        vals = [self._structural.idf.get(key, denom) / denom for key in keys]
        return max(0.0, min(1.0, sum(vals) / len(vals)))

    # -- query ------------------------------------------------------------------
    def query(self, graph: ThoughtGraph, *, mode: str, k: int) -> Sequence[CandidateResult]:
        require_mode(mode)
        if not isinstance(k, int) or isinstance(k, bool) or k <= 0:
            raise ValueError("k must be a positive integer")
        started = time.perf_counter()
        structural, s_seeds, usable, touched, skipped_dead, budget_used = self._structural_query(graph, variant="MULTI")
        content_scanned = mode != "structural"
        concept: dict[str, float] = {}
        c_seeds: dict[str, list[SeedCorrespondence]] = {}
        content: dict[str, float] = {}
        knowledge_about: dict[str, float] = {}
        knowledge_comp: dict[str, float] = {}
        if content_scanned:
            concept, c_seeds, _cu, c_touched, _cs, _cb = self._concept_query(graph)
            touched += c_touched
            content = self._content_query(graph)
            knowledge_about, knowledge_comp = self._knowledge_query(graph)
        candidates = set(structural) | set(concept) | set(content) | set(knowledge_about) | set(knowledge_comp)
        w = self.fusion_weights
        fused = {
            cid: w["structural"] * structural.get(cid, 0.0) + w["concept"] * concept.get(cid, 0.0)
            + w["content"] * content.get(cid, 0.0)
            for cid in candidates
        }
        if mode == "structural":
            primary = dict(structural)
        elif mode == "complementary":
            k_max = max(knowledge_comp.values(), default=0.0) or 1.0
            primary = {cid: (knowledge_comp.get(cid, 0.0) / k_max) + 0.5 * fused.get(cid, 0.0) for cid in candidates}
        else:
            primary = fused
        structural_ranks = self._ranks(structural)
        concept_ranks = self._ranks(concept)
        content_ranks = self._ranks(content)
        knowledge_ranks = self._ranks({**knowledge_about, **knowledge_comp})
        primary_ranks = self._ranks({cid: primary.get(cid, 0.0) for cid in candidates} if candidates else {})
        eligible = [cid for cid in candidates if primary_ranks.get(cid, 10**9) <= k and primary.get(cid, 0.0) > 0.0]
        ordered = sorted(eligible, key=lambda cid: (primary_ranks.get(cid, 10**9), cid))
        results: list[CandidateResult] = []
        for candidate_id in ordered:
            seeds = list(s_seeds.get(candidate_id, ()))
            taken = {(s.query_node, s.candidate_node) for s in seeds}
            for s in c_seeds.get(candidate_id, ()):
                if (s.query_node, s.candidate_node) not in taken:
                    seeds.append(s)
            results.append(
                CandidateResult(
                    candidate_id=candidate_id,
                    channel_scores={
                        "content": content.get(candidate_id, 0.0),
                        "concept": concept.get(candidate_id, 0.0),
                        "knowledge_about": knowledge_about.get(candidate_id, 0.0),
                        "knowledge_complement": knowledge_comp.get(candidate_id, 0.0),
                        "structural": structural.get(candidate_id, 0.0),
                        "primary": primary.get(candidate_id, 0.0),
                    },
                    channel_ranks={
                        "content": content_ranks.get(candidate_id, 0),
                        "concept": concept_ranks.get(candidate_id, 0),
                        "knowledge": knowledge_ranks.get(candidate_id, 0),
                        "structural": structural_ranks.get(candidate_id, 0),
                        "primary": primary_ranks.get(candidate_id, 0),
                    },
                    seed_correspondences=tuple(seeds),
                    usable_query_evidence=usable,
                    requires_structural_verification=True,
                    polarity_reliable=False,
                    index_version=INDEX_VERSION,
                    feature_version=FEATURE_VERSION,
                    corpus_snapshot=self.corpus_snapshot,
                    config=self.config,
                )
            )
        self.last_query = QueryDiagnostics(
            postings_touched=touched,
            latency_seconds=time.perf_counter() - started,
            live_query_keys=budget_used,
            skipped_dead_keys=skipped_dead,
            budget_used=budget_used,
            usable_query_evidence=usable,
            content_scanned=content_scanned,
            requested_k=k,
            returned=len(results),
            tie_group_expanded=len(results) > k,
            tie_policy=TIE_POLICY,
        )
        return results

    def query_ablation(self, graph: ThoughtGraph, *, variant: DescriptorVariant, k: int = 20) -> tuple[list[tuple[str, float]], int]:
        """Named D0/D1/MULTI control. Not the CandidateIndex shipping path."""
        scores, _seeds, _usable, touched, _skipped, _budget = self._structural_query(graph, variant=variant, apply_budget=False)
        ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))[:k]
        return ranked, touched

    # -- persistence ------------------------------------------------------------
    def dump(self, path: str | Path) -> None:
        path = Path(path)
        payload = {
            **self._policy(),
            "corpus_snapshot": self.corpus_snapshot,
            "thought_ids": sorted(self._graphs),
            "graphs": {thought_id: graph.to_dict() for thought_id, graph in self._graphs.items()},
            "structural_df": dict(self._structural.df),
            "concept_df": dict(self._concept.df),
            "content_df": dict(self._content_df),
            "cutoff": self._cutoff_value,
        }
        path.write_bytes(_canonical_bytes(payload) + b"\n")

    @classmethod
    def load(cls, path: str | Path) -> "InvertedCandidateIndex":
        """Restore an index from ``dump()``; any version/snapshot mismatch fails closed."""
        path = Path(path)
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("index_version") != INDEX_VERSION:
            raise ValueError(f"persisted index_version {payload.get('index_version')!r} != {INDEX_VERSION!r}")
        if payload.get("feature_version") != FEATURE_VERSION:
            raise ValueError(f"persisted feature_version {payload.get('feature_version')!r} != {FEATURE_VERSION!r}")
        index = cls(
            query_budget=int(payload.get("query_budget", QUERY_BUDGET)),
            stop_df_frac=float(payload.get("stop_df_frac", STOP_DF_FRAC)),
            min_corpus_for_stop=int(payload.get("min_corpus_for_stop", MIN_CORPUS_FOR_STOP)),
            fusion_weights=payload.get("fusion_weights") or FUSION_WEIGHTS,
        )
        index.build(ThoughtGraph.from_dict(raw) for raw in payload["graphs"].values())
        if payload.get("corpus_snapshot") != index.corpus_snapshot:
            raise ValueError("persisted corpus_snapshot does not match rebuilt index")
        if sorted(payload.get("thought_ids") or []) != sorted(index._graphs):
            raise ValueError("persisted thought_ids do not match rebuilt index")
        return index
