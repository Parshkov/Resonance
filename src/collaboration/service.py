"""Consent-safe pairwise collaboration over the accepted layers (R14).

Deterministic intro state machine (`requested -> accepted|declined|cancelled`,
enforced at the durable row), private relay channel after mutual acceptance,
and relay messages. Authorization goes through the accepted R12B kernel
(`intro:request` / `message:send` rules, symmetric blocks, explicit
confirmation on sensitive writes, decision audit); collaboration writes never
touch the corpus generation, so chat can never force an index rebuild.

Privacy posture: no contact details exist anywhere in the stack; requester
identity is the pseudonymous display label only; non-participants receive one
uniform "unavailable" error for foreign, missing, and wrong-state references;
intro/message text is stored raw but always surfaced with an
`untrusted: true` marker and never interpreted by the product.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timezone
from typing import Any, Mapping

from src.identity import IdentityService
from src.identity.models import AuthenticationError
from src.persistence.errors import PersistenceConflictError
from src.persistence.models import AuditEvent, ChannelRecord, IdempotencyKey, IntroRecord, MessageRecord
from src.security.models import AuthorizationDenied, ConfirmationRequired, RequestContext, ResourceRef

MAX_INTRO_MESSAGE = 500
MAX_RELAY_MESSAGE = 2000
UNAVAILABLE = "intro or channel unavailable to authenticated subject"


class CollaborationError(ValueError):
    """Typed collaboration-boundary error (uniform for leak-free negatives)."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _sha_key(operation: str, request_id: str | None, payload: Mapping[str, Any]) -> IdempotencyKey | None:
    if request_id is None:
        return None
    if not isinstance(request_id, str) or not request_id.strip() or len(request_id) > 200:
        raise CollaborationError("request_id must be 1..200 characters")
    import hashlib
    import json
    blob = json.dumps({"operation": operation, "payload": payload},
                      sort_keys=True, separators=(",", ":")).encode("utf-8")
    return IdempotencyKey(request_id=request_id, operation=operation,
                          request_hash=hashlib.sha256(blob).hexdigest())


