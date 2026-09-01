"""Shared lightweight records between alignment and scoring stages."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PathMatch:
    query_relation: str
    candidate_relations: tuple[str, ...]
    realizes_nodes: tuple[str, ...]
    support: float
