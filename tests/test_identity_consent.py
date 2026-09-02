from __future__ import annotations

import copy
import unittest
from dataclasses import dataclass, replace
from typing import Any, Mapping

from src.identity import (
    AuthenticationError,
    AuthorizationError,
    ConfirmationRequiredError,
    ConsentChoices,
    CsrfError,
    IdentityService,
    ManualUIAdapter,
    WebMCPAdapter,
)
from src.identity.models import IdentityEvent


@dataclass(frozen=True)
class FakeUser:
    user_id: str
    display_label: str
    avatar_placeholder: str
    revoked_at: str | None = None

    def to_dict(self):
        return self.__dict__.copy()


@dataclass(frozen=True)
class FakeSession:
    session_id: str
    user_id: str
    thought_dna: Mapping[str, Any]
    consent: Mapping[str, Any]
    location: Mapping[str, Any]
    presentation: Mapping[str, Any]
    record_kind: str = "volunteer"
    notes: str = ""
    revoked_at: str | None = None
    deleted_at: str | None = None

    def to_dict(self):
        return self.__dict__.copy()


class FakeR11Backend:
    """Deterministic in-memory implementation of the declared R11 seam."""

    def __init__(self, *, durable_events=None, durable_users=None, durable_sessions=None):
        self.events = durable_events if durable_events is not None else []
        self.users = durable_users if durable_users is not None else {}
        self.sessions = durable_sessions if durable_sessions is not None else {}
        self.index = set()

    def create_user(self, user_id, *, display_label, avatar_placeholder=None):
        user = FakeUser(user_id, display_label, avatar_placeholder or display_label)
        self.users[user_id] = user
        return user

    def get_user(self, user_id):
        return self.users.get(user_id)

    def revoke_user(self, user_id):
        user = self.users[user_id]
        user = replace(user, revoked_at="revoked")
        self.users[user_id] = user
        for sid, session in list(self.sessions.items()):
            if session.user_id == user_id and session.deleted_at is None:
                self.revoke_session(sid, reason="user_revoked")
        return user

    def create_session(self, **kwargs):
        session = FakeSession(
            session_id=kwargs["session_id"],
            user_id=kwargs["user_id"],
            thought_dna=copy.deepcopy(kwargs["thought_dna"]),
            consent=dict(kwargs["consent"]),
            location=dict(kwargs["location"]),
            presentation=dict(kwargs["presentation"]),
            record_kind=kwargs["record_kind"],
            notes=kwargs["notes"],
        )
        old = self.sessions.get(session.session_id)
        if old:
            session = replace(session, revoked_at=old.revoked_at, deleted_at=old.deleted_at)
        self.sessions[session.session_id] = session
        self._sync_index(session)
        return session

    def get_session(self, session_id):
        return self.sessions.get(session_id)

    def list_sessions(self):
        return list(self.sessions.values())

    def update_consent(self, session_id, consent):
        session = replace(self.sessions[session_id], consent=dict(consent))
        self.sessions[session_id] = session
        self._sync_index(session)
        return session

    def update_presentation(self, session_id, *, location=None, presentation=None):
        session = self.sessions[session_id]
        session = replace(
            session,
            location=dict(location) if location is not None else session.location,
            presentation=dict(presentation) if presentation is not None else session.presentation,
        )
        self.sessions[session_id] = session
        return session

    def revoke_session(self, session_id, *, reason="revoked"):
        session = self.sessions[session_id]
        session = replace(
            session,
            consent={
                "share_enabled": False,
                "share_thought_dna": False,
                "share_coarse_location": False,
                "share_display_profile": False,
            },
            revoked_at="revoked",
        )
        self.sessions[session_id] = session
        self.index.discard(session_id)
        return session

    def delete_session(self, session_id):
        session = self.revoke_session(session_id)
        session = replace(session, deleted_at="deleted")
        self.sessions[session_id] = session
        return session

    def append_identity_event(self, event: IdentityEvent):
        self.events.append(event)

    def list_identity_events(self):
        # Mirror R11 SQLite ordering: ORDER BY created_at, event_id.
        return sorted(self.events, key=lambda e: (e.created_at, e.event_id))

    def _sync_index(self, session):
        discoverable = (
            session.deleted_at is None
            and session.revoked_at is None
            and session.consent.get("share_enabled")
            and session.consent.get("share_thought_dna")
        )
        (self.index.add if discoverable else self.index.discard)(session.session_id)


def dna(thought_id="thought-1"):
    return {"schema_version": "thought-dna/0.1", "thought_id": thought_id, "nodes": [], "edges": []}