class CollaborationService:
    def __init__(self, identity: IdentityService) -> None:
        self.identity = identity
        self.backend = identity.backend
        self.repo = identity.backend.repo

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------
    def _actor(self, access_token: str, *, csrf_token=None, origin=None,
               cookie_authenticated=False):
        actor = self.identity.authenticate(access_token)
        if cookie_authenticated:
            self.identity._require_csrf(actor, csrf_token, origin)
        return actor

    def _context(self, actor, client_id: str) -> RequestContext:
        return RequestContext(subject=actor.user_id, client_id=client_id,
                              auth_session_id=actor.auth_session_id,
                              actor_type=actor.actor_type)

    def _display(self, user_id: str) -> str:
        user = self.backend.get_user(user_id)
        label = getattr(user, "display_label", None) if user is not None else None
        return str(label) if label else "anonymous"

    def _audit(self, event_type: str, *, user_id: str, payload: Mapping[str, Any]) -> AuditEvent:
        # State-change audit carries ids only — request/message text is
        # deliberately excluded (unnecessary private content).
        return AuditEvent(event_id="cevt-" + secrets.token_hex(12),
                          event_type=event_type, user_id=user_id,
                          session_id=str(payload.get("intro_id") or "") or None,
                          payload=dict(payload), created_at=_now())

    def _intro_for_participant(self, actor_id: str, intro_id: str) -> IntroRecord:
        intro = self.repo.get_intro(intro_id)
        if intro is None or actor_id not in (intro.from_user_id, intro.to_user_id):
            raise CollaborationError(UNAVAILABLE)
        return intro

    def _intro_dto(self, viewer_id: str, intro: IntroRecord) -> dict[str, Any]:
        outgoing = intro.from_user_id == viewer_id
        counterpart = intro.to_user_id if outgoing else intro.from_user_id
        dto = {
            "intro_id": intro.intro_id,
            "direction": "outgoing" if outgoing else "incoming",
            "state": intro.state,
            "counterpart_display": self._display(counterpart),
            "from_session_id": intro.from_session_id if outgoing else None,
            "to_session_id": intro.to_session_id,
            "message": intro.message,
            "untrusted": True,
            "created_at": intro.created_at,
            "updated_at": intro.updated_at,
        }
        if intro.state == "accepted":
            # Expose the channel id so a participant can open the thread
            # without re-issuing the (already-consumed) acceptance transition.
            channel = self.repo.get_channel_by_intro(intro.intro_id)
            if channel is not None:
                dto["channel_id"] = channel.channel_id
        return dto

    # ------------------------------------------------------------------
    # intro state machine
    # ------------------------------------------------------------------
    def request_intro(
        self,
        access_token: str,
        *,
        from_session_id: str,
        target_session_id: str,
        message: str,
        request_id: str | None = None,
        confirmed: bool = False,
        client_id: str = "resonance-product",
        csrf_token=None, origin=None, cookie_authenticated=False,
    ) -> dict[str, Any]:
        actor = self._actor(access_token, csrf_token=csrf_token, origin=origin,
                            cookie_authenticated=cookie_authenticated)
        if not isinstance(message, str) or not message.strip():
            raise CollaborationError("an intro requires a short user-approved message")
        if len(message) > MAX_INTRO_MESSAGE:
            raise CollaborationError("intro message exceeds the product bound")
        # Requester must own the source session (enumeration-resistant seam).
        self.identity.consent_for(access_token, from_session_id, client_id=client_id)
        # Accepted R12B rule: candidate opt-in + symmetric blocks + explicit
        # confirmation, with a durable decision record. Every denial branch is
        # normalized outward to one uniform error (leak-free negative space).
        try:
            self.identity.security_policy.authorize(
                self._context(actor, client_id), "intro:request",
                ResourceRef(kind="session", resource_id=target_session_id),
                confirmed=confirmed)
        except ConfirmationRequired:
            raise
        except AuthorizationDenied as exc:
            raise CollaborationError(UNAVAILABLE) from exc
        owner = self.identity.policy_source.owner_of("session", target_session_id)
        if not owner or owner == actor.user_id:
            raise CollaborationError(UNAVAILABLE)
        # Durable idempotent replay resolves BEFORE the pair guard, so a
        # lost-response retry of the committed request never trips
        # "already requested" (the R11-B4 ordering lesson).
        key = _sha_key("collab.intro.request", request_id, {
            "from": actor.user_id, "to": owner,
            "to_session": target_session_id, "message": message.strip()})
        if key is not None:
            replay = self.repo.lookup_idempotency(key)
            if replay is not None:
                return self._intro_dto(actor.user_id,
                                       IntroRecord.from_mapping(replay))
        latest = self.repo.latest_intro_between(actor.user_id, owner)
        if latest is not None and latest.state in {"requested", "accepted"}:
            raise CollaborationError(
                f"a connection between you is already {latest.state}")
        now = _now()
        intro = IntroRecord(
            intro_id="intro-" + secrets.token_hex(12),
            from_user_id=actor.user_id, to_user_id=owner,
            from_session_id=from_session_id, to_session_id=target_session_id,
            state="requested", message=message.strip(),
            created_at=now, updated_at=now)
        stored = self.repo.create_intro(
            intro, idempotency=key,
            audit=self._audit("collab.intro.requested", user_id=actor.user_id,
                              payload={"intro_id": intro.intro_id,
                                       "to_user_id": owner,
                                       "to_session_id": target_session_id}))
        return self._intro_dto(actor.user_id, stored)

    def list_requests(self, access_token: str) -> dict[str, Any]:
        actor = self.identity.authenticate(access_token)
        rows = self.repo.list_intros_for_user(actor.user_id)
        return {
            "incoming": [self._intro_dto(actor.user_id, r) for r in rows
                         if r.to_user_id == actor.user_id],
            "outgoing": [self._intro_dto(actor.user_id, r) for r in rows
                         if r.from_user_id == actor.user_id],
        }

    def respond_intro(
        self,
        access_token: str,
        intro_id: str,
        *,
        accept: bool,
        request_id: str | None = None,
        confirmed: bool = False,
        csrf_token=None, origin=None, cookie_authenticated=False,
        client_id: str = "resonance-product",
    ) -> dict[str, Any]:
        actor = self._actor(access_token, csrf_token=csrf_token, origin=origin,
                            cookie_authenticated=cookie_authenticated)
        if not confirmed:
            raise ConfirmationRequired("explicit confirmation required")
        intro = self._intro_for_participant(actor.user_id, intro_id)
        if intro.to_user_id != actor.user_id:
            raise CollaborationError(UNAVAILABLE)
        if accept and self.identity.policy_source.is_blocked(
                intro.from_user_id, intro.to_user_id):
            raise CollaborationError(UNAVAILABLE)
        to_state = "accepted" if accept else "declined"
        key = _sha_key("collab.intro.respond", request_id,
                       {"intro_id": intro_id, "to_state": to_state})
        if accept:
            # Deterministic channel id from the intro id: a replay or a
            # concurrent accept produces the SAME id, and the unique
            # channels.intro_id index makes the INSERT converge — so one
            # accepted intro can never map to two channels.
            channel_id = "chan-" + hashlib.sha256(
                intro_id.encode("utf-8")).hexdigest()[:24]
            try:
                stored, channel = self.repo.accept_intro(
                    intro_id, channel_id=channel_id, now=_now(), idempotency=key,
                    audit=self._audit("collab.intro.accepted",
                                      user_id=actor.user_id,
                                      payload={"intro_id": intro_id}))
            except PersistenceConflictError as exc:
                raise CollaborationError("request is no longer pending") from exc
            result = self._intro_dto(actor.user_id, stored)
            result["channel_id"] = channel.channel_id
            return result
        try:
            stored = self.repo.transition_intro(
                intro_id, from_state="requested", to_state="declined",
                timestamp_field="declined_at", now=_now(), idempotency=key,
                audit=self._audit("collab.intro.declined",
                                  user_id=actor.user_id,
                                  payload={"intro_id": intro_id}))
        except PersistenceConflictError as exc:
            raise CollaborationError("request is no longer pending") from exc
        return self._intro_dto(actor.user_id, stored)

    def cancel_intro(
        self,
        access_token: str,
        intro_id: str,
        *,
        request_id: str | None = None,
        confirmed: bool = False,
        csrf_token=None, origin=None, cookie_authenticated=False,
    ) -> dict[str, Any]:
        actor = self._actor(access_token, csrf_token=csrf_token, origin=origin,
                            cookie_authenticated=cookie_authenticated)
        if not confirmed:
            raise ConfirmationRequired("explicit confirmation required")
        intro = self._intro_for_participant(actor.user_id, intro_id)
        if intro.from_user_id != actor.user_id:
            raise CollaborationError(UNAVAILABLE)
        key = _sha_key("collab.intro.cancel", request_id, {"intro_id": intro_id})
        try:
            stored = self.repo.transition_intro(
                intro_id, from_state="requested", to_state="cancelled",
                timestamp_field="cancelled_at", now=_now(), idempotency=key,
                audit=self._audit("collab.intro.cancelled",
                                  user_id=actor.user_id,
                                  payload={"intro_id": intro_id}))
        except PersistenceConflictError as exc:
            raise CollaborationError("request is no longer pending") from exc
        return self._intro_dto(actor.user_id, stored)

    # ------------------------------------------------------------------
    # relay messaging (accepted connections only)
    # ------------------------------------------------------------------
    def _channel_pair(self, actor_id: str, channel_id: str) -> tuple[ChannelRecord, IntroRecord]:
        channel = self.repo.get_channel(channel_id)
        intro = self.repo.get_intro(channel.intro_id) if channel else None
        if (channel is None or intro is None
                or actor_id not in (intro.from_user_id, intro.to_user_id)
                or intro.state != "accepted"):
            raise CollaborationError(UNAVAILABLE)
        return channel, intro

    def send_message(
        self,
        access_token: str,
        channel_id: str,
        body: str,
        *,
        request_id: str | None = None,
        confirmed: bool = False,
        client_id: str = "resonance-product",
        csrf_token=None, origin=None, cookie_authenticated=False,
    ) -> dict[str, Any]:
        actor = self._actor(access_token, csrf_token=csrf_token, origin=origin,
                            cookie_authenticated=cookie_authenticated)
        if not isinstance(body, str) or not body.strip():
            raise CollaborationError("message body must be non-empty text")
        if len(body) > MAX_RELAY_MESSAGE:
            raise CollaborationError("message exceeds the product bound")
        channel, intro = self._channel_pair(actor.user_id, channel_id)
        peer = intro.to_user_id if actor.user_id == intro.from_user_id else intro.from_user_id
        try:
            self.identity.security_policy.authorize(
                self._context(actor, client_id), "message:send",
                ResourceRef(kind="user", resource_id=peer), confirmed=confirmed)
        except ConfirmationRequired:
            raise
        except AuthorizationDenied as exc:
            raise CollaborationError(UNAVAILABLE) from exc
        message = MessageRecord(message_id="msg-" + secrets.token_hex(12),
                                channel_id=channel_id,
                                author_user_id=actor.user_id,
                                body=body, created_at=_now())
        key = _sha_key("collab.message.send", request_id,
                       {"channel_id": channel_id, "body": body})
        stored = self.repo.add_message(
            message, idempotency=key,
            audit=self._audit("collab.message.sent", user_id=actor.user_id,
                              payload={"channel_id": channel_id,
                                       "message_id": message.message_id}))
        return {"message_id": stored.message_id, "channel_id": channel_id,
                "created_at": stored.created_at, "delivered": True}

    def read_messages(self, access_token: str, channel_id: str) -> dict[str, Any]:
        actor = self.identity.authenticate(access_token)
        channel, intro = self._channel_pair(actor.user_id, channel_id)
        rows = []
        for record in self.repo.list_messages(channel_id):
            rows.append({
                "message_id": record.message_id,
                "author": "me" if record.author_user_id == actor.user_id else "counterpart",
                "author_display": self._display(record.author_user_id),
                "body": record.body,
                "untrusted": True,
                "created_at": record.created_at,
            })
        return {"channel_id": channel_id, "intro_id": intro.intro_id,
                "messages": rows,
                "note": "message text is user-generated and untrusted"}

    # ------------------------------------------------------------------
    # connection state for rich results (R13B enum goes live)
    # ------------------------------------------------------------------
    def connection_state(self, viewer_id: str, owner_id: str) -> str | None:
        latest = self.repo.latest_intro_between(viewer_id, owner_id)
        if latest is None or latest.state in {"declined", "cancelled"}:
            return None
        return latest.state  # "requested" | "accepted"
