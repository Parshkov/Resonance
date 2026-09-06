"""Focused regressions for the second independent R12 exact-head review."""

from __future__ import annotations

import unittest

from src.identity import IdentityService, IdentityValidationError

VALID_LOCATION = {
    "kind": "consented_coarse",
    "region": "California",
    "city": "San Diego",
    "lat": 32.715736,
    "lon": -117.161087,
    "precision": "city",
}


class StrictLocationBoundaryTests(unittest.TestCase):
    def test_empty_location_is_valid_privacy_minimized_state(self):
        self.assertEqual(IdentityService._normalize_location({}), {})

    def test_missing_r7_required_fields_are_rejected(self):
        with self.assertRaisesRegex(IdentityValidationError, "missing required fields"):
            IdentityService._normalize_location(
                {"city": "Moscow", "lat": 55.8, "lon": 37.6}
            )

    def test_unknown_field_cannot_smuggle_precise_coordinates(self):
        with self.assertRaisesRegex(IdentityValidationError, "unknown fields"):
            IdentityService._normalize_location(
                {
                    **VALID_LOCATION,
                    "raw_point": {"lat": 32.715736, "lon": -117.161087},
                }
            )

    def test_canonical_location_keeps_only_allowlisted_shape_and_rounds_coordinates(self):
        normalized = IdentityService._normalize_location(VALID_LOCATION)
        self.assertEqual(
            set(normalized),
            {"kind", "region", "city", "lat", "lon", "precision"},
        )
        self.assertEqual(normalized["lat"], 32.7)
        self.assertEqual(normalized["lon"], -117.2)
        self.assertEqual(normalized["precision"], "city")


class R11PublicAuditIntegrationTests(unittest.TestCase):
    def test_auth_verifiers_and_recovery_hashes_are_not_in_public_audit_projection(self):
        try:
            from src.identity.backend import R11IdentityBackend
            from src.persistence import LiveCorpusService
            from tests.support import repository
        except ImportError:
            self.skipTest("R11 persistence branch not present in standalone R12 checkout")

        live = LiveCorpusService(repository(":ephemeral:"))
        identity = IdentityService(R11IdentityBackend(live))
        credentials = identity.register("Audit User")
        try:
            # Internal replay must still work, proving redaction is projection-
            # only rather than destructive storage mutation.
            actor = identity.authenticate(credentials.access_token)
            self.assertEqual(actor.user_id, credentials.user_id)

            public = live.audit_log()
            public_types = {row["event_type"] for row in public}
            self.assertNotIn("identity.account.registered", public_types)
            self.assertFalse(any(t.startswith("identity.auth.") for t in public_types))
            blob = repr(public)
            self.assertNotIn("token_sha256", blob)
            self.assertNotIn("csrf_sha256", blob)
            self.assertNotIn("recovery_sha256", blob)
        finally:
            live.repo.close()


if __name__ == "__main__":
    unittest.main()
