"""Input, CSRF, rate, UGC and aggregate privacy guards."""

from __future__ import annotations

import hashlib
import hmac
import html
import json
import time
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from .models import CsrfRejected, PayloadRejected, RateLimitExceeded, UntrustedContent


@dataclass
class DeterministicRateLimiter:
    capacity: int = 10
    refill_per_second: float = 1.0
    clock: Any = time.monotonic
    _state: dict[tuple[str, str], tuple[float, float]] = field(default_factory=dict)

    def check(self, subject: str, action: str) -> None:
        if self.capacity <= 0 or self.refill_per_second < 0:
            raise ValueError("invalid rate limiter configuration")
        key = (subject, action)
        now = float(self.clock())
        tokens, last = self._state.get(key, (float(self.capacity), now))
        tokens = min(float(self.capacity), tokens + max(0.0, now - last) * self.refill_per_second)
        if tokens < 1.0:
            raise RateLimitExceeded("rate limit exceeded")
        self._state[key] = (tokens - 1.0, now)


@dataclass(frozen=True, slots=True)
class CsrfGuard:
    allowed_origins: frozenset[str]

    @staticmethod
    def token_digest(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def validate(
        self,
        *,
        cookie_authenticated: bool,
        origin: str | None,
        csrf_token: str | None,
        expected_csrf_digest: str | None,
    ) -> None:
        if not cookie_authenticated:
            return
        if not origin or origin not in self.allowed_origins:
            raise CsrfRejected("cross-origin mutation rejected")
        if not csrf_token or not expected_csrf_digest:
            raise CsrfRejected("missing CSRF proof")
        actual = self.token_digest(csrf_token)
        if not hmac.compare_digest(actual, expected_csrf_digest):
            raise CsrfRejected("invalid CSRF proof")


@dataclass(frozen=True, slots=True)
class PayloadBounds:
    max_json_bytes: int = 128_000
    max_nodes: int = 512
    max_edges: int = 2048
    max_depth: int = 32
    max_text_chars: int = 20_000

    def validate_json(self, value: Any) -> None:
        try:
            encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        except (TypeError, ValueError) as exc:
            raise PayloadRejected("payload is not valid JSON data") from exc
        if len(encoded) > self.max_json_bytes:
            raise PayloadRejected("payload exceeds request-size bound")
        depth = _max_depth(value)
        if depth > self.max_depth:
            raise PayloadRejected("payload exceeds nesting-depth bound")

    def validate_thought_dna(self, value: Mapping[str, Any]) -> None:
        self.validate_json(value)
        nodes = value.get("nodes", [])
        # The accepted Thought DNA schema uses `relations`. Keep `edges` as a
        # forward/backward-compatible alias, but never let an attacker bypass
        # the relation-count bound by choosing the canonical field name.
        relations = value.get("relations", value.get("edges", []))
        if not isinstance(nodes, Sequence) or isinstance(nodes, (str, bytes)):
            raise PayloadRejected("nodes must be an array")
        if not isinstance(relations, Sequence) or isinstance(relations, (str, bytes)):
            raise PayloadRejected("relations must be an array")
        if len(nodes) > self.max_nodes:
            raise PayloadRejected("Thought DNA node bound exceeded")
        if len(relations) > self.max_edges:
            raise PayloadRejected("Thought DNA relation bound exceeded")

    def untrusted_text(self, text: str) -> UntrustedContent:
        if not isinstance(text, str):
            raise PayloadRejected("UGC must be text")
        if len(text) > self.max_text_chars:
            raise PayloadRejected("UGC exceeds text-size bound")
        return UntrustedContent(text=text, rendered_text=html.escape(text, quote=True))


def _max_depth(value: Any, depth: int = 0) -> int:
    if isinstance(value, Mapping):
        if not value:
            return depth + 1
        return max(_max_depth(item, depth + 1) for item in value.values())
    if isinstance(value, (list, tuple)):
        if not value:
            return depth + 1
        return max(_max_depth(item, depth + 1) for item in value)
    return depth + 1


def suppress_small_buckets(counts: Mapping[str, int], *, minimum: int = 3) -> dict[str, int]:
    if minimum < 2:
        raise ValueError("minimum must be >= 2 for anti-inference")
    return {
        str(bucket): int(count)
        for bucket, count in counts.items()
        if int(count) >= minimum
    }


def safe_log_metadata(fields: Mapping[str, Any]) -> dict[str, Any]:
    """Allowlist operational metadata; silently omit private payload classes."""
    allowed = {
        "correlation_id",
        "subject",
        "client_id",
        "auth_session_id",
        "protocol_session_id",
        "action",
        "resource_kind",
        "resource_id",
        "grant_version",
        "decision",
        "reason",
        "actor_type",
        "status",
        "latency_ms",
    }
    return {key: fields[key] for key in allowed if key in fields}


@dataclass(frozen=True, slots=True)
class HostedTransportGuard:
    """Transport-neutral hosted-origin policy.

    HTTP adapters use this before dispatch.  It intentionally returns policy
    decisions rather than owning a specific web framework's CORS/CSP syntax.
    """

    allowed_origins: frozenset[str]
    tools_origins: frozenset[str]

    def __post_init__(self) -> None:
        if "*" in self.allowed_origins or "*" in self.tools_origins:
            raise ValueError("wildcard origins are forbidden for credentialed hosted surfaces")
        if not self.tools_origins.issubset(self.allowed_origins):
            raise ValueError("tools origins must be a subset of allowed origins")

    def validate_request(self, *, scheme: str, origin: str | None, credentialed: bool) -> None:
        if scheme.lower() != "https":
            raise PayloadRejected("hosted protected endpoint requires HTTPS")
        if credentialed and (not origin or origin not in self.allowed_origins):
            raise PayloadRejected("credentialed cross-origin request rejected")

    def cors_origin(self, origin: str | None) -> str | None:
        return origin if origin in self.allowed_origins else None

    def tools_origin_allowed(self, origin: str | None) -> bool:
        return bool(origin and origin in self.tools_origins)

    @staticmethod
    def validate_query_keys(query: Mapping[str, Any]) -> None:
        forbidden = {"token", "access_token", "authorization", "password", "secret", "api_key"}
        lowered = {str(key).lower() for key in query}
        overlap = forbidden.intersection(lowered)
        if overlap:
            raise PayloadRejected("credentials/secrets are forbidden in URLs")


def validate_coarse_location(location: Mapping[str, Any]) -> None:
    forbidden = {
        "address",
        "street",
        "postal_code",
        "zip",
        "gps",
        "latitude",
        "longitude",
        "lat",
        "lon",
        "exact_lat",
        "exact_lon",
    }
    overlap = forbidden.intersection({str(key).lower() for key in location})
    if overlap:
        raise PayloadRejected("exact location fields are not allowed")
    precision = str(location.get("precision", "coarse")).lower()
    if precision not in {"coarse", "city", "region", "country"}:
        raise PayloadRejected("location precision is too exact for the pilot")
