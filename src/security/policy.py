"""Fail-closed authorization and session-grant policy kernel for Resonance."""

from __future__ import annotations

import secrets
import time
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from .guards import DeterministicRateLimiter, safe_log_metadata
from .models import (
    AuthenticationRequired,
    AuthorizationDenied,
    ConfirmationRequired,
    Decision,
    GrantCheckpoint,
    PolicyDecision,
    RequestContext,
    ResourceRef,
    SessionBindingError,
)
from .store import PolicySource

OWNER_ACTIONS = frozenset({
    "session:create",
    "session:read_private",
    "session:update",
    "session:share",
    "session:revoke",
    "session:delete",
    "account:export",
    "account:delete",
})
SENSITIVE_WRITES = frozenset({
    "session:share",
    "session:revoke",
    "session:delete",
    "account:delete",
    "intro:request",
    "message:send",
    "workspace:invite",
    "workspace:remove_member",
    "security:block",
})
WORKSPACE_READ = frozenset({"workspace:read", "message:read", "artifact:read"})
WORKSPACE_WRITE = frozenset({"workspace:write", "message:send", "artifact:write"})
WORKSPACE_ADMIN = frozenset({"workspace:invite", "workspace:remove_member"})
PEER_ACTIONS = frozenset({"discovery:read", "intro:request", "message:send"})


class AuditTrail:
    def __init__(self) -> None:
        self._events: list[dict[str, Any]] = []

    def append(self, decision: PolicyDecision) -> None:
        self._events.append(safe_log_metadata(decision.to_safe_dict()))

    def events(self) -> tuple[dict[str, Any], ...]:
        return tuple(dict(event) for event in self._events)


class SessionGrantRegistry:
    """Binds protocol session IDs to subject + client + policy checkpoint."""

    def __init__(self, source: PolicySource, *, ttl_seconds: int = 3600, clock: Any = time.time) -> None:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        self.source = source
        self.ttl_seconds = ttl_seconds
        self.clock = clock
        self._bindings: dict[str, GrantCheckpoint] = {}

    def bind(self, context: RequestContext, *, protocol_session_id: str | None = None) -> GrantCheckpoint:
        _require_authenticated(context)
        sid = protocol_session_id or f"mcp-{secrets.token_urlsafe(16)}"
        if sid in self._bindings:
            raise SessionBindingError("protocol session id is already bound")
        checkpoint = GrantCheckpoint(
            protocol_session_id=sid,
            subject=context.subject,
            client_id=context.client_id,
            grant_version=self.source.generation_for(context.subject),
            expires_at=float(self.clock()) + self.ttl_seconds,
        )
        self._bindings[sid] = checkpoint
        return checkpoint

    def require(self, context: RequestContext, protocol_session_id: str) -> GrantCheckpoint:
        _require_authenticated(context)
        checkpoint = self._bindings.get(protocol_session_id)
        if checkpoint is None:
            raise SessionBindingError("unknown protocol session")
        if checkpoint.expires_at <= float(self.clock()):
            self._bindings.pop(protocol_session_id, None)
            raise SessionBindingError("expired protocol session")
        if checkpoint.subject != context.subject or checkpoint.client_id != context.client_id:
            raise SessionBindingError("protocol session belongs to a different subject/client")
        return checkpoint

    def refresh_generation(self, context: RequestContext, protocol_session_id: str) -> GrantCheckpoint:
        checkpoint = self.require(context, protocol_session_id)
        refreshed = GrantCheckpoint(
            protocol_session_id=checkpoint.protocol_session_id,
            subject=checkpoint.subject,
            client_id=checkpoint.client_id,
            grant_version=self.source.generation_for(context.subject),
            expires_at=checkpoint.expires_at,
        )
        self._bindings[protocol_session_id] = refreshed
        return refreshed

    def revoke(self, protocol_session_id: str) -> None:
        self._bindings.pop(protocol_session_id, None)

    def rotate(self, context: RequestContext, protocol_session_id: str) -> GrantCheckpoint:
        self.require(context, protocol_session_id)
        self.revoke(protocol_session_id)
        return self.bind(context)


