"""Transport-neutral identity, authentication, and consent types for Resonance."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

IDENTITY_CONTRACT_VERSION = "resonance-identity/0.1"


class IdentityError(RuntimeError):
    """Base class for identity-layer failures."""


class AuthenticationError(IdentityError):
    """Credential is missing, expired, revoked, or unknown."""


class AuthorizationError(IdentityError):
    """Authenticated subject does not own the requested object."""


class CsrfError(IdentityError):
    """Cookie-authenticated mutation did not prove same-origin intent."""


class ConfirmationRequiredError(IdentityError):
    """A sensitive state change was requested without visible confirmation."""


class IdentityValidationError(IdentityError):
    """Identity/consent input is invalid or unsafe."""


@dataclass(frozen=True, slots=True)
class ActorContext:
    user_id: str
    auth_session_id: str
    actor_type: str = "human"


@dataclass(frozen=True, slots=True)
class SessionCredentials:
    access_token: str
    csrf_token: str
    auth_session_id: str
    user_id: str
    expires_at: str
    recovery_secret: str | None = None

    @property
    def cookie_policy(self) -> Mapping[str, Any]:
        """Required browser-cookie attributes; the CSRF token is sent separately."""
        return {
            "secure": True,
            "http_only": True,
            "same_site": "Strict",
            "path": "/",
        }


@dataclass(frozen=True, slots=True)
class ConsentChoices:
    share_thought_dna: bool = False
    share_display_profile: bool = False
    share_coarse_location: bool = False
    allow_intro_requests: bool = False

    def to_corpus_consent(self) -> dict[str, bool]:
        """Exact projection to the R11/R7 consent contract.

        Collaboration availability is intentionally NOT a structural-index flag;
        it stays in the identity layer and can gate intro actions later.
        """
        return {
            "share_enabled": bool(self.share_thought_dna),
            "share_thought_dna": bool(self.share_thought_dna),
            "share_coarse_location": bool(self.share_coarse_location),
            "share_display_profile": bool(self.share_display_profile),
        }

    @classmethod
    def from_corpus_and_intro(
        cls,
        corpus: Mapping[str, Any],
        *,
        allow_intro_requests: bool,
    ) -> "ConsentChoices":
        return cls(
            share_thought_dna=bool(corpus.get("share_thought_dna", False)),
            share_display_profile=bool(corpus.get("share_display_profile", False)),
            share_coarse_location=bool(corpus.get("share_coarse_location", False)),
            allow_intro_requests=bool(allow_intro_requests),
        )


@dataclass(frozen=True, slots=True)
class IdentityEvent:
    event_id: str
    event_type: str
    user_id: str | None
    session_id: str | None
    payload: Mapping[str, Any]
    created_at: str
