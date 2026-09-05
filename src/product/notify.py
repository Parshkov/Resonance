"""Telling someone a resonance appeared, when they are not here (2026-09-05).

The product's promise is that it keeps looking after you leave: you say the one
thing you are working on, close the tab, and months later somebody arrives whose
reasoning has the same shape. The standing search does that faithfully -- it
records the finding, both ways, and never twice.

And then nobody was told. "Told" meant "will see it if they come back", so the
half of the promise that matters most -- the part that happens while you are
living your life -- did not happen at all. Someone could have been waiting for
three weeks with the answer sitting on a page they had no reason to open.

WHAT AN EMAIL FROM HERE SAYS. That something happened. Never what.

On the page, an arrival card names the other person's pseudonym and topic, and
that is right: they are signed in, on the surface where the match was made.
An email is a different room. It is forwarded, it sits in backups, it is read
by whatever assistant the person has pointed at their inbox, and it survives
long after both people have moved on. So it carries no pseudonym, no topic, no
field, no score -- nothing about the other person at all. It says that someone
is here, and where to look. Anyone who intercepts it learns that this address
uses Resonance, which they already knew by receiving it.

WHO GETS ONE. Only an address the person signed in with and the provider
verified, and only while they have not turned it off. One a day at most: the
standing search can find several people in a minute, and five emails would
teach someone to filter us out, after which the promise is broken again and
quietly.

WHEN THERE IS NO TRANSPORT. Nothing is sent, the fact is stated in the health
endpoint and printed once at startup, and no notification is recorded as
delivered. A queue that nobody drains is worse than an empty one: it looks
like the feature exists.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import smtplib
import ssl
import time
from email.message import EmailMessage
from typing import Any, Callable, Mapping

PREFERENCE_KIND = "notify_pref"
SENT_KIND = "notify_sent"
DAILY_LIMIT_SECONDS = 20 * 3600      # "once a day", forgiving of an early check

SUBJECT = "Someone is here whose reasoning has the same shape as yours"


def _body(origin: str, unsubscribe: str) -> str:
    return (
        "Someone whose reasoning has the same shape as yours is on Resonance.\n\n"
        "Who they are, what they are working on, and how close the match is are\n"
        "on the site -- this message deliberately carries none of it.\n\n"
        f"    {origin}\n\n"
        "They have not been told about you, and will not be unless you ask for an\n"
        "introduction and they agree.\n\n"
        "To stop these emails:\n"
        f"    {unsubscribe}\n"
    )


class Sender:
    """Somewhere to hand an email. Absent by default, and honest about it."""

    def send(self, to: str, subject: str, body: str) -> bool:
        raise NotImplementedError


class NoTransport(Sender):
    """No mail server is configured, so nothing is sent and nothing pretends."""

    reason = ("no mail server configured (set RESONANCE_SMTP_HOST, "
              "RESONANCE_SMTP_USER, RESONANCE_SMTP_PASSWORD, RESONANCE_MAIL_FROM)")

    def send(self, to: str, subject: str, body: str) -> bool:
        return False


class SmtpSender(Sender):
    """A real SMTP server, over TLS, with the credentials from the environment."""

    def __init__(self, host: str, port: int, user: str, password: str,
                 sender: str, timeout: float = 20.0) -> None:
        self.host, self.port = host, port
        self.user, self.password = user, password
        self.sender, self.timeout = sender, timeout

    def send(self, to: str, subject: str, body: str) -> bool:
        message = EmailMessage()
        message["From"] = self.sender
        message["To"] = to
        message["Subject"] = subject
        # RFC 8058: an unsubscribe that the mail client itself can offer, so
        # the way out is never harder to find than the way in.
        message["List-Unsubscribe"] = f"<{body.rsplit(chr(10), 2)[-2].strip()}>"
        message.set_content(body)
        context = ssl.create_default_context()
        if self.port == 465:
            with smtplib.SMTP_SSL(self.host, self.port, timeout=self.timeout,
                                  context=context) as server:
                server.login(self.user, self.password)
                server.send_message(message)
        else:
            with smtplib.SMTP(self.host, self.port, timeout=self.timeout) as server:
                server.starttls(context=context)
                server.login(self.user, self.password)
                server.send_message(message)
        return True


def sender_from_env(environ: Mapping[str, str] | None = None) -> Sender:
    env = environ if environ is not None else os.environ
    host = str(env.get("RESONANCE_SMTP_HOST") or "").strip()
    user = str(env.get("RESONANCE_SMTP_USER") or "").strip()
    password = str(env.get("RESONANCE_SMTP_PASSWORD") or "").strip()
    sender = str(env.get("RESONANCE_MAIL_FROM") or "").strip()
    if not (host and user and password and sender):
        return NoTransport()
    try:
        port = int(str(env.get("RESONANCE_SMTP_PORT") or "587"))
    except ValueError:
        port = 587
    return SmtpSender(host, port, user, password, sender)


def unsubscribe_token(user_id: str, secret: bytes) -> str:
    """A token that stands on its own, and carries the account inside itself.

    Someone deciding to stop hearing from us should not have to sign in first:
    "to stop these emails, log in" is the sentence nobody follows, and the
    alternative they choose is marking us as spam -- after which nobody here
    is reachable again, quietly.

    The account is inside the token rather than beside it in the URL. A bare
    `?who=person-…` would travel through mail logs, proxy logs, and the
    history of whoever forwards the message; the id is not a secret from its
    owner, but it should not be lying around in other people's records either.
    """
    packed = base64.urlsafe_b64encode(user_id.encode()).decode().rstrip("=")
    digest = hmac.new(secret, f"unsubscribe:{user_id}".encode(), hashlib.sha256)
    return f"{packed}.{digest.hexdigest()[:32]}"


def account_in_token(token: str, secret: bytes) -> str | None:
    """The account a token is for, or nothing if it was not signed for one."""
    packed, _, signature = str(token or "").partition(".")
    if not packed or not signature:
        return None
    try:
        user_id = base64.urlsafe_b64decode(packed + "=" * (-len(packed) % 4)).decode()
    except Exception:  # noqa: BLE001 - a malformed token is simply not a token
        return None
    expected = hmac.new(secret, f"unsubscribe:{user_id}".encode(), hashlib.sha256)
    if not hmac.compare_digest(expected.hexdigest()[:32], signature):
        return None
    return user_id


def unsubscribe_matches(user_id: str, token: str, secret: bytes) -> bool:
    return account_in_token(token, secret) == user_id


class Notifier:
    """Decides who to tell, and remembers that they were told."""

    def __init__(self, identity: Any, repository: Any, *, origin: str,
                 secret: bytes, sender: Sender | None = None,
                 clock: Callable[[], float] = time.time) -> None:
        self.identity = identity
        self.repository = repository
        self.origin = origin.rstrip("/")
        self.secret = secret
        self.sender = sender or sender_from_env()
        self.clock = clock

    # -- the person's own choice ----------------------------------------
    def wants_email(self, user_id: str) -> bool:
        record = self._get(PREFERENCE_KIND, user_id)
        return not (record or {}).get("unsubscribed", False)

    def unsubscribe(self, user_id: str) -> None:
        self._put(PREFERENCE_KIND, user_id, {"unsubscribed": True,
                                             "at": self.clock()}, user_id)

    def resubscribe(self, user_id: str) -> None:
        self._put(PREFERENCE_KIND, user_id, {"unsubscribed": False,
                                             "at": self.clock()}, user_id)

    def unsubscribe_url(self, user_id: str) -> str:
        return (f"{self.origin}/notifications/stop"
                f"?token={unsubscribe_token(user_id, self.secret)}")

    # -- deciding -------------------------------------------------------
    def address_for(self, user_id: str) -> str | None:
        """A verified address this person signed in with, or nothing.

        An unverified address belongs to whoever claimed it, and telling that
        stranger a resonance appeared would be the first thing this product
        must never do.
        """
        try:
            claims = self.identity.identity_claims(user_id) or {}
        except Exception:  # noqa: BLE001 - never fail a share over a lookup
            return None
        email = str(claims.get("email") or "").strip()
        if not email or not claims.get("email_verified"):
            return None
        return email

    def _recently_told(self, user_id: str) -> bool:
        record = self._get(SENT_KIND, user_id) or {}
        last = float(record.get("at") or 0.0)
        return (self.clock() - last) < DAILY_LIMIT_SECONDS

    # -- doing ----------------------------------------------------------
    def tell(self, user_id: str) -> str:
        """Tell this person something arrived. Returns what happened, for logs.

        Every refusal is a word rather than a silent False, because the one
        thing worse than not sending is not knowing why nothing was sent.
        """
        if isinstance(self.sender, NoTransport):
            return "no_transport"
        if not self.wants_email(user_id):
            return "unsubscribed"
        if self._recently_told(user_id):
            return "already_told_today"
        address = self.address_for(user_id)
        if not address:
            return "no_verified_address"
        body = _body(self.origin, self.unsubscribe_url(user_id))
        try:
            if not self.sender.send(address, SUBJECT, body):
                return "transport_declined"
        except Exception as exc:  # noqa: BLE001 - a share must never fail on mail
            print(f"[notify] could not send: {type(exc).__name__}: {exc}", flush=True)
            return "send_failed"
        self._put(SENT_KIND, user_id, {"at": self.clock()}, user_id)
        return "sent"

    # -- storage --------------------------------------------------------
    def _get(self, kind: str, key: str) -> dict[str, Any] | None:
        try:
            record = self.repository.get_grant(kind, key)
        except Exception:  # noqa: BLE001
            return None
        return dict(record) if record else None

    def _put(self, kind: str, key: str, payload: Mapping[str, Any],
             user_id: str) -> None:
        try:
            self.repository.put_grant(kind, key, dict(payload), user_id=user_id)
        except Exception as exc:  # noqa: BLE001
            print(f"[notify] could not record {kind}: "
                  f"{type(exc).__name__}: {exc}", flush=True)
