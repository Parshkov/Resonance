"""Sign-in mount: the only door through which an account comes into being.

Resonance looks for people who reason alike and tells them about each other.
That is impossible over anonymous accounts: the same person arriving from
Claude, from ChatGPT and from a browser would be three unrelated strangers, no
one of them could be recognised on their return, and none of them could be told
that a match had finally appeared. So an account is not minted on arrival any
more -- it is created behind a provider that has verified who signed in, and
every later surface resolves to that same account.

This module owns only the browser-facing sign-in: the provider redirect, the
callback exchange, and the session cookie that results. Account semantics stay
in `src/identity`; the provider protocol stays in `src/identity/federation`.
"""

from __future__ import annotations

import html
import secrets
import urllib.parse
import time
from http.cookies import SimpleCookie
from typing import Any, Mapping

from src.identity.federation import (
    FederationError,
    configured_providers,
    exchange_code,
)

from .oauth_mount import MountResponse

AUTH_PREFIX = "/auth/"
SIGN_IN_PATH = "/auth/sign-in"
STATE_COOKIE = "resonance_auth_state"
STATE_TTL_SECONDS = 600
CALLBACK_TEMPLATE = "/auth/callback/{provider}"


def is_auth_path(path: str) -> bool:
    return path == SIGN_IN_PATH or path.startswith(AUTH_PREFIX)


def safe_next(candidate: str | None) -> str:
    """Only ever come back to a path on this origin.

    An open redirect here would let a page elsewhere borrow the sign-in flow to
    land a person somewhere they did not choose, carrying the impression that
    Resonance sent them.
    """
    value = (candidate or "").strip()
    if not value.startswith("/") or value.startswith("//") or value.startswith("/\\"):
        return "/"
    if any(ch in value for ch in ("\r", "\n")):
        return "/"
    return value


class SignInStates:
    """Short-lived, single-use records of a sign-in in flight.

    Held in the process rather than the database because a state outlives only
    the redirect to the provider and back. A restart mid-sign-in costs one
    retry and never leaves a usable record behind.
    """

    def __init__(self, *, clock: Any = time.time, ttl: int = STATE_TTL_SECONDS) -> None:
        self._records: dict[str, dict[str, Any]] = {}
        self._clock = clock
        self._ttl = ttl

    def issue(self, *, provider: str, next_path: str) -> tuple[str, str]:
        self._expire()
        state = secrets.token_urlsafe(24)
        nonce = secrets.token_urlsafe(24)
        self._records[state] = {
            "provider": provider,
            "next": next_path,
            "nonce": nonce,
            "expires_at": self._clock() + self._ttl,
        }
        return state, nonce

    def take(self, state: str) -> dict[str, Any] | None:
        self._expire()
        record = self._records.pop(state or "", None)
        if record is None or record["expires_at"] <= self._clock():
            return None
        return record

    def _expire(self) -> None:
        now = self._clock()
        for key in [k for k, v in self._records.items() if v["expires_at"] <= now]:
            self._records.pop(key, None)


def _cookie_value(headers: Mapping[str, str], name: str) -> str:
    raw = headers.get("Cookie") or headers.get("cookie") or ""
    if not raw:
        return ""
    jar = SimpleCookie()
    try:
        jar.load(raw)
    except Exception:  # noqa: BLE001 - a malformed jar is simply no cookie
        return ""
    morsel = jar.get(name)
    return morsel.value if morsel is not None else ""


def _state_cookie(nonce: str, *, secure: bool) -> str:
    # Lax, not Strict: the provider sends the person back with a top-level GET
    # from another site, and a Strict cookie would not accompany it — the very
    # navigation this nonce exists to bind.
    flag = "; Secure" if secure else ""
    return (f"{STATE_COOKIE}={nonce}; HttpOnly; SameSite=Lax; Path=/auth; "
            f"Max-Age={STATE_TTL_SECONDS}{flag}")


def _cleared_state_cookie(*, secure: bool) -> str:
    flag = "; Secure" if secure else ""
    return f"{STATE_COOKIE}=; HttpOnly; SameSite=Lax; Path=/auth; Max-Age=0{flag}"


def _redirect(location: str, *, extra: Mapping[str, str] | None = None,
              cookies: tuple[str, ...] = ()) -> MountResponse:
    headers: dict[str, str] = {"Location": location, "Cache-Control": "no-store"}
    headers.update(extra or {})
    return MountResponse(302, headers, b"", cookies)


def _page(body: str, *, status: int = 200,
          cookies: tuple[str, ...] = ()) -> MountResponse:
    document = (
        "<!doctype html>\n<html lang=\"en\">\n<head>\n"
        "<meta charset=\"utf-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
        "<title>Sign in — Resonance</title>\n"
        "<link rel=\"stylesheet\" href=\"/legal.css\">\n"
        "<link rel=\"icon\" href=\"/favicon.svg\" type=\"image/svg+xml\">\n"
        "</head>\n<body>\n<main class=\"doc doc-narrow\">\n"
        f"{body}\n</main>\n</body>\n</html>\n"
    )
    return MountResponse(status, {
        "Content-Type": "text/html; charset=utf-8",
        "Cache-Control": "no-store",
    }, document.encode("utf-8"), cookies)


