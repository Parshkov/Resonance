"""Authentication for the remote MCP endpoint.

Two grades, honestly labeled:

* **Bearer/session tokens** -- full-strength for local integration tests and
  pilot use: opaque random tokens mapped to subjects, constant-time compared.
* **OAuth 2.1 authorization-code + PKCE semantics** -- the flow SHAPE clients
  in agent ecosystems expect: /authorize issues a code bound to
  code_challenge (S256 only), /token verifies code_verifier and exchanges it
  for a bearer token. Demo-grade by declaration: no consent UI, single
  static demo user directory, no refresh tokens, in-memory stores. This is a
  compliance surface for client interop, not a production IdP.

No business logic here; the service layer owns authorization RULES, this
module only authenticates subjects.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass, field
from typing import Any


def _s256(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


@dataclass
class AuthStore:
    users: dict[str, str] = field(default_factory=lambda: {"demo": "user-demo"})
    tokens: dict[str, str] = field(default_factory=dict)      # token -> subject
    codes: dict[str, dict[str, Any]] = field(default_factory=dict)
    code_ttl_seconds: int = 300
    clock: Any = time.time

    def issue_token(self, subject: str) -> str:
        token = secrets.token_urlsafe(32)
        self.tokens[token] = subject
        return token

    def subject_for_token(self, token: str | None) -> str | None:
        if not token:
            return None
        for known, subject in self.tokens.items():
            if hmac.compare_digest(known, token):
                return subject
        return None

    # -- OAuth 2.1 code + PKCE ---------------------------------------------
    def issue_code(self, user: str, code_challenge: str,
                   redirect_uri: str, client_id: str) -> str:
        if user not in self.users:
            raise ValueError("unknown demo user")
        if not code_challenge:
            raise ValueError("code_challenge required (PKCE is mandatory)")
        code = secrets.token_urlsafe(24)
        self.codes[code] = {"subject": self.users[user],
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
        if not hmac.compare_digest(record["challenge"], _s256(code_verifier)):
            raise ValueError("PKCE verification failed")
        return self.issue_token(record["subject"])
