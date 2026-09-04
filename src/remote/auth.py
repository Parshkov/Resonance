"""OAuth 2.1 authorization-code + PKCE code store for the remote MCP endpoint.

The remote bearer token IS the accepted R12 access token — there is no separate
token directory here. This module holds only the single-use PKCE authorization
codes that bind a completed R12 authentication (the issued access token) to a
code_challenge, and exchange it for that same access token after S256
verification. Demo-grade by declaration: no consent UI, no refresh tokens,
in-memory store, no standards discovery metadata. It is a client-interop
compliance surface, not a production IdP; the accepted R12 identity model owns
authentication and R12B owns authorization rules.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import time
from dataclasses import dataclass, field
from typing import Any


def _s256(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


@dataclass
class CodeStore:
    codes: dict[str, dict[str, Any]] = field(default_factory=dict)
    code_ttl_seconds: int = 300
    clock: Any = time.time

    def issue_code(self, access_token: str, code_challenge: str,
                   redirect_uri: str, client_id: str) -> str:
        if not access_token:
            raise ValueError("authenticated access token required")
        if not code_challenge:
            raise ValueError("code_challenge required (PKCE is mandatory)")
        code = secrets.token_urlsafe(24)
        self.codes[code] = {"access_token": access_token,
                            "challenge": code_challenge,
                            "redirect_uri": redirect_uri,
                            "client_id": client_id,
                            "expires": self.clock() + self.code_ttl_seconds}
        return code

    def exchange_code(self, code: str, code_verifier: str,
                      redirect_uri: str, client_id: str) -> str:
        record = self.codes.pop(code, None)          # single use
        if record is None or record["expires"] < self.clock():
            raise ValueError("invalid or expired authorization code")
        if record["redirect_uri"] != redirect_uri or record["client_id"] != client_id:
            raise ValueError("redirect_uri/client_id mismatch")
        if not code_verifier or not hmac.compare_digest(
                record["challenge"], _s256(code_verifier)):
            raise ValueError("PKCE verification failed")
        return record["access_token"]
