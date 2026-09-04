"""Authoritative R12 identity/R11 persistence adapter for the R12B policy.

The adapter derives every decision from the identity backend on each call.  If
the backend is :class:`R11IdentityBackend`, this state is durable SQLite or
PostgreSQL state; no parallel authorization database is introduced.
"""

from __future__ import annotations

import secrets
import time
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

from src.security.models import PolicyDecision
from src.security.policy import AuditTrail

from .backend import IdentityBackend
from .models import IdentityEvent

SECURITY_BLOCK_SET = "security.block.set"
SECURITY_DECISION = "security.policy.decision"
SECURITY_REPORT = "security.report"


def _field(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, Mapping):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if hasattr(value, "to_dict"):
        return dict(value.to_dict())
    if is_dataclass(value):
        return dict(asdict(value))
    return {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


class IdentityPolicySource:
    """Resolve policy from the current R12 identity backend.

    R11-backed identity events provide the durable block/report/intro state.
    Corpus records remain authoritative for ownership, revocation, deletion,
    and the public discovery choices that affect the index.
    """

    def __init__(self, backend: IdentityBackend) -> None:
        self.backend = backend

    def _events(self) -> tuple[IdentityEvent, ...]:
        return tuple(self.backend.list_identity_events())

    def generation_for(self, subject: str) -> int:
        repo = getattr(self.backend, "repo", None)
        corpus_generation = int(repo.get_corpus_generation()) if repo is not None else 0
        session_versions = sum(
            int(_field(item, "version", 0) or 0)
            for item in self.backend.list_sessions()
            if _field(item, "user_id") == subject
        )
        policy_events = sum(
            1
            for event in self._events()
            if event.event_type != SECURITY_DECISION
            and (event.user_id == subject or str(event.payload.get("peer_id", "")) == subject)
        )
        return corpus_generation + session_versions + policy_events

    def owner_of(self, kind: str, resource_id: str) -> str | None:
        if kind in {"user", "account"}:
            return resource_id if self.backend.get_user(resource_id) is not None else None
        if kind == "session":
            session = self.backend.get_session(resource_id)
            return str(_field(session, "user_id")) if session is not None else None
        if kind == "thought":
            for session in self.backend.list_sessions():
                thought = _mapping(_field(session, "thought_dna", {}))
                if str(thought.get("thought_id", "")) == resource_id:
                    return str(_field(session, "user_id"))
        return None

    def workspace_of(self, kind: str, resource_id: str) -> str | None:
        # R14 owns durable workspace relationships. Unknown workspace state is
        # deliberately denied until that adapter extends this source.
        return None

    def session_consent(self, session_id: str) -> Mapping[str, bool]:
        session = self.backend.get_session(session_id)
        if session is None:
            return {}
        raw = _field(session, "consent", {})
        consent = _mapping(raw)
        allow_intro = False
        for event in self._events():
            if event.session_id != session_id:
                continue
            if event.event_type in {"identity.consent.set", "identity.intro_consent.set"}:
                allow_intro = bool(event.payload.get("allow_intro_requests", False))
        return {
            "share_thought_dna": bool(consent.get("share_thought_dna", False)),
            "share_display_profile": bool(consent.get("share_display_profile", False)),
            "share_coarse_location": bool(consent.get("share_coarse_location", False)),
            "allow_intro_requests": allow_intro,
            "revoked": _field(session, "revoked_at") is not None,
            "deleted": _field(session, "deleted_at") is not None,
        }

    def workspace_role(self, workspace_id: str, subject: str) -> str | None:
        return None

    def peer_action_allowed(self, subject: str, peer_id: str, action: str) -> bool:
        if action == "intro:request":
            # Candidate opt-in is the R12 peer capability. The policy also
            # checks consent on the exact target session before this seam.
            return any(
                _field(session, "user_id") == peer_id
                and self.session_consent(str(_field(session, "session_id"))).get(
                    "allow_intro_requests", False
                )
                for session in self.backend.list_sessions()
            )
        if action == "message:send":
            # R14 extends the deferral point this method reserved: relay
            # messaging is allowed exactly between mutually ACCEPTED
            # connections, read from the durable intro records per call.
            repo = getattr(self.backend, "repo", None)
            if repo is None or not hasattr(repo, "accepted_user_pairs"):
                return False
            return frozenset((subject, peer_id)) in repo.accepted_user_pairs()
        return False

    def is_blocked(self, subject: str, peer_id: str) -> bool:
        blocked = False
        pair = frozenset((subject, peer_id))
        for event in self._events():
            if event.event_type != SECURITY_BLOCK_SET or event.user_id is None:
                continue
            event_pair = frozenset((event.user_id, str(event.payload.get("peer_id", ""))))
            if event_pair == pair:
                blocked = bool(event.payload.get("blocked", False))
        return blocked

    def auth_session_active(self, subject: str, auth_session_id: str) -> bool:
        active: dict[str, str] = {}
        for event in self._events():
            if event.event_type == "identity.auth.issued" and event.session_id and event.user_id:
                active[event.session_id] = event.user_id
            elif event.event_type == "identity.auth.revoked" and event.session_id:
                active.pop(event.session_id, None)
        return active.get(auth_session_id) == subject

    def block(self, subject: str, peer_id: str) -> None:
        self._append(
            SECURITY_BLOCK_SET,
            user_id=subject,
            payload={"peer_id": peer_id, "blocked": True},
        )

    def unblock(self, subject: str, peer_id: str) -> None:
        self._append(
            SECURITY_BLOCK_SET,
            user_id=subject,
            payload={"peer_id": peer_id, "blocked": False},
        )

    def report(self, subject: str, peer_id: str, reason_code: str) -> None:
        self._append(
            SECURITY_REPORT,
            user_id=subject,
            payload={"peer_id": peer_id, "reason_code": reason_code},
        )

    def record_decision(self, decision: PolicyDecision) -> None:
        safe = decision.to_safe_dict()
        # Durable policy history must not reconstruct the live authentication
        # or protocol-session graph. Correlation/client/action/resource fields
        # are enough for operational provenance; session identifiers stay only
        # in the inspectable in-process audit trail.
        safe.pop("auth_session_id", None)
        safe.pop("protocol_session_id", None)
        self._append(
            SECURITY_DECISION,
            user_id=decision.subject,
            session_id=(decision.resource_id if decision.resource_kind == "session" else None),
            payload=safe,
        )

    def _append(
        self,
        event_type: str,
        *,
        user_id: str,
        payload: Mapping[str, Any],
        session_id: str | None = None,
    ) -> None:
        self.backend.append_identity_event(
            IdentityEvent(
                event_id=f"sevt-{time.time_ns():020d}-{secrets.token_hex(4)}",
                event_type=event_type,
                user_id=user_id,
                session_id=session_id,
                payload=dict(payload),
                created_at=_now(),
            )
        )


class DurableIdentityAuditTrail(AuditTrail):
    """Keep the inspectable in-process trail and persist its safe projection."""

    def __init__(self, source: IdentityPolicySource) -> None:
        super().__init__()
        self.source = source

    def append(self, decision: PolicyDecision) -> None:
        super().append(decision)
        self.source.record_decision(decision)
