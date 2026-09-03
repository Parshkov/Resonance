"""Thin transport adapters; authorization remains in IdentityService."""

from __future__ import annotations

from typing import Any, Mapping

from .models import ConsentChoices
from .service import IdentityService


class CookieSessionAdapter:
    """Shared mutation surface for manual browser UI and browser WebMCP."""

    actor_type = "human"

    client_id = "browser"

    def __init__(self, service: IdentityService, *, request_origin: str) -> None:
        self.service = service
        self.request_origin = request_origin

    def owned_sessions(self, access_token: str) -> list[dict[str, Any]]:
        return self.service.owned_sessions(
            access_token,
            actor_type=self.actor_type,
            client_id=self.client_id,
        )

    def create_thought_session(
        self,
        access_token: str,
        csrf_token: str,
        *,
        thought_dna: Mapping[str, Any],
        location: Mapping[str, Any],
        presentation: Mapping[str, Any],
    ) -> Any:
        return self.service.create_thought_session(
            access_token,
            thought_dna=thought_dna,
            location=location,
            presentation=presentation,
            csrf_token=csrf_token,
            origin=self.request_origin,
            cookie_authenticated=True,
            actor_type=self.actor_type,
            client_id=self.client_id,
        )

    def update_thought_session(
        self,
        access_token: str,
        csrf_token: str,
        session_id: str,
        *,
        thought_dna: Mapping[str, Any],
        location: Mapping[str, Any] | None = None,
        presentation: Mapping[str, Any] | None = None,
    ) -> Any:
        return self.service.update_thought_session(
            access_token,
            session_id,
            thought_dna=thought_dna,
            location=location,
            presentation=presentation,
            csrf_token=csrf_token,
            origin=self.request_origin,
            cookie_authenticated=True,
            actor_type=self.actor_type,
            client_id=self.client_id,
        )

    def set_consent(
        self,
        access_token: str,
        csrf_token: str,
        session_id: str,
        choices: ConsentChoices,
        *,
        confirmed: bool,
    ) -> ConsentChoices:
        return self.service.set_consent(
            access_token,
            session_id,
            choices,
            confirmed=confirmed,
            csrf_token=csrf_token,
            origin=self.request_origin,
            cookie_authenticated=True,
            actor_type=self.actor_type,
            client_id=self.client_id,
        )

    def revoke(self, access_token: str, csrf_token: str, session_id: str, *, confirmed: bool) -> Any:
        return self.service.revoke_thought_session(
            access_token,
            session_id,
            confirmed=confirmed,
            csrf_token=csrf_token,
            origin=self.request_origin,
            cookie_authenticated=True,
            actor_type=self.actor_type,
            client_id=self.client_id,
        )

    def delete(self, access_token: str, csrf_token: str, session_id: str, *, confirmed: bool) -> Any:
        return self.service.delete_thought_session(
            access_token,
            session_id,
            confirmed=confirmed,
            csrf_token=csrf_token,
            origin=self.request_origin,
            cookie_authenticated=True,
            actor_type=self.actor_type,
            client_id=self.client_id,
        )

    def block_user(
        self,
        access_token: str,
        csrf_token: str,
        peer_id: str,
        *,
        confirmed: bool,
    ) -> None:
        self.service.block_user(
            access_token,
            peer_id,
            confirmed=confirmed,
            csrf_token=csrf_token,
            origin=self.request_origin,
            cookie_authenticated=True,
            client_id=self.client_id,
        )

    def report_user(
        self,
        access_token: str,
        csrf_token: str,
        peer_id: str,
        reason_code: str,
    ) -> None:
        self.service.report_user(
            access_token,
            peer_id,
            reason_code,
            csrf_token=csrf_token,
            origin=self.request_origin,
            cookie_authenticated=True,
            client_id=self.client_id,
        )


class ManualUIAdapter(CookieSessionAdapter):
    actor_type = "human"
    client_id = "manual-ui"


class WebMCPAdapter(CookieSessionAdapter):
    actor_type = "agent"
    client_id = "webmcp"
    untrusted_content_hint = True


class BearerAgentAdapter:
    """Future remote-MCP/API bearer path; same policy, no browser CSRF layer."""

    actor_type = "agent"
    client_id = "remote-agent"
    untrusted_content_hint = True

    def __init__(self, service: IdentityService) -> None:
        self.service = service

    def owned_sessions(self, access_token: str) -> list[dict[str, Any]]:
        return self.service.owned_sessions(
            access_token,
            actor_type=self.actor_type,
            client_id=self.client_id,
        )

    def set_consent(
        self,
        access_token: str,
        session_id: str,
        choices: ConsentChoices,
        *,
        confirmed: bool,
    ) -> ConsentChoices:
        return self.service.set_consent(
            access_token,
            session_id,
            choices,
            confirmed=confirmed,
            cookie_authenticated=False,
            actor_type=self.actor_type,
            client_id=self.client_id,
        )

    def block_user(self, access_token: str, peer_id: str, *, confirmed: bool) -> None:
        self.service.block_user(
            access_token,
            peer_id,
            confirmed=confirmed,
            client_id=self.client_id,
        )

    def report_user(self, access_token: str, peer_id: str, reason_code: str) -> None:
        self.service.report_user(
            access_token,
            peer_id,
            reason_code,
            client_id=self.client_id,
        )
