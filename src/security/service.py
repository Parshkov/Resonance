"""Small mutation facade for block/report and protected writes.

State mutation remains delegated to the authoritative policy source adapter;
this service only enforces authorization/confirmation and records safe audit
provenance.  R11/R12 adapters can implement these methods over durable state.
"""

from __future__ import annotations

from typing import Any, Protocol

from .models import RequestContext, ResourceRef
from .policy import SecurityPolicy


class MutablePolicySource(Protocol):
    def block(self, subject: str, peer_id: str) -> None: ...
    def report(self, subject: str, peer_id: str, reason_code: str) -> None: ...


class SecurityService:
    def __init__(self, policy: SecurityPolicy, source: MutablePolicySource) -> None:
        self.policy = policy
        self.source = source

    def block_user(
        self,
        context: RequestContext,
        peer_id: str,
        *,
        confirmed: bool,
        protocol_session_id: str | None = None,
    ) -> dict[str, Any]:
        resource = ResourceRef(kind="user", resource_id=peer_id)
        decision = self.policy.authorize(
            context,
            "security:block",
            resource,
            confirmed=confirmed,
            protocol_session_id=protocol_session_id,
        )
        self.source.block(context.subject, peer_id)
        return decision.to_safe_dict()

    def report_user(
        self,
        context: RequestContext,
        peer_id: str,
        reason_code: str,
        *,
        protocol_session_id: str | None = None,
    ) -> dict[str, Any]:
        if not reason_code or len(reason_code) > 64:
            raise ValueError("reason_code must be 1..64 characters")
        resource = ResourceRef(kind="user", resource_id=peer_id)
        decision = self.policy.authorize(
            context,
            "security:report",
            resource,
            confirmed=True,
            protocol_session_id=protocol_session_id,
        )
        self.source.report(context.subject, peer_id, reason_code)
        return decision.to_safe_dict()
