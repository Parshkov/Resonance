"""Authenticated HTTP server for the live product.

Manual UI, browser WebMCP tools, and plain HTTP clients converge on one
`LiveProductService`. The server owns only transport concerns: cookie session
issuance, CSRF header relay, Origin relay, body bounds, security headers, and
JSON shaping. All authorization, consent, freshness, and discovery semantics
stay in the accepted layers underneath.

The accepted R10 browser tool surface (`demo/ui/webmcp.mjs`) is served as-is
and its `/api/webmcp/*` wire contract is exposed here backed by the live
service, so the exact accepted tools operate on real authenticated state.
"""

from __future__ import annotations

import argparse
import os
import json
from html import escape
import secrets
import threading
import time
from collections import deque
from dataclasses import dataclass
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import parse_qs, urlparse

from src.identity import IdentityService, R11IdentityBackend
from src.identity.service import ACCOUNT_IDENTITY_LINKED
from src.identity.models import (
    AuthenticationError,
    AuthorizationError,
    ConfirmationRequiredError,
    ConsentChoices,
    CsrfError,
    IdentityValidationError,
)
from src.ingestion.service import (
    ConfirmationError,
    DraftNotFound,
    IngestionError,
    ShareIntent,
)
from src.persistence import LiveCorpusService
from src.persistence.factory import open_repository
from src.persistence.errors import (
    PersistenceConflictError,
    PersistenceStaleIndexError,
    PersistenceStateError,
    PersistenceValidationError,
)
from src.persistence.seed import seed_r7
from src.collaboration import CollaborationError
from src.workspaces import WorkspaceError
from src.security.models import ConfirmationRequired as PolicyConfirmationRequired
from src.product import authorship as authorship_rule
from src.product.notify import (Notifier, NoTransport, account_in_token,
                                self_test)
from src.product.service import LiveProductService, ProductError, StaleResultError
from src.product.mcp_bridge import (
    BridgeError,
    INVALID_REQUEST,
    PARSE_ERROR,
    RemoteMCPBridge,
    bearer_token,
)
from src.product import auth_mount, oauth_mount

REPO = Path(__file__).resolve().parents[2]
UI_DIR = REPO / "demo" / "ui"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8788
MAX_BODY_BYTES = 96 * 1024
# Unauthenticated account creation is bounded per client address so an
# anonymous caller cannot grow the database or spam introductions.
REGISTRATION_LIMIT = 20
REGISTRATION_WINDOW_SECONDS = 3600.0
_registration_hits: dict[str, deque] = {}
_registration_lock = threading.Lock()


def _client_ip(headers: Mapping[str, str], peer: str) -> str:
    forwarded = (headers.get("X-Forwarded-For") or "").split(",", 1)[0].strip()
    return forwarded or peer


def registration_allowed(ip: str, *, now: float | None = None) -> bool:
    if ip in ("127.0.0.1", "::1", "localhost", ""):
        return True                        # local development / test harness
    now = time.monotonic() if now is None else now
    with _registration_lock:
        hits = _registration_hits.setdefault(ip, deque())
        while hits and now - hits[0] > REGISTRATION_WINDOW_SECONDS:
            hits.popleft()
        if len(hits) >= REGISTRATION_LIMIT:
            return False
        hits.append(now)
        return True
COOKIE_NAME = "resonance_token"

STATIC = {
    "/styles.css": ("styles.css", "text/css; charset=utf-8"),
    "/app.mjs": ("app.mjs", "text/javascript; charset=utf-8"),
    "/webmcp.mjs": ("webmcp.mjs", "text/javascript; charset=utf-8"),
    "/deeplink.mjs": ("deeplink.mjs", "text/javascript; charset=utf-8"),
    "/collab.mjs": ("collab.mjs", "text/javascript; charset=utf-8"),
    "/session.mjs": ("session.mjs", "text/javascript; charset=utf-8"),
    "/collab_ui.mjs": ("collab_ui.mjs", "text/javascript; charset=utf-8"),
    "/workspaces.mjs": ("workspaces.mjs", "text/javascript; charset=utf-8"),
    "/account.mjs": ("account.mjs", "text/javascript; charset=utf-8"),
    # One file per piece of work, so several people can build at once without
    # meeting in the middle of styles.css.
    "/topics.mjs": ("topics.mjs", "text/javascript; charset=utf-8"),
    "/topics.css": ("topics.css", "text/css; charset=utf-8"),
    "/geo.mjs": ("geo.mjs", "text/javascript; charset=utf-8"),
    "/geo.css": ("geo.css", "text/css; charset=utf-8"),
    "/shared_list.mjs": ("shared_list.mjs", "text/javascript; charset=utf-8"),
    "/shared_list.css": ("shared_list.css", "text/css; charset=utf-8"),
    # The frame: colour scheme (applied before first paint), navigation built
    # from the sections that are on the page, notices. Loaded by index.html.
    "/theme.mjs": ("theme.mjs", "text/javascript; charset=utf-8"),
    "/shell.mjs": ("shell.mjs", "text/javascript; charset=utf-8"),
    # What the standing search found while the person was away.
    "/resonances.mjs": ("resonances.mjs", "text/javascript; charset=utf-8"),
    # R16 Chrome audit: collaboration drawer + narrow-viewport rules (CSP-safe
    # linked stylesheet) and a favicon (the page used to 404 on /favicon.ico).
    "/live_ui.css": ("live_ui.css", "text/css; charset=utf-8"),
    "/legal.css": ("legal.css", "text/css; charset=utf-8"),
    "/favicon.svg": ("favicon.svg", "image/svg+xml"),
    "/favicon.ico": ("favicon.svg", "image/svg+xml"),
}

def _mcp_path_token(path: str) -> str | None:
    """`/mcp` -> "" (key must come in the Authorization header);
    `/mcp/<key>` -> key; anything else -> None."""
    if path == "/mcp":
        return ""
    if path.startswith("/mcp/"):
        key = path[len("/mcp/"):]
        return key if key and "/" not in key else None
    return None


HEAD_INJECTION = (
    '  <link rel="icon" href="/favicon.svg" type="image/svg+xml">\n'
    '  <link rel="stylesheet" href="/live_ui.css">\n</head>'
)


@dataclass
class ProductRuntime:
    live: LiveCorpusService
    identity: IdentityService
    product: LiveProductService
    allowed_origins: frozenset[str]


def engine_identity(runtime: "ProductRuntime") -> dict[str, str]:
    """Versions a tester needs to know which engine answered (no secrets)."""
    from src import scoring as _scoring
    from src.engine import ENGINE_VERSION
    from src.extraction import EXTRACTOR_VERSION
    from src.fingerprint.keys import FEATURE_VERSION
    from src.index import INDEX_VERSION
    from src.semantics import SEMANTICS_VERSION
    engine = runtime.live.engine
    return {
        "engine_version": ENGINE_VERSION,
        "scoring_version": _scoring.SCORE_MODEL_VERSION,
        "classify_policy": _scoring.CLASSIFY_POLICY,
        "index_version": INDEX_VERSION,
        "feature_version": FEATURE_VERSION,
        "semantics_version": SEMANTICS_VERSION,
        "extractor_version": EXTRACTOR_VERSION,
        "verifier_config_hash": engine.verifier.config_hash,
    }


def corpus_summary(runtime: "ProductRuntime") -> dict[str, Any]:
    """How much of the live corpus is real people vs seeded demo personas."""
    kinds = runtime.live.session_kinds()
    demo = sum(n for kind, n in kinds.items() if kind != "volunteer")
    return {"sessions_by_kind": kinds, "volunteer_sessions": kinds.get("volunteer", 0),
            "demo_sessions": demo, "demo_personas_present": demo > 0}


