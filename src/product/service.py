"""Authenticated live-product service over the accepted R10-R12C layers.

Composition only: identity/consent decisions come from R12(+R12B), durable
state and fail-closed discovery from R11, private-first ingestion from R12C,
and the discovery DTO from the accepted R8 layer. This module adds exactly the
product-boundary concerns the #85 contract names:

* viewer-scoped authorization for discovery and evidence reads;
* per-viewer block filtering (blocks are viewer-relative and can never live in
  the shared index);
* presentation-only coarse-distance context and k-anonymous heat aggregation;
* result_id-bound evidence reads that fail closed when the durable corpus
  generation moves (the accepted R10 fidelity pattern);
* freshness/consistency exposure on every discovery response.

Rank, score, order, and classification are passed through byte-unchanged from
the accepted engine DTO; this layer may only redact or drop rows that current
consent/blocks forbid, never reorder or rescore them.
"""

from __future__ import annotations

import hashlib
import json
import math
import threading
from typing import Any, Mapping

from src.graph import ThoughtGraph
from src.identity import IdentityService
from src.identity.models import AuthorizationError
from src.ingestion import IdentityIngestionService
from src.security.guards import suppress_small_buckets

LIVE_PRODUCT_CONTRACT = "resonance-live-product/0.1"
LOCATION_NOTE = (
    "Location and distance are presentation-only and never influence matching, "
    "ranking, or scores. Missing location never lowers resonance."
)

NEAR_KM = 300.0
REGIONAL_KM = 1500.0
MAX_STORED_RESULTS = 64
EARTH_RADIUS_KM = 6371.0


class ProductError(ValueError):
    """Typed product-boundary error."""


class StaleResultError(ProductError):
    """Stored discovery result no longer matches the durable corpus generation."""


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def _distance_bucket(km: float) -> str:
    if km <= NEAR_KM:
        return "near"
    if km <= REGIONAL_KM:
        return "regional"
    return "far"


def _coords(location: Mapping[str, Any] | None) -> tuple[float, float] | None:
    if not location:
        return None
    lat, lon = location.get("lat"), location.get("lon")
    if isinstance(lat, (int, float)) and isinstance(lon, (int, float)) \
            and not isinstance(lat, bool) and not isinstance(lon, bool):
        return float(lat), float(lon)
    return None


