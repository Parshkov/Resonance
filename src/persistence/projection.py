"""R7 projection validation for durable session rows.

Consolidated from the R11/R12 review-hardening shims (which used to patch the
service classes at import time). A private prepared row may stay sparse until
the explicit share transition; a row becoming discoverable must satisfy the
complete R7 projection contract (city-level coarse location, full presentation).
"""

from __future__ import annotations

import math
from typing import Any, Mapping

from .errors import PersistenceStateError, PersistenceValidationError

LOCATION_KEYS = frozenset({"kind", "region", "city", "lat", "lon", "precision"})
PRESENTATION_KEYS = frozenset({"domain", "topic", "cluster_id"})
LOCATION_KINDS = frozenset({"synthetic_coarse", "consented_coarse"})
PRIVATE_AUDIT_EVENT_TYPES = frozenset({"identity.account.registered"})


def consent_mapping(value: Any) -> dict[str, Any]:
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


def discoverable_consent(consent: Any) -> bool:
    mapping = consent_mapping(consent)
    return bool(mapping.get("share_enabled", False)) and bool(mapping.get("share_thought_dna", False))


def validate_location(location: Mapping[str, Any], *, share_coarse_location: bool) -> None:
    if not isinstance(location, Mapping):
        raise PersistenceValidationError("location must be an object")
    if not location:
        if share_coarse_location:
            raise PersistenceValidationError("share_coarse_location requires a complete city-level location")
        return
    keys = set(location)
    missing = sorted(LOCATION_KEYS - keys)
    unknown = sorted(keys - LOCATION_KEYS)
    if missing:
        raise PersistenceValidationError(f"location missing required fields: {missing}")
    if unknown:
        raise PersistenceValidationError(f"location contains unknown fields: {unknown}")
    if location.get("kind") not in LOCATION_KINDS:
        raise PersistenceValidationError(f"location.kind must be one of {sorted(LOCATION_KINDS)}")
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
            raise PersistenceValidationError(f"location.{field} must be finite and within [{lo}, {hi}]")
        if round(number, 1) != number:
            raise PersistenceValidationError(f"location.{field} must be rounded to 0.1 degree (city-level)")


def validate_presentation(presentation: Mapping[str, Any]) -> None:
    if not isinstance(presentation, Mapping):
        raise PersistenceValidationError("presentation must be an object")
    keys = set(presentation)
    missing = sorted(PRESENTATION_KEYS - keys)
    unknown = sorted(keys - PRESENTATION_KEYS)
    if missing:
        raise PersistenceValidationError(f"presentation missing required fields: {missing}")
    if unknown:
        raise PersistenceValidationError(f"presentation contains unknown fields: {unknown}")
    for field in PRESENTATION_KEYS:
        if not isinstance(presentation.get(field), str) or not str(presentation[field]).strip():
            raise PersistenceValidationError(f"presentation.{field} must be a non-empty string")


def validate_projection_parts(*, consent: Any, location: Mapping[str, Any], presentation: Mapping[str, Any]) -> None:
    """Private rows may omit presentation; discoverable rows need the full projection."""
    consent_map = consent_mapping(consent)
    validate_location(location, share_coarse_location=bool(consent_map.get("share_coarse_location", False)))
    if discoverable_consent(consent) or presentation:
        validate_presentation(presentation)


def validate_stored_session(session: Any) -> None:
    try:
        validate_projection_parts(consent=session.consent, location=session.location,
                                  presentation=session.presentation)
    except PersistenceValidationError as exc:
        raise PersistenceStateError(f"stored session {session.session_id!r} is not R7-projectable: {exc}") from exc


def postgres_unique_violation(exc: BaseException) -> bool:
    code = getattr(exc, "sqlstate", None) or getattr(exc, "pgcode", None)
    if code == "23505":
        return True
    return "duplicate key value violates unique constraint" in str(exc).lower()


def is_private_audit_event(event_type: str) -> bool:
    return event_type.startswith("identity.auth.") or event_type in PRIVATE_AUDIT_EVENT_TYPES