def startup_purge_demo(runtime: "ProductRuntime", environ: Mapping[str, str] | None = None) -> dict[str, int] | None:
    """One-shot operator action: ``RESONANCE_PURGE_DEMO=1`` tombstones every seeded
    demo session and revokes the demo persona accounts at process start
    (idempotent; real participants are never touched). Prints counts only."""
    environ = os.environ if environ is None else environ
    if environ.get("RESONANCE_PURGE_DEMO", "").strip().lower() not in ("1", "true", "yes", "on"):
        return None
    from src.persistence.seed import purge_demo
    result = purge_demo(runtime.live)
    print(f"purge-demo: sessions_deleted={result['sessions_deleted']} "
          f"users_revoked={result['users_revoked']} (RESONANCE_PURGE_DEMO set; unset it after this deploy)")
    return result


def startup_purge_sessions(runtime: "ProductRuntime",
                           environ: Mapping[str, str] | None = None) -> dict[str, Any] | None:
    """One-shot operator action: ``RESONANCE_PURGE_SESSIONS=<id>[,<id>…]``
    tombstones exactly the sessions the operator named, at process start.

    This exists because `purge-demo` deliberately cannot help here. It selects
    rows by `record_kind != "volunteer"`, and the rows an owner actually needs
    to remove — duplicate guest sessions left by acceptance runs before they
    learned to revoke themselves — are real `volunteer` records. The product's
    own `delete_session` needs the *owner's* access token, and those guests'
    tokens are long gone.

    So this deletes by explicit id and nothing else. It never selects rows on
    its own, never matches a pattern, and never touches a session the operator
    did not type. Every id is reported with what happened to it, including ids
    that do not exist and ids that were already deleted, so a run that quietly
    did less than the operator intended is visible in the log. Idempotent: a
    second run reports `already_deleted` for everything and changes nothing.

    Prints ids and counts only — never a topic, a label or any thought content.
    """
    environ = os.environ if environ is None else environ
    raw = (environ.get("RESONANCE_PURGE_SESSIONS") or "").strip()
    if not raw:
        return None
    wanted: list[str] = []
    for chunk in raw.replace(",", " ").split():
        token = chunk.strip()
        if token and token not in wanted:
            wanted.append(token)
    outcome: dict[str, str] = {}
    deleted = 0
    for session_id in wanted:
        session = runtime.live.get_session(session_id)
        if session is None:
            outcome[session_id] = "missing"
            continue
        if session.deleted_at is not None:
            outcome[session_id] = "already_deleted"
            continue
        runtime.live.delete_session(session_id, rebuild=False)
        outcome[session_id] = "deleted"
        deleted += 1
    if deleted:
        runtime.live.rebuild_index()
    result = {"requested": len(wanted), "deleted": deleted,
              "already_deleted": sum(1 for v in outcome.values() if v == "already_deleted"),
              "missing": sum(1 for v in outcome.values() if v == "missing"),
              "outcome": outcome}
    print(f"purge-sessions: requested={result['requested']} deleted={result['deleted']} "
          f"already_deleted={result['already_deleted']} missing={result['missing']} "
          f"({', '.join(f'{k}={v}' for k, v in outcome.items())}) "
          f"(RESONANCE_PURGE_SESSIONS set; unset it after this deploy)")
    return result


def startup_assign_pseudonyms(runtime: "ProductRuntime",
                              environ: Mapping[str, str] | None = None) -> dict[str, Any] | None:
    """One-shot operator action: give a human pseudonym to accounts that lack one.

    ``RESONANCE_ASSIGN_PSEUDONYMS=report`` counts and prints; ``=1`` applies.

    The display label is what other participants see. Two kinds of account have
    the wrong thing there: the ones created before pseudonyms existed, whose
    label is a `guest-…` identifier, and — far worse — the ones created by
    federated sign-in before this was fixed, whose label is the person's real
    name as their provider knows it. A structural match is not consent to learn
    someone's name, so that is a disclosure, not an aesthetic problem.

    An account already carrying a pseudonym from this service's own vocabulary
    is left exactly as it is, so a second run changes nothing. Prints counts and
    account ids only — never the label being replaced, because that label is the
    very thing that should not be written down anywhere else.
    """
    environ = os.environ if environ is None else environ
    mode = (environ.get("RESONANCE_ASSIGN_PSEUDONYMS") or "").strip().lower()
    if mode not in {"1", "true", "yes", "report", "dry-run"}:
        return None
    dry_run = mode in {"report", "dry-run"}

    from src.identity.pseudonyms import generate as _generate, is_pseudonym

    users = list(runtime.live.repo.list_users())
    taken = {str(getattr(u, "display_label", "") or "") for u in users
             if is_pseudonym(getattr(u, "display_label", ""))}
    live = [u for u in users if getattr(u, "revoked_at", None) is None]
    revoked = len(users) - len(live)
    # Counted separately rather than as "everything we are not renaming". A
    # single skipped-count conflated revoked accounts with accounts that
    # already had a pseudonym, and an operator reads these numbers before
    # deciding to change 160 people's names.
    already_named = [u for u in live if is_pseudonym(getattr(u, "display_label", ""))]
    needs = [u for u in live if not is_pseudonym(getattr(u, "display_label", ""))]

    assigned: list[str] = []
    for user in needs:
        name = _generate(taken)
        taken.add(name)
        if not dry_run:
            runtime.live.create_user(user.user_id, display_label=name, rebuild=False)
        assigned.append(user.user_id)
    if not dry_run and assigned:
        runtime.live.rebuild_index()

    result = {
        "dry_run": dry_run,
        "accounts": len(users),
        "revoked_skipped": revoked,
        "already_named": len(already_named),
        "assigned": len(assigned),
        "account_ids": assigned,
    }
    print(f"assign-pseudonyms: {'REPORT ONLY, nothing changed' if dry_run else 'applied'} "
          f"accounts={result['accounts']} revoked_skipped={result['revoked_skipped']} "
          f"already_named={result['already_named']} assigned={result['assigned']} "
          f"(RESONANCE_ASSIGN_PSEUDONYMS set; unset it after this deploy)")
    return result