@dataclass
class SecurityPolicy:
    source: PolicySource
    sessions: SessionGrantRegistry
    audit: AuditTrail
    limiter: DeterministicRateLimiter

    @classmethod
    def build(cls, source: PolicySource, *, limiter: DeterministicRateLimiter | None = None) -> "SecurityPolicy":
        return cls(
            source=source,
            sessions=SessionGrantRegistry(source),
            audit=AuditTrail(),
            limiter=limiter or DeterministicRateLimiter(capacity=30, refill_per_second=1.0),
        )

    def authorize(
        self,
        context: RequestContext,
        action: str,
        resource: ResourceRef,
        *,
        protocol_session_id: str | None = None,
        confirmed: bool = False,
        correlation_id: str | None = None,
    ) -> PolicyDecision:
        _require_authenticated(context)
        self.limiter.check(context.subject, action)
        correlation = correlation_id or f"sec-{secrets.token_hex(8)}"

        checkpoint: GrantCheckpoint | None = None
        if protocol_session_id is not None:
            try:
                checkpoint = self.sessions.require(context, protocol_session_id)
            except AuthorizationDenied as exc:
                decision = self._decision(
                    context, action, resource, protocol_session_id, Decision.DENY,
                    str(exc), self.source.generation_for(context.subject), correlation,
                )
                self.audit.append(decision)
                raise

        current_generation = self.source.generation_for(context.subject)
        try:
            self._authorize_current(context, action, resource)
            # Token scopes only narrow an authoritative server-side allow.
            if context.token_scopes and action not in context.token_scopes:
                raise AuthorizationDenied("token scope narrows this server-side grant")
            if action in SENSITIVE_WRITES and not confirmed:
                raise ConfirmationRequired("explicit confirmation required for sensitive write")
        except ConfirmationRequired as exc:
            decision = self._decision(
                context, action, resource, protocol_session_id, Decision.CONFIRM,
                str(exc), current_generation, correlation,
            )
            self.audit.append(decision)
            raise
        except AuthorizationDenied as exc:
            decision = self._decision(
                context, action, resource, protocol_session_id, Decision.DENY,
                str(exc), current_generation, correlation,
            )
            self.audit.append(decision)
            raise

        # A changed policy generation never carries a stale grant forward.  We
        # have just re-evaluated against current authoritative state, so the
        # checkpoint may now advance to the version that justified this allow.
        if checkpoint is not None and checkpoint.grant_version != current_generation:
            checkpoint = self.sessions.refresh_generation(context, protocol_session_id or "")
            current_generation = checkpoint.grant_version

        decision = self._decision(
            context, action, resource, protocol_session_id, Decision.ALLOW,
            "authoritative policy allowed", current_generation, correlation,
        )
        self.audit.append(decision)
        return decision

    def _authorize_current(
        self,
        context: RequestContext,
        action: str,
        resource: ResourceRef,
    ) -> None:
        if not self.source.auth_session_active(context.subject, context.auth_session_id):
            raise AuthorizationDenied("authentication session is no longer active")
        owner = self.source.owner_of(resource.kind, resource.resource_id)

        if action in OWNER_ACTIONS:
            if not owner or owner != context.subject:
                raise AuthorizationDenied("resource unavailable to authenticated subject")
            return

        if action == "discovery:read":
            if owner == context.subject:
                return
            if not owner:
                raise AuthorizationDenied("candidate resource unavailable")
            if self.source.is_blocked(context.subject, owner):
                raise AuthorizationDenied("interaction is blocked")
            consent = self.source.session_consent(resource.resource_id)
            if consent.get("revoked") or consent.get("deleted") or not consent.get("share_thought_dna"):
                raise AuthorizationDenied("candidate is not discoverable")
            return

        if action == "intro:request":
            peer = owner
            if not peer:
                raise AuthorizationDenied("candidate identity unavailable")
            if self.source.is_blocked(context.subject, peer):
                raise AuthorizationDenied("interaction is blocked")
            consent = self.source.session_consent(resource.resource_id)
            if not consent.get("allow_intro_requests"):
                raise AuthorizationDenied("candidate does not accept intro requests")
            if not self.source.peer_action_allowed(context.subject, peer, action):
                raise AuthorizationDenied("current collaboration policy does not allow intro")
            return

        if action == "message:send" and resource.kind == "user":
            peer = resource.resource_id
            if self.source.is_blocked(context.subject, peer):
                raise AuthorizationDenied("interaction is blocked")
            if not self.source.peer_action_allowed(context.subject, peer, action):
                raise AuthorizationDenied("current collaboration policy does not allow direct message")
            return

        if action in WORKSPACE_READ | WORKSPACE_WRITE | WORKSPACE_ADMIN:
            workspace_id = self.source.workspace_of(resource.kind, resource.resource_id)
            if not workspace_id:
                raise AuthorizationDenied("resource is not linked to an authorized workspace")
            role = self.source.workspace_role(workspace_id, context.subject)
            if role is None:
                raise AuthorizationDenied("active workspace membership required")
            if action in WORKSPACE_WRITE and role not in {"owner", "admin", "member"}:
                raise AuthorizationDenied("workspace role cannot write")
            if action in WORKSPACE_ADMIN and role not in {"owner", "admin"}:
                raise AuthorizationDenied("workspace admin role required")
            return

        if action in {"intro:request", "message:send"}:
            raise AuthorizationDenied("authoritative peer/workspace scope required")

        if action in {"security:block", "security:report"}:
            if resource.kind != "user" or not resource.resource_id or resource.resource_id == context.subject:
                raise AuthorizationDenied("valid peer resource required")
            return

        raise AuthorizationDenied("action has no server-side policy rule")

    @staticmethod
    def discovery_projection(
        context: RequestContext,
        resource: ResourceRef,
        source: PolicySource,
        candidate: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Consent-safe presentation projection; never changes rank/score.

        The structural result is assumed already computed by the accepted R8
        discovery layer.  This helper only removes presentation fields that
        current authoritative consent does not allow.
        """
        owner = source.owner_of(resource.kind, resource.resource_id)
        if owner and source.is_blocked(context.subject, owner):
            raise AuthorizationDenied("interaction is blocked")
        consent = source.session_consent(resource.resource_id)
        if consent.get("revoked") or consent.get("deleted") or not consent.get("share_thought_dna"):
            raise AuthorizationDenied("candidate is not discoverable")
        allowed = {
            "session_id",
            "score",
            "relation",
            "evidence",
            "classification",
            "provenance",
        }
        if consent.get("share_display_profile"):
            allowed.update({"display_name", "topic", "domain"})
        if consent.get("share_coarse_location"):
            allowed.add("coarse_location")
        return {key: value for key, value in candidate.items() if key in allowed}

    def _decision(
        self,
        context: RequestContext,
        action: str,
        resource: ResourceRef,
        protocol_session_id: str | None,
        decision: Decision,
        reason: str,
        grant_version: int,
        correlation_id: str,
    ) -> PolicyDecision:
        return PolicyDecision(
            correlation_id=correlation_id,
            subject=context.subject,
            client_id=context.client_id,
            auth_session_id=context.auth_session_id,
            protocol_session_id=protocol_session_id,
            action=action,
            resource_kind=resource.kind,
            resource_id=resource.resource_id,
            grant_version=grant_version,
            decision=decision,
            reason=reason,
            actor_type=context.actor_type,
        )


def _require_authenticated(context: RequestContext) -> None:
    if not context.subject or not context.client_id or not context.auth_session_id:
        raise AuthenticationRequired("authenticated subject/client/session required")


def redact_decisions(decisions: Iterable[PolicyDecision]) -> list[dict[str, Any]]:
    return [safe_log_metadata(item.to_safe_dict()) for item in decisions]
