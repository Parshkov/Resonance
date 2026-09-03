"""Durable, owner-scoped ingestion over the R12 identity product boundary."""

from __future__ import annotations

import re
import secrets
import time
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Any, Mapping

from src.graph import ThoughtGraph
from src.identity import ConsentChoices, IdentityService
from src.identity.models import IdentityEvent

from .service import (
    EMPTY_SHA256,
    ConfirmationError,
    DraftNotFound,
    IngestionError,
    IngestionService,
    PreparedArtifact,
    ShareCommit,
    ShareIntent,
)

INGESTION_PREPARED = "ingestion.draft.prepared"
INGESTION_SHARED = "ingestion.draft.shared"
INGESTION_DISCARDED = "ingestion.draft.discarded"


def _field(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, Mapping):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _durable_diagnostic(message: str) -> str:
    """Preserve warning meaning without retaining quoted raw-source fragments."""
    return re.sub(r"(['\"]).*?\1", "'[redacted]'", str(message))


@dataclass(frozen=True, slots=True)
class _DraftState:
    event: IdentityEvent
    status: str


class IdentityShareSink:
    """Commit a prepared private R11 row through R12 consent + R12B policy."""

    def __init__(
        self,
        service: "IdentityIngestionService",
        *,
        access_token: str,
        state: _DraftState,
        csrf_token: str | None,
        origin: str | None,
        cookie_authenticated: bool,
        client_id: str,
        protocol_session_id: str | None,
    ) -> None:
        self.service = service
        self.access_token = access_token
        self.state = state
        self.csrf_token = csrf_token
        self.origin = origin
        self.cookie_authenticated = cookie_authenticated
        self.client_id = client_id
        self.protocol_session_id = protocol_session_id

    def commit_prepared(self, commit: ShareCommit) -> Mapping[str, Any]:
        event = self.state.event
        session_id = str(event.session_id or "")
        if (
            not session_id
            or event.user_id != commit.subject
            or str(event.payload.get("draft_id", "")) != commit.draft_id
        ):
            raise DraftNotFound(commit.draft_id)
        required_presentation = {"cluster_id", "topic", "domain"}
        missing = sorted(required_presentation.difference(commit.presentation))
        if missing:
            raise IngestionError(
                "share preview is missing required presentation fields: "
                + ", ".join(missing)
            )
        session = self.service.identity.backend.get_session(session_id)
        if session is None or dict(_field(session, "thought_dna", {})) != dict(commit.thought_dna):
            raise DraftNotFound(commit.draft_id)

        choices = ConsentChoices(
            share_thought_dna=True,
            share_display_profile=bool(commit.share_intent.get("share_display_profile", False)),
            share_coarse_location=bool(commit.share_intent.get("share_coarse_location", False)),
            allow_intro_requests=bool(commit.share_intent.get("receive_intro_requests", False)),
        )
        # Always use the original version + durable request id. That makes a
        # response-lost retry replay the committed share, while an unrelated
        # manual share/update cannot masquerade as this confirmed preview.
        self.service.identity.set_consent(
            self.access_token,
            session_id,
            choices,
            confirmed=True,
            csrf_token=self.csrf_token,
            origin=self.origin,
            cookie_authenticated=self.cookie_authenticated,
            client_id=self.client_id,
            protocol_session_id=self.protocol_session_id,
            expected_version=int(event.payload["prepared_version"]),
            request_id=f"ingestion-share:{commit.draft_id}",
        )

        self.service._append_event(
            INGESTION_SHARED,
            user_id=commit.subject,
            session_id=session_id,
            payload={"draft_id": commit.draft_id},
        )
        return {
            "draft_id": commit.draft_id,
            "session_id": session_id,
            "thought_id": str(commit.thought_dna.get("thought_id", "")),
            "shared": True,
            "discoverable": True,
        }