def startup_purge_unsigned(runtime: "ProductRuntime",
                           environ: Mapping[str, str] | None = None) -> dict[str, Any] | None:
    """One-shot operator action: retire every account nobody ever signed into.

    ``RESONANCE_PURGE_UNSIGNED=report`` counts and prints; ``=1`` carries it out.

    This applies the product's own rule to what came before it. Resonance
    introduces people to each other, so an account has to belong to someone who
    can be recognised on return and reached when a match appears. An account
    with no verified sign-in behind it can be neither. Leaving its thoughts
    discoverable is worse than an empty corpus: a real participant is shown a
    resonance with someone who can never accept an introduction — the service
    inventing a person.

    `purge-demo` cannot help here, because it selects on `record_kind` and these
    are genuine `volunteer` rows left by acceptance runs. The distinction that
    matters is not what kind of row it is, but whether a person stands behind it.

    An account is spared when the identity log carries a linked provider
    identity for it, and when its id is listed in ``RESONANCE_PURGE_KEEP``.
    Prints ids and counts only — never a topic, a label or any thought content.
    Idempotent: a second run finds nothing left to do.
    """
    environ = os.environ if environ is None else environ
    mode = (environ.get("RESONANCE_PURGE_UNSIGNED") or "").strip().lower()
    if mode not in {"1", "true", "yes", "report", "dry-run"}:
        return None
    dry_run = mode in {"report", "dry-run"}
    keep = {token for token in
            (environ.get("RESONANCE_PURGE_KEEP") or "").replace(",", " ").split()
            if token}

    identity = runtime.identity
    signed_in = {
        event.user_id for event in identity.backend.list_identity_events()
        if event.event_type == ACCOUNT_IDENTITY_LINKED and event.user_id
    }
    sessions = [row for row in runtime.live.repo.list_sessions()
                if getattr(row, "deleted_at", None) is None]
    doomed_sessions: list[str] = []
    doomed_owners: set[str] = set()
    for row in sessions:
        session_id = str(getattr(row, "session_id", "") or "")
        owner = identity.policy_source.owner_of("session", session_id)
        if not owner or owner in signed_in or owner in keep or session_id in keep:
            continue
        doomed_sessions.append(session_id)
        doomed_owners.add(owner)

    # An account with no verified sign-in and nothing shared is an empty shell
    # left by an acceptance run. Under the rule this action exists to apply it
    # should not exist at all, and leaving it behind means the next operator
    # reads a count of hundreds of "accounts" that are nobody.
    owners_with_surviving_sessions = set()
    for row in sessions:
        session_id = str(getattr(row, "session_id", "") or "")
        if session_id in doomed_sessions:
            continue
        owner = identity.policy_source.owner_of("session", session_id)
        if owner:
            owners_with_surviving_sessions.add(owner)
    empty_accounts = []
    for user in runtime.live.repo.list_users():
        user_id = str(getattr(user, "user_id", "") or "")
        if getattr(user, "revoked_at", None) is not None:
            continue
        if not user_id or user_id in signed_in or user_id in keep:
            continue
        if user_id in owners_with_surviving_sessions:
            continue
        empty_accounts.append(user_id)
    doomed_owners.update(empty_accounts)

    result: dict[str, Any] = {
        "dry_run": dry_run,
        "sessions_considered": len(sessions),
        "accounts_signed_in": len(signed_in),
        "sessions_to_delete": len(doomed_sessions),
        "accounts_to_revoke": len(doomed_owners),
        "empty_accounts": len(empty_accounts),
        "kept_by_request": sorted(keep),
    }
    if not dry_run and (doomed_sessions or doomed_owners):
        for session_id in doomed_sessions:
            runtime.live.delete_session(session_id, rebuild=False)
        for user_id in sorted(doomed_owners):
            try:
                runtime.live.revoke_user(user_id)
            except Exception as exc:  # noqa: BLE001 - report, never abort the boot
                print(f"purge-unsigned: could not revoke {user_id} "
                      f"({exc.__class__.__name__})")
        if doomed_sessions:
            runtime.live.rebuild_index()
        result["deleted"] = len(doomed_sessions)
    print(f"purge-unsigned: {'REPORT ONLY, nothing changed' if dry_run else 'applied'} "
          f"sessions_considered={result['sessions_considered']} "
          f"accounts_signed_in={result['accounts_signed_in']} "
          f"sessions_to_delete={result['sessions_to_delete']} "
          f"accounts_to_revoke={result['accounts_to_revoke']} "
          f"(of which empty={result['empty_accounts']}) kept={len(keep)} "
          f"(RESONANCE_PURGE_UNSIGNED set; unset it after this deploy)")
    return result


def build_runtime(
    db_path: str = ":memory:",
    *,
    allowed_origins: frozenset[str],
    confirmation_secret: bytes | None = None,
    seed: bool | None = None,
    # The order the operator declared origins in is the only thing that says
    # which host is canonical: a set cannot. Links in an email must point at
    # the host people actually use -- picking alphabetically sent them to a
    # platform host that had been deleted.
    declared_origins: Sequence[str] | None = None,
) -> ProductRuntime:
    """``seed=None`` seeds the R7 demo corpus only for an ephemeral ``:memory:``
    database (local development, tests). A persistent database is never seeded
    unless the operator asks for it explicitly (``--seed-demo`` /
    ``RESONANCE_SEED_DEMO=1``); seeded rows are demo personas, not people."""
    if seed is None:
        seed = db_path == ":memory:"
    # Explicit path or DSN: a postgres:// / postgresql:// target selects the
    # PostgreSQL repository, anything else is a SQLite file (or ":memory:").
    # Previously this hard-wired SQLiteRepository, so a DSN was silently treated
    # as a file name and the live product could never run on PostgreSQL.
    live = LiveCorpusService(open_repository(db_path))
    if seed:
        seed_r7(live)
    identity = IdentityService(
        R11IdentityBackend(live), allowed_origins=allowed_origins
    )
    if confirmation_secret is None:
        # Ephemeral runtime only; persistent DBs are gated at the CLI boundary.
        confirmation_secret = secrets.token_bytes(32)
    elif not confirmation_secret:
        raise ValueError(
            "confirmation_secret must be non-empty; an empty secret would "
            "silently fall back to a per-process value and orphan drafts"
        )
    product = LiveProductService(identity, confirmation_secret=confirmation_secret)
    # Someone who has left is reached where they are, or not at all. The
    # transport is configured by environment; without one, nothing is sent and
    # the health endpoint says so rather than implying a promise being kept.
    notifier = Notifier(
        identity, getattr(live, "repo", None),
        origin=oauth_mount.canonical_origin(declared_origins, allowed_origins),
        secret=confirmation_secret)
    product.standing.notifier = notifier
    product.notifier = notifier
    address = str(os.environ.get("RESONANCE_MAIL_SELFTEST") or "").strip()
    if address and "@" in address:
        # One message, to one address the operator named, to answer the only
        # question the health endpoint cannot: does mail actually arrive.
        print(f"mail self-test: {self_test(notifier.sender, address)}", flush=True)
    if isinstance(notifier.sender, NoTransport):
        # Once, here, rather than on every finding: a deployment that cannot
        # reach anyone should be impossible to miss and impossible to drown in.
        print(f"notifications: nobody can be reached — {NoTransport.reason}",
              flush=True)
    return ProductRuntime(live=live, identity=identity, product=product,
                          allowed_origins=allowed_origins)



def _unsubscribe_page(stopped: bool) -> str:
    """One sentence and a way back. Nothing to sign into, nothing to undo by
    accident: someone who arrives here has already decided."""
    said = ("You will not get any more email from Resonance.<br>"
            "Your thought is untouched: it is still discoverable, still "
            "looking, and whatever it finds is on the site when you visit."
            if stopped else
            "That link has expired or was not meant for this account, so "
            "nothing was changed. The unsubscribe link at the bottom of any "
            "Resonance email will work.")
    return (
        '<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        "<title>Resonance email</title>"
        '<link rel="stylesheet" href="/oauth/consent.css">'
        '<script src="/theme.mjs"></script></head><body>'
        '<main class="consent"><p class="brand">'
        '<span class="mark" aria-hidden="true"></span>Resonance</p>'
        f"<h1>{'Email stopped' if stopped else 'Nothing changed'}</h1>"
        f"<p>{said}</p>"
        '<p><a class="primary-link" href="/">Back to Resonance</a></p>'
        "</main></body></html>"
    )


class _DiscardWriter:
    """Sink for HEAD responses: headers are already flushed, the body is dropped.
    Installed only between end_headers() and the end of do_HEAD(), which puts
    the real socket writer back before socketserver finishes the request."""

    closed = False

    def write(self, data: bytes) -> int:
        return len(data)

    def flush(self) -> None:
        pass

    def close(self) -> None:
        pass


