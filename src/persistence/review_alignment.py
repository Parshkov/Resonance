"""Cross-layer R11 alignment hardening discovered during R12C review.

Private prepared sessions must be allowed to remain sparse until the explicit
share transition, while any session becoming discoverable must still satisfy
the complete R7 projection contract.  This module also preserves optimistic
concurrency precedence for already-stale metadata writes: a request that cannot
possibly commit reports the stale-version conflict before validating replacement
metadata, while the repository transaction remains the authoritative race guard.
"""

from __future__ import annotations

from typing import Any

from .errors import PersistenceConflictError
from .service import LiveCorpusService
from . import review_hardening as _hardening

_INSTALLED = False


def _discoverable_consent(consent: Any) -> bool:
    mapping = _hardening._consent_mapping(consent)
    return bool(mapping.get("share_enabled", False)) and bool(
        mapping.get("share_thought_dna", False)
    )


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    original_validate = _hardening._validate_projection_parts
    original_update_presentation = LiveCorpusService.update_presentation

    def validate_projection_parts(*, consent, location, presentation) -> None:
        # Private rows are durable preparation state, not public R7 projection.
        # They may omit presentation entirely. If either location or presentation
        # is supplied, its shape is still validated; the complete projection is
        # mandatory at the transition to discoverable state.
        if not _discoverable_consent(consent):
            consent_map = _hardening._consent_mapping(consent)
            _hardening._validate_location(
                location,
                share_coarse_location=bool(
                    consent_map.get("share_coarse_location", False)
                ),
            )
            if presentation:
                _hardening._validate_presentation(presentation)
            return
        original_validate(
            consent=consent,
            location=location,
            presentation=presentation,
        )

    def update_presentation(self, session_id, **kwargs):
        expected_version = kwargs.get("expected_version")
        request_id = kwargs.get("request_id")
        if expected_version is not None:
            current = self.repo.get_session(session_id)
            if current is not None and int(current.version) != int(expected_version):
                # Durable idempotent replay must run before stale-version rejection.
                # If a request_id is present, delegate to the normal service path:
                # it first resolves same-key/same-payload replay (or key collision),
                # then reaches the authoritative repository version check on a miss.
                if request_id is None:
                    raise PersistenceConflictError(
                        f"stale session version for {session_id!r}"
                    )
        return original_update_presentation(self, session_id, **kwargs)

    # The existing hardening wrappers resolve this module-global function at
    # call time, so replacing it updates create/update/consent validation without
    # replacing their class identities or bypassing repository transaction guards.
    _hardening._validate_projection_parts = validate_projection_parts
    LiveCorpusService.update_presentation = update_presentation
