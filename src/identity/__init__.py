"""R12 privacy-first identity/auth/consent service."""

from .adapters import BearerAgentAdapter, ManualUIAdapter, WebMCPAdapter
from .backend import IdentityBackend, R11IdentityBackend
from .models import (
    IDENTITY_CONTRACT_VERSION,
    ActorContext,
    AuthenticationError,
    AuthorizationError,
    ConfirmationRequiredError,
    ConsentChoices,
    CsrfError,
    IdentityError,
    IdentityValidationError,
    SessionCredentials,
)
from .service import IdentityService
from .review_hardening import install as _install_review_hardening

_install_review_hardening()
del _install_review_hardening

__all__ = [
    "IDENTITY_CONTRACT_VERSION",
    "ActorContext",
    "AuthenticationError",
    "AuthorizationError",
    "BearerAgentAdapter",
    "ConfirmationRequiredError",
    "ConsentChoices",
    "CsrfError",
    "IdentityBackend",
    "IdentityError",
    "IdentityService",
    "IdentityValidationError",
    "ManualUIAdapter",
    "R11IdentityBackend",
    "SessionCredentials",
    "WebMCPAdapter",
]
