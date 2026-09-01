"""Inverted multi-channel CandidateIndex."""

from __future__ import annotations

import hashlib
import json
import math
import re
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from src.fingerprint.keys import FEATURE_VERSION, DescriptorVariant, fingerprints
from src.graph import ThoughtGraph, canonical_sha256
from src.interfaces import (
    CandidateResult,
    ConfigRef,
    SeedCorrespondence,
    require_mode,
)

INDEX_VERSION = "resonance-index/0.1.1"
TOKEN_RE = re.compile(r"[a-z0-9]+")
QUERY_BUDGET = 64
SCALE_FLOOR = 1000
SMALL_CORPUS_MAX_DF_FRAC = 0.90


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _tokens(*texts: str) -> list[str]:
    out: list[str] = []
    for text in texts:
        out.extend(TOKEN_RE.findall(text.lower()))
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


class InvertedCandidateIndex:
    """Deterministic CandidateIndex. Default structural path is MULTI."""

    def __init__(
        self,
        *,
        max_df_frac: float = 0.005,
        min_df_cutoff: int = 5,
        query_budget: int = QUERY_BUDGET,
        scale_floor: int = SCALE_FLOOR,
        small_corpus_max_df_frac: float = SMALL_CORPUS_MAX_DF_FRAC,
    ) -> None:
        if query_budget < 1:
            raise ValueError("query_budget must be >= 1")
        self.max_df_frac = float(max_df_frac)
        self.min_df_cutoff = int(min_df_cutoff)
        self.query_budget = int(query_budget)
        self.scale_floor = int(scale_floor)
        self.small_corpus_max_df_frac = float(small_corpus_max_df_frac)
        self._graphs: dict[str, ThoughtGraph] = {}
        self.last_query: QueryDiagnostics | None = None
        self._rebuild()

    def _policy(self) -> dict[str, object]:
        return {
            "index_version": INDEX_VERSION,
            "feature_version": FEATURE_VERSION,
            "max_df_frac": self.max_df_frac,
            "min_df_cutoff": self.min_df_cutoff,
            "query_budget": self.query_budget,
            "scale_floor": self.scale_floor,
            "small_corpus_max_df_frac": self.small_corpus_max_df_frac,
            "default_variant": "MULTI",
        }

    def _cutoff(self, n: int) -> float:
        if n < self.scale_floor:
            return max(self.small_corpus_max_df_frac * n, 1.0)
        return max(self.min_df_cutoff, self.max_df_frac * n)

    def _rebuild(self) -> None:
        graphs = self._graphs
        n = max(len(graphs), 1)
        cutoff = self._cutoff(len(graphs))
        structural: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
        structural_df: Counter[str] = Counter()
        content_tf: dict[str, Counter[str]] = {}
        content_postings: dict[str, dict[str, int]] = defaultdict(dict)
        content_df: Counter[str] = Counter()
        about: dict[str, list[str]] = defaultdict(list)
        about_df: Counter[str] = Counter()
        requires: dict[str, set[str]] = defaultdict(set)
        graph_keys: dict[str, list[tuple[str, str, str]]] = {}
        for thought_id, graph in graphs.items():
            records = fingerprints(graph, "MULTI")
            graph_keys[thought_id] = records
            seen_keys: set[str] = set()
            for key, left, right in records:
                structural[key].append((thought_id, left, right))
                if key not in seen_keys:
                    structural_df[key] += 1
                    seen_keys.add(key)
            bag: Counter[str] = Counter(_tokens(graph.source.text, *(node.label for node in graph.nodes)))
            content_tf[thought_id] = bag
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
        dead = {key for key, df in structural_df.items() if df > cutoff}
        self._structural = structural
        self._structural_df = structural_df
        self._structural_dead = dead
        self._structural_idf = {key: math.log((n + 1) / (df + 1)) for key, df in structural_df.items()}
        self._graph_keys = graph_keys
        self._content = content_tf
        self._content_postings = content_postings
        self._content_df = content_df
        self._content_idf = {term: math.log((n + 1) / (df + 1)) for term, df in content_df.items()}
        self._about = about
        self._about_df = about_df
        self._about_idf = {concept: math.log((n + 1) / (df + 1)) for concept, df in about_df.items()}
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

    def _structural_query(
        self,
        graph: ThoughtGraph,
        *,
        variant: DescriptorVariant = "MULTI",
        apply_budget: bool = True,
    ) -> tuple[dict[str, float], dict[str, list[SeedCorrespondence]], float, int, int, int]:
        query_fps = fingerprints(graph, variant)
        by_key: dict[str, list[tuple[str, str]]] = defaultdict(list)
        for key, qa, qb in query_fps:
            by_key[key].append((qa, qb))
        skipped_dead = 0
        live: list[tuple[str, float, list[tuple[str, str]]]] = []
        for key, pairs in by_key.items():
            if key in self._structural_dead or key not in self._structural_idf:
                skipped_dead += 1
                continue
            live.append((key, self._structural_idf[key], pairs))
        live.sort(key=lambda item: (-item[1], item[0]))
        budget = self.query_budget if apply_budget else len(live)
        selected = live[:budget]
        support: dict[str, dict[tuple[str, str], float]] = defaultdict(lambda: defaultdict(float))
        contrib: dict[str, list[tuple[float, str, str, str, str]]] = defaultdict(list)
        touched = 0
        usable = 0.0
        for key, weight, pairs in selected:
            usable += weight
            posts = self._structural.get(key, ())
            touched += len(posts)
            for qa, qb in pairs:
                for thought_id, ca, cb in posts:
                    if thought_id == graph.thought_id:
                        continue
                    support[thought_id][(qa, ca)] += weight
                    support[thought_id][(qb, cb)] += weight
                    contrib[thought_id].append((weight, qa, qb, ca, cb))
        scores: dict[str, float] = {}
        seeds: dict[str, list[SeedCorrespondence]] = {}
        for thought_id, pair_weights in support.items():
            ordered = sorted(pair_weights.items(), key=lambda item: (-item[1], item[0][0], item[0][1]))
            mapping: dict[str, str] = {}
            used_q: set[str] = set()
            used_c: set[str] = set()
            for (qn, cn), weight in ordered:
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
            scores[thought_id] = coherent / usable if usable > 0 else 0.0
            seeds[thought_id] = [
                SeedCorrespondence(query_node=qn, candidate_node=cn, support=pair_weights[(qn, cn)], channel="structural")
                for qn, cn in mapping.items()
            ]
        return scores, seeds, usable, touched, skipped_dead, len(selected)

    def _content_query(self, graph: ThoughtGraph) -> dict[str, float]:
        query_bag = Counter(_tokens(graph.source.text, *(node.label for node in graph.nodes)))
        scores: dict[str, float] = defaultdict(float)
        for term, qf in query_bag.items():
            idf = self._content_idf.get(term)
            if not idf:
                continue
            for thought_id, tf in self._content_postings.get(term, {}).items():
                if thought_id == graph.thought_id:
                    continue
                scores[thought_id] += idf * qf * (tf / (tf + 1.2))
        return {key: value for key, value in scores.items() if value}

    def _knowledge_query(self, graph: ThoughtGraph) -> tuple[dict[str, float], dict[str, float]]:
        about_ids = {ref.id for node in graph.nodes if node.knowledge for ref in node.knowledge.about}
        require_ids = {ref.id for node in graph.nodes if node.knowledge for ref in node.knowledge.requires}
        about_scores: dict[str, float] = defaultdict(float)
        complement_scores: dict[str, float] = defaultdict(float)
        for concept in about_ids:
            weight = self._about_idf.get(concept, 0.0)
            if not weight:
                continue
            for thought_id in self._about.get(concept, ()):
                if thought_id != graph.thought_id:
                    about_scores[thought_id] += weight
        for concept in require_ids:
            weight = self._about_idf.get(concept, 0.0)
            if not weight:
                continue
            for thought_id in self._about.get(concept, ()):
                if thought_id != graph.thought_id:
                    complement_scores[thought_id] += weight
        return dict(about_scores), dict(complement_scores)

    def _ranks(self, scores: Mapping[str, float]) -> dict[str, int]:
        ordered = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
        return {thought_id: rank for rank, (thought_id, _) in enumerate(ordered, start=1)}

    def query(self, graph: ThoughtGraph, *, mode: str, k: int) -> Sequence[CandidateResult]:
        require_mode(mode)
        if not isinstance(k, int) or isinstance(k, bool) or k <= 0:
            raise ValueError("k must be a positive integer")
        started = time.perf_counter()
        structural, seeds, usable, touched, skipped_dead, budget_used = self._structural_query(graph, variant="MULTI")
        content_scanned = mode != "structural"
        if content_scanned:
            content = self._content_query(graph)
            knowledge_about, knowledge_comp = self._knowledge_query(graph)
        else:
            content = {}
            knowledge_about, knowledge_comp = {}, {}
        if mode == "complementary":
            primary = knowledge_comp or knowledge_about or structural
        elif mode == "structural":
            primary = structural
        else:
            primary = structural or content or knowledge_about
        candidates = set(structural) | set(content) | set(knowledge_about) | set(knowledge_comp)
        structural_ranks = self._ranks(structural)
        content_ranks = self._ranks(content)
        knowledge_ranks = self._ranks({**knowledge_about, **knowledge_comp})
        primary_ranks = self._ranks({cid: primary.get(cid, 0.0) for cid in candidates} if candidates else {})
        ordered = sorted(candidates, key=lambda cid: (primary_ranks.get(cid, 10**9), cid))[:k]
        results: list[CandidateResult] = []
        for candidate_id in ordered:
            results.append(
                CandidateResult(
                    candidate_id=candidate_id,
                    channel_scores={
                        "content": content.get(candidate_id, 0.0),
                        "knowledge_about": knowledge_about.get(candidate_id, 0.0),
                        "knowledge_complement": knowledge_comp.get(candidate_id, 0.0),
                        "structural": structural.get(candidate_id, 0.0),
                    },
                    channel_ranks={
                        "content": content_ranks.get(candidate_id, 0),
                        "knowledge": knowledge_ranks.get(candidate_id, 0),
                        "structural": structural_ranks.get(candidate_id, 0),
                    },
                    seed_correspondences=tuple(seeds.get(candidate_id, ())),
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
        )
        return results

    def query_ablation(
        self,
        graph: ThoughtGraph,
        *,
        variant: DescriptorVariant,
        k: int = 20,
    ) -> tuple[list[tuple[str, float]], int]:
        """Named D0/D1/MULTI control. Not the CandidateIndex shipping path."""
        scores, _seeds, _usable, touched, _skipped, _budget = self._structural_query(
            graph, variant=variant, apply_budget=False
        )
        ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))[:k]
        return ranked, touched

    def dump(self, path: Path) -> None:
        payload = {
            **self._policy(),
            "corpus_snapshot": self.corpus_snapshot,
            "thought_ids": sorted(self._graphs),
            "graphs": {thought_id: graph.to_dict() for thought_id, graph in self._graphs.items()},
            "structural_df": dict(self._structural_df),
            "content_df": dict(self._content_df),
            "cutoff": self._cutoff_value,
        }
        path.write_bytes(_canonical_bytes(payload) + b"\n")

    @classmethod
    def load(cls, path: Path) -> "InvertedCandidateIndex":
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("index_version") != INDEX_VERSION:
            raise ValueError(
                f"persisted index_version {payload.get('index_version')!r} != {INDEX_VERSION!r}"
            )
        if payload.get("feature_version") != FEATURE_VERSION:
            raise ValueError(
                f"persisted feature_version {payload.get('feature_version')!r} != {FEATURE_VERSION!r}"
            )
        index = cls(
            max_df_frac=float(payload["max_df_frac"]),
            min_df_cutoff=int(payload["min_df_cutoff"]),
            query_budget=int(payload.get("query_budget", QUERY_BUDGET)),
            scale_floor=int(payload.get("scale_floor", SCALE_FLOOR)),
            small_corpus_max_df_frac=float(payload.get("small_corpus_max_df_frac", SMALL_CORPUS_MAX_DF_FRAC)),
        )
        index.build(ThoughtGraph.from_dict(raw) for raw in payload["graphs"].values())
        if payload.get("corpus_snapshot") != index.corpus_snapshot:
            raise ValueError("persisted corpus_snapshot does not match rebuilt index")
        if sorted(payload.get("thought_ids") or []) != sorted(index._graphs):
            raise ValueError("persisted thought_ids do not match rebuilt index")
        return index
