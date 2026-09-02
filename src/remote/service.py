"""Product service seam: the ONE place every transport converges.

stdio MCP, remote Streamable HTTP, (future) WebMCP and the human UI call
these methods with an authenticated subject; no transport carries business
or matching semantics of its own. Wraps the ACCEPTED discovery service and
engine facade -- accepted semantics untouched.

Authorization rules live here (not in transports): every call requires a
subject; per-subject rate limits; user-generated context is treated as
untrusted text (size-capped, never evaluated).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Mapping

from src.discovery.fixtures.r7_corpus import build
from src.discovery.service import DiscoveryService
from src.graph import ThoughtGraph

MAX_CONTEXT_CHARS = 20_000          # UGC guard: untrusted, size-capped
SERVICE_VERSION = "resonance-product-service/0.1"


class AuthorizationError(Exception):
    """Missing/invalid subject or exceeded quota; transports map this to
    their own 401/429 -- never to a silent degradation."""


@dataclass
class RateLimiter:
    """Deterministic token bucket per subject (clock injectable for tests)."""

    capacity: int = 30
    refill_per_second: float = 1.0
    clock: Any = time.monotonic
    _state: dict[str, tuple[float, float]] = field(default_factory=dict)

    def check(self, subject: str) -> None:
        now = self.clock()
        tokens, last = self._state.get(subject, (float(self.capacity), now))
        tokens = min(self.capacity, tokens + (now - last) * self.refill_per_second)
        if tokens < 1.0:
            raise AuthorizationError("rate limit exceeded for subject")
        self._state[subject] = (tokens - 1.0, now)


class ProductService:
    def __init__(self, discovery: DiscoveryService | None = None,
                 limiter: RateLimiter | None = None):
        if discovery is None:
            engine, registry, _ = build()
            discovery = DiscoveryService(engine, registry)
        self.discovery = discovery
        self.engine = discovery.engine
        self.limiter = limiter or RateLimiter()

    # -- every method takes an authenticated subject ------------------------
    def _require(self, subject: str | None) -> str:
        if not subject:
            raise AuthorizationError("authenticated subject required")
        self.limiter.check(subject)
        return subject

    def identity(self, subject: str | None) -> dict[str, Any]:
        self._require(subject)
        return {"service_version": SERVICE_VERSION,
                **self.discovery.provenance()}

    def ingest(self, subject: str | None, context: str,
               source_id: str | None = None) -> ThoughtGraph:
        self._require(subject)
        if not isinstance(context, str) or not context.strip():
            raise ValueError("context must be a non-empty string")
        if len(context) > MAX_CONTEXT_CHARS:
            raise ValueError("context exceeds the untrusted-input size cap")
        return self.engine.ingest(context, source_id=source_id)

    def discover(self, subject: str | None, thought: Mapping[str, Any] | ThoughtGraph,
                 *, mode: str, k: int = 8) -> dict[str, Any]:
        self._require(subject)
        graph = (thought if isinstance(thought, ThoughtGraph)
                 else ThoughtGraph.from_dict(dict(thought)))
        return self.discovery.discover(graph, mode=mode, k=k)

    def compare(self, subject: str | None, a: Mapping[str, Any],
                b: Mapping[str, Any], *, mode: str) -> Any:
        self._require(subject)
        return self.engine.compare(ThoughtGraph.from_dict(dict(a)),
                                   ThoughtGraph.from_dict(dict(b)), mode=mode)

    def get_thought(self, subject: str | None, thought_id: str) -> ThoughtGraph | None:
        self._require(subject)
        if not isinstance(thought_id, str) or len(thought_id) > 200:
            raise ValueError("invalid thought_id")
        return self.engine.get(thought_id)