class ProductHandler(BaseHTTPRequestHandler):
    server_version = "ResonanceLiveProduct/0.1"
    runtime: ProductRuntime  # injected via server factory

    # -- plumbing ----------------------------------------------------------
    def log_message(self, fmt: str, *args: Any) -> None:  # quiet tests
        pass

    def _security_headers(self) -> None:
        self.send_header("Content-Security-Policy",
                         "default-src 'self'; frame-ancestors 'none'")
        self.send_header("Cross-Origin-Opener-Policy", "same-origin")
        self.send_header("Permissions-Policy", "tools=(self)")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")

    def _send_json(self, payload: Mapping[str, Any],
                   status: HTTPStatus = HTTPStatus.OK,
                   cookie: str | None = None) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        if cookie is not None:
            self.send_header("Set-Cookie", cookie)
        self._security_headers()
        self.end_headers()
        self.wfile.write(body)

    def _send_error_json(self, status: HTTPStatus, code: str, message: str) -> None:
        self._send_json({"error": code, "message": message}, status)

    def _send_bytes(self, body: bytes, content_type: str) -> None:
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self._security_headers()
        self.end_headers()
        self.wfile.write(body)

    def _body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or 0)
        if length < 0 or length > MAX_BODY_BYTES:
            raise IngestionError("request body exceeds product bound")
        raw = self.rfile.read(length) if length else b"{}"
        try:
            parsed = json.loads(raw.decode("utf-8") or "{}")
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise IngestionError("request body must be a JSON object") from exc
        if not isinstance(parsed, dict):
            raise IngestionError("request body must be a JSON object")
        return parsed

    def _token(self) -> str:
        cookie = SimpleCookie(self.headers.get("Cookie", ""))
        morsel = cookie.get(COOKIE_NAME)
        if morsel is None or not morsel.value:
            raise AuthenticationError("missing session cookie")
        return morsel.value

    def _origin(self) -> str | None:
        return self.headers.get("Origin")

    def _csrf(self) -> str | None:
        return self.headers.get("X-Resonance-CSRF")

    def _secure_cookies(self) -> bool:
        origins = self.runtime.allowed_origins
        return bool(origins) and all(o.startswith("https://") for o in origins)

    def _cookie_for(self, token: str) -> str:
        # Behind a TLS-terminating proxy the process only ever sees plain HTTP,
        # so derive `Secure` from the deployment contract instead: when every
        # allowed browser origin is https://, the cookie must never travel over
        # http. Local http://127.0.0.1 runs and tests keep the plain form.
        secure = "; Secure" if self._secure_cookies() else ""
        # Lax, not Strict. Resonance is reached through cross-site top-level
        # navigations by design: a chat client sends the browser from claude.ai
        # or chatgpt.com to /oauth/authorize. Under Strict the session cookie
        # was not sent on that navigation, so the consent page could not see
        # that this browser was already signed in, and every client connection
        # bound to a separate account — the same person split across surfaces,
        # which is precisely what this product cannot afford.
        #
        # Lax is safe here because the cookie is not what authorises writes.
        # Every state-changing request is a POST carrying an X-Resonance-CSRF
        # token checked against the session, with the Origin checked against
        # the allowlist; Lax withholds the cookie from cross-site POSTs anyway.
        return (f"{COOKIE_NAME}={token}; HttpOnly; SameSite=Lax; Path=/{secure}")

    def _security_kwargs(self) -> dict[str, Any]:
        return {
            "csrf_token": self._csrf(),
            "origin": self._origin(),
            "cookie_authenticated": True,
            "client_id": "live-product-http",
        }

    # -- routing -----------------------------------------------------------
    def do_HEAD(self) -> None:  # noqa: N802
        # Link scanners, uptime checkers and browsers preflight with HEAD; the
        # stdlib handler answered 501. Run the GET route and drop the body: the
        # headers (status, Content-Type, Content-Length, security headers) are
        # exactly those of the GET.
        real_wfile = self.wfile
        self._head_only = True
        try:
            self.do_GET()
        finally:
            self._head_only = False
            self.wfile = real_wfile

    def end_headers(self) -> None:
        super().end_headers()
        if getattr(self, "_head_only", False):
            self.wfile = _DiscardWriter()

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        try:
            if oauth_mount.is_oauth_path(parsed.path):
                self._handle_oauth("GET", parsed.path, parse_qs(parsed.query))
                return
            if auth_mount.is_auth_path(parsed.path):
                self._handle_auth("GET", parsed.path, parse_qs(parsed.query))
                return
            self._route_get(parsed.path, parse_qs(parsed.query))
        except Exception as exc:  # noqa: BLE001 - transport boundary
            self._handle_error(exc)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        try:
            if _mcp_path_token(parsed.path) is not None:
                self._handle_mcp(parsed.path)
                return
            if oauth_mount.is_oauth_path(parsed.path):
                self._handle_oauth("POST", parsed.path, parse_qs(parsed.query))
                return
            if auth_mount.is_auth_path(parsed.path):
                self._handle_auth("POST", parsed.path, parse_qs(parsed.query))
                return
            self._route_post(parsed.path)
        except Exception as exc:  # noqa: BLE001 - transport boundary
            self._handle_error(exc)

    # -- sign-in mount ---------------------------------------------------------
    def _auth_mount(self) -> Any:
        """One mount per process, so a sign-in in flight survives the redirect
        out to the provider and back."""
        mount = getattr(self.runtime, "auth_mount", None)
        if mount is None:
            mount = auth_mount.AuthMount(
                self.runtime.identity,
                cookie_for=self._cookie_for,
                secure_cookies=self._secure_cookies(),
            )
            self.runtime.auth_mount = mount
        # The cookie factory is bound to a handler instance, and handlers are
        # per-request; rebind so the long-lived mount always writes a cookie
        # shaped by the request it is answering.
        mount.cookie_for = self._cookie_for
        mount.secure_cookies = self._secure_cookies()
        return mount

    def _handle_auth(self, method: str, path: str, query: dict[str, list[str]]) -> None:
        response = self._auth_mount().handle(
            method, path, query, {k: v for k, v in self.headers.items()},
            issuer=self._issuer())
        self.send_response(response.status)
        headers = dict(response.headers)
        headers["Content-Length"] = str(len(response.body))
        for key, value in headers.items():
            self.send_header(key, value)
        for cookie in response.cookies:
            self.send_header("Set-Cookie", cookie)
        self._security_headers()
        self.end_headers()
        if response.body:
            self.wfile.write(response.body)

    def _sign_in_required(self) -> bool:
        """True where a real sign-in is on offer.

        Resonance introduces people to each other, so an account has to belong
        to someone who can be recognised on return and told when a match
        appears. Wherever a provider is configured, that is the only way in. A
        deployment with no provider at all — a local run, the test suite — has
        no sign-in to insist on, and keeps the pseudonymous path.
        """
        return bool(self._auth_mount().providers)

    # -- canonical OAuth mount (R15C, #136) ------------------------------------
    def _issuer(self) -> str:
        return oauth_mount.public_issuer(self.runtime.allowed_origins, self.headers)

    def _oauth_core(self) -> Any:
        # The protocol core is owned by src/remote (R15A); the runtime carries
        # it when configured. Without it the paths answer 404 and nothing else
        # in the product changes.
        return getattr(self.runtime, "oauth_core", None)

    def _handle_oauth(self, method: str, path: str, query: dict[str, list[str]]) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        if length < 0 or length > MAX_BODY_BYTES:
            raise IngestionError("request body exceeds product bound")
        body = self.rfile.read(length) if (length and method == "POST") else b""
        core = self._oauth_core()
        if core is None:
            self._send_error_json(HTTPStatus.NOT_FOUND, "not_found", "unknown path")
            return
        response = oauth_mount.dispatch(
            core, method=method, path=path, query=query,
            headers={k: v for k, v in self.headers.items()}, body=body, issuer=self._issuer())
        self.send_response(response.status)
        headers = dict(response.headers)
        if response.status != 304:
            # A 304 answers "what you have is current" and carries no
            # representation, so it must not describe one: no body, and no
            # Content-Type or Content-Length invented for an absent one.
            headers.setdefault("Content-Type", "application/json; charset=utf-8")
            headers["Content-Length"] = str(len(response.body))
        for key, value in headers.items():
            self.send_header(key, value)
        # Same CSP as the rest of the origin; the consent page must not need
        # inline script/style (stated in the HANDOFF on #134).
        self._security_headers()
        self.end_headers()
        if response.body:
            self.wfile.write(response.body)

    def do_DELETE(self) -> None:  # noqa: N802
        # Streamable HTTP clients may terminate a session explicitly; the
        # bridge is stateless, so acknowledge without state.
        if _mcp_path_token(urlparse(self.path).path) is not None:
            self.send_response(HTTPStatus.NO_CONTENT)
            self._security_headers()
            self.end_headers()
            return
        self._send_error_json(HTTPStatus.NOT_FOUND, "not_found", "unknown path")

    # -- remote MCP (Streamable HTTP, R17) ------------------------------------
    def _handle_mcp(self, path: str) -> None:
        """POST /mcp[/<key>]: one JSON-RPC message (or batch) per request,
        answered with a single JSON body (no SSE stream is offered)."""
        issuer = self._issuer()
        presented = bearer_token(self.headers.get("Authorization"), _mcp_path_token(path) or None)
        # With the canonical OAuth core mounted, the presented bearer is checked
        # for audience/revocation there and mapped to the R12 access token; the
        # manual key path (bearer IS the R12 token) stays as the debug fallback.
        token = oauth_mount.resolve_bearer(self._oauth_core(), presented, issuer=issuer)
        if token:
            try:
                self.runtime.identity.authenticate(token)
            except AuthenticationError:
                token = None
        if not token:
            # RFC 9728: the challenge tells a hosted client where the
            # protected-resource metadata (and from it the authorization
            # server) lives, so connecting with only the /mcp URL can start
            # the browser authorization flow.
            self.send_response(HTTPStatus.UNAUTHORIZED)
            self.send_header("WWW-Authenticate", oauth_mount.www_authenticate(
                issuer, error="invalid_token" if presented else None))
            body = json.dumps({"error": "authentication_failed",
                               "message": "authorize this client through "
                                          f"{oauth_mount.resource_metadata_url(issuer)} "
                                          "(hosted clients do this automatically), or send "
                                          "an MCP key as Authorization: Bearer <key>"}).encode()
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self._security_headers()
            self.end_headers()
            self.wfile.write(body)
            return
        length = int(self.headers.get("Content-Length") or 0)
        if length < 0 or length > MAX_BODY_BYTES:
            raise IngestionError("request body exceeds product bound")
        raw = self.rfile.read(length) if length else b""
        try:
            message = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._send_json({"jsonrpc": "2.0", "id": None,
                             "error": {"code": PARSE_ERROR, "message": "invalid JSON"}},
                            HTTPStatus.BAD_REQUEST)
            return
        bridge = RemoteMCPBridge(self.runtime.product)
        if isinstance(message, list):
            if not message:
                self._send_json({"jsonrpc": "2.0", "id": None,
                                 "error": {"code": INVALID_REQUEST, "message": "empty batch"}},
                                HTTPStatus.BAD_REQUEST)
                return
            responses = [r for r in (bridge.handle(m, token) for m in message) if r is not None]
            if not responses:
                self._send_accepted()
                return
            body = json.dumps(responses, ensure_ascii=False, default=str).encode("utf-8")
            self._send_bytes(body, "application/json; charset=utf-8")
            return
        response = bridge.handle(message, token)
        if response is None:
            self._send_accepted()
            return
        body = json.dumps(response, ensure_ascii=False, default=str).encode("utf-8")
        self._send_bytes(body, "application/json; charset=utf-8")

    def _send_accepted(self) -> None:
        self.send_response(HTTPStatus.ACCEPTED)
        self.send_header("Content-Length", "0")
        self._security_headers()
        self.end_headers()

    def _handle_error(self, exc: Exception) -> None:
        mapping = [
            ((AuthenticationError,), HTTPStatus.UNAUTHORIZED, "authentication_failed"),
            ((AuthorizationError, DraftNotFound), HTTPStatus.FORBIDDEN,
             "authorization_failed"),
            ((CsrfError,), HTTPStatus.FORBIDDEN, "csrf_rejected"),
            ((ConfirmationRequiredError, ConfirmationError, PolicyConfirmationRequired), HTTPStatus.CONFLICT,
             "confirmation_required"),
            ((StaleResultError, PersistenceStaleIndexError), HTTPStatus.CONFLICT,
             "stale_result"),
            ((PersistenceConflictError,), HTTPStatus.CONFLICT, "conflict"),
            ((CollaborationError,), HTTPStatus.BAD_REQUEST, "collaboration_unavailable"),
            ((WorkspaceError,), HTTPStatus.BAD_REQUEST, "workspace_unavailable"),
            ((IdentityValidationError, PersistenceValidationError, IngestionError,
              ProductError, BridgeError, ValueError), HTTPStatus.BAD_REQUEST, "validation_failed"),
            ((PersistenceStateError,), HTTPStatus.CONFLICT, "state_conflict"),
        ]
        for types, status, code in mapping:
            if isinstance(exc, types):
                self._send_error_json(status, code, str(exc))
                return
        self._send_error_json(HTTPStatus.INTERNAL_SERVER_ERROR, "internal_error",
                              "unexpected product error")

    # Documentation pages a connector directory requires before it will list a
    # server: Claude rejects a submission outright without a privacy policy, and
    # OpenAI's form asks for website, support, privacy and terms URLs that
    # "match the publisher and disclose relevant data handling". They are served
    # from this origin so the URL a reviewer checks is the URL the tools run on.
    DOC_PAGES = {
        "/privacy": "privacy.html",
        "/terms": "terms.html",
        "/support": "support.html",
    }

    def _send_doc_page(self, filename: str) -> None:
        html = (UI_DIR / filename).read_text(encoding="utf-8")
        # The contact address is deliberately NOT baked into the repository: it
        # is the operator's, and publishing someone's address is their decision.
        # Unset, the page says so plainly rather than showing a plausible
        # address that nobody reads.
        contact = (os.environ.get("RESONANCE_CONTACT") or "").strip()
        html = html.replace("__RESONANCE_CONTACT__", contact
                            or "not configured on this deployment")
        html = html.replace("__RESONANCE_ORIGIN__", self._issuer())
        self._send_bytes(html.encode("utf-8"), "text/html; charset=utf-8")

    def _initial_account(self) -> dict[str, str]:
        """Who this visitor is, before any JavaScript runs.

        The masthead used to arrive empty and fill itself in from a fetch, so
        the account appeared a moment late and shoved the row it is in. The
        server already knows -- the cookie is on the request -- so it says so
        in the HTML and the page paints once. This is the same override seam as
        `_initial_app_state`; the API-only server knows nothing about a browser
        visitor and says nothing.
        """
        return {}

    def _stamp_account(self, html: str) -> str:
        account = self._initial_account()
        if not account:
            return html
        attributes = " ".join(
            f'data-{key}="{escape(str(value), quote=True)}"'
            for key, value in sorted(account.items()) if value != "")
        return html.replace('<div class="account-slot" id="account-slot">',
                            f'<div class="account-slot" id="account-slot" {attributes}>', 1)

    def _initial_app_state(self, params: Mapping[str, list[str]]) -> str:
        """`data-state` to serve in the HTML, before any JavaScript runs.

        The API-only server has no live browser product, so it keeps the
        neutral "loading". `src/product/web_server.py` overrides this: it can tell
        whether this visitor has anything shared, and serving the answer is
        what stops the page rendering one view and then replacing it.
        """
        return "loading"

    # -- GET ---------------------------------------------------------------
    def _route_get(self, path: str, params: dict[str, list[str]]) -> None:
        product = self.runtime.product
        if path == "/notifications/stop":
            # Deliberately reachable without signing in. "To stop these
            # emails, log in first" is the sentence nobody follows; the
            # alternative they choose is marking us as spam, and then nobody
            # here is ever reachable again. The token is an HMAC over the
            # account, so it stops that account's mail and can do nothing else
            # -- it opens no session, reads no thought, and names no one.
            token = (params.get("token") or [""])[0]
            notifier = getattr(self.runtime.product, "notifier", None)
            who = (account_in_token(token, notifier.secret)
                   if notifier is not None else None)
            stopped = who is not None
            if stopped:
                notifier.unsubscribe(who)
            self._send_bytes(_unsubscribe_page(stopped).encode("utf-8"),
                             "text/html; charset=utf-8")
            return
        if path in {"/", "/index.html"}:
            html = (UI_DIR / "index.html").read_text(encoding="utf-8")
            # Stamp the state the page will end up in, so the browser paints it
            # once. Left at "loading", a first-time visitor saw the results
            # dashboard — skeleton cards, "Resonance map", "Useful matches" —
            # and only then the onboarding that replaces it, which reads as the
            # page changing its mind. `_initial_app_state` knows the answer
            # before any JavaScript runs.
            html = html.replace('data-state="loading"',
                                f'data-state="{self._initial_app_state(params)}"', 1)
            html = self._stamp_account(html)
            injected = html.replace("</head>", HEAD_INJECTION, 1).replace(
                "</body>",
                '  <script type="module" src="/webmcp.mjs"></script>\n'
                '  <script type="module" src="/deeplink.mjs"></script>\n'
                '  <script type="module" src="/session.mjs"></script>\n'
                '  <script type="module" src="/collab.mjs"></script>\n'
                '  <script type="module" src="/collab_ui.mjs"></script>\n'
                '  <script type="module" src="/workspaces.mjs"></script>\n'
                '  <script type="module" src="/account.mjs"></script>\n'
                '  <script type="module" src="/resonances.mjs"></script>\n'
                '  <script type="module" src="/topics.mjs"></script>\n'
                '  <script type="module" src="/geo.mjs"></script>\n'
                '  <script type="module" src="/shared_list.mjs"></script>\n</body>',
            )
            self._send_bytes(injected.encode("utf-8"), "text/html; charset=utf-8")
            return
        if path in self.DOC_PAGES:
            self._send_doc_page(self.DOC_PAGES[path])
            return
        if path == "/.well-known/openai-apps-challenge":
            # OpenAI's app submission proves control of the hosting domain by
            # serving a token it hands the publisher. The spec is explicit: the
            # response is ONLY the token — not JSON, not a list. Unset, this is
            # a 404 rather than an empty 200, so a half-configured deployment
            # cannot look verified.
            token = (os.environ.get("RESONANCE_OPENAI_CHALLENGE") or "").strip()
            if not token:
                self._send_error_json(HTTPStatus.NOT_FOUND, "not_found",
                                      "no OpenAI apps challenge token is configured")
                return
            self._send_bytes(token.encode("utf-8"), "text/plain; charset=utf-8")
            return
        if path in STATIC:
            filename, content_type = STATIC[path]
            self._send_bytes((UI_DIR / filename).read_bytes(), content_type)
            return
        if _mcp_path_token(path) is not None:
            # No server->client SSE stream is offered; Streamable HTTP clients
            # treat 405 on GET as "POST only", which is the whole bridge.
            self.send_response(HTTPStatus.METHOD_NOT_ALLOWED)
            self.send_header("Allow", "POST, DELETE")
            self.send_header("Content-Length", "0")
            self._security_headers()
            self.end_headers()
            return
        if path == "/api/product/health":
            health = self.runtime.live.health()
            # Whether anyone can actually be reached. A deployment with no
            # mail server still works, but it does not keep the promise that
            # this looks for you after you leave -- and that must be visible
            # here rather than discovered by a person who waited for nothing.
            notifier = getattr(product, "notifier", None)
            reachable = notifier is not None and not isinstance(
                notifier.sender, NoTransport)
            self._send_json({"ok": health.ok, "mode": "live",
                             "freshness": product.freshness(),
                             "engine": engine_identity(self.runtime),
                             "corpus": corpus_summary(self.runtime),
                             "notifications": {
                                 "can_reach_people": reachable,
                                 "why_not": None if reachable else NoTransport.reason,
                             }})
            return
        if path in {"/api/product/state", "/api/webmcp/state"}:
            token = None
            try:
                token = self._token()
            except AuthenticationError:
                pass
            state = dict(product.state(token))
            # The page shows "Sign in" rather than an anonymous start only
            # where a sign-in actually exists to offer.
            state["sign_in_required"] = self._sign_in_required()
            state["sign_in_url"] = auth_mount.SIGN_IN_PATH
            self._send_json(state)
            return
        if path == "/api/product/sessions":
            self._send_json({"sessions": product.owned_sessions(self._token())})
            return
        if path == "/api/product/resonances":
            # What the standing search found while this person was not looking.
            # The half of the product that waits: read it and you learn who
            # arrived after you shared, which no discovery call could tell you.
            include_seen = (params.get("include_seen") or [""])[0] == "1"
            self._send_json(product.pending_resonances(
                self._token(), include_seen=include_seen))
            return
        if path == "/api/product/intro/list":
            self._send_json(product.list_requests(self._token()))
            return
        if path == "/api/product/channel/messages":
            channel_id = (params.get("channel_id") or [""])[0]
            self._send_json(product.read_messages(self._token(), channel_id))
            return
        if path == "/api/product/workspaces":
            self._send_json(product.list_my_workspaces(self._token()))
            return
        if path == "/api/product/workspace":
            wid = (params.get("workspace_id") or [""])[0]
            self._send_json(product.get_workspace(self._token(), wid))
            return
        if path in {"/api/product/preview", "/api/webmcp/preview"}:
            draft_id = (params.get("draft_id") or [""])[0]
            self._send_json(product.preview(self._token(), draft_id,
                                            client_id="live-product-http"))
            return
        if path in {"/api/product/discover", "/api/webmcp/discover"}:
            session_id = (params.get("session_id") or [""])[0]
            mode = (params.get("mode") or ["analogical"])[0]
            k = int((params.get("k") or ["8"])[0])
            response = product.discover(self._token(), session_id, mode=mode, k=k)
            if path.startswith("/api/webmcp/"):
                response = _webmcp_discover_shape(response)
            self._send_json(response)
            return
        if path in {"/api/product/match", "/api/webmcp/match"}:
            result_id = (params.get("result_id") or [""])[0]
            session_id = (params.get("session_id") or [""])[0]
            self._send_json(product.get_match(self._token(), result_id, session_id))
            return
        if path == "/api/product/rich_discover":
            session_id = (params.get("session_id") or [""])[0]
            mode = (params.get("mode") or ["analogical"])[0]
            k = int((params.get("k") or ["8"])[0])
            self._send_json(product.rich_discover(self._token(), session_id,
                                                  mode=mode, k=k))
            return
        if path == "/api/product/visual/map":
            result_id = (params.get("result_id") or [""])[0]
            svg = product.visual_map(self._token(), result_id)
            self._send_svg(svg)
            return
        if path == "/api/product/visual/structure":
            result_id = (params.get("result_id") or [""])[0]
            session_id = (params.get("session_id") or [""])[0]
            svg = product.visual_structure(self._token(), result_id, session_id)
            self._send_svg(svg)
            return
        self._send_error_json(HTTPStatus.NOT_FOUND, "not_found", "unknown path")

    def _send_svg(self, svg: str) -> None:
        """User-specific visuals: authorized per request, never cached across
        identities, no long-lived URLs (result_id-scoped, staleness-checked)."""
        body = svg.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "image/svg+xml; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "private, no-store")
        self._security_headers()
        self.end_headers()
        self.wfile.write(body)

    # -- POST --------------------------------------------------------------
    def _route_post(self, path: str) -> None:
        product = self.runtime.product
        if path in ("/api/product/guest", "/api/product/register"):
            ip = _client_ip(self.headers, self.client_address[0] if self.client_address else "")
            if not registration_allowed(ip):
                self._send_error_json(HTTPStatus.TOO_MANY_REQUESTS, "rate_limited",
                                      "too many accounts created from this address; try later")
                return
        if path in ("/api/product/guest", "/api/product/register") and \
                self._sign_in_required():
            # An anonymous account cannot be told that a match appeared, and
            # cannot be recognised when the same person returns through another
            # client. Where a sign-in exists, it is the only way an account is
            # created.
            self._send_json({"error": "sign_in_required",
                             "message": "Resonance accounts are created by signing in.",
                             "sign_in_url": auth_mount.SIGN_IN_PATH},
                            status=HTTPStatus.FORBIDDEN)
            return
        if path == "/api/product/guest":
            creds = product.register_guest()
            self._send_json(
                {"user_id": creds.user_id, "csrf_token": creds.csrf_token,
                 "expires_at": creds.expires_at,
                 "recovery_secret": creds.recovery_secret},
                cookie=self._cookie_for(creds.access_token))
            return
        if path == "/api/product/register":
            body = self._body()
            creds = product.register(str(body.get("display_label", "")))
            self._send_json(
                {"user_id": creds.user_id, "csrf_token": creds.csrf_token,
                 "expires_at": creds.expires_at,
                 "recovery_secret": creds.recovery_secret},
                cookie=self._cookie_for(creds.access_token))
            return
        if path == "/api/product/login":
            body = self._body()
            creds = product.login(str(body.get("user_id", "")),
                                  str(body.get("recovery_secret", "")))
            self._send_json(
                {"user_id": creds.user_id, "csrf_token": creds.csrf_token,
                 "expires_at": creds.expires_at},
                cookie=self._cookie_for(creds.access_token))
            return
        if path == "/api/product/resonances/seen":
            body = self._body()
            keys = body.get("alert_keys")
            self._send_json(product.mark_resonances_seen(
                self._token(), [str(k) for k in keys] if isinstance(keys, list) else []))
            return
        if path == "/api/product/resonances/dismiss":
            body = self._body()
            self._send_json(product.dismiss_resonance(
                self._token(), str(body.get("alert_key", ""))))
            return
        if path == "/api/product/logout":
            product.logout(self._token())
            self._send_json({"logged_out": True},
                            cookie=f"{COOKIE_NAME}=; Max-Age=0; Path=/")
            return
        if path == "/api/product/mcp_key":
            # R17: mint a second identity session for the SAME account so the
            # person's chat client can act through the remote MCP bridge.
            # Cookie + CSRF authenticated like every other browser write; the
            # browser session itself is untouched (no rotation).
            token = self._token()
            identity = self.runtime.identity
            actor = identity.authenticate(token)
            identity._require_csrf(actor, self._csrf(), self._origin())  # noqa: SLF001 — same gate as writes
            creds = identity._issue_session(actor.user_id, actor_type="agent")  # noqa: SLF001
            host = self.headers.get("X-Forwarded-Host") or self.headers.get("Host") or ""
            scheme = self.headers.get("X-Forwarded-Proto") or "http"
            origin = f"{scheme}://{host}" if host else ""
            self._send_json({
                "user_id": creds.user_id,
                "mcp_key": creds.access_token,
                "expires_at": creds.expires_at,
                "endpoint": f"{origin}/mcp",
                "endpoint_with_key": f"{origin}/mcp/{creds.access_token}",
                "note": "Shown once. Anyone holding this key acts as this account "
                        "in Resonance; treat it like a password.",
            })
            return
        if path == "/api/product/rotate":
            creds = product.rotate_session(self._token())
            self._send_json(
                {"user_id": creds.user_id, "csrf_token": creds.csrf_token,
                 "expires_at": creds.expires_at},
                cookie=self._cookie_for(creds.access_token))
            return

        token = self._token()
        body = self._body()
        security = self._security_kwargs()

        if path in {"/api/product/prepare", "/api/webmcp/prepare"}:
            if path == "/api/webmcp/prepare":
                # An assistant is driving the page here, exactly as it drives
                # the MCP bridge, so it owes the same answer: whose reasoning
                # is this? /api/product/prepare is the person's own click on
                # their own page, and has nobody to declare.
                try:
                    authorship_rule.require(body)
                except authorship_rule.AuthorshipError as exc:
                    raise IngestionError(str(exc)) from exc
            intent_raw = body.get("share_intent") or {}
            intent = ShareIntent(
                share_display_profile=bool(intent_raw.get("share_display_profile", True)),
                share_coarse_location=bool(intent_raw.get("share_coarse_location", False)),
                receive_intro_requests=bool(intent_raw.get("receive_intro_requests", False)),
            )
            common = dict(
                presentation=body.get("presentation") or {},
                coarse_location=body.get("coarse_location"),
                intent=intent, **security,
            )
            if (body.get("candidate") is None) == (body.get("context") is None):
                raise IngestionError("provide exactly one of candidate or context")
            if body.get("candidate") is not None:
                result = product.prepare_structured(token, body["candidate"], **common)
            else:
                result = product.prepare_raw_text(token, str(body["context"]), **common)
            self._send_json(result)
            return
        if path in {"/api/product/share", "/api/webmcp/share"}:
            self._send_json(product.share_prepared(
                token, str(body.get("draft_id", "")),
                confirmation_token=str(body.get("confirmation_token", "")),
                confirmed=bool(body.get("confirmed", False)), **security))
            return
        if path == "/api/product/discard":
            self._send_json(product.discard(
                token, str(body.get("draft_id", "")),
                confirmed=bool(body.get("confirmed", False)), **security))
            return
        if path in {"/api/product/consent", "/api/webmcp/consent"}:
            choices_raw = body.get("choices") or {}
            choices = ConsentChoices(
                share_thought_dna=bool(choices_raw.get("share_thought_dna", False)),
                share_display_profile=bool(choices_raw.get("share_display_profile", False)),
                share_coarse_location=bool(choices_raw.get("share_coarse_location", False)),
                allow_intro_requests=bool(choices_raw.get("allow_intro_requests", False)),
            )
            result = product.set_consent(
                token, str(body.get("session_id", "")), choices,
                confirmed=bool(body.get("confirmed", False)), **security)
            self._send_json({"session_id": body.get("session_id"),
                             "consent": result.to_corpus_consent(),
                             "allow_intro_requests": result.allow_intro_requests})
            return
        if path == "/api/product/metadata":
            stored = product.update_metadata(
                token, str(body.get("session_id", "")),
                location=body.get("location"),
                presentation=body.get("presentation"), **security)
            self._send_json({"session_id": str(body.get("session_id", "")),
                             "version": int(getattr(stored, "version", 0))})
            return
        if path == "/api/product/revoke":
            stored = product.revoke_session(
                token, str(body.get("session_id", "")),
                confirmed=bool(body.get("confirmed", False)), **security)
            self._send_json({"session_id": str(body.get("session_id", "")),
                             "revoked": True,
                             "discoverable": False})
            return
        if path == "/api/product/intro/request":
            self._send_json(product.request_intro(
                token,
                from_session_id=str(body.get("from_session_id", "")),
                target_session_id=str(body.get("target_session_id", "")),
                message=str(body.get("message", "")),
                request_id=body.get("request_id"),
                confirmed=bool(body.get("confirmed", False)), **security))
            return
        if path == "/api/product/intro/respond":
            # Declining is what happens when nobody chose anything: the field
            # defaulted to False, so a renamed key, a typo or a half-built
            # client silently refused a stranger's introduction on this
            # person's behalf. Refusing to meet someone is a decision, and it
            # has to be made, not fallen into.
            decision = body.get("accept")
            if not isinstance(decision, bool):
                raise ValueError("accept must be true or false: an introduction "
                                 "is never declined by default")
            self._send_json(product.respond_intro(
                token, str(body.get("intro_id", "")),
                accept=decision,
                request_id=body.get("request_id"),
                confirmed=bool(body.get("confirmed", False)), **security))
            return
        if path == "/api/product/intro/cancel":
            self._send_json(product.cancel_intro(
                token, str(body.get("intro_id", "")),
                request_id=body.get("request_id"),
                confirmed=bool(body.get("confirmed", False)), **security))
            return
        if path == "/api/product/workspace/create":
            self._send_json(product.create_workspace(
                token, str(body.get("intro_id", "")),
                title=str(body.get("title", "")), brief=str(body.get("brief", "")),
                **security))
            return
        if path == "/api/product/workspace/invite":
            self._send_json(product.workspace_invite(
                token, str(body.get("workspace_id", "")),
                str(body.get("invitee_user_id", "")),
                role=str(body.get("role", "member")), **security))
            return
        if path == "/api/product/workspace/respond":
            self._send_json(product.workspace_respond_invite(
                token, str(body.get("workspace_id", "")),
                accept=bool(body.get("accept", False)), **security))
            return
        if path == "/api/product/workspace/remove":
            self._send_json(product.workspace_remove_member(
                token, str(body.get("workspace_id", "")),
                str(body.get("target_user_id", "")), **security))
            return
        if path == "/api/product/workspace/leave":
            self._send_json(product.workspace_leave(
                token, str(body.get("workspace_id", "")), **security))
            return
        if path == "/api/product/workspace/brief":
            self._send_json(product.workspace_update_brief(
                token, str(body.get("workspace_id", "")), str(body.get("brief", "")),
                expected_version=int(body.get("expected_version", 1)), **security))
            return
        if path == "/api/product/workspace/note":
            self._send_json(product.workspace_add_note(
                token, str(body.get("workspace_id", "")), str(body.get("body", "")),
                **security))
            return
        if path == "/api/product/workspace/task":
            self._send_json(product.workspace_add_task(
                token, str(body.get("workspace_id", "")), str(body.get("title", "")),
                **security))
            return
        if path == "/api/product/workspace/task_state":
            self._send_json(product.workspace_set_task_state(
                token, str(body.get("workspace_id", "")), str(body.get("task_id", "")),
                str(body.get("state", "")), **security))
            return
        if path == "/api/product/workspace/link":
            self._send_json(product.workspace_link_match(
                token, str(body.get("workspace_id", "")), str(body.get("session_id", "")),
                str(body.get("why", "")), **security))
            return
        if path == "/api/product/workspace/artifact":
            self._send_json(product.workspace_add_artifact(
                token, str(body.get("workspace_id", "")),
                label=str(body.get("label", "")), kind=str(body.get("kind", "file")),
                sha256=str(body.get("sha256", "")), size_bytes=int(body.get("size_bytes", 0)),
                **security))
            return
        if path == "/api/product/channel/send":
            self._send_json(product.send_message(
                token, str(body.get("channel_id", "")),
                str(body.get("body", "")),
                request_id=body.get("request_id"),
                confirmed=bool(body.get("confirmed", False)), **security))
            return
        if path == "/api/product/delete":
            product.delete_session(
                token, str(body.get("session_id", "")),
                confirmed=bool(body.get("confirmed", False)), **security)
            self._send_json({"session_id": str(body.get("session_id", "")),
                             "deleted": True, "discoverable": False})
            return
        self._send_error_json(HTTPStatus.NOT_FOUND, "not_found", "unknown path")


