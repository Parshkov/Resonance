"""Privacy-first, transport-neutral identity/auth/consent service."""

from __future__ import annotations

import hashlib
import hmac
import math
import secrets
import time
from dataclasses import asdict, is_dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

from .backend import IdentityBackend
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


class IdentityService:
    """Single authorization/policy service for UI, WebMCP, API, and remote MCP.

    The service never accepts an actor/user id from a mutation caller.  It
    resolves the subject from an opaque credential and then checks ownership
    against the durable R11 record before touching a user-owned object.
    """

    def __init__(self, backend: IdentityBackend, *, session_ttl_seconds: int = 7 * 24 * 3600) -> None:
        if session_ttl_seconds <= 0:
            raise ValueError("session_ttl_seconds must be positive")
        self.backend = backend
        self.session_ttl_seconds = session_ttl_seconds

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
        return self.register(f"guest-{secrets.token_hex(3)}", actor_type=actor_type)

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

    def revoke_account(self, access_token: str, *, confirmed: bool) -> None:
        self._require_confirmation(confirmed)
        actor = self.authenticate(access_token)
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
        cookie_authenticated: bool = False,
        actor_type: str = "human",
    ) -> Any:
        actor = self.authenticate(access_token, actor_type=actor_type)
        if cookie_authenticated:
            self._require_csrf(actor, csrf_token)
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
        cookie_authenticated: bool = False,
        actor_type: str = "human",
    ) -> Any:
        actor, current = self._require_owned(access_token, session_id, actor_type=actor_type)
        if cookie_authenticated:
            self._require_csrf(actor, csrf_token)
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
        cookie_authenticated: bool = False,
        actor_type: str = "human",
    ) -> ConsentChoices:
        self._require_confirmation(confirmed)
        actor, current = self._require_owned(access_token, session_id, actor_type=actor_type)
        if cookie_authenticated:
            self._require_csrf(actor, csrf_token)
        current_choices = self._consent_choices(current)
        disabling_intro = current_choices.allow_intro_requests and not choices.allow_intro_requests
        if disabling_intro:
            self._append_intro_consent(actor, session_id, False)
        self.backend.update_consent(
            session_id,
            choices.to_corpus_consent(),
            expected_version=int(_field(current, "version", 0)),
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
        cookie_authenticated: bool = False,
        actor_type: str = "human",
    ) -> Any:
        actor, current = self._require_owned(access_token, session_id, actor_type=actor_type)
        if cookie_authenticated:
            self._require_csrf(actor, csrf_token)
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
        cookie_authenticated: bool = False,
        actor_type: str = "human",
    ) -> Any:
        self._require_confirmation(confirmed)
        actor, current = self._require_owned(access_token, session_id, actor_type=actor_type)
        if cookie_authenticated:
            self._require_csrf(actor, csrf_token)
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
        cookie_authenticated: bool = False,
        actor_type: str = "human",
    ) -> Any:
        self._require_confirmation(confirmed)
        actor, current = self._require_owned(access_token, session_id, actor_type=actor_type)
        if cookie_authenticated:
            self._require_csrf(actor, csrf_token)
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
    def owned_sessions(self, access_token: str, *, actor_type: str = "human") -> list[dict[str, Any]]:
        actor = self.authenticate(access_token, actor_type=actor_type)
        result: list[dict[str, Any]] = []
        for session in self.backend.list_sessions():
            if _field(session, "user_id") != actor.user_id:
                continue
            raw = _mapping(session)
            raw["consent_choices"] = self._consent_choices(session).to_corpus_consent() | {
                "allow_intro_requests": self._consent_choices(session).allow_intro_requests
            }
            result.append(raw)
        return result

    def consent_for(self, access_token: str, session_id: str, *, actor_type: str = "human") -> ConsentChoices:
        _, session = self._require_owned(access_token, session_id, actor_type=actor_type)
        return self._consent_choices(session)

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

    def _require_owned(self, access_token: str, session_id: str, *, actor_type: str) -> tuple[ActorContext, Any]:
        actor = self.authenticate(access_token, actor_type=actor_type)
        session = self.backend.get_session(session_id)
        if session is None or _field(session, "user_id") != actor.user_id:
            # Deliberately do not distinguish not-found from somebody-else's
            # object; this reduces object-enumeration signal.
            raise AuthorizationError("session unavailable to authenticated subject")
        return actor, session

    def _require_csrf(self, actor: ActorContext, csrf_token: str | None) -> None:
        if not csrf_token:
            raise CsrfError("missing CSRF token")
        state = self._active_auth_states().get(actor.auth_session_id)
        if state is None or not hmac.compare_digest(state["csrf_sha256"], _hash_secret(csrf_token)):
            raise CsrfError("invalid CSRF token")

    @staticmethod
    def _require_confirmation(confirmed: bool) -> None:
        if not confirmed:
            raise ConfirmationRequiredError("explicit user confirmation is required")

    @staticmethod
    def _normalize_location(location: Mapping[str, Any]) -> dict[str, Any]:
        # R7's current corpus shape represents city-level coarse location with
        # a synthetic centroid.  Reject accidental exact-address/GPS fields;
        # schema validation itself remains R11's responsibility.
        forbidden = {"address", "street", "postal_code", "gps", "exact_lat", "exact_lon"}
        overlap = forbidden.intersection(location)
        if overlap:
            raise IdentityValidationError(f"exact location fields are not allowed: {sorted(overlap)}")
        precision = location.get("precision")
        if precision is not None and precision != "city":
            raise IdentityValidationError("location precision must be city-level")
        coarse = dict(location)
        has_lat = "lat" in coarse
        has_lon = "lon" in coarse
        if has_lat != has_lon:
            raise IdentityValidationError("coarse location requires both lat and lon")
        if has_lat:
            lat = coarse["lat"]
            lon = coarse["lon"]
            if (
                isinstance(lat, bool)
                or isinstance(lon, bool)
                or not isinstance(lat, (int, float))
                or not isinstance(lon, (int, float))
                or not math.isfinite(float(lat))
                or not math.isfinite(float(lon))
                or not -90 <= float(lat) <= 90
                or not -180 <= float(lon) <= 180
            ):
                raise IdentityValidationError("coarse location coordinates are invalid")
            coarse["lat"] = round(float(lat), 1)
            coarse["lon"] = round(float(lon), 1)
            coarse["precision"] = "city"
        return coarse

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
