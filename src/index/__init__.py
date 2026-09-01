"""Multi-channel candidate generation. No verifier or MCP logic."""

from .store import INDEX_VERSION, QUERY_BUDGET, InvertedCandidateIndex, QueryDiagnostics

__all__ = ["INDEX_VERSION", "QUERY_BUDGET", "InvertedCandidateIndex", "QueryDiagnostics"]