def _webmcp_discover_shape(response: Mapping[str, Any]) -> dict[str, Any]:
    """Adapt the live payload to the accepted R10 tool wire field names."""
    return {
        "contract_version": response["contract_version"],
        "result_id": response["result_id"],
        "source": response["source"],
        "discovery_contract": response.get("discovery_contract"),
        "query": response.get("query", {}),
        "matches_in_backend_order": list(response.get("matches", [])),
        "aggregation": response.get("aggregation", {}),
        "freshness": response.get("freshness", {}),
        "location_note": response.get("location_note", ""),
    }


def serve(
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    *,
    runtime: ProductRuntime,
) -> ThreadingHTTPServer:
    handler = type("BoundProductHandler", (ProductHandler,), {"runtime": runtime})
    return ThreadingHTTPServer((host, port), handler)


def _require_strong(secret: bytes, source: str) -> bytes:
    """An empty or short secret must fail loudly, never fall back to random."""
    if len(secret) < 32:
        raise ValueError(
            f"{source} must hold a stable secret of at least 32 bytes "
            f"(got {len(secret)}); an empty/short secret would silently orphan "
            "prepared drafts on restart"
        )
    return secret


def _redact_db(target: str) -> str:
    """Mask the userinfo of a DSN for logging; file paths pass through."""
    parsed = urlparse(target)
    if parsed.scheme in {"postgres", "postgresql"} and parsed.hostname:
        port = f":{parsed.port}" if parsed.port else ""
        user = f"{parsed.username}@" if parsed.username else ""
        return f"{parsed.scheme}://{user}{parsed.hostname}{port}{parsed.path}"
    return target


