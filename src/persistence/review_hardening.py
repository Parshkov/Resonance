"""Focused hardening for independent R11/R12 exact-head review findings.

This module keeps the recovery diff small while closing repository-boundary
failures discovered by the independent Fable review:

* backend uniqueness violations must never escape as raw driver exceptions;
* malformed presentation/location state must be rejected before durable writes
  and must not make a process permanently unbootable after restart; and
* credential-verifier/auth-session events must not enter the public audit view.

`install()` patches the already-defined R11 classes in place at package import.
That preserves the public class identities/import paths consumed by R12/R12B
while keeping the review recovery isolated and easy to remove once the R11
implementation is consolidated on main.
"""

from __future__ import annotations

import math
import sqlite3
from dataclasses import replace
from typing import Any, Mapping

from .errors import (
    PersistenceConflictError,
    PersistenceStateError,
    PersistenceValidationError,
)
from .postgres_store import PostgresRepository
from .service import LiveCorpusService
from .sqlite_store import SQLiteRepository

_INSTALLED = False

_LOCATION_KEYS = frozenset({"kind", "region", "city", "lat", "lon", "precision"})
_PRESENTATION_KEYS = frozenset({"domain", "topic", "cluster_id"})
_LOCATION_KINDS = frozenset({"synthetic_coarse", "consented_coarse"})
_PRIVATE_AUDIT_EVENT_TYPES = frozenset({"identity.account.registered"})


def _consent_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if hasattr(value, "to_dict"):
        return dict(value.to_dict())
    return {
        "share_enabled": bool(getattr(value, "share_enabled", False)),
        "share_thought_dna": bool(getattr(value, "share_thought_dna", False)),
        "share_coarse_location": bool(getattr(value, "share_coarse_location", False)),
        "share_display_profile": bool(getattr(value, "share_display_profile", False)),
    }


def _validate_location(location: Mapping[str, Any], *, share_coarse_location: bool) -> None:
    if not isinstance(location, Mapping):
        raise PersistenceValidationError("location must be an object")
    if not location:
        if share_coarse_location:
            raise PersistenceValidationError(
                "share_coarse_location requires a complete city-level location"
            )
        return

    keys = set(location)
    missing = sorted(_LOCATION_KEYS - keys)
    unknown = sorted(keys - _LOCATION_KEYS)
    if missing:
        raise PersistenceValidationError(f"location missing required fields: {missing}")
    if unknown:
        raise PersistenceValidationError(f"location contains unknown fields: {unknown}")
    if location.get("kind") not in _LOCATION_KINDS:
        raise PersistenceValidationError(
            f"location.kind must be one of {sorted(_LOCATION_KINDS)}"
        )
    if location.get("precision") != "city":
        raise PersistenceValidationError("location.precision must be 'city'")
    for field in ("region", "city"):
        if not isinstance(location.get(field), str) or not str(location[field]).strip():
            raise PersistenceValidationError(f"location.{field} must be a non-empty string")
    for field, lo, hi in (("lat", -90.0, 90.0), ("lon", -180.0, 180.0)):
        value = location.get(field)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise PersistenceValidationError(f"location.{field} must be a finite number")
        number = float(value)
        if not math.isfinite(number) or number < lo or number > hi:
            raise PersistenceValidationError(
                f"location.{field} must be finite and within [{lo}, {hi}]"
            )
        if round(number, 1) != number:
            raise PersistenceValidationError(
                f"location.{field} must be rounded to 0.1 degree (city-level)"
            )


def _validate_presentation(presentation: Mapping[str, Any]) -> None:
    if not isinstance(presentation, Mapping):
        raise PersistenceValidationError("presentation must be an object")
    keys = set(presentation)
    missing = sorted(_PRESENTATION_KEYS - keys)
    unknown = sorted(keys - _PRESENTATION_KEYS)
    if missing:
        raise PersistenceValidationError(f"presentation missing required fields: {missing}")
    if unknown:
        raise PersistenceValidationError(f"presentation contains unknown fields: {unknown}")
    for field in _PRESENTATION_KEYS:
        if not isinstance(presentation.get(field), str) or not str(presentation[field]).strip():
            raise PersistenceValidationError(
                f"presentation.{field} must be a non-empty string"
            )


def _validate_projection_parts(
    *,
    consent: Any,
    location: Mapping[str, Any],
    presentation: Mapping[str, Any],
) -> None:
    consent_map = _consent_mapping(consent)
    _validate_location(
        location,
        share_coarse_location=bool(consent_map.get("share_coarse_location", False)),
    )
    _validate_presentation(presentation)


def _validate_stored_session(session: Any) -> None:
    try:
        _validate_projection_parts(
            consent=session.consent,
            location=session.location,
            presentation=session.presentation,
        )
    except PersistenceValidationError as exc:
        raise PersistenceStateError(
            f"stored session {session.session_id!r} is not R7-projectable: {exc}"
        ) from exc


def _postgres_unique_violation(exc: BaseException) -> bool:
    code = getattr(exc, "sqlstate", None) or getattr(exc, "pgcode", None)
    if code == "23505":
        return True
    return "duplicate key value violates unique constraint" in str(exc).lower()


def _is_private_public_audit_event(event_type: str) -> bool:
    return event_type.startswith("identity.auth.") or event_type in _PRIVATE_AUDIT_EVENT_TYPES


