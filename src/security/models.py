"""Transport-neutral security policy types for the Resonance hosted pilot."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, FrozenSet, Mapping

SECURITY_CONTRACT_VERSION = "resonance-security/0.1"


class SecurityError(RuntimeError):
    """Base class for fail-closed security failures."""


class AuthenticationRequired(SecurityError):
    """A protected operation has no authenticated subject."""


class AuthorizationDenied(SecurityError):
    """The authoritative server-side policy denied an operation."""


class SessionBindingError(AuthorizationDenied):
    """A protocol session does not belong to the current subject/client."""


class ConfirmationRequired(AuthorizationDenied):
    """A sensitive write lacks an explicit human confirmation checkpoint."""


class CsrfRejected(AuthorizationDenied):
    """A cookie-authenticated write failed same-origin/CSRF validation."""


class RateLimitExceeded(AuthorizationDenied):
    """A deterministic action quota was exhausted."""


class PayloadRejected(SecurityError):
    """Untrusted input violates a size/shape/content safety bound."""


class OAuthGrantError(SecurityError):
    """OAuth authorization-code issuance or exchange failed closed."""


class Decision(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    CONFIRM = "confirm"


@dataclass(frozen=True, slots=True)
class RequestContext:
    """Authenticated context supplied by the transport authentication layer.

    ``token_scopes`` are never authoritative.  They may narrow a server-side
    grant, but they can never widen one.
    """

    subject: str
    client_id: str
    auth_session_id: str
    actor_type: str = "human"
    token_scopes: FrozenSet[str] = field(default_factory=frozenset)


@dataclass(frozen=True, slots=True)
class ResourceRef:
    """Opaque resource locator supplied by a client/transport.

    Ownership, workspace membership, and peer identity are deliberately NOT
    accepted here.  The server resolves them from :class:`PolicySource`.
    """

    kind: str
    resource_id: str


@dataclass(frozen=True, slots=True)
class GrantCheckpoint:
    protocol_session_id: str
    subject: str
    client_id: str
    grant_version: int
    expires_at: float


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    correlation_id: str
    subject: str
    client_id: str
    auth_session_id: str
    protocol_session_id: str | None
    action: str
    resource_kind: str
    resource_id: str
    grant_version: int
    decision: Decision
    reason: str
    actor_type: str = "human"

    def to_safe_dict(self) -> dict[str, Any]:
        """Audit-safe projection.  Private content/tokens are not fields here."""
        return {
            "correlation_id": self.correlation_id,
            "subject": self.subject,
            "client_id": self.client_id,
            "auth_session_id": self.auth_session_id,
            "protocol_session_id": self.protocol_session_id,
            "action": self.action,
            "resource_kind": self.resource_kind,
            "resource_id": self.resource_id,
            "grant_version": self.grant_version,
            "decision": self.decision.value,
            "reason": self.reason,
            "actor_type": self.actor_type,
        }


@dataclass(frozen=True, slots=True)
class UntrustedContent:
    """Explicit boundary object for content originating from another user."""

    text: str
    rendered_text: str
    untrusted_content: bool = True

    def tool_metadata(self) -> Mapping[str, bool]:
        return {"untrustedContentHint": True}


@dataclass(frozen=True, slots=True)
class AuthorizationCodeRecord:
    code: str
    subject: str
    client_id: str
    redirect_uri: str
    code_challenge: str
    resource: str
    audience: str
    expires_at: float
