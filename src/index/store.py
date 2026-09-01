"""Inverted multi-channel CandidateIndex."""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence

from src.fingerprint.keys import FEATURE_VERSION, DescriptorVariant, fingerprints
from src.graph import ThoughtGraph, canonical_sha256
from src.interfaces import (
    CandidateResult,
    ConfigRef,
    SeedCorrespondence,
    require_mode,
)

INDEX_VERSION = "resonance-index/0.1"
TOKEN_RE = re.compile(r"[a-z0-9]+")


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _tokens(*texts: str) -> list[str]:
    out: list[str] = []
    for text in texts:
        out.extend(TOKEN_RE.findall(text.lower()))
    return out


class InvertedCandidateIndex:
    """Deterministic CandidateIndex. Default structural path is MULTI."""

    def __init__(self, *, max_df_frac: float = 0.005, min_df_cutoff: int = 5) -> None:
        self.max_df_frac = max_df_frac
        self.min_df_cutoff = min_df_cutoff
        self._graphs: dict[str, ThoughtGraph] = {}
        self._rebuild()

    def _rebuild(self) -> None:
        graphs = self._graphs
        n = max(len(graphs), 1)
        cutoff = max(self.min_df_cutoff, self.max_df_frac * n)
        structural: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
        structural_df: Counter[str] = Counter()
        content: dict[str, Counter[str]] = {}
        content_df: Counter[str] = Counter()
        about: dict[str, list[str]] = defaultdict(list)
        about_df: Counter[str] = Counter()
        requires: dict[str, set[str]] = defaultdict(set)
        for thought_id, graph in graphs.items():
            seen_keys: set[str] = set()
            for key, left, right in fingerprints(graph, "MULTI"):
                structural[key].append((thought_id, left, right))
                if key not in seen_keys:
                    structural_df[key] += 1
                    seen_keys.add(key)
            bag: Counter[str] = Counter()
            seen_terms: set[str] = set()
            for token in _tokens(graph.source.text, *(node.label for node in graph.nodes)):
                bag[token] += 1
                if token not in seen_terms:
                    content_df[token] += 1
                    seen_terms.add(token)
            content[thought_id] = bag
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
        self._content = content
        self._content_df = content_df
        self._content_idf = {term: math.log((n + 1) / (df + 1)) for term, df in content_df.items()}
        self._about = about
        self._about_df = about_df
        self._about_idf = {concept: math.log((n + 1) / (df + 1)) for concept, df in about_df.items()}
        self._requires = requires
        self._corpus_n = n
        snapshot = _sha(sorted((thought_id, canonical_sha256(graph.to_dict())) for thought_id, graph in graphs.items()))
        self.corpus_snapshot = snapshot
        self.config = ConfigRef(
            component="retrieval",
            component_version=INDEX_VERSION,
            config_hash=_sha(
                {
                    "index_version": INDEX_VERSION,
                    "feature_version": FEATURE_VERSION,
                    "max_df_frac": self.max_df_frac,
                    "min_df_cutoff": self.min_df_cutoff,
                    "default_variant": "MULTI",
                    "corpus_snapshot": snapshot,
                }
            ),
        )

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
    ) -> tuple[dict[str, float], dict[str, list[SeedCorrespondence]], float, int]:
        query_fps = fingerprints(graph, variant)
        support: dict[str, dict[tuple[str, str], float]] = defaultdict(lambda: defaultdict(float))
        contrib: dict[str, list[tuple[float, str, str, str, str]]] = defaultdict(list)
        touched = 0
        usable = 0.0
        seen_keys: set[str] = set()
        for key, qa, qb in query_fps:
            if key in self._structural_dead or key not in self._structural_idf:
                continue
            weight = self._structural_idf[key]
            if key not in seen_keys:
                usable += weight
                seen_keys.add(key)
            posts = self._structural[key]
            touched += len(posts)
            for thought_id, ca, cb in posts:
                if thought_id == graph.thought_id:
                    continue
                support[thought_id][(qa, ca)] += weight
                support[thought_id][(qb, cb)] += weight
                contrib[thought_id].append((weight, qa, qb, ca, cb))
        scores: dict[str, float] = {}
        seeds: dict[str, list[SeedCorrespondence]] = {}
        for thought_id, pair_weights in support.items():
            ordered = sorted(pair_weights.items(), key=lambda item: -item[1])
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
        return scores, seeds, usable, touched

    def _content_query(self, graph: ThoughtGraph) -> dict[str, float]:
        query_bag = Counter(_tokens(graph.source.text, *(node.label for node in graph.nodes)))
        scores: dict[str, float] = {}
        for thought_id, bag in self._content.items():
            if thought_id == graph.thought_id:
                continue
            score = 0.0
            for term, qf in query_bag.items():
                if term not in bag or term not in self._content_idf:
                    continue
                tf = bag[term]
                score += self._content_idf[term] * qf * (tf / (tf + 1.2))
            if score:
                scores[thought_id] = score
        return scores

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
        structural, seeds, usable, _touched = self._structural_query(graph, variant="MULTI")
        content = self._content_query(graph)
        knowledge_about, knowledge_comp = self._knowledge_query(graph)
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
        return results

    def query_ablation(
        self,
        graph: ThoughtGraph,
        *,
        variant: DescriptorVariant,
        k: int = 20,
    ) -> tuple[list[tuple[str, float]], int]:
        """Named D0/D1/MULTI control. Not the CandidateIndex shipping path."""
        scores, _seeds, _usable, touched = self._structural_query(graph, variant=variant)
        ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))[:k]
        return ranked, touched

    def dump(self, path: Path) -> None:
        payload = {
            "index_version": INDEX_VERSION,
            "feature_version": FEATURE_VERSION,
            "corpus_snapshot": self.corpus_snapshot,
            "thought_ids": sorted(self._graphs),
            "graphs": {thought_id: graph.to_dict() for thought_id, graph in self._graphs.items()},
        }
        path.write_bytes(_canonical_bytes(payload) + b"\n")

    @classmethod
    def load(cls, path: Path) -> "InvertedCandidateIndex":
        payload = json.loads(path.read_text(encoding="utf-8"))
        index = cls()
        for raw in payload["graphs"].values():
            index.upsert(ThoughtGraph.from_dict(raw))
        return index
