"""Focused R12 hardening for the independent Fable exact-head review.

The original recovery correctly bounds and rounds coordinates, but its denylist
still permitted incomplete R7 location objects and arbitrary extra fields. That
could both smuggle precise data and create a durable row that later crashes the
R11 presentation projection. This module installs an exact allowlist while
preserving the existing coordinate normalization behavior.
"""

from __future__ import annotations

from typing import Any, Mapping

from .models import IdentityValidationError
from .service import IdentityService

_INSTALLED = False
_LOCATION_KEYS = frozenset({"kind", "region", "city", "lat", "lon", "precision"})
_LOCATION_KINDS = frozenset({"synthetic_coarse", "consented_coarse"})


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    original_normalize = IdentityService._normalize_location

    def strict_normalize(location: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(location, Mapping):
            raise IdentityValidationError("location must be an object")
        # Privacy minimization: location is optional. An empty object means the
        # user has not supplied location data at all. R11 separately prevents
        # enabling share_coarse_location until a complete coarse location exists.
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
            raise IdentityValidationError(
                f"location.kind must be one of {sorted(_LOCATION_KINDS)}"
            )
        if location.get("precision") != "city":
            raise IdentityValidationError("location precision must be city-level")
        for field in ("region", "city"):
            value = location.get(field)
            if not isinstance(value, str) or not value.strip():
                raise IdentityValidationError(
                    f"location.{field} must be a non-empty string"
                )

        # Reuse the already-reviewed bounds/finite checks and deterministic
        # one-decimal rounding. Because the key set is now exact, no hidden
        # precise payload can survive in an arbitrary extra field.
        coarse = original_normalize(location)
        if set(coarse) != set(_LOCATION_KEYS):
            raise IdentityValidationError("normalized location shape is not canonical")
        return coarse

    IdentityService._normalize_location = staticmethod(strict_normalize)
