"""Federated sign-in providers.

Resonance exists to put people who reason alike in touch with each other. An
anonymous account cannot serve that: the same person arriving from Claude, from
ChatGPT and from a browser would be three strangers, and none of them could be
told when a match finally appears. So an account is created only behind a
provider that has verified who signed in.

What is taken from a provider is deliberately small: a stable subject
identifier, a handle to display, and a verified email address used to reach the
person when a resonance is found. No provider scope beyond basic profile and
email is ever requested.

Providers are configured entirely from the environment. A provider without
credentials is simply absent -- the service never pretends to offer a sign-in
it cannot complete.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

USER_AGENT = "resonance-auth/1.0"
HTTP_TIMEOUT_SECONDS = 10


class FederationError(Exception):
    """A provider exchange did not yield a verified identity."""


@dataclass(frozen=True)
class FederatedIdentity:
    """A person as a provider vouches for them."""

    provider: str
    subject: str
    email: str
    email_verified: bool
    handle: str

    def display_label(self) -> str:
        label = (self.handle or self.email.split("@", 1)[0] or self.subject).strip()
        return label[:80] or self.subject[:80]


@dataclass(frozen=True)
class ProviderConfig:
    name: str
    label: str
    client_id: str
    client_secret: str
    authorize_url: str
    token_url: str
    scope: str
    extra_authorize: Mapping[str, str] = None  # type: ignore[assignment]

    def authorize_redirect(self, *, redirect_uri: str, state: str) -> str:
        params = {
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": self.scope,
            "state": state,
        }
        params.update(self.extra_authorize or {})
        return f"{self.authorize_url}?{urllib.parse.urlencode(params)}"


def _post_form(url: str, form: Mapping[str, str]) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=urllib.parse.urlencode(form).encode("utf-8"),
        headers={
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": USER_AGENT,
        },
        method="POST",
    )
    return _send(request)


def _get_json(url: str, token: str, *, accept: str = "application/json") -> Any:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": accept,
            "Authorization": f"Bearer {token}",
            "User-Agent": USER_AGENT,
        },
        method="GET",
    )
    return _send(request)


def _send(request: urllib.request.Request) -> Any:
    try:
        with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
            raw = response.read()
    except urllib.error.HTTPError as exc:  # noqa: PERF203 - distinct diagnosis
        raise FederationError(f"provider returned HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise FederationError("provider unreachable") from exc
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise FederationError("provider returned a non-JSON body") from exc


def _access_token(document: Mapping[str, Any]) -> str:
    if document.get("error"):
        # The provider's own words are the useful diagnosis; the description is
        # provider-authored text, so it is not echoed to the person.
        raise FederationError(f"provider rejected the code: {document['error']}")
    token = str(document.get("access_token") or "")
    if not token:
        raise FederationError("provider returned no access token")
    return token


class GoogleProvider:
    """OpenID Connect authorization-code flow against Google."""

    name = "google"
    label = "Google"
    userinfo_url = "https://openidconnect.googleapis.com/v1/userinfo"

    @staticmethod
    def config(client_id: str, client_secret: str) -> ProviderConfig:
        return ProviderConfig(
            name=GoogleProvider.name,
            label=GoogleProvider.label,
            client_id=client_id,
            client_secret=client_secret,
            authorize_url="https://accounts.google.com/o/oauth2/v2/auth",
            token_url="https://oauth2.googleapis.com/token",
            scope="openid email profile",
            # No refresh token is wanted: sign-in is a one-shot proof of who
            # this is, not standing access to a Google account.
            extra_authorize={"prompt": "select_account"},
        )

    @staticmethod
    def exchange(config: ProviderConfig, code: str, redirect_uri: str) -> FederatedIdentity:
        document = _post_form(config.token_url, {
            "code": code,
            "client_id": config.client_id,
            "client_secret": config.client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        })
        profile = _get_json(GoogleProvider.userinfo_url, _access_token(document))
        if not isinstance(profile, Mapping):
            raise FederationError("provider returned an unexpected profile")
        subject = str(profile.get("sub") or "")
        email = str(profile.get("email") or "").strip().lower()
        if not subject:
            raise FederationError("provider returned no stable subject")
        return FederatedIdentity(
            provider=GoogleProvider.name,
            subject=subject,
            email=email,
            email_verified=bool(profile.get("email_verified")),
            handle=str(profile.get("name") or "").strip(),
        )


class GitHubProvider:
    """OAuth 2.0 authorization-code flow against GitHub."""

    name = "github"
    label = "GitHub"
    user_url = "https://api.github.com/user"
    emails_url = "https://api.github.com/user/emails"

    @staticmethod
    def config(client_id: str, client_secret: str) -> ProviderConfig:
        return ProviderConfig(
            name=GitHubProvider.name,
            label=GitHubProvider.label,
            client_id=client_id,
            client_secret=client_secret,
            authorize_url="https://github.com/login/oauth/authorize",
            token_url="https://github.com/login/oauth/access_token",
            scope="read:user user:email",
        )

    @staticmethod
    def exchange(config: ProviderConfig, code: str, redirect_uri: str) -> FederatedIdentity:
        document = _post_form(config.token_url, {
            "code": code,
            "client_id": config.client_id,
            "client_secret": config.client_secret,
            "redirect_uri": redirect_uri,
        })
        token = _access_token(document)
        accept = "application/vnd.github+json"
        profile = _get_json(GitHubProvider.user_url, token, accept=accept)
        if not isinstance(profile, Mapping):
            raise FederationError("provider returned an unexpected profile")
        subject = str(profile.get("id") or "")
        if not subject:
            raise FederationError("provider returned no stable subject")
        email, verified = GitHubProvider._primary_email(token, accept)
        return FederatedIdentity(
            provider=GitHubProvider.name,
            subject=subject,
            email=email,
            email_verified=verified,
            handle=str(profile.get("login") or "").strip(),
        )

    @staticmethod
    def _primary_email(token: str, accept: str) -> tuple[str, bool]:
        """GitHub keeps the address off the profile when it is private, so the
        verified primary is read from the dedicated endpoint."""
        try:
            entries = _get_json(GitHubProvider.emails_url, token, accept=accept)
        except FederationError:
            return "", False
        if not isinstance(entries, Sequence):
            return "", False
        for entry in entries:
            if isinstance(entry, Mapping) and entry.get("primary") and entry.get("verified"):
                return str(entry.get("email") or "").strip().lower(), True
        return "", False


PROVIDERS = {
    GoogleProvider.name: GoogleProvider,
    GitHubProvider.name: GitHubProvider,
}


def configured_providers(environ: Mapping[str, str] | None = None) -> dict[str, ProviderConfig]:
    """Every provider this deployment can actually complete a sign-in with."""
    env = os.environ if environ is None else environ
    found: dict[str, ProviderConfig] = {}
    for name, provider in PROVIDERS.items():
        prefix = f"RESONANCE_AUTH_{name.upper()}"
        client_id = (env.get(f"{prefix}_CLIENT_ID") or "").strip()
        client_secret = (env.get(f"{prefix}_CLIENT_SECRET") or "").strip()
        if client_id and client_secret:
            found[name] = provider.config(client_id, client_secret)
    return found


def exchange_code(config: ProviderConfig, code: str, redirect_uri: str) -> FederatedIdentity:
    provider = PROVIDERS.get(config.name)
    if provider is None:
        raise FederationError(f"unknown provider {config.name}")
    identity = provider.exchange(config, code, redirect_uri)
    if not identity.email or not identity.email_verified:
        # An unverified address cannot be used to tell someone a match appeared,
        # and it cannot safely stand for a person. Refuse rather than degrade.
        raise FederationError("provider did not supply a verified email address")
    return identity