def _resolve_secret(secret_file: str | None, environ: Mapping[str, str],
                    db_path: str) -> bytes | None:
    """Durable-draft HMAC secret policy (R12C seam).

    A persistent DB REQUIRES a stable secret (file or env) or startup fails
    explicitly — a per-process random secret would orphan every prepared
    private draft on restart. Ephemeral in-memory runs may use a random one.
    Plaintext secrets on the CLI are deliberately not accepted.
    """
    if secret_file:
        return _require_strong(Path(secret_file).read_bytes().strip(),
                               f"secret file {secret_file!r}")
    env_secret = environ.get("RESONANCE_CONFIRMATION_SECRET", "").strip()
    if env_secret:
        return _require_strong(env_secret.encode("utf-8"),
                               "RESONANCE_CONFIRMATION_SECRET")
    if db_path != ":memory:":
        raise ValueError(
            "a persistent --db requires a stable confirmation secret: pass "
            "--secret-file or set RESONANCE_CONFIRMATION_SECRET, otherwise "
            "prepared private drafts cannot survive a restart"
        )
    return None


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Resonance live product server")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--db", default="live-product.sqlite3")
    parser.add_argument("--origin", action="append", default=None,
                        help="allowed browser origin (repeatable)")
    parser.add_argument("--secret-file", default=None,
                        help="file holding the stable draft-confirmation secret")
    parser.add_argument("--seed-demo", action="store_true",
                        help="seed the R7 demo corpus (25 labelled demo personas) into this database; "
                             "RESONANCE_SEED_DEMO=1 has the same effect. Persistent databases are "
                             "never seeded by default; :memory: always is")
    args = parser.parse_args(argv)
    seed = True if args.db == ":memory:" else (
        args.seed_demo or os.environ.get("RESONANCE_SEED_DEMO", "").strip().lower() in ("1", "true", "yes", "on"))
    origins = frozenset(args.origin or [f"http://{args.host}:{args.port}"])
    try:
        secret = _resolve_secret(args.secret_file, os.environ, args.db)
    except ValueError as exc:
        parser.error(str(exc))
    runtime = build_runtime(args.db, allowed_origins=origins, declared_origins=(args.origin or []),
                            confirmation_secret=secret,
                            seed=seed)
    startup_purge_demo(runtime)
    startup_purge_sessions(runtime)
    startup_purge_unsigned(runtime)
    startup_assign_pseudonyms(runtime)
    # R15C (#136): canonical OAuth for hosted MCP clients on this same origin.
    # The startup log names the FIRST declared --origin; per-request metadata
    # still follows the host actually addressed (see `_issuer`).
    oauth_mount.attach_core(
        runtime, issuer=oauth_mount.canonical_origin(args.origin, origins))
    server = serve(args.host, args.port, runtime=runtime)
    # Never echo credentials: a PostgreSQL DSN carries the password, and this
    # line lands in platform logs (privacy-safe logs are an R16 gate).
    print(f"live product on http://{args.host}:{args.port} "
          f"(origins: {sorted(origins)}; db: {_redact_db(args.db)}; mode: LIVE)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    main()
