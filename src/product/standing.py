"""The half of Resonance that waits.

Discovery answers one question — *who resonates with me right now* — and until
now that was the whole product. It left the most common case unserved: you
share a thought, nobody in the world matches it yet, and that is the end. The
person who would have matched you arrives next week and neither of you ever
finds out.

So a shared thought is not only a query. It is a standing search. While it is
discoverable it keeps looking, and when someone whose reasoning has the same
shape arrives, both sides are told.

The mechanics are deliberately small. When a thought becomes discoverable, the
accepted discovery path runs once for it. Every match that comes back is
recorded twice: once for the person who just shared, and once for the person
they matched — for whom this is the news that could not otherwise reach them.
Nothing new is computed; the same engine, the same scores, the same consent
filtering.

An alert is a *pointer*, never a snapshot of someone. It holds two session ids
and the scores as they were measured. Everything that could have changed since
— consent, revocation, a block, the account itself — is re-checked when the
alert is read, so a withdrawn thought stops being reported the moment it is
withdrawn.
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any, Mapping

from src.graph import ThoughtGraph

# Alerts live in the same durable record store as OAuth grants: it is already
# keyed by (kind, account) and already cleaned up when an account is removed,
# so a standing search cannot outlive the person it belongs to.
ALERT_KIND = "resonance_alert"

# How many alerts one account can accumulate. Beyond this the oldest unseen
# ones are the least useful — a person who has not looked in that long needs a
# summary, not a backlog.
MAX_ALERTS_PER_ACCOUNT = 200

DEFAULT_MODE = "analogical"
DEFAULT_K = 8


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _alert_key(user_id: str, mine: str, theirs: str) -> str:
    """One pair, one alert, forever.

    The key is the identity of the finding rather than of the event, so a
    re-share, a re-index or a repeated sweep cannot tell someone twice about
    the same person.
    """
    return f"{user_id}|{mine}|{theirs}"


class StandingSearchError(ValueError):
    """A standing-search operation could not be carried out."""


class StandingSearch:
    """Standing searches and the alerts they produce.

    Constructed with the `LiveProductService` it belongs to; it reaches the
    engine, the consent policy and the record store through that one seam
    rather than opening its own.
    """

    def __init__(self, product: Any) -> None:
        self.product = product
        self.identity = product.identity
        self.live = product.live
        self._lock = threading.RLock()

    # -- storage seam ---------------------------------------------------
    @property
    def _repo(self) -> Any | None:
        """The durable store, or None on a runtime that has none.

        A runtime without one keeps working: discovery is unaffected and only
        the waiting half is silently unavailable. That is stated in `available`
        rather than hidden, so a caller can say so instead of implying that
        nobody matched.
        """
        repo = getattr(self.live, "repo", None)
        if repo is None or not hasattr(repo, "list_grants_for_user"):
            return None
        return repo

    @property
    def available(self) -> bool:
        return self._repo is not None

    # -- the sweep ------------------------------------------------------
    def sweep_for_session(self, session_id: str, *, mode: str = DEFAULT_MODE,
                          k: int = DEFAULT_K) -> dict[str, Any]:
        """Record the resonances of one newly discoverable thought, both ways.

        Runs at the moment a thought becomes discoverable. Failures here must
        never fail the share that triggered them — the person's thought is
        shared either way — so the caller is expected to swallow errors and
        this method reports what it managed rather than raising.
        """
        repo = self._repo
        if repo is None:
            return {"available": False, "alerts_written": 0}
        source = self.identity.policy_source
        owner = source.owner_of("session", session_id)
        if not owner:
            return {"available": True, "alerts_written": 0, "reason": "no owner"}
        session = self.identity.backend.get_session(session_id)
        if session is None:
            return {"available": True, "alerts_written": 0, "reason": "no session"}

        graph = ThoughtGraph.from_dict(dict(session.thought_dna))
        raw = self.live.discover(graph, mode=mode, k=k)
        written = 0
        for row in raw.get("matches", []):
            written += self._record_pair(owner, session_id, row, mode=mode)
        return {"available": True, "alerts_written": written}

    def _record_pair(self, owner: str, session_id: str, row: Mapping[str, Any],
                     *, mode: str) -> int:
        theirs = str(row.get("session_id", ""))
        if not theirs or theirs == session_id:
            return 0
        if not self._is_a_resonance(row):
            return 0
        source = self.identity.policy_source
        their_owner = source.owner_of("session", theirs)
        if not their_owner or their_owner == owner:
            # Two thoughts of your own resonating is not an introduction to
            # anyone; it is you agreeing with yourself.
            return 0
        if not self._is_live_participant(theirs):
            return 0
        if not self._is_live_participant(session_id):
            return 0
        scores = dict(row.get("scores", {}) or {})
        written = 0
        # Each side is told in its own terms: "your thought X resonates with
        # their thought Y". Blocks are directional, so each side is checked
        # on its own rather than once for the pair.
        if not source.is_blocked(owner, their_owner):
            written += self._put(owner, session_id, theirs, scores=scores, mode=mode,
                                 reason="you_shared")
        if not source.is_blocked(their_owner, owner):
            written += self._put(their_owner, theirs, session_id, scores=scores,
                                 mode=mode, reason="they_arrived")
        return written

    @staticmethod
    def _is_a_resonance(row: Mapping[str, Any]) -> bool:
        """Only tell someone about a pair the engine itself calls a resonance.

        Discovery returns rows it declines to endorse: a shared skeleton with no
        semantic evidence comes back classified `negative`, and a row can carry a
        hard rejection outright. The engine decides what a resonance is, and this
        half of the product had been overriding it — telling a person "someone
        resonates with your thought" about a pair the very same search reported
        as a non-match, one screen away. Worse, that is the pair a person would
        then be asked to make an introduction over.
        """
        if row.get("hard_rejection"):
            return False
        return str(row.get("mode_classification") or "").lower() not in {"", "negative"}

    def _is_live_participant(self, session_id: str) -> bool:
        """A session worth telling someone about: discoverable, and a person.

        Seeded demo rows carry a record kind of their own. Telling a real
        participant that a fixture resonates with them would be the service
        inventing a person.
        """
        consent = self.identity.policy_source.session_consent(session_id)
        if not consent or consent.get("revoked") or consent.get("deleted"):
            return False
        if not consent.get("share_thought_dna"):
            return False
        record = self.identity.backend.get_session(session_id)
        kind = str(getattr(record, "record_kind", "") or "")
        return kind == "volunteer"

    def _put(self, user_id: str, mine: str, theirs: str, *, scores: Mapping[str, Any],
             mode: str, reason: str) -> int:
        repo = self._repo
        if repo is None:
            return 0
        key = _alert_key(user_id, mine, theirs)
        with self._lock:
            if repo.get_grant(ALERT_KIND, key) is not None:
                return 0                     # already told; never tell twice
            existing = repo.list_grants_for_user(ALERT_KIND, user_id)
            if len(existing) >= MAX_ALERTS_PER_ACCOUNT:
                return 0
            repo.put_grant(ALERT_KIND, key, {
                "alert_key": key,
                "user_id": user_id,
                "my_session_id": mine,
                "their_session_id": theirs,
                "mode": mode,
                "scores_at_detection": dict(scores),
                "detected_at": _now(),
                "reason": reason,
                "seen_at": None,
            }, user_id=user_id)
        return 1

    # -- reading --------------------------------------------------------
    def pending(self, access_token: str, *, include_seen: bool = False) -> dict[str, Any]:
        """Resonances found for this account while it was not looking.

        Every alert is re-checked against the present: the other thought must
        still be discoverable by a real participant, neither side may have
        blocked the other, and the viewer must still own their own side. An
        alert that fails any of those is dropped from the answer and from the
        store, because it describes something that is no longer true.
        """
        actor = self.identity.authenticate(access_token)
        repo = self._repo
        if repo is None:
            return {"available": False, "alerts": [], "unseen_count": 0}
        source = self.identity.policy_source
        alerts: list[dict[str, Any]] = []
        stale: list[str] = []
        for record in repo.list_grants_for_user(ALERT_KIND, actor.user_id):
            row = dict(record)
            mine = str(row.get("my_session_id", ""))
            theirs = str(row.get("their_session_id", ""))
            if source.owner_of("session", mine) != actor.user_id:
                stale.append(str(row.get("alert_key", "")))
                continue
            their_owner = source.owner_of("session", theirs)
            if not their_owner or not self._is_live_participant(theirs) \
                    or not self._is_live_participant(mine):
                stale.append(str(row.get("alert_key", "")))
                continue
            if source.is_blocked(actor.user_id, their_owner) or \
                    source.is_blocked(their_owner, actor.user_id):
                stale.append(str(row.get("alert_key", "")))
                continue
            if row.get("seen_at") and not include_seen:
                continue
            alerts.append(self._present(actor.user_id, row, their_owner))
        for key in stale:
            if key:
                repo.pop_grant(ALERT_KIND, key)
        alerts.sort(key=lambda a: a.get("detected_at") or "", reverse=True)
        return {
            "available": True,
            "alerts": alerts,
            "unseen_count": sum(1 for a in alerts if not a.get("seen_at")),
        }

    def _present(self, viewer_id: str, row: Mapping[str, Any],
                 their_owner: str) -> dict[str, Any]:
        theirs = str(row.get("their_session_id", ""))
        record = self.identity.backend.get_session(theirs)
        consent = self.identity.policy_source.session_consent(theirs)
        display: dict[str, Any] = {}
        if consent.get("share_display_profile"):
            presentation = dict(getattr(record, "presentation", {}) or {})
            for field in ("topic", "domain"):
                if presentation.get(field):
                    display[field] = presentation[field]
        connection = None
        collaboration = getattr(self.product, "collaboration", None)
        if collaboration is not None:
            try:
                connection = collaboration.connection_state(viewer_id, their_owner)
            except Exception:  # noqa: BLE001 - presentation only
                connection = None
        return {
            "alert_key": row.get("alert_key"),
            "my_session_id": row.get("my_session_id"),
            "their_session_id": theirs,
            "mode": row.get("mode"),
            "scores_at_detection": dict(row.get("scores_at_detection", {}) or {}),
            "detected_at": row.get("detected_at"),
            # `you_shared` is a resonance that already existed when you shared;
            # `they_arrived` is someone who turned up afterwards. The second is
            # the one that could not have reached you any other way.
            "reason": row.get("reason"),
            "seen_at": row.get("seen_at"),
            "display": display,
            "connection_state": connection,
        }

    def mark_seen(self, access_token: str, alert_keys: list[str]) -> dict[str, Any]:
        """Record that these were shown to the person.

        Seen is not the same as dismissed: the alert stays readable, it simply
        stops counting as news.
        """
        actor = self.identity.authenticate(access_token)
        repo = self._repo
        if repo is None:
            return {"available": False, "marked": 0}
        marked = 0
        with self._lock:
            for key in alert_keys:
                record = repo.get_grant(ALERT_KIND, str(key))
                if record is None or record.get("user_id") != actor.user_id:
                    continue
                if record.get("seen_at"):
                    continue
                updated = dict(record)
                updated["seen_at"] = _now()
                repo.put_grant(ALERT_KIND, str(key), updated, user_id=actor.user_id)
                marked += 1
        return {"available": True, "marked": marked}

    def dismiss(self, access_token: str, alert_key: str) -> dict[str, Any]:
        """Remove one alert for good, at the person's request."""
        actor = self.identity.authenticate(access_token)
        repo = self._repo
        if repo is None:
            return {"available": False, "dismissed": False}
        record = repo.get_grant(ALERT_KIND, str(alert_key))
        if record is None or record.get("user_id") != actor.user_id:
            return {"available": True, "dismissed": False}
        repo.pop_grant(ALERT_KIND, str(alert_key))
        return {"available": True, "dismissed": True}

    def retract_for_session(self, session_id: str) -> int:
        """Withdraw the alerts that point at a thought no longer shared.

        Called when a thought is revoked or deleted. `pending` would drop them
        anyway on the next read, but a person who revokes expects the effect to
        be immediate rather than deferred to whenever someone next looks.
        """
        repo = self._repo
        if repo is None:
            return 0
        source = self.identity.policy_source
        owner = source.owner_of("session", session_id)
        removed = 0
        with self._lock:
            for candidate_owner in {owner} if owner else set():
                for record in list(repo.list_grants_for_user(ALERT_KIND, candidate_owner)):
                    if record.get("my_session_id") == session_id:
                        repo.pop_grant(ALERT_KIND, str(record.get("alert_key", "")))
                        removed += 1
        return removed