class IdentityIngestionService:
    """One authenticated preparation boundary for UI, WebMCP, and remote MCP.

    A prepared artifact is immediately stored as a private, sanitized R11
    session. Sharing only changes consent after an exact preview token and
    explicit confirmation. The access token, never a caller owner field,
    supplies the durable subject.
    """

    def __init__(
        self,
        identity: IdentityService,
        *,
        core: IngestionService | None = None,
        confirmation_secret: bytes | None = None,
    ) -> None:
        if core is None and not confirmation_secret:
            raise ValueError(
                "a stable confirmation_secret is required for durable draft recovery"
            )
        self.identity = identity
        self.core = core or IngestionService(secret=confirmation_secret)

    def prepare_structured(
        self,
        access_token: str,
        candidate: Mapping[str, Any],
        *,
        presentation: Mapping[str, Any] | None = None,
        coarse_location: Mapping[str, Any] | None = None,
        intent: ShareIntent | None = None,
        csrf_token: str | None = None,
        origin: str | None = None,
        cookie_authenticated: bool = False,
        client_id: str = "resonance-product",
        protocol_session_id: str | None = None,
    ) -> dict[str, Any]:
        prepared = self.core.prepare_structured(
            candidate,
            presentation=presentation,
            coarse_location=coarse_location,
            intent=intent,
        )
        return self._persist_prepared(
            access_token,
            prepared,
            csrf_token=csrf_token,
            origin=origin,
            cookie_authenticated=cookie_authenticated,
            client_id=client_id,
            protocol_session_id=protocol_session_id,
        )

    def prepare_raw_text(
        self,
        access_token: str,
        context: str,
        *,
        source_id: str | None = None,
        presentation: Mapping[str, Any] | None = None,
        coarse_location: Mapping[str, Any] | None = None,
        intent: ShareIntent | None = None,
        csrf_token: str | None = None,
        origin: str | None = None,
        cookie_authenticated: bool = False,
        client_id: str = "resonance-product",
        protocol_session_id: str | None = None,
    ) -> dict[str, Any]:
        prepared = self.core.prepare_raw_text(
            context,
            source_id=source_id,
            presentation=presentation,
            coarse_location=coarse_location,
            intent=intent,
        )
        return self._persist_prepared(
            access_token,
            prepared,
            csrf_token=csrf_token,
            origin=origin,
            cookie_authenticated=cookie_authenticated,
            client_id=client_id,
            protocol_session_id=protocol_session_id,
        )

    def preview(
        self,
        access_token: str,
        draft_id: str,
        *,
        client_id: str = "resonance-product",
        protocol_session_id: str | None = None,
    ) -> dict[str, Any]:
        self._load_owned(
            access_token,
            draft_id,
            client_id=client_id,
            protocol_session_id=protocol_session_id,
        )
        return self.core.preview(draft_id)

    def share_prepared(
        self,
        access_token: str,
        draft_id: str,
        *,
        confirmation_token: str,
        confirmed: bool,
        csrf_token: str | None = None,
        origin: str | None = None,
        cookie_authenticated: bool = False,
        client_id: str = "resonance-product",
        protocol_session_id: str | None = None,
    ) -> Mapping[str, Any]:
        if not confirmed:
            raise ConfirmationError("explicit user confirmation is required")
        actor, state = self._load_owned(
            access_token,
            draft_id,
            client_id=client_id,
            protocol_session_id=protocol_session_id,
        )
        sink = IdentityShareSink(
            self,
            access_token=access_token,
            state=state,
            csrf_token=csrf_token,
            origin=origin,
            cookie_authenticated=cookie_authenticated,
            client_id=client_id,
            protocol_session_id=protocol_session_id,
        )
        return self.core.share_prepared(
            draft_id,
            subject=actor.user_id,
            confirmation_token=confirmation_token,
            sink=sink,
        )

    def discard(
        self,
        access_token: str,
        draft_id: str,
        *,
        confirmed: bool,
        csrf_token: str | None = None,
        origin: str | None = None,
        cookie_authenticated: bool = False,
        client_id: str = "resonance-product",
        protocol_session_id: str | None = None,
    ) -> dict[str, Any]:
        if not confirmed:
            raise ConfirmationError("explicit user confirmation is required")
        actor, state = self._load_owned(
            access_token,
            draft_id,
            client_id=client_id,
            protocol_session_id=protocol_session_id,
        )
        session_id = str(state.event.session_id)
        self.identity.delete_thought_session(
            access_token,
            session_id,
            confirmed=True,
            csrf_token=csrf_token,
            origin=origin,
            cookie_authenticated=cookie_authenticated,
            client_id=client_id,
            protocol_session_id=protocol_session_id,
        )
        self._append_event(
            INGESTION_DISCARDED,
            user_id=actor.user_id,
            session_id=session_id,
            payload={"draft_id": draft_id},
        )
        if self.core.has_draft(draft_id):
            self.core.discard(draft_id)
        return {
            "draft_id": draft_id,
            "session_id": session_id,
            "discarded": True,
            "discoverable": False,
        }

    def _persist_prepared(
        self,
        access_token: str,
        prepared: Mapping[str, Any],
        *,
        csrf_token: str | None,
        origin: str | None,
        cookie_authenticated: bool,
        client_id: str,
        protocol_session_id: str | None,
    ) -> dict[str, Any]:
        draft_id = str(prepared["draft_id"])
        artifact = self.core.get_prepared(draft_id)
        actor = self.identity.authenticate(access_token)
        try:
            stored = self.identity.create_thought_session(
                access_token,
                thought_dna=artifact.graph.to_dict(),
                location=dict(artifact.coarse_location or {}),
                presentation=dict(artifact.presentation),
                record_kind="volunteer",
                notes="prepared by resonance-ingestion/0.1; raw source not retained",
                csrf_token=csrf_token,
                origin=origin,
                cookie_authenticated=cookie_authenticated,
                client_id=client_id,
                protocol_session_id=protocol_session_id,
            )
            artifact = replace(
                artifact,
                graph=ThoughtGraph.from_dict(dict(_field(stored, "thought_dna", {}))),
                presentation=dict(_field(stored, "presentation", {}) or {}),
                coarse_location=dict(_field(stored, "location", {}) or {}) or None,
            )
            self.core.restore_prepared(artifact)
            self._append_event(
                INGESTION_PREPARED,
                user_id=actor.user_id,
                session_id=str(_field(stored, "session_id")),
                payload={
                    "draft_id": draft_id,
                    "input_kind": artifact.input_kind,
                    "warnings": [_durable_diagnostic(item) for item in artifact.warnings],
                    "abstentions": [_durable_diagnostic(item) for item in artifact.abstentions],
                    "share_intent": artifact.intent.to_dict(),
                    "prepared_version": int(_field(stored, "version", 0)),
                },
            )
        except Exception:
            if self.core.has_draft(draft_id):
                self.core.discard(draft_id)
            raise
        return dict(prepared) | {
            "session_id": str(_field(stored, "session_id")),
            "durable": True,
        }

    def _load_owned(
        self,
        access_token: str,
        draft_id: str,
        *,
        client_id: str,
        protocol_session_id: str | None,
    ) -> tuple[Any, _DraftState]:
        actor = self.identity.authenticate(access_token)
        state = self._draft_state(draft_id)
        if state is None or state.status != "prepared" or state.event.user_id != actor.user_id:
            raise DraftNotFound(draft_id)
        session_id = str(state.event.session_id or "")
        try:
            self.identity.consent_for(
                access_token,
                session_id,
                client_id=client_id,
                protocol_session_id=protocol_session_id,
            )
        except Exception as exc:
            raise DraftNotFound(draft_id) from exc
        session = self.identity.backend.get_session(session_id)
        if (
            session is None
            or _field(session, "revoked_at") is not None
            or _field(session, "deleted_at") is not None
        ):
            raise DraftNotFound(draft_id)
        if not self.core.has_draft(draft_id):
            payload = state.event.payload
            intent_raw = dict(payload.get("share_intent", {}))
            artifact = PreparedArtifact(
                draft_id=draft_id,
                graph=ThoughtGraph.from_dict(dict(_field(session, "thought_dna", {}))),
                input_kind=str(payload.get("input_kind", "agent_structured")),
                source_sha256=EMPTY_SHA256,
                warnings=tuple(str(item) for item in payload.get("warnings", ())),
                abstentions=tuple(str(item) for item in payload.get("abstentions", ())),
                presentation=dict(_field(session, "presentation", {}) or {}),
                coarse_location=dict(_field(session, "location", {}) or {}) or None,
                intent=ShareIntent(
                    share_display_profile=bool(
                        intent_raw.get("share_display_profile", True)
                    ),
                    share_coarse_location=bool(
                        intent_raw.get("share_coarse_location", False)
                    ),
                    receive_intro_requests=bool(
                        intent_raw.get("receive_intro_requests", False)
                    ),
                ),
                created_at=state.event.created_at,
            )
            self.core.restore_prepared(artifact)
        return actor, state

    def _draft_state(self, draft_id: str) -> _DraftState | None:
        state: _DraftState | None = None
        for event in self.identity.backend.list_identity_events():
            if str(event.payload.get("draft_id", "")) != draft_id:
                continue
            if event.event_type == INGESTION_PREPARED:
                state = _DraftState(event, "prepared")
            elif event.event_type == INGESTION_SHARED and state is not None:
                state = _DraftState(event, "shared")
            elif event.event_type == INGESTION_DISCARDED and state is not None:
                state = _DraftState(event, "discarded")
        return state

    def _append_event(
        self,
        event_type: str,
        *,
        user_id: str,
        session_id: str,
        payload: Mapping[str, Any],
    ) -> None:
        self.identity.backend.append_identity_event(
            IdentityEvent(
                event_id=f"ievt-{time.time_ns():020d}-{secrets.token_hex(4)}",
                event_type=event_type,
                user_id=user_id,
                session_id=session_id,
                payload=dict(payload),
                created_at=_now(),
            )
        )


