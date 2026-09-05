"""Privacy-first, transport-neutral identity/auth/consent service."""

from __future__ import annotations

import hashlib
import hmac
import math
import secrets
import time
from dataclasses import asdict, is_dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, FrozenSet, Mapping

from src.security import (
    AuthorizationDenied as SecurityAuthorizationDenied,
    ConfirmationRequired as SecurityConfirmationRequired,
    CsrfGuard,
    CsrfRejected,
    DeterministicRateLimiter,
    PayloadBounds,
    PayloadRejected,
    RequestContext,
    ResourceRef,
    SecurityPolicy,
    SessionGrantRegistry,
)

from .backend import IdentityBackend
from .pseudonyms import generate as generate_pseudonym
from .models import (
    ActorContext,
    AuthenticationError,
    AuthorizationError,
    ConfirmationRequiredError,
    ConsentChoices,
    CsrfError,
    IdentityEvent,
    IdentityValidationError,
    SessionCredentials,
)
from .security import DurableIdentityAuditTrail, IdentityPolicySource

AUTH_ISSUED = "identity.auth.issued"
AUTH_REVOKED = "identity.auth.revoked"
CONSENT_SET = "identity.consent.set"
INTRO_CONSENT_SET = "identity.intro_consent.set"
THOUGHT_CREATED = "identity.thought.created"
THOUGHT_UPDATED = "identity.thought.updated"
THOUGHT_REVOKED = "identity.thought.revoked"
THOUGHT_DELETED = "identity.thought.deleted"
ACCOUNT_REGISTERED = "identity.account.registered"
ACCOUNT_REVOKED = "identity.account.revoked"
ACCOUNT_IDENTITY_LINKED = "identity.account.identity_linked"