class LiveProductService:
    """One authenticated boundary for manual UI, browser WebMCP, and remote MCP."""

    def __init__(
        self,
        identity: IdentityService,
        *,
        confirmation_secret: bytes | None = None,
        ingestion: IdentityIngestionService | None = None,
        aggregation_minimum: int = 3,
    ) -> None:
        if ingestion is None and not confirmation_secret:
            raise ValueError(
                "a stable confirmation_secret is required for durable draft recovery"
            )
        self.identity = identity
        self.backend = identity.backend
        self.live = self.backend.live_corpus
        self.ingestion = ingestion or IdentityIngestionService(
            identity, confirmation_secret=confirmation_secret
        )
        if aggregation_minimum < 2:
            raise ValueError("aggregation_minimum must be >= 2 for anti-inference")
        self.aggregation_minimum = aggregation_minimum
        self._lock = threading.RLock()
        self._results: dict[str, dict[str, Any]] = {}
        self._result_order: list[str] = []

    # ------------------------------------------------------------------
    # thin delegations: one boundary, accepted semantics untouched
    # ------------------------------------------------------------------
    def register(self, display_label: str, **kwargs: Any):
        return self.identity.register(display_label, **kwargs)

    def register_guest(self, **kwargs: Any):
        return self.identity.register_guest(**kwargs)

    def login(self, user_id: str, recovery_secret: str, **kwargs: Any):
        return self.identity.login(user_id, recovery_secret, **kwargs)

    def logout(self, access_token: str) -> None:
        self.identity.logout(access_token)

    def owned_sessions(self, access_token: str, **kwargs: Any) -> list[dict[str, Any]]:
        return self.identity.owned_sessions(access_token, **kwargs)

    def prepare_structured(self, access_token: str, candidate, **kwargs: Any):
        return self.ingestion.prepare_structured(access_token, candidate, **kwargs)

    def prepare_raw_text(self, access_token: str, context: str, **kwargs: Any):
        return self.ingestion.prepare_raw_text(access_token, context, **kwargs)

    def preview(self, access_token: str, draft_id: str, **kwargs: Any):
        return self.ingestion.preview(access_token, draft_id, **kwargs)

    def share_prepared(self, access_token: str, draft_id: str, **kwargs: Any):
        return self.ingestion.share_prepared(access_token, draft_id, **kwargs)

    def discard(self, access_token: str, draft_id: str, **kwargs: Any):
        return self.ingestion.discard(access_token, draft_id, **kwargs)

    def set_consent(self, access_token: str, session_id: str, choices, **kwargs: Any):
        return self.identity.set_consent(access_token, session_id, choices, **kwargs)

    def update_metadata(self, access_token: str, session_id: str, **kwargs: Any):
        return self.identity.update_metadata(access_token, session_id, **kwargs)

    def revoke_session(self, access_token: str, session_id: str, **kwargs: Any):
        return self.identity.revoke_thought_session(access_token, session_id, **kwargs)

    def delete_session(self, access_token: str, session_id: str, **kwargs: Any):
        return self.identity.delete_thought_session(access_token, session_id, **kwargs)

    # ------------------------------------------------------------------
    # freshness / mode
    # ------------------------------------------------------------------
    def freshness(self) -> dict[str, Any]:
        health = self.live.health()
        return {
            "db_generation": health.db_generation,
            "serving_generation": health.serving_generation,
            "index_current": health.index_current,
            "engine_snapshot": health.engine_snapshot,
        }

    def state(self, access_token: str | None = None) -> dict[str, Any]:
        health = self.live.health()
        owned = []
        if access_token:
            owned = [
                {
                    "session_id": row.get("session_id"),
                    "thought_id": row.get("thought_id"),
                    "record_kind": row.get("record_kind"),
                    "share_state": row.get("share_state"),
                    "version": row.get("version"),
                }
                for row in self.identity.owned_sessions(access_token)
            ]
        return {
            "contract_version": LIVE_PRODUCT_CONTRACT,
            "mode": "live",
            "mode_note": "DB-backed live product state; seed/replay demo is a separate, clearly labeled mode.",
            "freshness": self.freshness(),
            "health_ok": health.ok,
            "users": health.users,
            "sessions": health.sessions,
            "discoverable": health.discoverable,
            "owned_sessions": owned,
        }

    # ------------------------------------------------------------------
    # discovery
    # ------------------------------------------------------------------
    def discover(
        self,
        access_token: str,
        session_id: str,
        *,
        mode: str = "analogical",
        k: int = 8,
        client_id: str = "resonance-product",
        protocol_session_id: str | None = None,
    ) -> dict[str, Any]:
        """Run accepted structural discovery from a session the viewer owns.

        The engine result is passed through order/score-unchanged; this layer
        only removes rows current consent or viewer-relative blocks forbid and
        attaches presentation-only context.
        """
        actor = self.identity.authenticate(access_token)
        # Ownership + enumeration resistance through the accepted R12 seam.
        self.identity.consent_for(
            access_token, session_id,
            client_id=client_id, protocol_session_id=protocol_session_id,
        )
        session = self.backend.get_session(session_id)
        if session is None:
            raise AuthorizationError("session unavailable to authenticated subject")
        graph = ThoughtGraph.from_dict(dict(session.thought_dna))
        raw = self.live.discover(graph, mode=mode, k=k)

        # Distance context requires BOTH sides' coarse-location consent. The
        # query session may hold a privately stored location (R12C persists it
        # before any share), so the viewer's own current consent gates it too.
        viewer_consent = self.identity.policy_source.session_consent(session_id)
        viewer_coords = None
        if viewer_consent.get("share_coarse_location"):
            viewer_coords = _coords(dict(getattr(session, "location", {}) or {}))
        matches: list[dict[str, Any]] = []
        dropped_blocked = 0
        for row in raw["matches"]:
            projected = self._project_row(actor.user_id, row, viewer_coords)
            if projected is None:
                dropped_blocked += 1
                continue
            matches.append(projected)
        rejected: list[dict[str, Any]] = []
        for row in raw.get("rejected", []):
            projected = self._project_row(actor.user_id, row, viewer_coords,
                                          allow_hard_rejected=True)
            if projected is None:
                dropped_blocked += 1
                continue
            rejected.append(projected)

        freshness = self.freshness()
        payload = {
            "contract_version": LIVE_PRODUCT_CONTRACT,
            "source": "live",
            "discovery_contract": raw.get("contract_version"),
            "query": dict(raw.get("query", {})),
            "matches": matches,
            "rejected": rejected,
            "aggregation": self._aggregate(matches),
            "blocked_rows_removed": dropped_blocked,
            "location_note": LOCATION_NOTE,
            "freshness": freshness,
        }
        result_id = "result-" + hashlib.sha256(_canonical(payload)).hexdigest()[:24]
        payload["result_id"] = result_id
        with self._lock:
            self._results[result_id] = {
                "subject": actor.user_id,
                "serving_generation": freshness["serving_generation"],
                "payload": payload,
            }
            if result_id in self._result_order:
                self._result_order.remove(result_id)
            self._result_order.append(result_id)
            while len(self._result_order) > MAX_STORED_RESULTS:
                expired = self._result_order.pop(0)
                self._results.pop(expired, None)
        return payload

    def get_match(
        self,
        access_token: str,
        result_id: str,
        session_id: str,
    ) -> dict[str, Any]:
        """Evidence read bound to the exact stored discovery result.

        Never silently recomputes: a moved corpus generation or a consent
        change invalidates the stored result with a typed error.
        """
        actor = self.identity.authenticate(access_token)
        with self._lock:
            record = self._results.get(result_id)
        if record is None or record["subject"] != actor.user_id:
            raise ProductError(
                "discovery result is unknown, expired, or not yours; run discovery again"
            )
        current = self.freshness()
        if (not current["index_current"]
                or record["serving_generation"] != current["serving_generation"]):
            with self._lock:
                self._results.pop(result_id, None)
            raise StaleResultError(
                "durable corpus changed after this discovery; run discovery again"
            )
        for row in list(record["payload"]["matches"]) + list(record["payload"]["rejected"]):
            if row.get("session_id") == session_id:
                # Blocks and consent transitions do not move the corpus
                # generation, so every stored evidence read re-checks the
                # CURRENT viewer-relative authorization for this exact row.
                source = self.identity.policy_source
                owner = source.owner_of("session", session_id)
                if owner and source.is_blocked(actor.user_id, owner):
                    raise ProductError("match is no longer available")
                consent = source.session_consent(session_id)
                if consent and (consent.get("revoked") or consent.get("deleted")
                                or not consent.get("share_thought_dna")):
                    raise ProductError("match is no longer available")
                return {
                    "contract_version": LIVE_PRODUCT_CONTRACT,
                    "source": "live",
                    "result_id": result_id,
                    "freshness": current,
                    "match": row,
                }
        raise ProductError(
            "match is not present in the referenced discovery result"
        )

    # ------------------------------------------------------------------
    # projection helpers (redact/drop only; never reorder or rescore)
    # ------------------------------------------------------------------
    def _project_row(
        self,
        viewer_id: str,
        row: Mapping[str, Any],
        viewer_coords: tuple[float, float] | None,
        *,
        allow_hard_rejected: bool = False,
    ) -> dict[str, Any] | None:
        candidate_session = str(row.get("session_id", ""))
        source = self.identity.policy_source
        owner = source.owner_of("session", candidate_session)
        if owner and source.is_blocked(viewer_id, owner):
            return None
        consent = source.session_consent(candidate_session)
        if consent:
            if consent.get("revoked") or consent.get("deleted"):
                return None
            if not consent.get("share_thought_dna") and not allow_hard_rejected:
                return None
        projected = dict(row)
        display = dict(projected.get("display", {}) or {})
        if consent and not consent.get("share_display_profile"):
            # Mirror R12B projection semantics: with profile sharing off, no
            # profile-derived presentation metadata escapes either.
            projected["person_pseudonym"] = "anonymous"
            for field in ("topic", "domain", "cluster_id"):
                display.pop(field, None)
        if consent and not consent.get("share_coarse_location"):
            display.pop("location", None)
        candidate_coords = _coords(display.get("location"))
        if viewer_coords is not None and candidate_coords is not None:
            km = _haversine_km(*viewer_coords, *candidate_coords)
            display["distance_context"] = {
                "bucket": _distance_bucket(km),
                "approx_km": round(km, -1),
                "presentation_only": True,
            }
        projected["display"] = display
        return projected

    def _aggregate(self, matches: list[dict[str, Any]]) -> dict[str, Any]:
        buckets: dict[str, int] = {}
        for match in matches:
            location = (match.get("display") or {}).get("location")
            region = location.get("region") if location else None
            if region:
                buckets[region] = buckets.get(region, 0) + 1
        visible = suppress_small_buckets(buckets, minimum=self.aggregation_minimum)
        total = sum(visible.values())
        return {
            "basis": "discoverable_matches_with_shareable_location_only",
            "anti_inference_minimum": self.aggregation_minimum,
            "suppressed_bucket_count": len(buckets) - len(visible),
            "buckets": [
                {"bucket_id": b, "count": n,
                 "intensity": round(n / total, 4) if total else 0.0}
                for b, n in sorted(visible.items())
            ],
        }
