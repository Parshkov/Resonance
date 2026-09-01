"""Dependency-inversion ports for Resonance R2-R5 implementations."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Protocol, runtime_checkable

from src.graph import ThoughtGraph

from .types import CandidateResult, ExtractionResult, ResonanceHit, SeedCorrespondence, VerifierResult


@runtime_checkable
class GraphValidator(Protocol):
    def validate(self, graph: ThoughtGraph) -> None: ...


@runtime_checkable
class Extractor(Protocol):
    def extract(self, context: str, *, source_id: str | None = None) -> ExtractionResult: ...


@runtime_checkable
class ThoughtStore(Protocol):
    def put(self, graph: ThoughtGraph) -> None: ...
    def get(self, thought_id: str) -> ThoughtGraph | None: ...
    def contains(self, thought_id: str) -> bool: ...


@runtime_checkable
class CandidateIndex(Protocol):
    """Graph-level candidate retrieval only; never node-pair semantic pruning."""

    def upsert(self, graph: ThoughtGraph) -> None: ...
    def remove(self, thought_id: str) -> None: ...
    def query(
        self,
        graph: ThoughtGraph,
        *,
        mode: str,
        k: int,
    ) -> Sequence[CandidateResult]: ...


@runtime_checkable
class StructuralVerifier(Protocol):
    def verify(
        self,
        query: ThoughtGraph,
        candidate: ThoughtGraph,
        *,
        seeds: Sequence[SeedCorrespondence] = (),
    ) -> VerifierResult: ...


@runtime_checkable
class EngineFacade(Protocol):
    """Pure-Python facade intended to be the only future transport boundary."""

    def ingest(self, context: str, *, source_id: str | None = None) -> ThoughtGraph: ...
    def index(self, graph: ThoughtGraph) -> None: ...
    def find(self, graph: ThoughtGraph, *, mode: str, k: int = 20) -> Sequence[ResonanceHit]: ...
    def compare(self, a: ThoughtGraph, b: ThoughtGraph, *, mode: str) -> VerifierResult: ...
    def explain(self, a_id: str, b_id: str) -> VerifierResult | None: ...
    def get(self, thought_id: str) -> ThoughtGraph | None: ...


class ConfigSource(Protocol):
    """Minimal immutable config/version lookup used by components and reports."""

    def snapshot(self) -> Mapping[str, str]: ...