def _now_dt() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def _hash_secret(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _field(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, Mapping):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if hasattr(value, "to_dict"):
        return dict(value.to_dict())
    if is_dataclass(value):
        return dict(asdict(value))
    raise IdentityValidationError(f"cannot project {type(value).__name__} as mapping")


_LOCATION_KEYS = frozenset({"kind", "region", "city", "lat", "lon", "precision"})
_LOCATION_KINDS = frozenset({"synthetic_coarse", "consented_coarse"})


class IdentityService:
    """Single authorization/policy service for UI, WebMCP, API, and remote MCP.

    The service never accepts an actor/user id from a mutation caller.  It
    resolves the subject from an opaque credential and then checks ownership
    against the durable R11 record before touching a user-owned object.
    """

    def __init__(
        self,
        backend: IdentityBackend,
        *,
        session_ttl_seconds: int = 7 * 24 * 3600,
        allowed_origins: FrozenSet[str] = frozenset({"https://resonance.local"}),
        payload_bounds: PayloadBounds | None = None,
        rate_limiter: DeterministicRateLimiter | None = None,
    ) -> None:
        if session_ttl_seconds <= 0:
            raise ValueError("session_ttl_seconds must be positive")
        self.backend = backend
        self.session_ttl_seconds = session_ttl_seconds
        self.policy_source = IdentityPolicySource(backend)
        self.security_policy = SecurityPolicy(
            source=self.policy_source,
            sessions=SessionGrantRegistry(self.policy_source),
            audit=DurableIdentityAuditTrail(self.policy_source),
            limiter=rate_limiter
            or DeterministicRateLimiter(capacity=30, refill_per_second=1.0),
        )
        self.csrf_guard = CsrfGuard(allowed_origins)
        self.payload_bounds = payload_bounds or PayloadBounds()

    # -- accounts / auth -------------------------------------------------
    def register(self, display_label: str, *, actor_type: str = "human") -> SessionCredentials:
        label = display_label.strip()
        if not label or len(label) > 80:
            raise IdentityValidationError("display_label must be 1..80 characters")
        user_id = f"person-{secrets.token_hex(8)}"
        self.backend.create_user(user_id, display_label=label, avatar_placeholder=label)
        recovery_secret = secrets.token_urlsafe(32)
        self._append(
            ACCOUNT_REGISTERED,
            user_id=user_id,
            session_id=None,
            payload={"recovery_sha256": _hash_secret(recovery_secret)},
        )
        credentials = self._issue_session(user_id, actor_type=actor_type)
        return SessionCredentials(
            access_token=credentials.access_token,
            csrf_token=credentials.csrf_token,
            auth_session_id=credentials.auth_session_id,
            user_id=credentials.user_id,
            expires_at=credentials.expires_at,
            recovery_secret=recovery_secret,
        )

    def login(self, user_id: str, recovery_secret: str, *, actor_type: str = "human") -> SessionCredentials:
        user = self.backend.get_user(user_id)
        if user is None or _field(user, "revoked_at") is not None:
            raise AuthenticationError("account unavailable")
        wanted = _hash_secret(recovery_secret or "")
        registered_hash = None
        for event in self.backend.list_identity_events():
            if event.event_type == ACCOUNT_REGISTERED and event.user_id == user_id:
                registered_hash = str(event.payload.get("recovery_sha256", ""))
        if not registered_hash or not hmac.compare_digest(registered_hash, wanted):
            raise AuthenticationError("invalid account recovery credential")
        # A login always issues a new opaque session identifier/token; caller-
        # supplied session ids are never accepted, preventing fixation.
        return self._issue_session(user_id, actor_type=actor_type)

    def register_guest(self, *, actor_type: str = "human") -> SessionCredentials:
        return self.register(self.fresh_pseudonym(), actor_type=actor_type)

    def fresh_pseudonym(self) -> str:
        """A display name nobody else is using.

        The display label is what other participants see, so it must be a
        pseudonym and it must be unique. Existing labels are read from the
        backend rather than assumed, because two people meeting under the same
        name in a service built for introductions would be worse than an ugly
        name.

        A backend that cannot list its users is a wiring fault, not a runtime
        hiccup, and it is raised. Swallowing it is what let this method hand
        out names blind: every draw looked fine, and uniqueness was left to
        luck until two people collided.
        """
        lister = getattr(self.backend, "list_users", None)
        if lister is None:
            raise AttributeError(
                f"{type(self.backend).__name__} cannot list users, so a unique "
                "pseudonym cannot be chosen")
        try:
            taken = {str(_field(user, "display_label") or "") for user in lister()}
        except Exception as exc:  # noqa: BLE001 - a name is better than a failed sign-in
            print(f"[identity] could not read existing names, naming blind: "
                  f"{type(exc).__name__}: {exc}", flush=True)
            taken = set()
        return generate_pseudonym(taken)

    # -- federated sign-in ----------------------------------------------
    def find_user_by_identity(self, provider: str, subject: str) -> str | None:
        """The account a provider subject already belongs to, if any.

        The link is read from the identity event log, the same place the
        account's own credential verifier lives, so a sign-in and a recovery
        login are accounted for by one durable history.
        """
        if not provider or not subject:
            return None
        found: str | None = None
        for event in self.backend.list_identity_events():
            if event.event_type != ACCOUNT_IDENTITY_LINKED:
                continue
            if event.payload.get("provider") != provider:
                continue
            if str(event.payload.get("subject") or "") != subject:
                continue
            found = event.user_id
        if found is None:
            return None
        user = self.backend.get_user(found)
        if user is None or _field(user, "revoked_at") is not None:
            return None
        return found

    def identity_claims(self, user_id: str) -> dict[str, Any]:
        """What is known about who this account belongs to.

        Returned to a connected client through the OAuth userinfo endpoint, and
        used to reach the person when a resonance appears for them.
        """
        claims: dict[str, Any] = {}
        for event in self.backend.list_identity_events():
            if event.event_type != ACCOUNT_IDENTITY_LINKED or event.user_id != user_id:
                continue
            claims = {
                "provider": str(event.payload.get("provider") or ""),
                "email": str(event.payload.get("email") or ""),
                "email_verified": bool(event.payload.get("email_verified")),
                # The name the provider knows them by. Shown back to the person
                # so they can confirm which account they are on; never exposed
                # to another participant.
                "name": str(event.payload.get("name") or ""),
            }
        return claims

    def sign_in_federated(
        self,
        *,
        provider: str,
        subject: str,
        email: str,
        email_verified: bool,
        display_label: str,
        actor_type: str = "human",
    ) -> SessionCredentials:
        """Sign a person in behind a provider that has verified who they are.

        An unverified address is refused rather than stored: the whole point of
        an account here is that a match can be told to a real person later, and
        an address nobody has proven cannot carry that.
        """
        if not provider or not subject:
            raise IdentityValidationError("provider and subject are required")
        if not email_verified or not email:
            raise IdentityValidationError("a verified email address is required")
        existing = self.find_user_by_identity(provider, subject)
        if existing is not None:
            return self._issue_session(existing, actor_type=actor_type)
        # The provider's name is NOT the display label. The display label is
        # what other participants see, and a structural match is not consent to
        # learn someone's real name — so the account is given a pseudonym and
        # the real name is kept beside the address, where only its owner and
        # the clients they authorise can read it.
        credentials = self.register(self.fresh_pseudonym(), actor_type=actor_type)
        self._link_identity(
            credentials.user_id,
            provider=provider,
            subject=subject,
            email=email,
            email_verified=email_verified,
            name=display_label,
        )
        return credentials

    def link_identity_to_account(
        self,
        user_id: str,
        *,
        provider: str,
        subject: str,
        email: str,
        email_verified: bool,
    ) -> None:
        """Attach a provider identity to an account that already exists.

        Refused when the subject already belongs to a different account, so one
        person's provider login can never silently take over another account.
        """
        owner = self.find_user_by_identity(provider, subject)
        if owner is not None and owner != user_id:
            raise AuthorizationError("this provider identity belongs to another account")
        user = self.backend.get_user(user_id)
        if user is None or _field(user, "revoked_at") is not None:
            raise AuthenticationError("account unavailable")
        if owner == user_id:
            return
        self._link_identity(
            user_id,
            provider=provider,
            subject=subject,
            email=email,
            email_verified=email_verified,
        )

    def _link_identity(
        self,
        user_id: str,
        *,
        provider: str,
        subject: str,
        email: str,
        email_verified: bool,
        name: str = "",
    ) -> None:
        self._append(
            ACCOUNT_IDENTITY_LINKED,
            user_id=user_id,
            session_id=None,
            payload={
                "provider": provider,
                "subject": subject,
                "email": email,
                "email_verified": bool(email_verified),
                "name": str(name or ""),
            },
        )

    def authenticate(self, access_token: str, *, actor_type: str | None = None) -> ActorContext:
        if not access_token:
            raise AuthenticationError("missing access token")
        wanted = _hash_secret(access_token)
        for state in self._active_auth_states().values():
            if not hmac.compare_digest(state["token_sha256"], wanted):
                continue
            if _parse_iso(state["expires_at"]) <= _now_dt():
                raise AuthenticationError("expired access token")
            user = self.backend.get_user(state["user_id"])
            if user is None or _field(user, "revoked_at") is not None:
                raise AuthenticationError("account is revoked or missing")
            return ActorContext(
                user_id=state["user_id"],
                auth_session_id=state["auth_session_id"],
                actor_type=state["actor_type"],
            )
        raise AuthenticationError("unknown or revoked access token")

    def logout(self, access_token: str) -> None:
        actor = self.authenticate(access_token)
        self._revoke_auth_session(actor, reason="logout")

    def rotate_session(self, access_token: str, *, actor_type: str = "human") -> SessionCredentials:
        actor = self.authenticate(access_token, actor_type=actor_type)
        self._revoke_auth_session(actor, reason="rotation")
        return self._issue_session(actor.user_id, actor_type=actor.actor_type)

    def revoke_account(
        self,
        access_token: str,
        *,
        confirmed: bool,
        client_id: str = "resonance-product",
        protocol_session_id: str | None = None,
    ) -> None:
        actor = self.authenticate(access_token)
        self._authorize(
            actor,
            "account:delete",
            ResourceRef("user", actor.user_id),
            confirmed=confirmed,
            client_id=client_id,
            protocol_session_id=protocol_session_id,
        )
        # Minimize display-profile data first. If a later revocation write
        # fails, the still-authenticated user can retry without leaving PII in
        # the public-profile columns.
        self.backend.anonymize_user(actor.user_id)
        self.backend.revoke_user(actor.user_id)
        for auth in self._active_auth_states().values():
            if auth["user_id"] == actor.user_id:
                self._append(
                    AUTH_REVOKED,
                    user_id=actor.user_id,
                    session_id=auth["auth_session_id"],
                    payload={"reason": "account_revoked"},
                )
        self._append(ACCOUNT_REVOKED, user_id=actor.user_id, session_id=None, payload={})

    def export_account(
        self,
        access_token: str,
        *,
        client_id: str = "resonance-product",
        protocol_session_id: str | None = None,
    ) -> dict[str, Any]:
        """Return the authenticated owner's stored profile and Thought sessions.

        Authentication hashes and recovery material are intentionally absent.
        """
        actor = self.authenticate(access_token)
        self._authorize(
            actor,
            "account:export",
            ResourceRef("user", actor.user_id),
            confirmed=True,
            client_id=client_id,
            protocol_session_id=protocol_session_id,
        )
        user = self.backend.get_user(actor.user_id)
        return {
            "user": _mapping(user) if user is not None else None,
            "sessions": [
                _mapping(session)
                for session in self.backend.list_sessions()
                if _field(session, "user_id") == actor.user_id
            ],
        }

    # -- owned thought sessions -----------------------------------------
    def create_thought_session(
        self,
        access_token: str,
        *,
        thought_dna: Mapping[str, Any],
        location: Mapping[str, Any],
        presentation: Mapping[str, Any],
        record_kind: str = "volunteer",
        notes: str = "",
        csrf_token: str | None = None,
        origin: str | None = None,
        cookie_authenticated: bool = False,
        actor_type: str = "human",
        client_id: str = "resonance-product",
        protocol_session_id: str | None = None,
    ) -> Any:
        actor = self.authenticate(access_token, actor_type=actor_type)
        if cookie_authenticated:
            self._require_csrf(actor, csrf_token, origin)
        self._authorize(
            actor,
            "session:create",
            ResourceRef("user", actor.user_id),
            confirmed=True,
            client_id=client_id,
            protocol_session_id=protocol_session_id,
        )
        try:
            self.payload_bounds.validate_thought_dna(thought_dna)
            self.payload_bounds.validate_json(location)
            self.payload_bounds.validate_json(presentation)
        except PayloadRejected as exc:
            raise IdentityValidationError(str(exc)) from exc
        coarse_location = self._normalize_location(location)
        session_id = f"ses-{secrets.token_hex(8)}"
        stored = self.backend.create_session(
            session_id=session_id,
            user_id=actor.user_id,
            thought_dna=thought_dna,
            consent=ConsentChoices().to_corpus_consent(),
            location=coarse_location,
            presentation=dict(presentation),
            record_kind=record_kind,
            builder_id="r12-identity-consent",
            notes=notes,
        )
        self._append(
            THOUGHT_CREATED,
            user_id=actor.user_id,
            session_id=session_id,
            payload={"actor_type": actor.actor_type, "share_state": "private"},
        )
        return stored

    def update_thought_session(
        self,
        access_token: str,
        session_id: str,
        *,
        thought_dna: Mapping[str, Any],
        location: Mapping[str, Any] | None = None,
        presentation: Mapping[str, Any] | None = None,
        csrf_token: str | None = None,
        origin: str | None = None,
        cookie_authenticated: bool = False,
        actor_type: str = "human",
        client_id: str = "resonance-product",
        protocol_session_id: str | None = None,
    ) -> Any:
        actor, current = self._require_owned(
            access_token,
            session_id,
            actor_type=actor_type,
            action="session:update",
            client_id=client_id,
            protocol_session_id=protocol_session_id,
        )
        if cookie_authenticated:
            self._require_csrf(actor, csrf_token, origin)
        try:
            self.payload_bounds.validate_thought_dna(thought_dna)
            if location is not None:
                self.payload_bounds.validate_json(location)
            if presentation is not None:
                self.payload_bounds.validate_json(presentation)
        except PayloadRejected as exc:
            raise IdentityValidationError(str(exc)) from exc
        if bool(self._corpus_consent(current).get("share_thought_dna", False)):
            raise ConfirmationRequiredError(
                "revoke sharing before replacing a discoverable Thought DNA artifact"
            )
        current_location = dict(_field(current, "location", {}) or {})
        current_presentation = dict(_field(current, "presentation", {}) or {})
        next_location = (
            self._normalize_location(location)
            if location is not None
            else self._normalize_location(current_location)
        )
        consent = self._corpus_consent(current)
        stored = self.backend.create_session(
            session_id=session_id,
            user_id=actor.user_id,
            thought_dna=thought_dna,
            consent=consent,
            location=next_location,
            presentation=dict(presentation) if presentation is not None else current_presentation,
            record_kind=str(_field(current, "record_kind", "volunteer")),
            builder_id="r12-identity-consent",
            notes=str(_field(current, "notes", "")),
            expected_version=int(_field(current, "version", 0)),
        )
        self._append(
            THOUGHT_UPDATED,
            user_id=actor.user_id,
            session_id=session_id,
            payload={"actor_type": actor.actor_type},
        )
        return stored

    def set_consent(
        self,
        access_token: str,
        session_id: str,
        choices: ConsentChoices,
        *,
        confirmed: bool,
        csrf_token: str | None = None,
        origin: str | None = None,
        cookie_authenticated: bool = False,
        actor_type: str = "human",
        client_id: str = "resonance-product",
        protocol_session_id: str | None = None,
        expected_version: int | None = None,
        request_id: str | None = None,
    ) -> ConsentChoices:
        actor, current = self._require_owned(
            access_token,
            session_id,
            actor_type=actor_type,
            action="session:share",
            confirmed=confirmed,
            client_id=client_id,
            protocol_session_id=protocol_session_id,
        )
        if cookie_authenticated:
            self._require_csrf(actor, csrf_token, origin)
        current_choices = self._consent_choices(current)
        disabling_intro = current_choices.allow_intro_requests and not choices.allow_intro_requests
        if disabling_intro:
            self._append_intro_consent(actor, session_id, False)
        self.backend.update_consent(
            session_id,
            choices.to_corpus_consent(),
            expected_version=(
                int(_field(current, "version", 0))
                if expected_version is None
                else expected_version
            ),
            request_id=request_id,
        )
        self._append(
            CONSENT_SET,
            user_id=actor.user_id,
            session_id=session_id,
            payload={
                "share_thought_dna": choices.share_thought_dna,
                "share_display_profile": choices.share_display_profile,
                "share_coarse_location": choices.share_coarse_location,
                "allow_intro_requests": choices.allow_intro_requests,
                "actor_type": actor.actor_type,
            },
        )
        if not disabling_intro:
            self._append_intro_consent(
                actor,
                session_id,
                choices.allow_intro_requests,
            )
        return choices

    def update_metadata(
        self,
        access_token: str,
        session_id: str,
        *,
        location: Mapping[str, Any] | None = None,
        presentation: Mapping[str, Any] | None = None,
        csrf_token: str | None = None,
        origin: str | None = None,
        cookie_authenticated: bool = False,
        actor_type: str = "human",
        client_id: str = "resonance-product",
        protocol_session_id: str | None = None,
    ) -> Any:
        actor, current = self._require_owned(
            access_token,
            session_id,
            actor_type=actor_type,
            action="session:update",
            client_id=client_id,
            protocol_session_id=protocol_session_id,
        )
        if cookie_authenticated:
            self._require_csrf(actor, csrf_token, origin)
        try:
            if location is not None:
                self.payload_bounds.validate_json(location)
            if presentation is not None:
                self.payload_bounds.validate_json(presentation)
        except PayloadRejected as exc:
            raise IdentityValidationError(str(exc)) from exc
        if location is not None:
            location = self._normalize_location(location)
        return self.backend.update_presentation(
            session_id,
            location=dict(location) if location is not None else None,
            presentation=dict(presentation) if presentation is not None else None,
            expected_version=int(_field(current, "version", 0)),
        )

    def revoke_thought_session(
        self,
        access_token: str,
        session_id: str,
        *,
        confirmed: bool,
        csrf_token: str | None = None,
        origin: str | None = None,
        cookie_authenticated: bool = False,
        actor_type: str = "human",
        client_id: str = "resonance-product",
        protocol_session_id: str | None = None,
    ) -> Any:
        actor, current = self._require_owned(
            access_token,
            session_id,
            actor_type=actor_type,
            action="session:revoke",
            confirmed=confirmed,
            client_id=client_id,
            protocol_session_id=protocol_session_id,
        )
        if cookie_authenticated:
            self._require_csrf(actor, csrf_token, origin)
        self._append_intro_consent(actor, session_id, False)
        stored = self.backend.revoke_session(
            session_id,
            reason="user_revoked",
            expected_version=int(_field(current, "version", 0)),
        )
        self._append(
            CONSENT_SET,
            user_id=actor.user_id,
            session_id=session_id,
            payload={
                "share_thought_dna": False,
                "share_display_profile": False,
                "share_coarse_location": False,
                "allow_intro_requests": False,
                "actor_type": actor.actor_type,
            },
        )
        self._append(
            THOUGHT_REVOKED,
            user_id=actor.user_id,
            session_id=session_id,
            payload={"actor_type": actor.actor_type},
        )
        return stored

    def delete_thought_session(
        self,
        access_token: str,
        session_id: str,
        *,
        confirmed: bool,
        csrf_token: str | None = None,
        origin: str | None = None,
        cookie_authenticated: bool = False,
        actor_type: str = "human",
        client_id: str = "resonance-product",
        protocol_session_id: str | None = None,
    ) -> Any:
        actor, current = self._require_owned(
            access_token,
            session_id,
            actor_type=actor_type,
            action="session:delete",
            confirmed=confirmed,
            client_id=client_id,
            protocol_session_id=protocol_session_id,
        )
        if cookie_authenticated:
            self._require_csrf(actor, csrf_token, origin)
        self._append_intro_consent(actor, session_id, False)
        stored = self.backend.delete_session(
            session_id,
            expected_version=int(_field(current, "version", 0)),
        )
        self._append(
            CONSENT_SET,
            user_id=actor.user_id,
            session_id=session_id,
            payload={
                "share_thought_dna": False,
                "share_display_profile": False,
                "share_coarse_location": False,
                "allow_intro_requests": False,
                "actor_type": actor.actor_type,
            },
        )
        self._append(
            THOUGHT_DELETED,
            user_id=actor.user_id,
            session_id=session_id,
            payload={"actor_type": actor.actor_type},
        )
        return stored

    # -- owner views -----------------------------------------------------
    def owned_sessions(
        self,
        access_token: str,
        *,
        actor_type: str = "human",
        client_id: str = "resonance-product",
        protocol_session_id: str | None = None,
    ) -> list[dict[str, Any]]:
        actor = self.authenticate(access_token, actor_type=actor_type)
        result: list[dict[str, Any]] = []
        for session in self.backend.list_sessions():
            if _field(session, "user_id") != actor.user_id:
                continue
            self._authorize(
                actor,
                "session:read_private",
                ResourceRef("session", str(_field(session, "session_id"))),
                confirmed=True,
                client_id=client_id,
                protocol_session_id=protocol_session_id,
            )
            raw = _mapping(session)
            raw["consent_choices"] = self._consent_choices(session).to_corpus_consent() | {
                "allow_intro_requests": self._consent_choices(session).allow_intro_requests
            }
            result.append(raw)
        return result

    def consent_for(
        self,
        access_token: str,
        session_id: str,
        *,
        actor_type: str = "human",
        client_id: str = "resonance-product",
        protocol_session_id: str | None = None,
    ) -> ConsentChoices:
        _, session = self._require_owned(
            access_token,
            session_id,
            actor_type=actor_type,
            action="session:read_private",
            client_id=client_id,
            protocol_session_id=protocol_session_id,
        )
        return self._consent_choices(session)

    def authorize_discovery(
        self,
        access_token: str,
        session_id: str,
        *,
        client_id: str = "resonance-product",
        protocol_session_id: str | None = None,
    ) -> dict[str, Any]:
        """Authorize and return a consent-minimized candidate presentation."""
        actor = self.authenticate(access_token)
        resource = ResourceRef("session", session_id)
        self._authorize(
            actor,
            "discovery:read",
            resource,
            confirmed=True,
            client_id=client_id,
            protocol_session_id=protocol_session_id,
        )
        session = self.backend.get_session(session_id)
        if session is None:
            raise AuthorizationError("session unavailable to authenticated subject")
        owner_id = str(_field(session, "user_id"))
        owner = self.backend.get_user(owner_id)
        consent = self.policy_source.session_consent(session_id)
        result: dict[str, Any] = {
            "session_id": session_id,
            "thought_id": str(_mapping(_field(session, "thought_dna", {})).get("thought_id", "")),
            "presentation": _mapping(_field(session, "presentation", {})),
            "record_kind": str(_field(session, "record_kind", "")),
            "person": {
                "person_id": owner_id,
                "display_label": "anonymous",
                "avatar_placeholder": "anonymous",
            },
        }
        if consent.get("share_display_profile") and owner is not None:
            result["person"] = {
                "person_id": owner_id,
                "display_label": str(_field(owner, "display_label", "anonymous")),
                "avatar_placeholder": str(_field(owner, "avatar_placeholder", "anonymous")),
            }
        if consent.get("share_coarse_location"):
            result["location"] = _mapping(_field(session, "location", {}))
        return result

    def bind_protocol_session(
        self,
        access_token: str,
        *,
        client_id: str,
        protocol_session_id: str | None = None,
    ) -> str:
        context = self.request_context(access_token, client_id=client_id)
        checkpoint = self.security_policy.sessions.bind(
            context,
            protocol_session_id=protocol_session_id,
        )
        return checkpoint.protocol_session_id

    def request_context(self, access_token: str, *, client_id: str) -> RequestContext:
        """Resolve an authenticated transport context without caller identity claims."""
        actor = self.authenticate(access_token)
        return self._request_context(actor, client_id=client_id)

    def block_user(
        self,
        access_token: str,
        peer_id: str,
        *,
        confirmed: bool,
        csrf_token: str | None = None,
        origin: str | None = None,
        cookie_authenticated: bool = False,
        client_id: str = "resonance-product",
        protocol_session_id: str | None = None,
    ) -> None:
        actor = self.authenticate(access_token)
        if cookie_authenticated:
            self._require_csrf(actor, csrf_token, origin)
        self._authorize(
            actor,
            "security:block",
            ResourceRef("user", peer_id),
            confirmed=confirmed,
            client_id=client_id,
            protocol_session_id=protocol_session_id,
        )
        self.policy_source.block(actor.user_id, peer_id)

    def report_user(
        self,
        access_token: str,
        peer_id: str,
        reason_code: str,
        *,
        csrf_token: str | None = None,
        origin: str | None = None,
        cookie_authenticated: bool = False,
        client_id: str = "resonance-product",
        protocol_session_id: str | None = None,
    ) -> None:
        if not reason_code or len(reason_code) > 64:
            raise IdentityValidationError("reason_code must be 1..64 characters")
        actor = self.authenticate(access_token)
        if cookie_authenticated:
            self._require_csrf(actor, csrf_token, origin)
        self._authorize(
            actor,
            "security:report",
            ResourceRef("user", peer_id),
            confirmed=True,
            client_id=client_id,
            protocol_session_id=protocol_session_id,
        )
        self.policy_source.report(actor.user_id, peer_id, reason_code)

    # -- internal policy -------------------------------------------------
    def _issue_session(self, user_id: str, *, actor_type: str) -> SessionCredentials:
        if actor_type not in {"human", "agent"}:
            raise IdentityValidationError("actor_type must be human or agent")
        access_token = secrets.token_urlsafe(32)
        csrf_token = secrets.token_urlsafe(24)
        auth_session_id = f"auth-{secrets.token_hex(12)}"
        now = _now_dt()
        expires_at = _iso(now + timedelta(seconds=self.session_ttl_seconds))
        self._append(
            AUTH_ISSUED,
            user_id=user_id,
            session_id=auth_session_id,
            payload={
                "token_sha256": _hash_secret(access_token),
                "csrf_sha256": _hash_secret(csrf_token),
                "expires_at": expires_at,
                "actor_type": actor_type,
            },
            created_at=_iso(now),
        )
        return SessionCredentials(
            access_token=access_token,
            csrf_token=csrf_token,
            auth_session_id=auth_session_id,
            user_id=user_id,
            expires_at=expires_at,
        )

    def _revoke_auth_session(self, actor: ActorContext, *, reason: str) -> None:
        self._append(
            AUTH_REVOKED,
            user_id=actor.user_id,
            session_id=actor.auth_session_id,
            payload={"reason": reason},
        )

    def _active_auth_states(self) -> dict[str, dict[str, str]]:
        states: dict[str, dict[str, str]] = {}
        for event in self.backend.list_identity_events():
            if event.event_type == AUTH_ISSUED and event.session_id and event.user_id:
                states[event.session_id] = {
                    "auth_session_id": event.session_id,
                    "user_id": event.user_id,
                    "token_sha256": str(event.payload.get("token_sha256", "")),
                    "csrf_sha256": str(event.payload.get("csrf_sha256", "")),
                    "expires_at": str(event.payload.get("expires_at", "")),
                    "actor_type": str(event.payload.get("actor_type", "human")),
                }
            elif event.event_type == AUTH_REVOKED and event.session_id:
                states.pop(event.session_id, None)
        return states

    def _latest_intro_consent(self, session_id: str) -> bool:
        value = False
        for event in self.backend.list_identity_events():
            if event.event_type in {CONSENT_SET, INTRO_CONSENT_SET} and event.session_id == session_id:
                value = bool(event.payload.get("allow_intro_requests", False))
        return value

    def _consent_choices(self, session: Any) -> ConsentChoices:
        session_id = str(_field(session, "session_id"))
        return ConsentChoices.from_corpus_and_intro(
            self._corpus_consent(session),
            allow_intro_requests=self._latest_intro_consent(session_id),
        )

    @staticmethod
    def _corpus_consent(session: Any) -> dict[str, Any]:
        raw = _field(session, "consent", {})
        if isinstance(raw, Mapping):
            return dict(raw)
        if hasattr(raw, "to_dict"):
            return dict(raw.to_dict())
        return {
            "share_enabled": bool(_field(raw, "share_enabled", False)),
            "share_thought_dna": bool(_field(raw, "share_thought_dna", False)),
            "share_coarse_location": bool(_field(raw, "share_coarse_location", False)),
            "share_display_profile": bool(_field(raw, "share_display_profile", False)),
        }

    def _require_owned(
        self,
        access_token: str,
        session_id: str,
        *,
        actor_type: str,
        action: str,
        confirmed: bool = True,
        client_id: str,
        protocol_session_id: str | None,
    ) -> tuple[ActorContext, Any]:
        actor = self.authenticate(access_token, actor_type=actor_type)
        self._authorize(
            actor,
            action,
            ResourceRef("session", session_id),
            confirmed=confirmed,
            client_id=client_id,
            protocol_session_id=protocol_session_id,
        )
        session = self.backend.get_session(session_id)
        if session is None or _field(session, "user_id") != actor.user_id:
            # Deliberately do not distinguish not-found from somebody-else's
            # object; this reduces object-enumeration signal.
            raise AuthorizationError("session unavailable to authenticated subject")
        return actor, session

    def _require_csrf(
        self,
        actor: ActorContext,
        csrf_token: str | None,
        origin: str | None,
    ) -> None:
        state = self._active_auth_states().get(actor.auth_session_id)
        try:
            self.csrf_guard.validate(
                cookie_authenticated=True,
                origin=origin,
                csrf_token=csrf_token,
                expected_csrf_digest=(state or {}).get("csrf_sha256"),
            )
        except CsrfRejected as exc:
            raise CsrfError(str(exc)) from exc

    @staticmethod
    def _request_context(actor: ActorContext, *, client_id: str) -> RequestContext:
        return RequestContext(
            subject=actor.user_id,
            client_id=client_id,
            auth_session_id=actor.auth_session_id,
            actor_type=actor.actor_type,
        )

    def _authorize(
        self,
        actor: ActorContext,
        action: str,
        resource: ResourceRef,
        *,
        confirmed: bool,
        client_id: str,
        protocol_session_id: str | None,
    ) -> None:
        try:
            self.security_policy.authorize(
                self._request_context(actor, client_id=client_id),
                action,
                resource,
                confirmed=confirmed,
                protocol_session_id=protocol_session_id,
            )
        except SecurityConfirmationRequired as exc:
            raise ConfirmationRequiredError(str(exc)) from exc
        except SecurityAuthorizationDenied as exc:
            raise AuthorizationError(str(exc)) from exc

    @staticmethod
    def _require_confirmation(confirmed: bool) -> None:
        if not confirmed:
            raise ConfirmationRequiredError("explicit user confirmation is required")

    @staticmethod
    def _normalize_location(location: Mapping[str, Any]) -> dict[str, Any]:
        """Exact-allowlist city-level coarse location (R12 review hardening).

        An empty object means no location was supplied. Otherwise the key set
        must be exactly {kind, region, city, lat, lon, precision}: an arbitrary
        extra field could smuggle precise data or create a durable row that
        later breaks the R11 presentation projection. Coordinates are bounded,
        finite and rounded to one decimal.
        """
        if not isinstance(location, Mapping):
            raise IdentityValidationError("location must be an object")
        if not location:
            return {}
        keys = set(location)
        missing = sorted(_LOCATION_KEYS - keys)
        unknown = sorted(keys - _LOCATION_KEYS)
        if missing:
            raise IdentityValidationError(f"location missing required fields: {missing}")
        if unknown:
            raise IdentityValidationError(f"location contains unknown fields: {unknown}")
        if location.get("kind") not in _LOCATION_KINDS:
            raise IdentityValidationError(f"location.kind must be one of {sorted(_LOCATION_KINDS)}")
        if location.get("precision") != "city":
            raise IdentityValidationError("location precision must be city-level")
        for field in ("region", "city"):
            value = location.get(field)
            if not isinstance(value, str) or not value.strip():
                raise IdentityValidationError(f"location.{field} must be a non-empty string")
        lat, lon = location["lat"], location["lon"]
        if (
            isinstance(lat, bool) or isinstance(lon, bool)
            or not isinstance(lat, (int, float)) or not isinstance(lon, (int, float))
            or not math.isfinite(float(lat)) or not math.isfinite(float(lon))
            or not -90 <= float(lat) <= 90 or not -180 <= float(lon) <= 180
        ):
            raise IdentityValidationError("coarse location coordinates are invalid")
        return {
            "kind": location["kind"], "region": location["region"], "city": location["city"],
            "lat": round(float(lat), 1), "lon": round(float(lon), 1), "precision": "city",
        }

    def _append_intro_consent(
        self,
        actor: ActorContext,
        session_id: str,
        allowed: bool,
    ) -> None:
        self._append(
            INTRO_CONSENT_SET,
            user_id=actor.user_id,
            session_id=session_id,
            payload={
                "allow_intro_requests": bool(allowed),
                "actor_type": actor.actor_type,
            },
        )

    def _append(
        self,
        event_type: str,
        *,
        user_id: str | None,
        session_id: str | None,
        payload: Mapping[str, Any],
        created_at: str | None = None,
    ) -> None:
        self.backend.append_identity_event(
            IdentityEvent(
                event_id=f"ievt-{time.time_ns():020d}-{secrets.token_hex(4)}",
                event_type=event_type,
                user_id=user_id,
                session_id=session_id,
                payload=dict(payload),
                created_at=created_at or _iso(_now_dt()),
            )
        )
