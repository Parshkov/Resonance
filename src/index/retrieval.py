"""Deterministic inverted candidate index with observable channel evidence."""

from __future__ import annotations

import hashlib
import json
import math
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Iterable, Mapping, Sequence

from src.fingerprint import FingerprintConfig, LandmarkFingerprint, content_tokens, structural_fingerprints
from src.graph import ThoughtGraph, canonical_json
from src.interfaces import CandidateResult, ConfigRef, SeedCorrespondence, require_mode

INDEX_FORMAT_VERSION = "resonance-candidate-index/0.1"
_CHANNELS = ("structural", "content", "knowledge_about", "knowledge_complement")


def _stable_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256(value: object) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _freeze_float_map(value: Mapping[str, float]) -> Mapping[str, float]:
    return MappingProxyType({str(key): float(item) for key, item in value.items()})


def _freeze_int_map(value: Mapping[str, int]) -> Mapping[str, int]:
    return MappingProxyType({str(key): int(item) for key, item in value.items()})


@dataclass(frozen=True, slots=True)
class IndexConfig:
    fingerprint: FingerprintConfig = field(default_factory=FingerprintConfig)
    enabled_channels: tuple[str, ...] = _CHANNELS
    # Keep only truly corpus-global motifs dead by default. Benchmark v0.1
    # intentionally repeats the same ten-edge structure across most documents;
    # a conventional 1--5% stop-DF rule deletes every query feature there.
    max_df_ratio: float = 0.95
    max_df_floor: int = 32
    content_query_budget: int = 64
    knowledge_query_budget: int = 64
    include_source_text_content: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.enabled_channels, tuple) or not all(
            isinstance(channel, str) for channel in self.enabled_channels
        ):
            raise ValueError("enabled_channels must be a tuple of strings")
        if not self.enabled_channels or len(set(self.enabled_channels)) != len(self.enabled_channels):
            raise ValueError("enabled_channels must be a non-empty unique tuple")
        if any(channel not in _CHANNELS for channel in self.enabled_channels):
            raise ValueError(f"enabled_channels must contain only {_CHANNELS}")
        if isinstance(self.max_df_ratio, bool) or not isinstance(self.max_df_ratio, (int, float)):
            raise ValueError("max_df_ratio must be a finite number in (0,1]")
        if not math.isfinite(float(self.max_df_ratio)) or not 0.0 < float(self.max_df_ratio) <= 1.0:
            raise ValueError("max_df_ratio must be a finite number in (0,1]")
        if isinstance(self.max_df_floor, bool) or not isinstance(self.max_df_floor, int) or self.max_df_floor < 1:
            raise ValueError("max_df_floor must be an integer >= 1")
        for name, value in (
            ("content_query_budget", self.content_query_budget),
            ("knowledge_query_budget", self.knowledge_query_budget),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(f"{name} must be an integer >= 1")
        if not isinstance(self.include_source_text_content, bool):
            raise ValueError("include_source_text_content must be boolean")

    def to_dict(self) -> dict[str, object]:
        return {
            "fingerprint": self.fingerprint.to_dict(),
            "enabled_channels": list(self.enabled_channels),
            "max_df_ratio": float(self.max_df_ratio),
            "max_df_floor": self.max_df_floor,
            "content_query_budget": self.content_query_budget,
            "knowledge_query_budget": self.knowledge_query_budget,
            "include_source_text_content": self.include_source_text_content,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> "IndexConfig":
        expected = {
            "fingerprint",
            "enabled_channels",
            "max_df_ratio",
            "max_df_floor",
            "content_query_budget",
            "knowledge_query_budget",
            "include_source_text_content",
        }
        if set(value) != expected:
            raise ValueError(f"index config fields must be exactly {sorted(expected)}")
        fingerprint = value["fingerprint"]
        channels = value["enabled_channels"]
        if not isinstance(fingerprint, dict):
            raise ValueError("index fingerprint config must be an object")
        if not isinstance(channels, list) or not all(isinstance(item, str) for item in channels):
            raise ValueError("enabled_channels must be a list of strings")
        return cls(
            fingerprint=FingerprintConfig.from_dict(fingerprint),
            enabled_channels=tuple(channels),
            max_df_ratio=value["max_df_ratio"],  # type: ignore[arg-type]
            max_df_floor=value["max_df_floor"],  # type: ignore[arg-type]
            content_query_budget=value["content_query_budget"],  # type: ignore[arg-type]
            knowledge_query_budget=value["knowledge_query_budget"],  # type: ignore[arg-type]
            include_source_text_content=value["include_source_text_content"],  # type: ignore[arg-type]
        )

    @property
    def config_hash(self) -> str:
        return _sha256({"format": INDEX_FORMAT_VERSION, **self.to_dict()})


@dataclass(frozen=True, slots=True)
class _StructuralPosting:
    thought_id: str
    endpoint_a: str
    endpoint_b: str
    feature_version: str


@dataclass(frozen=True, slots=True)
class _KnowledgePosting:
    thought_id: str
    node_id: str
    confidence: float


@dataclass(frozen=True, slots=True)
class QueryDiagnostics:
    query_id: str
    mode: str
    corpus_size: int
    query_budget: int
    generated_structural_features: int
    selected_structural_features: int
    skipped_common_structural_features: int
    skipped_evidence_fraction: float
    postings_touched_by_channel: Mapping[str, int]
    latency_ms_by_channel: Mapping[str, float]
    candidate_count_by_channel: Mapping[str, int]
    total_latency_ms: float
    max_posting_length: int
    index_bytes_estimate: int
    replay_sha256: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "postings_touched_by_channel", _freeze_int_map(self.postings_touched_by_channel))
        object.__setattr__(self, "latency_ms_by_channel", _freeze_float_map(self.latency_ms_by_channel))
        object.__setattr__(self, "candidate_count_by_channel", _freeze_int_map(self.candidate_count_by_channel))


@dataclass(frozen=True, slots=True)
class QueryOutcome:
    results: tuple[CandidateResult, ...]
    diagnostics: QueryDiagnostics


@dataclass(frozen=True, slots=True)
class IndexStats:
    corpus_size: int
    structural_keys: int
    structural_postings: int
    content_keys: int
    content_postings: int
    knowledge_about_keys: int
    max_posting_length: int
    index_bytes_estimate: int
    corpus_snapshot: str
    index_version: str
    feature_version: str
    config_hash: str


@dataclass(slots=True)
class _ChannelEvidence:
    scores: dict[str, float] = field(default_factory=dict)
    seeds: dict[str, tuple[SeedCorrespondence, ...]] = field(default_factory=dict)
    usable_query_evidence: float = 0.0
    postings_touched: int = 0


class CandidateRetrievalIndex:
    """In-memory derived index implementing the accepted CandidateIndex port.

    Public upsert is incremental. Corpus snapshot hashing is lazy, so inserting
    N graphs does not rebuild all prior features or re-hash the full corpus N
    times.
    """

    def __init__(self, config: IndexConfig | None = None) -> None:
        self.config = config or IndexConfig()
        self._graphs: dict[str, ThoughtGraph] = {}
        self._graph_digests: dict[str, str] = {}
        self._features_by_thought: dict[str, tuple[LandmarkFingerprint, ...]] = {}
        self._tokens_by_thought: dict[str, Counter[str]] = {}
        self._about_by_thought: dict[str, tuple[tuple[str, str, float], ...]] = {}
        self._structural_postings: dict[str, list[_StructuralPosting]] = defaultdict(list)
        self._structural_df: Counter[str] = Counter()
        self._content_postings: dict[str, dict[str, int]] = defaultdict(dict)
        self._about_postings: dict[str, list[_KnowledgePosting]] = defaultdict(list)
        self._snapshot_cache: str | None = None
        self._last_query: QueryDiagnostics | None = None
        self._upsert_seconds = 0.0
        self._upsert_count = 0

    @property
    def feature_version(self) -> str:
        return self.config.fingerprint.feature_version

    @property
    def index_version(self) -> str:
        return f"{INDEX_FORMAT_VERSION}+{self.config.config_hash[:16]}"

    @property
    def config_ref(self) -> ConfigRef:
        return ConfigRef(
            component="candidate-index",
            component_version=INDEX_FORMAT_VERSION,
            config_hash=self.config.config_hash,
        )

    @property
    def last_query_diagnostics(self) -> QueryDiagnostics | None:
        return self._last_query

    @property
    def corpus_snapshot(self) -> str:
        if self._snapshot_cache is None:
            self._snapshot_cache = _sha256(
                {
                    "config_hash": self.config.config_hash,
                    "graphs": sorted(self._graph_digests.items()),
                }
            )
        return self._snapshot_cache

    def upsert(self, graph: ThoughtGraph) -> None:
        started = time.perf_counter()
        graph.validate()
        if graph.thought_id in self._graphs:
            self.remove(graph.thought_id)

        features = (
            structural_fingerprints(graph, self.config.fingerprint)
            if "structural" in self.config.enabled_channels
            else ()
        )
        tokens = (
            Counter(content_tokens(graph, include_source_text=self.config.include_source_text_content))
            if "content" in self.config.enabled_channels
            else Counter()
        )
        about: list[tuple[str, str, float]] = []
        if {"knowledge_about", "knowledge_complement"} & set(self.config.enabled_channels):
            for node in graph.nodes:
                if node.knowledge is None:
                    continue
                for reference in node.knowledge.about:
                    about.append((reference.id, node.id, reference.conf))

        self._graphs[graph.thought_id] = graph
        self._graph_digests[graph.thought_id] = hashlib.sha256(
            canonical_json(graph.to_dict()).encode("utf-8")
        ).hexdigest()
        self._features_by_thought[graph.thought_id] = features
        self._tokens_by_thought[graph.thought_id] = tokens
        self._about_by_thought[graph.thought_id] = tuple(sorted(about))

        for feature in features:
            self._structural_postings[feature.key].append(
                _StructuralPosting(
                    graph.thought_id,
                    feature.endpoint_a,
                    feature.endpoint_b,
                    self.feature_version,
                )
            )
        self._structural_df.update({feature.key for feature in features})
        for token, count in tokens.items():
            self._content_postings[token][graph.thought_id] = count
        for concept_id, node_id, confidence in about:
            self._about_postings[concept_id].append(
                _KnowledgePosting(graph.thought_id, node_id, confidence)
            )

        self._snapshot_cache = None
        self._upsert_count += 1
        self._upsert_seconds += time.perf_counter() - started

    def extend(self, graphs: Iterable[ThoughtGraph]) -> None:
        for graph in graphs:
            self.upsert(graph)

    def remove(self, thought_id: str) -> None:
        if thought_id not in self._graphs:
            return
        features = self._features_by_thought.pop(thought_id)
        feature_keys = {feature.key for feature in features}
        for key in feature_keys:
            self._structural_df[key] -= 1
            if self._structural_df[key] <= 0:
                del self._structural_df[key]
        for key in feature_keys:
            posts = self._structural_postings[key]
            self._structural_postings[key] = [
                post for post in posts if post.thought_id != thought_id
            ]
            if not self._structural_postings[key]:
                del self._structural_postings[key]
        for token in self._tokens_by_thought.pop(thought_id):
            self._content_postings[token].pop(thought_id, None)
            if not self._content_postings[token]:
                del self._content_postings[token]
        concept_ids = {concept_id for concept_id, _, _ in self._about_by_thought.pop(thought_id)}
        for concept_id in concept_ids:
            self._about_postings[concept_id] = [
                post for post in self._about_postings[concept_id] if post.thought_id != thought_id
            ]
            if not self._about_postings[concept_id]:
                del self._about_postings[concept_id]
        del self._graphs[thought_id]
        del self._graph_digests[thought_id]
        self._snapshot_cache = None

    def query(self, graph: ThoughtGraph, *, mode: str, k: int) -> Sequence[CandidateResult]:
        return self.query_with_diagnostics(graph, mode=mode, k=k).results

    def query_with_diagnostics(self, graph: ThoughtGraph, *, mode: str, k: int) -> QueryOutcome:
        require_mode(mode)
        if isinstance(k, bool) or not isinstance(k, int) or k < 1:
            raise ValueError("k must be an integer >= 1")
        graph.validate()
        query_started = time.perf_counter()
        evidence: dict[str, _ChannelEvidence] = {}
        latencies: dict[str, float] = {}

        generated = 0
        selected = 0
        skipped_common = 0
        if "structural" in self.config.enabled_channels:
            started = time.perf_counter()
            structural, generated, selected, skipped_common = self._query_structural(graph)
            evidence["structural"] = structural
            latencies["structural"] = (time.perf_counter() - started) * 1000.0
        if "content" in self.config.enabled_channels:
            started = time.perf_counter()
            evidence["content"] = self._query_content(graph)
            latencies["content"] = (time.perf_counter() - started) * 1000.0
        if "knowledge_about" in self.config.enabled_channels:
            started = time.perf_counter()
            evidence["knowledge_about"] = self._query_knowledge(graph, complementary=False)
            latencies["knowledge_about"] = (time.perf_counter() - started) * 1000.0
        if "knowledge_complement" in self.config.enabled_channels and mode == "complementary":
            started = time.perf_counter()
            evidence["knowledge_complement"] = self._query_knowledge(graph, complementary=True)
            latencies["knowledge_complement"] = (time.perf_counter() - started) * 1000.0

        ranked_by_channel: dict[str, list[tuple[str, float]]] = {}
        ranks_by_channel: dict[str, dict[str, int]] = {}
        for channel, channel_evidence in evidence.items():
            ranked = sorted(channel_evidence.scores.items(), key=lambda item: (-item[1], item[0]))
            ranked_by_channel[channel] = ranked
            ranks_by_channel[channel] = {thought_id: rank for rank, (thought_id, _) in enumerate(ranked, 1)}

        candidate_ids = set().union(*(item.scores for item in evidence.values())) if evidence else set()
        priority = {channel: offset for offset, channel in enumerate(_CHANNELS)}

        def union_key(thought_id: str) -> tuple[object, ...]:
            available = [
                (ranks_by_channel[channel][thought_id], priority[channel])
                for channel in ranks_by_channel
                if thought_id in ranks_by_channel[channel]
            ]
            best_rank, best_channel = min(available)
            best_score = max(
                channel.scores.get(thought_id, 0.0) for channel in evidence.values()
            )
            return (best_rank, best_channel, -best_score, thought_id)

        ordered_ids = sorted(candidate_ids, key=union_key)
        usable = sum(channel.usable_query_evidence for channel in evidence.values())
        results: list[CandidateResult] = []
        for thought_id in ordered_ids[:k]:
            scores = {channel: evidence.get(channel, _ChannelEvidence()).scores.get(thought_id, 0.0) for channel in _CHANNELS}
            ranks = {
                channel: channel_ranks[thought_id]
                for channel, channel_ranks in ranks_by_channel.items()
                if thought_id in channel_ranks
            }
            seeds = tuple(
                sorted(
                    {
                        seed
                        for channel in evidence.values()
                        for seed in channel.seeds.get(thought_id, ())
                    },
                    key=lambda seed: (-seed.support, seed.channel, seed.query_node, seed.candidate_node),
                )
            )
            results.append(
                CandidateResult(
                    candidate_id=thought_id,
                    channel_scores=scores,
                    channel_ranks=ranks,
                    seed_correspondences=seeds,
                    usable_query_evidence=usable,
                    requires_structural_verification=True,
                    polarity_reliable=False,
                    index_version=self.index_version,
                    feature_version=self.feature_version,
                    corpus_snapshot=self.corpus_snapshot,
                    config=self.config_ref,
                )
            )

        replay_payload = [
            {
                "candidate_id": result.candidate_id,
                "channel_scores": dict(result.channel_scores),
                "channel_ranks": dict(result.channel_ranks),
                "seeds": [
                    [seed.query_node, seed.candidate_node, seed.support, seed.channel]
                    for seed in result.seed_correspondences
                ],
                "usable_query_evidence": result.usable_query_evidence,
                "index_version": result.index_version,
                "feature_version": result.feature_version,
                "corpus_snapshot": result.corpus_snapshot,
            }
            for result in results
        ]
        stats = self.stats()
        generated_for_fraction = max(generated, 1)
        diagnostics = QueryDiagnostics(
            query_id=graph.thought_id,
            mode=mode,
            corpus_size=len(self._graphs),
            query_budget=self.config.fingerprint.query_budget,
            generated_structural_features=generated,
            selected_structural_features=selected,
            skipped_common_structural_features=skipped_common,
            skipped_evidence_fraction=max(0.0, 1.0 - selected / generated_for_fraction),
            postings_touched_by_channel={
                channel: evidence.get(channel, _ChannelEvidence()).postings_touched
                for channel in _CHANNELS
            },
            latency_ms_by_channel={channel: latencies.get(channel, 0.0) for channel in _CHANNELS},
            candidate_count_by_channel={
                channel: len(evidence.get(channel, _ChannelEvidence()).scores)
                for channel in _CHANNELS
            },
            total_latency_ms=(time.perf_counter() - query_started) * 1000.0,
            max_posting_length=stats.max_posting_length,
            index_bytes_estimate=stats.index_bytes_estimate,
            replay_sha256=_sha256(replay_payload),
        )
        self._last_query = diagnostics
        return QueryOutcome(tuple(results), diagnostics)

    def _df_cutoff(self) -> int:
        return max(self.config.max_df_floor, math.ceil(self.config.max_df_ratio * max(len(self._graphs), 1)))

    def _idf(self, df: int) -> float:
        return math.log((len(self._graphs) + 1) / (df + 1)) + 1.0

    def _select_structural(
        self, features: tuple[LandmarkFingerprint, ...]
    ) -> tuple[tuple[LandmarkFingerprint, ...], int]:
        cutoff = self._df_cutoff()
        common = sum(
            1
            for feature in features
            if feature.key in self._structural_df and self._structural_df[feature.key] > cutoff
        )
        active = [
            feature
            for feature in features
            if feature.key in self._structural_df and self._structural_df[feature.key] <= cutoff
        ]
        sort_key = lambda item: (
            -self._idf(self._structural_df[item.key]),
            -item.distance,
            item.key,
            item.endpoint_a,
            item.endpoint_b,
        )
        budget = self.config.fingerprint.query_budget
        scales = self.config.fingerprint.scales
        base_quota = budget // len(scales)
        selected: list[LandmarkFingerprint] = []
        selected_identity: set[tuple[str, str, str]] = set()
        for scale in scales:
            options = sorted((feature for feature in active if feature.scale == scale), key=sort_key)
            for feature in options[:base_quota]:
                selected.append(feature)
                selected_identity.add((feature.key, feature.endpoint_a, feature.endpoint_b))
        remaining = sorted(
            (
                feature
                for feature in active
                if (feature.key, feature.endpoint_a, feature.endpoint_b) not in selected_identity
            ),
            key=sort_key,
        )
        selected.extend(remaining[: max(0, budget - len(selected))])
        return tuple(selected[:budget]), common

    def _query_structural(
        self, graph: ThoughtGraph
    ) -> tuple[_ChannelEvidence, int, int, int]:
        all_features = structural_fingerprints(graph, self.config.fingerprint)
        selected, skipped_common = self._select_structural(all_features)
        pair_support: dict[str, dict[tuple[str, str], float]] = defaultdict(lambda: defaultdict(float))
        contributions: dict[str, list[tuple[float, str, str, str, str]]] = defaultdict(list)
        usable = 0.0
        touched = 0
        for feature in selected:
            weight = self._idf(self._structural_df[feature.key])
            usable += weight
            postings = self._structural_postings[feature.key]
            touched += len(postings)
            for posting in postings:
                if posting.thought_id == graph.thought_id:
                    continue
                if posting.feature_version != self.feature_version:
                    raise ValueError("posting feature version does not match active feature version")
                pair_support[posting.thought_id][(feature.endpoint_a, posting.endpoint_a)] += weight
                pair_support[posting.thought_id][(feature.endpoint_b, posting.endpoint_b)] += weight
                contributions[posting.thought_id].append(
                    (
                        weight,
                        feature.endpoint_a,
                        feature.endpoint_b,
                        posting.endpoint_a,
                        posting.endpoint_b,
                    )
                )

        evidence = _ChannelEvidence(usable_query_evidence=usable, postings_touched=touched)
        for thought_id, support in pair_support.items():
            used_query: set[str] = set()
            used_candidate: set[str] = set()
            mapping: dict[str, str] = {}
            chosen: list[tuple[str, str, float]] = []
            for (query_node, candidate_node), weight in sorted(
                support.items(), key=lambda item: (-item[1], item[0][0], item[0][1])
            ):
                if query_node in used_query or candidate_node in used_candidate:
                    continue
                mapping[query_node] = candidate_node
                used_query.add(query_node)
                used_candidate.add(candidate_node)
                chosen.append((query_node, candidate_node, weight))
            coherent = sum(
                weight
                for weight, query_a, query_b, candidate_a, candidate_b in contributions[thought_id]
                if mapping.get(query_a) == candidate_a and mapping.get(query_b) == candidate_b
            )
            score = coherent / usable if usable else 0.0
            if score <= 0.0:
                continue
            evidence.scores[thought_id] = min(score, 1.0)
            denom = max(2.0 * usable, 1e-12)
            evidence.seeds[thought_id] = tuple(
                SeedCorrespondence(
                    query_node=query_node,
                    candidate_node=candidate_node,
                    support=min(weight / denom, 1.0),
                    channel="structural",
                )
                for query_node, candidate_node, weight in chosen
            )
        return evidence, len(all_features), len(selected), skipped_common

    def _query_content(self, graph: ThoughtGraph) -> _ChannelEvidence:
        query_counts = Counter(
            content_tokens(graph, include_source_text=self.config.include_source_text_content)
        )
        weighted_tokens = []
        for token, query_tf in query_counts.items():
            postings = self._content_postings.get(token)
            if not postings:
                continue
            weighted_tokens.append((self._idf(len(postings)), token, query_tf))
        weighted_tokens.sort(key=lambda item: (-item[0], item[1]))
        selected = weighted_tokens[: self.config.content_query_budget]
        usable = sum(weight * query_tf for weight, _, query_tf in selected)
        raw: dict[str, float] = defaultdict(float)
        touched = 0
        for weight, token, query_tf in selected:
            postings = self._content_postings[token]
            touched += len(postings)
            for thought_id, candidate_tf in postings.items():
                if thought_id == graph.thought_id:
                    continue
                raw[thought_id] += weight * min(query_tf, candidate_tf)
        return _ChannelEvidence(
            scores={thought_id: value / usable for thought_id, value in raw.items()} if usable else {},
            usable_query_evidence=usable,
            postings_touched=touched,
        )

    def _query_knowledge(self, graph: ThoughtGraph, *, complementary: bool) -> _ChannelEvidence:
        query_refs: list[tuple[str, str, float]] = []
        for node in graph.nodes:
            if node.knowledge is None:
                continue
            refs = node.knowledge.requires if complementary else node.knowledge.about
            for reference in refs:
                query_refs.append((reference.id, node.id, reference.conf))
        query_refs.sort(key=lambda item: (item[0], item[1], -item[2]))
        query_refs = query_refs[: self.config.knowledge_query_budget]
        usable = sum(confidence for _, _, confidence in query_refs)
        raw: dict[str, float] = defaultdict(float)
        pair_support: dict[str, dict[tuple[str, str], float]] = defaultdict(lambda: defaultdict(float))
        touched = 0
        for concept_id, query_node, query_confidence in query_refs:
            postings = self._about_postings.get(concept_id, ())
            touched += len(postings)
            for posting in postings:
                if posting.thought_id == graph.thought_id:
                    continue
                support = min(query_confidence, posting.confidence)
                raw[posting.thought_id] += support
                pair_support[posting.thought_id][(query_node, posting.node_id)] += support
        channel = "knowledge_complement" if complementary else "knowledge_about"
        evidence = _ChannelEvidence(
            scores={thought_id: min(value / usable, 1.0) for thought_id, value in raw.items()} if usable else {},
            usable_query_evidence=usable,
            postings_touched=touched,
        )
        for thought_id, pairs in pair_support.items():
            used_query: set[str] = set()
            used_candidate: set[str] = set()
            seeds: list[SeedCorrespondence] = []
            for (query_node, candidate_node), support in sorted(
                pairs.items(), key=lambda item: (-item[1], item[0][0], item[0][1])
            ):
                if query_node in used_query or candidate_node in used_candidate:
                    continue
                used_query.add(query_node)
                used_candidate.add(candidate_node)
                seeds.append(
                    SeedCorrespondence(
                        query_node,
                        candidate_node,
                        min(support / max(usable, 1e-12), 1.0),
                        channel,
                    )
                )
            evidence.seeds[thought_id] = tuple(seeds)
        return evidence

    def stats(self) -> IndexStats:
        structural_lengths = [len(posts) for posts in self._structural_postings.values()]
        content_lengths = [len(posts) for posts in self._content_postings.values()]
        about_lengths = [len(posts) for posts in self._about_postings.values()]
        max_posting = max(structural_lengths + content_lengths + about_lengths + [0])
        structural_postings = sum(structural_lengths)
        content_postings = sum(content_lengths)
        about_postings = sum(about_lengths)
        # Stable implementation-independent estimate used for scale curves. It
        # is intentionally not presented as resident-set memory.
        bytes_estimate = (
            sum(len(key) for key in self._structural_postings)
            + structural_postings * 96
            + sum(len(key) for key in self._content_postings)
            + content_postings * 24
            + sum(len(key) for key in self._about_postings)
            + about_postings * 64
        )
        return IndexStats(
            corpus_size=len(self._graphs),
            structural_keys=len(self._structural_postings),
            structural_postings=structural_postings,
            content_keys=len(self._content_postings),
            content_postings=content_postings,
            knowledge_about_keys=len(self._about_postings),
            max_posting_length=max_posting,
            index_bytes_estimate=bytes_estimate,
            corpus_snapshot=self.corpus_snapshot,
            index_version=self.index_version,
            feature_version=self.feature_version,
            config_hash=self.config.config_hash,
        )

    def save(self, path: str | Path) -> None:
        target = Path(path)
        body = {
            "format_version": INDEX_FORMAT_VERSION,
            "index_version": self.index_version,
            "feature_version": self.feature_version,
            "config": self.config.to_dict(),
            "config_hash": self.config.config_hash,
            "corpus_snapshot": self.corpus_snapshot,
            "graphs": [self._graphs[key].to_dict() for key in sorted(self._graphs)],
        }
        payload = {**body, "integrity_sha256": _sha256(body)}
        temporary = target.with_name(target.name + ".tmp")
        temporary.write_text(_stable_json(payload) + "\n", encoding="utf-8")
        temporary.replace(target)

    @classmethod
    def load(
        cls,
        path: str | Path,
        *,
        expected_config: IndexConfig | None = None,
    ) -> "CandidateRetrievalIndex":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        expected_fields = {
            "format_version",
            "index_version",
            "feature_version",
            "config",
            "config_hash",
            "corpus_snapshot",
            "graphs",
            "integrity_sha256",
        }
        if not isinstance(payload, dict) or set(payload) != expected_fields:
            raise ValueError(f"persisted index fields must be exactly {sorted(expected_fields)}")
        integrity = payload.pop("integrity_sha256")
        if not isinstance(integrity, str) or integrity != _sha256(payload):
            raise ValueError("persisted index integrity hash mismatch")
        if payload["format_version"] != INDEX_FORMAT_VERSION:
            raise ValueError("persisted index format version is unsupported")
        if not isinstance(payload["config"], dict):
            raise ValueError("persisted index config must be an object")
        config = IndexConfig.from_dict(payload["config"])
        if payload["config_hash"] != config.config_hash:
            raise ValueError("persisted index config hash mismatch")
        if expected_config is not None and expected_config.config_hash != config.config_hash:
            raise ValueError("persisted index policy does not match expected config")
        index = cls(config)
        if payload["index_version"] != index.index_version:
            raise ValueError("persisted index version metadata mismatch")
        if payload["feature_version"] != index.feature_version:
            raise ValueError("persisted feature version metadata mismatch")
        graphs = payload["graphs"]
        if not isinstance(graphs, list):
            raise ValueError("persisted graphs must be an array")
        index.extend(ThoughtGraph.from_dict(graph) for graph in graphs)
        if payload["corpus_snapshot"] != index.corpus_snapshot:
            raise ValueError("persisted corpus snapshot mismatch")
        return index