def location():
    return {"kind": "synthetic_coarse", "region": "US-CA", "city": "San Diego", "lat": 32.7, "lon": -117.1, "precision": "city"}


def presentation():
    return {"domain": "test", "topic": "identity", "cluster_id": "test-cluster"}


class IdentityConsentTests(unittest.TestCase):
    def setUp(self):
        self.backend = FakeR11Backend()
        self.service = IdentityService(self.backend)
        self.alice = self.service.register("alice")
        self.bob = self.service.register("bob")

    def test_private_by_default_then_exact_consent_projection(self):
        session = self.service.create_thought_session(
            self.alice.access_token,
            thought_dna=dna(),
            location=location(),
            presentation=presentation(),
        )
        self.assertNotIn(session.session_id, self.backend.index)
        choices = ConsentChoices(True, True, True, True)
        self.service.set_consent(
            self.alice.access_token,
            session.session_id,
            choices,
            confirmed=True,
        )
        stored = self.backend.get_session(session.session_id)
        self.assertEqual(
            stored.consent,
            {
                "share_enabled": True,
                "share_thought_dna": True,
                "share_coarse_location": True,
                "share_display_profile": True,
            },
        )
        self.assertTrue(self.service.consent_for(self.alice.access_token, session.session_id).allow_intro_requests)
        self.assertIn(session.session_id, self.backend.index)

    def test_cross_user_id_substitution_is_rejected_without_existence_signal(self):
        session = self.service.create_thought_session(
            self.alice.access_token, thought_dna=dna(), location=location(), presentation=presentation()
        )
        with self.assertRaises(AuthorizationError) as owned:
            self.service.set_consent(
                self.bob.access_token,
                session.session_id,
                ConsentChoices(share_thought_dna=True),
                confirmed=True,
            )
        with self.assertRaises(AuthorizationError) as missing:
            self.service.set_consent(
                self.bob.access_token,
                "ses-does-not-exist",
                ConsentChoices(share_thought_dna=True),
                confirmed=True,
            )
        self.assertEqual(str(owned.exception), str(missing.exception))

    def test_cookie_mutations_require_csrf_and_visible_confirmation(self):
        ui = ManualUIAdapter(self.service)
        session = ui.create_thought_session(
            self.alice.access_token, thought_dna=dna(), location=location(), presentation=presentation()
        )
        with self.assertRaises(ConfirmationRequiredError):
            ui.set_consent(
                self.alice.access_token,
                self.alice.csrf_token,
                session.session_id,
                ConsentChoices(share_thought_dna=True),
                confirmed=False,
            )
        with self.assertRaises(CsrfError):
            ui.set_consent(
                self.alice.access_token,
                "wrong",
                session.session_id,
                ConsentChoices(share_thought_dna=True),
                confirmed=True,
            )
        ui.set_consent(
            self.alice.access_token,
            self.alice.csrf_token,
            session.session_id,
            ConsentChoices(share_thought_dna=True),
            confirmed=True,
        )

    def test_logout_then_pseudonymous_login_preserves_owned_state_without_email(self):
        session = self.service.create_thought_session(
            self.alice.access_token, thought_dna=dna(), location=location(), presentation=presentation()
        )
        recovery = self.alice.recovery_secret
        self.assertTrue(recovery)
        self.service.logout(self.alice.access_token)
        with self.assertRaises(AuthenticationError):
            self.service.authenticate(self.alice.access_token)
        logged_in = self.service.login(self.alice.user_id, recovery)
        self.assertNotEqual(logged_in.auth_session_id, self.alice.auth_session_id)
        self.assertEqual([x["session_id"] for x in self.service.owned_sessions(logged_in.access_token)], [session.session_id])
        with self.assertRaises(AuthenticationError):
            self.service.login(self.alice.user_id, "wrong-recovery")

    def test_logout_and_rotation_invalidate_old_credentials(self):
        rotated = self.service.rotate_session(self.alice.access_token)
        with self.assertRaises(AuthenticationError):
            self.service.authenticate(self.alice.access_token)
        self.assertEqual(self.service.authenticate(rotated.access_token).user_id, self.alice.user_id)
        self.service.logout(rotated.access_token)
        with self.assertRaises(AuthenticationError):
            self.service.authenticate(rotated.access_token)

    def test_restart_restores_auth_and_owned_state_from_durable_r11_seam(self):
        session = self.service.create_thought_session(
            self.alice.access_token, thought_dna=dna(), location=location(), presentation=presentation()
        )
        self.service.set_consent(
            self.alice.access_token,
            session.session_id,
            ConsentChoices(share_thought_dna=True, allow_intro_requests=True),
            confirmed=True,
        )
        restarted_backend = FakeR11Backend(
            durable_events=self.backend.events,
            durable_users=self.backend.users,
            durable_sessions=self.backend.sessions,
        )
        restarted = IdentityService(restarted_backend)
        self.assertEqual(restarted.authenticate(self.alice.access_token).user_id, self.alice.user_id)
        owned = restarted.owned_sessions(self.alice.access_token)
        self.assertEqual([item["session_id"] for item in owned], [session.session_id])
        self.assertTrue(restarted.consent_for(self.alice.access_token, session.session_id).allow_intro_requests)

    def test_shared_thought_cannot_be_silently_replaced(self):
        session = self.service.create_thought_session(
            self.alice.access_token, thought_dna=dna(), location=location(), presentation=presentation()
        )
        self.service.set_consent(
            self.alice.access_token, session.session_id, ConsentChoices(share_thought_dna=True), confirmed=True
        )
        with self.assertRaises(ConfirmationRequiredError):
            self.service.update_thought_session(
                self.alice.access_token, session.session_id, thought_dna=dna("thought-replacement")
            )

    def test_revoke_and_delete_fail_closed_from_discovery(self):
        session = self.service.create_thought_session(
            self.alice.access_token, thought_dna=dna(), location=location(), presentation=presentation()
        )
        self.service.set_consent(
            self.alice.access_token,
            session.session_id,
            ConsentChoices(share_thought_dna=True, share_coarse_location=True, allow_intro_requests=True),
            confirmed=True,
        )
        self.assertIn(session.session_id, self.backend.index)
        self.service.revoke_thought_session(self.alice.access_token, session.session_id, confirmed=True)
        self.assertNotIn(session.session_id, self.backend.index)
        self.assertEqual(self.service.consent_for(self.alice.access_token, session.session_id), ConsentChoices())
        self.service.delete_thought_session(self.alice.access_token, session.session_id, confirmed=True)
        self.assertNotIn(session.session_id, self.backend.index)

    def test_manual_ui_and_webmcp_have_same_authorization_and_consent_result(self):
        ui = ManualUIAdapter(self.service)
        webmcp = WebMCPAdapter(self.service)
        first = ui.create_thought_session(
            self.alice.access_token, thought_dna=dna("thought-ui"), location=location(), presentation=presentation()
        )
        second = webmcp.create_thought_session(
            self.alice.access_token, thought_dna=dna("thought-agent"), location=location(), presentation=presentation()
        )
        choices = ConsentChoices(True, True, False, True)
        ui.set_consent(self.alice.access_token, self.alice.csrf_token, first.session_id, choices, confirmed=True)
        webmcp.set_consent(self.alice.access_token, self.alice.csrf_token, second.session_id, choices, confirmed=True)
        self.assertEqual(self.backend.get_session(first.session_id).consent, self.backend.get_session(second.session_id).consent)
        self.assertEqual(self.service.consent_for(self.alice.access_token, first.session_id), choices)
        self.assertEqual(self.service.consent_for(self.alice.access_token, second.session_id), choices)
        with self.assertRaises(AuthorizationError):
            webmcp.set_consent(
                self.bob.access_token,
                self.bob.csrf_token,
                first.session_id,
                choices,
                confirmed=True,
            )

    def test_audit_never_persists_plaintext_access_or_csrf_tokens_or_dna(self):
        session = self.service.create_thought_session(
            self.alice.access_token, thought_dna=dna(), location=location(), presentation=presentation()
        )
        self.service.set_consent(
            self.alice.access_token,
            session.session_id,
            ConsentChoices(share_thought_dna=True),
            confirmed=True,
        )
        serialized = repr(self.backend.events)
        self.assertNotIn(self.alice.access_token, serialized)
        self.assertNotIn(self.alice.csrf_token, serialized)
        self.assertNotIn(self.alice.recovery_secret, serialized)
        self.assertNotIn("thought-dna/0.1", serialized)
        self.assertNotIn("thought_id", serialized)

    def test_account_revoke_invalidates_all_credentials_and_discovery(self):
        other = self.service.rotate_session(self.alice.access_token)
        session = self.service.create_thought_session(
            other.access_token, thought_dna=dna(), location=location(), presentation=presentation()
        )
        self.service.set_consent(
            other.access_token, session.session_id, ConsentChoices(share_thought_dna=True), confirmed=True
        )
        self.service.revoke_account(other.access_token, confirmed=True)
        self.assertNotIn(session.session_id, self.backend.index)
        with self.assertRaises(AuthenticationError):
            self.service.authenticate(other.access_token)


if __name__ == "__main__":
    unittest.main()
