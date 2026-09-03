"""Authenticated-subject OAuth authorization-code + PKCE security primitive."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import time
from typing import Any

from .models import AuthorizationCodeRecord, OAuthGrantError, RequestContext


def pkce_s256(verifier: str) -> str:
    try:
        digest = hashlib.sha256(verifier.encode("ascii")).digest()
    except UnicodeEncodeError as exc:
        raise OAuthGrantError("PKCE verifier must be ASCII") from exc
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


class AuthorizationCodeBroker:
    """Issues codes only for an already authenticated subject.

    There is deliberately no ``user``/``username`` parameter.  Subject comes
    exclusively from :class:`RequestContext` created by authentication.
    """

    def __init__(self, *, ttl_seconds: int = 300, clock: Any = time.time) -> None:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        self.ttl_seconds = ttl_seconds
        self.clock = clock
        self._codes: dict[str, AuthorizationCodeRecord] = {}

    def issue_code(
        self,
        context: RequestContext,
        *,
        client_id: str,
        redirect_uri: str,
        code_challenge: str,
        code_challenge_method: str,
        resource: str,
        audience: str,
    ) -> str:
        if not context.subject:
            raise OAuthGrantError("authenticated subject required")
        if context.client_id != client_id:
            raise OAuthGrantError("authenticated client mismatch")
        if code_challenge_method != "S256" or not code_challenge:
            raise OAuthGrantError("PKCE S256 required")
        if not redirect_uri or not resource or not audience:
            raise OAuthGrantError("redirect/resource/audience binding required")
        code = secrets.token_urlsafe(24)
        self._codes[code] = AuthorizationCodeRecord(
            code=code,
            subject=context.subject,
            client_id=client_id,
            redirect_uri=redirect_uri,
            code_challenge=code_challenge,
            resource=resource,
            audience=audience,
            expires_at=float(self.clock()) + self.ttl_seconds,
        )
        return code

    def exchange_code(
        self,
        code: str,
        *,
        client_id: str,
        redirect_uri: str,
        code_verifier: str,
        resource: str,
        audience: str,
    ) -> str:
        record = self._codes.pop(code, None)
        if record is None or record.expires_at < float(self.clock()):
            raise OAuthGrantError("invalid or expired authorization code")
        bindings = (
            hmac.compare_digest(record.client_id, client_id),
            hmac.compare_digest(record.redirect_uri, redirect_uri),
            hmac.compare_digest(record.resource, resource),
            hmac.compare_digest(record.audience, audience),
            hmac.compare_digest(record.code_challenge, pkce_s256(code_verifier)),
        )
        if not all(bindings):
            raise OAuthGrantError("authorization code binding/PKCE verification failed")
        return record.subject
