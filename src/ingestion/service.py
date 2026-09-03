"""Private-first Thought DNA preparation and share handoff.

R12C owns the ingestion boundary, not persistence, identity, or matching. The
service keeps only sanitized prepared artifacts in memory and hands a final
commit to an injected sink owned by R11/R12 integration. Raw source text is
used transiently and is not retained by default.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, Protocol

from src.extraction import CueExtractor, EXTRACTOR_ID, EXTRACTOR_VERSION
from src.graph import ThoughtGraph, validate_thought

INGESTION_VERSION = "resonance-ingestion/0.1"
EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()

FORBIDDEN_CONTROL_FIELDS = frozenset(
    {
        "user_id",
        "owner_id",
        "owner",
        "subject",
        "session_id",
        "consent",
        "share_enabled",
        "discoverable",
        "workspace_id",
    }
)


class IngestionError(ValueError):
    """Base validation/state error at the product ingestion boundary."""


class DraftNotFound(IngestionError):
    """Prepared draft is unknown or already consumed/discarded."""


class ConfirmationError(IngestionError):
    """Preview confirmation token is absent, stale, or invalid."""


@dataclass(frozen=True, slots=True)
class IngestionLimits:
    max_payload_bytes: int = 64 * 1024
    max_raw_text_chars: int = 20_000
    max_nodes: int = 64
    max_relations: int = 128
    max_presentation_bytes: int = 8 * 1024


@dataclass(frozen=True, slots=True)
class ShareIntent:
    """Exactly the non-owner fields a human will see before sharing."""

    share_display_profile: bool = True
    share_coarse_location: bool = False
    receive_intro_requests: bool = False

    def to_dict(self) -> dict[str, bool]:
        return {
            "share_thought_dna": True,
            "share_display_profile": self.share_display_profile,
            "share_coarse_location": self.share_coarse_location,
            "receive_intro_requests": self.receive_intro_requests,
        }


@dataclass(frozen=True, slots=True)
class PreparedArtifact:
    draft_id: str
    graph: ThoughtGraph
    input_kind: str
    source_sha256: str
    warnings: tuple[str, ...]
    abstentions: tuple[str, ...]
    presentation: Mapping[str, Any]
    coarse_location: Mapping[str, Any] | None
    intent: ShareIntent
    created_at: str

    def preview_dict(self) -> dict[str, Any]:
        return {
            "contract_version": INGESTION_VERSION,
            "draft_id": self.draft_id,
            "input_kind": self.input_kind,
            "thought_dna": self.graph.to_dict(),
            "warnings": list(self.warnings),
            "abstentions": list(self.abstentions),
            "presentation": dict(self.presentation),
            "coarse_location": (
                dict(self.coarse_location)
                if self.intent.share_coarse_location and self.coarse_location is not None
                else None
            ),
            "share_intent": self.intent.to_dict(),
            "source_retention": "not_retained",
            "requires_explicit_confirmation": True,
        }


@dataclass(frozen=True, slots=True)
class ShareCommit:
    """Trusted handoff. Actor identity is supplied by the authenticated layer."""

    subject: str
    draft_id: str
    thought_dna: Mapping[str, Any]
    presentation: Mapping[str, Any]
    coarse_location: Mapping[str, Any] | None
    share_intent: Mapping[str, bool]
    provenance: Mapping[str, Any]


class ShareSink(Protocol):
    """R11/R12 integration owns durable atomic commit + index update."""

    def commit_prepared(self, commit: ShareCommit) -> Mapping[str, Any]:
        ...


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _source_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _reject_control_fields(candidate: Mapping[str, Any]) -> None:
    found = sorted(FORBIDDEN_CONTROL_FIELDS.intersection(candidate))
    if found:
        raise IngestionError(
            "Thought DNA candidate may not choose product ownership/consent fields: "
            + ", ".join(found)
        )


def _sanitize_graph(graph: ThoughtGraph) -> ThoughtGraph:
    """Remove reconstructable raw source/spans while preserving graph semantics."""
    raw = graph.to_dict()
    raw["source"] = {"text": "", "sha256": EMPTY_SHA256}
    if raw["provenance"]["kind"] == "extracted":
        # The accepted Thought DNA schema requires source-grounded spans for
        # `extracted` provenance. Once raw source/spans are deliberately
        # removed, the durable graph becomes a prepared manual artifact; the
        # original extractor id/version remains in ShareCommit.provenance.
        raw["provenance"] = {
            "kind": "manual",
            "extractor": None,
            "human_id": "r12c-sanitized-preview",
        }
    for node in raw["nodes"]:
        node["spans"] = []
    for relation in raw["relations"]:
        relation["spans"] = []
        relation.pop("cue", None)
        relation.pop("provenance_refs", None)
    sanitized = ThoughtGraph.from_dict(raw)
    validate_thought(sanitized.to_dict())
    return sanitized


class IngestionService:
    """Transport-neutral private draft service.

    Prepared artifacts are deliberately ephemeral in this foundation. Final
    R11/R12 integration supplies durable owner-scoped draft/shared state.
    """

    def __init__(
        self,
        *,
        extractor: CueExtractor | None = None,
        limits: IngestionLimits | None = None,
        secret: bytes | None = None,
    ) -> None:
        self.extractor = extractor or CueExtractor()
        self.limits = limits or IngestionLimits()
        self._secret = secret or secrets.token_bytes(32)
        self._lock = threading.RLock()
        self._drafts: dict[str, PreparedArtifact] = {}

    def prepare_structured(
        self,
        candidate: Mapping[str, Any],
        *,
        presentation: Mapping[str, Any] | None = None,
        coarse_location: Mapping[str, Any] | None = None,
        intent: ShareIntent | None = None,
    ) -> dict[str, Any]:
        if not isinstance(candidate, Mapping):
            raise IngestionError("candidate must be a Thought DNA object")
        _reject_control_fields(candidate)
        self._require_payload_size(candidate)
        graph = ThoughtGraph.from_dict(dict(candidate))
        validate_thought(graph.to_dict())
        self._require_graph_bounds(graph)
        artifact = self._remember(
            graph=_sanitize_graph(graph),
            input_kind="agent_structured",
            source_sha256=graph.source.sha256,
            warnings=(),
            abstentions=(),
            presentation=presentation,
            coarse_location=coarse_location,
            intent=intent,
        )
        return self._prepared_result(artifact)

    def prepare_raw_text(
        self,
        context: str,
        *,
        source_id: str | None = None,
        presentation: Mapping[str, Any] | None = None,
        coarse_location: Mapping[str, Any] | None = None,
        intent: ShareIntent | None = None,
    ) -> dict[str, Any]:
        if not isinstance(context, str) or not context.strip():
            raise IngestionError("context must be a non-empty string")
        if len(context) > self.limits.max_raw_text_chars:
            raise IngestionError("raw text exceeds ingestion limit")
        result = self.extractor.extract(context, source_id=source_id)
        self._require_graph_bounds(result.graph)
        artifact = self._remember(
            graph=_sanitize_graph(result.graph),
            input_kind="raw_text_fallback",
            source_sha256=_source_hash(context),
            warnings=tuple(result.warnings),
            abstentions=tuple(result.abstentions),
            presentation=presentation,
            coarse_location=coarse_location,
            intent=intent,
        )
        # `context` is intentionally not assigned to service state.
        return self._prepared_result(artifact)

    def preview(self, draft_id: str) -> dict[str, Any]:
        with self._lock:
            artifact = self._drafts.get(draft_id)
            if artifact is None:
                raise DraftNotFound(draft_id)
            result = artifact.preview_dict()
            result["confirmation_token"] = self._confirmation_token(artifact)
            return result

    def discard(self, draft_id: str) -> dict[str, Any]:
        with self._lock:
            artifact = self._drafts.pop(draft_id, None)
        if artifact is None:
            raise DraftNotFound(draft_id)
        return {
            "contract_version": INGESTION_VERSION,
            "draft_id": draft_id,
            "discarded": True,
            "discoverable": False,
        }

    def share_prepared(
        self,
        draft_id: str,
        *,
        subject: str,
        confirmation_token: str,
        sink: ShareSink,
    ) -> Mapping[str, Any]:
        if not isinstance(subject, str) or not subject:
            raise IngestionError("authenticated subject is required")
        if not isinstance(confirmation_token, str) or not confirmation_token:
            raise ConfirmationError("confirmation token is required")

        with self._lock:
            artifact = self._drafts.get(draft_id)
            if artifact is None:
                raise DraftNotFound(draft_id)
            expected = self._confirmation_token(artifact)
            if not hmac.compare_digest(confirmation_token, expected):
                raise ConfirmationError("confirmation token is invalid or stale")

            commit = ShareCommit(
                subject=subject,
                draft_id=artifact.draft_id,
                thought_dna=artifact.graph.to_dict(),
                presentation=dict(artifact.presentation),
                coarse_location=(
                    dict(artifact.coarse_location)
                    if artifact.intent.share_coarse_location
                    and artifact.coarse_location is not None
                    else None
                ),
                share_intent=artifact.intent.to_dict(),
                provenance={
                    "ingestion_contract": INGESTION_VERSION,
                    "input_kind": artifact.input_kind,
                    "source_retained": False,
                    "extractor": (
                        {"id": EXTRACTOR_ID, "version": EXTRACTOR_VERSION}
                        if artifact.input_kind == "raw_text_fallback"
                        else None
                    ),
                    "warnings": list(artifact.warnings),
                    "abstentions": list(artifact.abstentions),
                },
            )
            # The sink owns one atomic durable consent/index transaction. The
            # draft is consumed only after it returns successfully.
            receipt = sink.commit_prepared(commit)
            self._drafts.pop(draft_id, None)
        return receipt

    def has_draft(self, draft_id: str) -> bool:
        with self._lock:
            return draft_id in self._drafts

    def get_prepared(self, draft_id: str) -> PreparedArtifact:
        """Return an immutable prepared artifact for a trusted store adapter."""
        with self._lock:
            artifact = self._drafts.get(draft_id)
            if artifact is None:
                raise DraftNotFound(draft_id)
            return artifact

    def restore_prepared(self, artifact: PreparedArtifact) -> None:
        """Restore a sanitized private draft from an authoritative store.

        Raw source text cannot enter through this seam: restored graphs must
        already carry the empty-source projection produced by `_sanitize_graph`.
        """
        graph = artifact.graph.to_dict()
        if graph.get("source") != {"text": "", "sha256": EMPTY_SHA256}:
            raise IngestionError("restored draft contains retained source text")
        validate_thought(graph)
        self._require_graph_bounds(artifact.graph)
        self._require_metadata_size(artifact.presentation, "presentation")
        if artifact.coarse_location is not None:
            self._require_metadata_size(artifact.coarse_location, "coarse_location")
        with self._lock:
            self._drafts[artifact.draft_id] = artifact

    def _remember(
        self,
        *,
        graph: ThoughtGraph,
        input_kind: str,
        source_sha256: str,
        warnings: tuple[str, ...],
        abstentions: tuple[str, ...],
        presentation: Mapping[str, Any] | None,
        coarse_location: Mapping[str, Any] | None,
        intent: ShareIntent | None,
    ) -> PreparedArtifact:
        safe_presentation = dict(presentation or {})
        safe_location = dict(coarse_location) if coarse_location is not None else None
        self._require_metadata_size(safe_presentation, "presentation")
        if safe_location is not None:
            self._require_metadata_size(safe_location, "coarse_location")
        if FORBIDDEN_CONTROL_FIELDS.intersection(safe_presentation):
            raise IngestionError("presentation may not contain ownership/consent controls")
        share_intent = intent or ShareIntent()
        # Opaque server-generated identity prevents an old preview token from
        # becoming valid again if identical content is discarded and prepared
        # later. Transport idempotency keys are a separate concern.
        draft_id = "draft-" + secrets.token_hex(12)
        artifact = PreparedArtifact(
            draft_id=draft_id,
            graph=graph,
            input_kind=input_kind,
            source_sha256=source_sha256,
            warnings=warnings,
            abstentions=abstentions,
            presentation=safe_presentation,
            coarse_location=safe_location,
            intent=share_intent,
            created_at=_utc_now(),
        )
        with self._lock:
            self._drafts[draft_id] = artifact
        return artifact

    def _prepared_result(self, artifact: PreparedArtifact) -> dict[str, Any]:
        return {
            "contract_version": INGESTION_VERSION,
            "draft_id": artifact.draft_id,
            "status": "prepared_private",
            "discoverable": False,
            "input_kind": artifact.input_kind,
            "warnings": list(artifact.warnings),
            "abstentions": list(artifact.abstentions),
            "source_retention": "not_retained",
            "next_step": "Read the exact preview, then explicitly confirm share.",
        }

    def _confirmation_token(self, artifact: PreparedArtifact) -> str:
        snapshot = {
            "draft_id": artifact.draft_id,
            "thought_dna": artifact.graph.to_dict(),
            "presentation": dict(artifact.presentation),
            "coarse_location": (
                dict(artifact.coarse_location) if artifact.coarse_location is not None else None
            ),
            "share_intent": artifact.intent.to_dict(),
        }
        return hmac.new(self._secret, _canonical_bytes(snapshot), hashlib.sha256).hexdigest()

    def _require_payload_size(self, value: Any) -> None:
        if len(_canonical_bytes(value)) > self.limits.max_payload_bytes:
            raise IngestionError("Thought DNA payload exceeds ingestion limit")

    def _require_metadata_size(self, value: Mapping[str, Any], name: str) -> None:
        try:
            encoded = _canonical_bytes(value)
        except (TypeError, ValueError) as exc:
            raise IngestionError(f"{name} must be JSON-serializable") from exc
        if len(encoded) > self.limits.max_presentation_bytes:
            raise IngestionError(f"{name} exceeds ingestion limit")

    def _require_graph_bounds(self, graph: ThoughtGraph) -> None:
        if len(graph.nodes) > self.limits.max_nodes:
            raise IngestionError("Thought DNA node count exceeds ingestion limit")
        if len(graph.relations) > self.limits.max_relations:
            raise IngestionError("Thought DNA relation count exceeds ingestion limit")