class IngestionAdapter:
    """Transport adapter; subclasses differ only in auth/CSRF context."""

    client_id = "product-api"
    cookie_authenticated = False
    untrusted_content_hint = False

    def __init__(
        self,
        service: IdentityIngestionService,
        *,
        request_origin: str | None = None,
        protocol_session_id: str | None = None,
    ) -> None:
        self.service = service
        self.request_origin = request_origin
        self.protocol_session_id = protocol_session_id

    def _security(self, csrf_token: str | None) -> dict[str, Any]:
        return {
            "csrf_token": csrf_token,
            "origin": self.request_origin,
            "cookie_authenticated": self.cookie_authenticated,
            "client_id": self.client_id,
            "protocol_session_id": self.protocol_session_id,
        }

    def prepare_structured(
        self,
        access_token: str,
        candidate: Mapping[str, Any],
        *,
        csrf_token: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        return self._mark_untrusted(self.service.prepare_structured(
            access_token,
            candidate,
            **kwargs,
            **self._security(csrf_token),
        ))

    def prepare_raw_text(
        self,
        access_token: str,
        context: str,
        *,
        csrf_token: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        return self._mark_untrusted(self.service.prepare_raw_text(
            access_token,
            context,
            **kwargs,
            **self._security(csrf_token),
        ))

    def preview(self, access_token: str, draft_id: str) -> dict[str, Any]:
        return self._mark_untrusted(self.service.preview(
            access_token,
            draft_id,
            client_id=self.client_id,
            protocol_session_id=self.protocol_session_id,
        ))

    def share_prepared(
        self,
        access_token: str,
        draft_id: str,
        *,
        confirmation_token: str,
        confirmed: bool,
        csrf_token: str | None = None,
    ) -> Mapping[str, Any]:
        return self.service.share_prepared(
            access_token,
            draft_id,
            confirmation_token=confirmation_token,
            confirmed=confirmed,
            **self._security(csrf_token),
        )

    def discard(
        self,
        access_token: str,
        draft_id: str,
        *,
        confirmed: bool,
        csrf_token: str | None = None,
    ) -> dict[str, Any]:
        return self.service.discard(
            access_token,
            draft_id,
            confirmed=confirmed,
            **self._security(csrf_token),
        )

    def resonance_prepare_thought(
        self,
        access_token: str,
        *,
        candidate: Mapping[str, Any] | None = None,
        context: str | None = None,
        csrf_token: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Canonical tool action: exactly one structured or raw input."""
        if (candidate is None) == (context is None):
            raise IngestionError("provide exactly one of candidate or context")
        if candidate is not None:
            return self.prepare_structured(
                access_token,
                candidate,
                csrf_token=csrf_token,
                **kwargs,
            )
        return self.prepare_raw_text(
            access_token,
            str(context),
            csrf_token=csrf_token,
            **kwargs,
        )

    def resonance_get_share_preview(
        self,
        access_token: str,
        draft_id: str,
    ) -> dict[str, Any]:
        return self.preview(access_token, draft_id)

    def resonance_share_prepared_thought(
        self,
        access_token: str,
        draft_id: str,
        *,
        confirmation_token: str,
        confirmed: bool,
        csrf_token: str | None = None,
    ) -> Mapping[str, Any]:
        return self.share_prepared(
            access_token,
            draft_id,
            confirmation_token=confirmation_token,
            confirmed=confirmed,
            csrf_token=csrf_token,
        )

    def resonance_discard_prepared_thought(
        self,
        access_token: str,
        draft_id: str,
        *,
        confirmed: bool,
        csrf_token: str | None = None,
    ) -> dict[str, Any]:
        return self.discard(
            access_token,
            draft_id,
            confirmed=confirmed,
            csrf_token=csrf_token,
        )

    def _mark_untrusted(self, result: Mapping[str, Any]) -> dict[str, Any]:
        projected = dict(result)
        if self.untrusted_content_hint:
            projected["_meta"] = {"untrustedContentHint": True}
        return projected


class ManualIngestionAdapter(IngestionAdapter):
    client_id = "manual-ui"
    cookie_authenticated = True


class WebMCPIngestionAdapter(IngestionAdapter):
    client_id = "webmcp"
    cookie_authenticated = True
    untrusted_content_hint = True


class RemoteMCPIngestionAdapter(IngestionAdapter):
    client_id = "remote-mcp"
    untrusted_content_hint = True
