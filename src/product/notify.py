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
import json
import os
import smtplib
import ssl
import urllib.error
import urllib.request
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

    def send(self, to: str, subject: str, body: str,
             unsubscribe: str = "") -> bool:
        raise NotImplementedError


class NoTransport(Sender):
    """No mail server is configured, so nothing is sent and nothing pretends."""

    reason = ("nowhere to hand an email: set RESONANCE_MAIL_API_KEY and "
              "RESONANCE_MAIL_FROM (an HTTPS provider, which is what works "
              "where outbound SMTP is blocked), or the RESONANCE_SMTP_* "
              "variables where it is not")

    def send(self, to: str, subject: str, body: str,
             unsubscribe: str = "") -> bool:
        return False


class SmtpSender(Sender):
    """A real SMTP server, over TLS, with the credentials from the environment."""

    def __init__(self, host: str, port: int, user: str, password: str,
                 sender: str, reply_to: str = "", timeout: float = 20.0) -> None:
        self.host, self.port = host, port
        self.user, self.password = user, password
        self.sender, self.timeout = sender, timeout
        # Sent from a technical mailbox, answered by a person. Somebody who
        # replies to say "how did you get my address" or "please stop" is
        # asking the most important question this service can be asked, and an
        # address nobody reads is the wrong place for it to land.
        self.reply_to = reply_to

    def send(self, to: str, subject: str, body: str,
             unsubscribe: str = "") -> bool:
        message = EmailMessage()
        message["From"] = self.sender
        message["To"] = to
        message["Subject"] = subject
        if self.reply_to:
            message["Reply-To"] = self.reply_to
        # RFC 8058: an unsubscribe the mail client itself can offer, so the way
        # out is never harder to find than the way in. Passed in rather than
        # parsed back out of the body -- reading the last line of prose to find
        # a URL breaks the moment anyone edits a sentence, and it would break
        # by throwing, which loses the email rather than the header.
        if unsubscribe:
            message["List-Unsubscribe"] = f"<{unsubscribe}>"
            message["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"
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


class HttpApiSender(Sender):
    """An email provider's HTTPS API, because SMTP does not leave this host.

    Measured, not assumed: on the platform this runs on, ports 587, 465 and 25
    all time out on IPv4 and have no IPv6 route at all. That is a block, and no
    credential fixes it. Port 443 obviously works -- the site is served over it
    -- so the message goes out the same door as everything else.

    Written for Resend's shape (POST /emails with from/to/subject/text), which
    Postmark and Mailgun differ from only in field names and URL; swapping is a
    handful of lines if this one ever disappoints.
    """

    def __init__(self, api_key: str, sender: str, reply_to: str = "",
                 url: str = "https://api.resend.com/emails",
                 timeout: float = 20.0) -> None:
        self.api_key = api_key
        self.sender = sender
        self.reply_to = reply_to
        self.url = url
        self.timeout = timeout

    def send(self, to: str, subject: str, body: str,
             unsubscribe: str = "") -> bool:
        payload: dict[str, Any] = {"from": self.sender, "to": [to],
                                   "subject": subject, "text": body}
        if self.reply_to:
            payload["reply_to"] = self.reply_to
        if unsubscribe:
            # RFC 8058, same as over SMTP: the way out is a button in the mail
            # client, not a link to hunt for at the bottom.
            payload["headers"] = {
                "List-Unsubscribe": f"<{unsubscribe}>",
                "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
            }
        request = urllib.request.Request(
            self.url, data=json.dumps(payload).encode("utf-8"),
            headers={"Authorization": f"Bearer {self.api_key}",
                     "Content-Type": "application/json"},
            method="POST")
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return 200 <= response.status < 300
        except urllib.error.HTTPError as exc:
            # The provider's own words about why, which is the whole reason to
            # surface this rather than return a bare False.
            detail = exc.read().decode("utf-8", "replace")[:200]
            raise RuntimeError(f"{exc.code} {detail}") from exc


def sender_from_env(environ: Mapping[str, str] | None = None) -> Sender:
    env = environ if environ is not None else os.environ
    sender_address = str(env.get("RESONANCE_MAIL_FROM") or "").strip()
    reply_to_address = str(env.get("RESONANCE_MAIL_REPLY_TO")
                           or env.get("RESONANCE_CONTACT") or "").strip()

    # Preferred, because it is the one that works where this runs.
    api_key = str(env.get("RESONANCE_MAIL_API_KEY") or "").strip()
    if api_key and sender_address:
        return HttpApiSender(
            api_key, sender_address, reply_to_address,
            url=str(env.get("RESONANCE_MAIL_API_URL")
                    or "https://api.resend.com/emails").strip())

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
    # Falls back to the address the site already publishes as its contact, so
    # a reply reaches a person even when nobody set this.
    reply_to = str(env.get("RESONANCE_MAIL_REPLY_TO")
                   or env.get("RESONANCE_CONTACT") or "").strip()
    return SmtpSender(host, port, user, password, sender, reply_to)


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


SELF_TEST_SUBJECT = "Resonance can reach you"
SELF_TEST_BODY = (
    "This is the one message Resonance sends to prove it can send anything.\n\n"
    "If you are reading it, the mail path works end to end: the server has\n"
    "credentials, your provider accepted them, and the message arrived rather\n"
    "than being quarantined.\n\n"
    "Nothing about anybody was in this message, and nothing about anybody is\n"
    "in the real ones either -- they say that someone whose reasoning has the\n"
    "same shape as yours is here, and nothing more.\n\n"
    "Unset RESONANCE_MAIL_SELFTEST now; it costs one email on every restart.\n"
)


def reachability(host: str, ports: tuple[int, ...] = (587, 465, 25)) -> str:
    """Which of the mail server's addresses this host can actually open.

    "Network is unreachable" has two very different causes and one message:
    the platform blocks outbound SMTP, or the container has no IPv6 route and
    the resolver offered an AAAA record first. The first needs a different
    kind of transport; the second needs one line. Guessing between them costs
    an afternoon, so this asks each address on each port and reports what each
    one said.
    """
    import socket
    lines: list[str] = []
    for port in ports:
        try:
            candidates = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        except Exception as exc:  # noqa: BLE001
            lines.append(f"{port}: cannot resolve {host} ({exc})")
            continue
        for family, _type, _proto, _canon, sockaddr in candidates:
            name = "IPv6" if family == socket.AF_INET6 else "IPv4"
            probe = socket.socket(family, socket.SOCK_STREAM)
            probe.settimeout(6)
            try:
                probe.connect(sockaddr)
                lines.append(f"{port} {name} {sockaddr[0]}: open")
            except Exception as exc:  # noqa: BLE001
                lines.append(f"{port} {name} {sockaddr[0]}: {type(exc).__name__} {exc}")
            finally:
                probe.close()
    return "; ".join(lines) or "nothing to try"


def self_test(sender: Sender, address: str) -> str:
    """Send one message to a named address and say what happened.

    "The variables are set" and "mail leaves the building" are different
    claims, and only the second one matters. Proving the second normally needs
    two people and a real match; this proves it with neither, before anyone is
    invited and finds out the hard way that nothing arrives.

    Deliberately an operator action, like the purge and the pseudonym
    backfill: it goes to one address the operator names, never to a
    participant, and it says so in its own body.
    """
    if isinstance(sender, NoTransport):
        return f"not sent: {NoTransport.reason}"
    try:
        if sender.send(address, SELF_TEST_SUBJECT, SELF_TEST_BODY):
            return f"sent to {address}"
        return "not sent: the transport declined it"
    except Exception as exc:  # noqa: BLE001 - the whole point is to report this
        detail = ""
        host = getattr(sender, "host", "")
        if host:
            # A connection that never opened says nothing about credentials.
            # Report which addresses answered, so the next step is obvious
            # rather than a guess between "blocked" and "no route".
            detail = f" | reachability: {reachability(host)}"
        return f"not sent: {type(exc).__name__}: {exc}{detail}"


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
        stop = self.unsubscribe_url(user_id)
        body = _body(self.origin, stop)
        try:
            if not self.sender.send(address, SUBJECT, body, stop):
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