def install() -> None:
    """Install focused recovery guards once, preserving existing class identities."""
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    sqlite_put_session = SQLiteRepository.put_session
    postgres_put_session = PostgresRepository.put_session
    service_init = LiveCorpusService.__init__
    service_health = LiveCorpusService.health
    service_create = LiveCorpusService.create_session
    service_update_presentation = LiveCorpusService.update_presentation
    service_update_consent = LiveCorpusService.update_consent
    service_rebuild = LiveCorpusService.rebuild_index
    service_public_view = LiveCorpusService.public_session_view
    service_audit_log = LiveCorpusService.audit_log

    def guarded_sqlite_put_session(self, session, **kwargs):
        try:
            return sqlite_put_session(self, session, **kwargs)
        except sqlite3.IntegrityError as exc:
            raise PersistenceConflictError(
                "session identifier or thought_id conflicts with durable state"
            ) from exc

    def guarded_postgres_put_session(self, session, **kwargs):
        try:
            return postgres_put_session(self, session, **kwargs)
        except Exception as exc:
            if _postgres_unique_violation(exc):
                raise PersistenceConflictError(
                    "session identifier or thought_id conflicts with durable state"
                ) from exc
            raise

    def guarded_init(self, *args, **kwargs):
        try:
            service_init(self, *args, **kwargs)
            self._startup_degraded_reason = None
        except PersistenceStateError as exc:
            # Base __init__ initializes repo/lock/engine/registry before calling
            # rebuild_index. Keep the object alive in a fail-closed degraded
            # state so an authorized repair/revoke path can recover the bad row.
            self._serving_generation = None
            self._startup_degraded_reason = str(exc)

    def guarded_health(self):
        health = service_health(self)
        reason = getattr(self, "_startup_degraded_reason", None)
        if not reason:
            return health
        return replace(
            health,
            details={**dict(health.details), "degraded_reason": reason},
        )

    def guarded_create_session(self, **kwargs):
        consent = kwargs.get("consent")
        location = kwargs.get("location")
        presentation = kwargs.get("presentation")
        _validate_projection_parts(
            consent=consent,
            location=location,
            presentation=presentation,
        )

        thought = kwargs.get("thought_dna")
        session_id = kwargs.get("session_id")
        thought_id = thought.get("thought_id") if isinstance(thought, Mapping) else None
        if isinstance(thought_id, str):
            prior = self.repo.get_session_by_thought(thought_id)
            if prior is not None and prior.session_id != session_id:
                # v0.1 policy: a durable thought_id is never rebound to a new
                # session, including after deletion. Re-sharing requires a new
                # Thought DNA id, preserving tombstone/history semantics.
                raise PersistenceConflictError(
                    "thought_id is already reserved; a new session (including "
                    "re-share after delete) requires a new Thought DNA id"
                )
        return service_create(self, **kwargs)

    def guarded_update_presentation(self, session_id, **kwargs):
        current = self.repo.get_session(session_id)
        if current is not None:
            next_location = (
                kwargs.get("location")
                if kwargs.get("location") is not None
                else current.location
            )
            next_presentation = (
                kwargs.get("presentation")
                if kwargs.get("presentation") is not None
                else current.presentation
            )
            _validate_projection_parts(
                consent=current.consent,
                location=next_location,
                presentation=next_presentation,
            )
        return service_update_presentation(self, session_id, **kwargs)

    def guarded_update_consent(self, session_id, consent, **kwargs):
        current = self.repo.get_session(session_id)
        if current is not None:
            _validate_projection_parts(
                consent=consent,
                location=current.location,
                presentation=current.presentation,
            )
        return service_update_consent(self, session_id, consent, **kwargs)

    def guarded_rebuild_index(self):
        try:
            for session in self.repo.list_discoverable_sessions():
                user = self.repo.get_user(session.user_id)
                if user is None or user.hidden:
                    continue
                _validate_stored_session(session)
            result = service_rebuild(self)
            self._startup_degraded_reason = None
            return result
        except PersistenceStateError as exc:
            self._serving_generation = None
            self._startup_degraded_reason = str(exc)
            raise

    def guarded_public_session_view(self, session_id):
        session = self.repo.get_session(session_id)
        if session is not None and session.is_discoverable():
            _validate_stored_session(session)
        return service_public_view(self, session_id)

    def guarded_audit_log(self):
        # The durable audit table is also the R12 identity-event backing store.
        # Authentication verifier hashes and auth-session identifiers are
        # internal security state, not public audit data. Internal identity
        # replay uses repo.list_audit() directly and is therefore unaffected.
        public_rows = []
        for row in service_audit_log(self):
            event_type = str(row.get("event_type", ""))
            if _is_private_public_audit_event(event_type):
                continue
            public_rows.append(row)
        return public_rows

    SQLiteRepository.put_session = guarded_sqlite_put_session
    PostgresRepository.put_session = guarded_postgres_put_session
    LiveCorpusService.__init__ = guarded_init
    LiveCorpusService.health = guarded_health
    LiveCorpusService.create_session = guarded_create_session
    LiveCorpusService.update_presentation = guarded_update_presentation
    LiveCorpusService.update_consent = guarded_update_consent
    LiveCorpusService.rebuild_index = guarded_rebuild_index
    LiveCorpusService.public_session_view = guarded_public_session_view
    LiveCorpusService.audit_log = guarded_audit_log