def _sign_in_page(providers: Mapping[str, Any], next_path: str,
                  *, message: str = "") -> MountResponse:
    # URL-encoded before it is HTML-escaped: the destination is often an
    # authorize URL carrying its own query, and an unencoded `&` would split
    # `next` into separate parameters and strand the person on the home page.
    escaped_next = html.escape(urllib.parse.quote(next_path, safe=""))
    notice = f'<p class="doc-notice">{html.escape(message)}</p>' if message else ""
    if not providers:
        return _page(
            '<p class="doc-brand"><a href="/">Resonance</a></p>'
            "<h1>Sign-in is not configured</h1>"
            "<p class=\"doc-lede\">This deployment has no sign-in provider, so no "
            "account can be created. Nothing is stored and nothing is lost; the "
            "operator has to configure a provider before anyone can take part.</p>"
            '<p class="doc-foot"><a href="/">Back to Resonance</a></p>',
            status=503,
        )
    buttons = "\n".join(
        f'<a class="signin-provider" rel="nofollow" '
        f'href="/auth/start/{html.escape(name, quote=True)}?next={escaped_next}">'
        f"Continue with {html.escape(config.label)}</a>"
        for name, config in sorted(providers.items())
    )
    return _page(
        '<p class="doc-brand"><a href="/">Resonance</a></p>'
        "<h1>Sign in</h1>"
        '<p class="doc-lede">Resonance introduces people whose reasoning has the '
        "same shape. That only works if you are the same person each time you "
        "come back — from a browser, from Claude, from any chat you connect — "
        "and if there is a way to tell you when a match finally appears.</p>"
        f"{notice}"
        f'<div class="signin-providers">{buttons}</div>'
        '<p class="doc-fine">Resonance receives your email address and the name '
        "on your provider account. It never receives your password, and asks for "
        "no other access. Your email address is never shown to other people; what "
        "they can see is what you explicitly choose to share.</p>"
        '<p class="doc-foot"><a href="/">Back to Resonance</a> · '
        '<a href="/privacy">Privacy</a> · <a href="/terms">Terms</a></p>'
    )


class AuthMount:
    """Routes under `/auth/`, given an identity service and a cookie factory."""

    def __init__(self, identity: Any, *, cookie_for: Any, secure_cookies: bool,
                 environ: Mapping[str, str] | None = None,
                 states: SignInStates | None = None) -> None:
        self.identity = identity
        self.cookie_for = cookie_for
        self.secure_cookies = bool(secure_cookies)
        self._environ = environ
        self.states = states or SignInStates()

    @property
    def providers(self) -> dict[str, Any]:
        return configured_providers(self._environ)

    def handle(self, method: str, path: str, query: Mapping[str, list[str]],
               headers: Mapping[str, str], *, issuer: str) -> MountResponse:
        first = {k: (v[0] if v else "") for k, v in query.items()}
        if path == SIGN_IN_PATH and method in {"GET", "HEAD"}:
            return _sign_in_page(self.providers, safe_next(first.get("next")))
        if path.startswith("/auth/start/") and method in {"GET", "HEAD"}:
            return self._start(path[len("/auth/start/"):], first, issuer=issuer)
        if path.startswith("/auth/callback/") and method in {"GET", "HEAD"}:
            return self._callback(path[len("/auth/callback/"):], first, headers,
                                  issuer=issuer)
        if path == "/auth/sign-out" and method == "POST":
            return _redirect("/", cookies=(self._cleared_session_cookie(),))
        return MountResponse(404, {"Content-Type": "application/json; charset=utf-8"},
                             b'{"error":"not_found","message":"unknown auth path"}')

    # -- steps ------------------------------------------------------------
    def _start(self, provider_name: str, params: Mapping[str, str], *,
               issuer: str) -> MountResponse:
        providers = self.providers
        config = providers.get(provider_name)
        next_path = safe_next(params.get("next"))
        if config is None:
            return _sign_in_page(providers, next_path,
                                 message="That sign-in provider is not available here.")
        state, nonce = self.states.issue(provider=provider_name, next_path=next_path)
        redirect_uri = issuer.rstrip("/") + CALLBACK_TEMPLATE.format(provider=provider_name)
        return _redirect(
            config.authorize_redirect(redirect_uri=redirect_uri, state=state),
            cookies=(_state_cookie(nonce, secure=self.secure_cookies),),
        )

    def _callback(self, provider_name: str, params: Mapping[str, str],
                  headers: Mapping[str, str], *, issuer: str) -> MountResponse:
        providers = self.providers
        config = providers.get(provider_name)
        record = self.states.take(params.get("state", ""))
        cleared = _cleared_state_cookie(secure=self.secure_cookies)
        if config is None or record is None or record["provider"] != provider_name:
            return _sign_in_page(
                providers, "/",
                message="That sign-in attempt has expired. Please start again.",
            )
        next_path = safe_next(record.get("next"))
        if not secrets.compare_digest(_cookie_value(headers, STATE_COOKIE),
                                      str(record["nonce"])):
            # The state came back in a browser that did not begin the sign-in.
            return _sign_in_page(
                providers, next_path,
                message="That sign-in could not be verified in this browser. "
                        "Please start again.",
            )
        if params.get("error"):
            return _sign_in_page(providers, next_path,
                                 message="Sign-in was not completed.")
        code = params.get("code", "")
        if not code:
            return _sign_in_page(providers, next_path,
                                 message="The provider returned no authorization code.")
        redirect_uri = issuer.rstrip("/") + CALLBACK_TEMPLATE.format(provider=provider_name)
        try:
            person = exchange_code(config, code, redirect_uri)
        except FederationError:
            return _sign_in_page(
                providers, next_path,
                message="Your provider did not confirm a verified email address, "
                        "so no account was created.",
            )
        credentials = self.identity.sign_in_federated(
            provider=person.provider,
            subject=person.subject,
            email=person.email,
            email_verified=person.email_verified,
            display_label=person.display_label(),
        )
        return _redirect(next_path, cookies=(
            self.cookie_for(credentials.access_token),
            cleared,
        ))

    def _cleared_session_cookie(self) -> str:
        flag = "; Secure" if self.secure_cookies else ""
        return f"resonance_token=; HttpOnly; SameSite=Lax; Path=/; Max-Age=0{flag}"
