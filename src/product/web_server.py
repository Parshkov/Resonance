"""The production HTTP server: the live product plus the browser write path.

`src/product/server.py` serves the product API and the page; this module adds
the browser WebMCP tools on top of it — prepare, preview, share and consent —
so a person can go from a thought to a discoverable share without leaving the
page.  It is a transport adapter, not a second product state machine: identity,
drafts, consent, discovery results and intro/channel state all live in the
services underneath, and the only state kept here is a small per-process
operation receipt cache so an aborted browser write can be reconciled.

Every read and write requires an authenticated session, and discovery requires
a thought the visitor has explicitly shared.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import threading
from http import HTTPStatus
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import parse_qs

from src.ingestion.identity import (
    INGESTION_DISCARDED,
    INGESTION_PREPARED,
    INGESTION_SHARED,
)
from src.ingestion.service import ShareIntent
from src.product import authorship as authorship_rule
from src.product import phrasing
from src.product.mcp_bridge import (
    BridgeError, _PRIVATE, _SHARED, _WITHDRAWN, _coarse_location,
    _has_usable_structure, _in_state,
    _insufficient_structure_message, _slug, _structure_summary, build_thought_dna,
)
from src.product.service import LOCATION_NOTE
from src.identity.models import AuthenticationError
from src.identity.service import CONSENT_SET
from src.persistence.errors import PersistenceConflictError
from src.product import oauth_mount
from src.workspaces.topics import CONTRIBUTIONS_TABLE
from src.product.server import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    UI_DIR,
    ProductHandler,
    ProductRuntime,
    _redact_db,
    _resolve_secret,
    build_runtime,
    startup_purge_demo,
    startup_purge_sessions,
    startup_assign_pseudonyms,
    startup_purge_unsigned,
)

WEBMCP_CONTRACT = "resonance-webmcp/0.1"
REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")
WRITE_OPERATIONS = frozenset({"prepare", "share", "consent", "contribute"})
CANONICAL_K = 15
CANONICAL_MODE = "analogical"


def _fingerprint(body: Mapping[str, Any]) -> str:
    semantic = {key: value for key, value in body.items() if key != "request_id"}
    raw = json.dumps(semantic, sort_keys=True, separators=(",", ":"),
                     ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()



WEBMCP_SPOKEN_AS = {
    "prepare": "resonance_prepare_thought",
    "share": "resonance_share_thought",
    "consent": "resonance_stop_sharing",
}
"""Which tool's words fit each browser operation.

The browser surface had the same defect the chat one did: its tools handed
back a bare object, so an assistant driving the page read JSON out to the
person. The sentence comes from src.product.phrasing, the same place the MCP
bridge gets it, because two hand-written descriptions of one result is how
they start disagreeing.
"""


def _spoken(operation: str, wire: dict) -> dict:
    """The wire result, plus `say`: the same answer in words.

    Nothing is removed and nothing is restated differently — a client that
    ignores `say` sees exactly what it saw before.
    """
    tool = WEBMCP_SPOKEN_AS.get(operation)
    if tool is None:
        return wire
    return {**wire, "say": phrasing.say(tool, wire)}


class LiveWebMCPBridge:
    """Translation bookkeeping only; no authoritative product state lives here."""

    def __init__(self) -> None:
        self.lock = threading.RLock()
        self.operations: dict[tuple[str, str, str], dict[str, Any]] = {}

    def operation(self, subject: str, operation: str,
                  request_id: str) -> dict[str, Any] | None:
        with self.lock:
            return self.operations.get((subject, operation, request_id))

    def remember(self, subject: str, operation: str, request_id: str,
                 fingerprint: str, result: Mapping[str, Any]) -> None:
        with self.lock:
            self.operations[(subject, operation, request_id)] = {
                "fingerprint": fingerprint,
                "result": dict(result),
            }


def _latest_prepared_draft(product, token: str) -> str | None:
    actor = product.identity.authenticate(token)
    states: dict[str, tuple[str, str]] = {}
    for event in product.identity.backend.list_identity_events():
        if event.user_id != actor.user_id:
            continue
        draft_id = str(event.payload.get("draft_id", ""))
        if not draft_id:
            continue
        if event.event_type == INGESTION_PREPARED:
            states[draft_id] = ("prepared", event.created_at)
        elif event.event_type == INGESTION_SHARED:
            states[draft_id] = ("shared", event.created_at)
        elif event.event_type == INGESTION_DISCARDED:
            states[draft_id] = ("discarded", event.created_at)
    prepared = [(when, draft) for draft, (status, when) in states.items()
                if status == "prepared"]
    return max(prepared)[1] if prepared else None


def _owned_live_session(product, token: str) -> str | None:
    rows = product.owned_sessions(token)
    discoverable = [row for row in rows if row.get("share_state") == "discoverable"]
    if not discoverable:
        return None
    return str(discoverable[-1].get("session_id") or "") or None


def _has_shared(product, token: str) -> bool:
    return _owned_live_session(product, token) is not None


MAX_CONTEXT_CHARS = 4000


PLACEHOLDER_TOPIC = "Shared thought"


def _presentation_for(thought: Any) -> dict[str, Any]:
    """The durable projection needs exactly {topic, domain, cluster_id}; derive
    them from what the agent supplied (never from the raw text)."""
    topic = (str(thought.get("topic") or "").strip() if isinstance(thought, Mapping) else "") \
        or PLACEHOLDER_TOPIC
    domain = (str(thought.get("domain") or "").strip() if isinstance(thought, Mapping) else "") \
        or "general"
    return {"topic": topic[:120], "domain": domain[:60],
            "cluster_id": (_slug(topic) or "shared")[:48]}


def _topic_from_structure(thought_dna: Any) -> str:
    """Name a thought after its own causal spine.

    A share from this page arrives as text, so there is no topic to take from
    the caller and everything was landing as "Shared thought" in the domain
    "general" — every browser-shared thought titled identically, and the domain
    signal the classifier uses thrown away before it was ever computed. The
    extracted graph already says what the thought is: the thing that starts the
    chain and the thing it ends in.
    """
    if not isinstance(thought_dna, Mapping):
        return ""
    nodes = {str(n.get("id")): str(n.get("label") or "").strip()
             for n in (thought_dna.get("nodes") or []) if isinstance(n, Mapping)}
    relations = [r for r in (thought_dna.get("relations") or []) if isinstance(r, Mapping)]
    causal = [r for r in relations if str(r.get("type")) == "causes"]
    if not causal or not nodes:
        labels = [label for label in nodes.values() if label]
        return " · ".join(labels[:2])
    sources = {str(r.get("source")) for r in causal}
    targets = {str(r.get("target")) for r in causal}
    starts = [nodes[i] for i in sources - targets if nodes.get(i)]
    ends = [nodes[i] for i in targets - sources if nodes.get(i)]
    if starts and ends:
        return f"{sorted(starts)[0]} → {sorted(ends)[0]}"
    first = causal[0]
    head, tail = nodes.get(str(first.get("source")), ""), nodes.get(str(first.get("target")), "")
    return f"{head} → {tail}" if head and tail else (head or tail)


def _name_after_its_structure(product, token: str, session_id: Any,
                              security: Mapping[str, Any]) -> None:
    """Give a thought shared from this page a name of its own.

    A share from here arrives as text, so there is no topic to take from the
    caller, and every one of them was landing as "Shared thought" in the domain
    "general" — indistinguishable from each other to the people they matched.

    Named after the share rather than before it: renaming bumps the session
    version, and the share checks the version it prepared against. Nothing new
    is disclosed by doing it afterwards, because the name is derived from the
    same extracted structure the person had already read in the preview and
    approved. A failure here is silent: a plainly titled shared thought is
    better than a share that did not happen.
    """
    if not session_id:
        return
    try:
        session = product.identity.backend.get_session(str(session_id))
        existing = dict(getattr(session, "presentation", {}) or {})
        if str(existing.get("topic") or "") != PLACEHOLDER_TOPIC:
            # The caller named it. A structured share carries the person's own
            # words for what this is, and those are not ours to overwrite.
            return
        derived = _topic_from_structure(dict(getattr(session, "thought_dna", {}) or {}))
        if not derived:
            return
        product.update_metadata(
            token, str(session_id),
            presentation={"topic": derived[:120],
                          "domain": existing.get("domain") or "general",
                          "cluster_id": (_slug(derived) or "shared")[:48]},
            **security)
    except Exception:  # noqa: BLE001 - a plain title beats a broken share
        pass


def _live_context(product, token: str) -> dict[str, Any] | None:
    session_id = _owned_live_session(product, token)
    if not session_id:
        return None
    session = product.identity.backend.get_session(session_id)
    if session is None:
        return None
    thought = dict(getattr(session, "thought_dna", {}) or {})
    presentation = dict(getattr(session, "presentation", {}) or {})
    location = dict(getattr(session, "location", {}) or {})
    consent = product.identity.policy_source.session_consent(session_id)
    context: dict[str, Any] = {
        "contract_version": "resonance-ui-context/0.1",
        "active_thought": {
            "thought_id": thought.get("thought_id", ""),
            "source": thought.get("source", {"text": "", "sha256": ""}),
            "nodes": [
                {"id": n.get("id"), "label": n.get("label"), "role": n.get("role")}
                for n in thought.get("nodes", [])
            ],
            "relations": [
                {"id": r.get("id"), "source": r.get("source"),
                 "target": r.get("target"), "type": r.get("type")}
                for r in thought.get("relations", [])
            ],
        },
        "consent": {"shared_with_resonance": True},
        "pinned_request": {"mode": CANONICAL_MODE, "k": CANONICAL_K},
    }
    if consent.get("share_display_profile"):
        context["presentation"] = {
            "topic": presentation.get("topic", "Shared thought"),
            "domain": presentation.get("domain", ""),
        }
    if consent.get("share_coarse_location") and location:
        context["location"] = location
    return context


MINE_CONTRACT = "resonance-mine/0.1"


def _when_last_shared(product, user_id: str) -> dict[str, str]:
    """When each of this person's thoughts last became discoverable.

    The session record remembers when it was prepared and when it was
    withdrawn, but not when it was shared: sharing is a consent decision, and
    those live in the identity log. The last consent that said "discoverable"
    is the moment a person means by "when I shared it".
    """
    moments: dict[str, str] = {}
    for event in product.identity.backend.list_identity_events():
        if event.user_id != user_id or not event.session_id:
            continue
        became_discoverable = event.event_type == INGESTION_SHARED or (
            event.event_type == CONSENT_SET
            and event.payload.get("share_thought_dna") is True)
        if not became_discoverable:
            continue
        session_id = str(event.session_id)
        if str(event.created_at) > moments.get(session_id, ""):
            moments[session_id] = str(event.created_at)
    return moments


def _everything_here(product, token: str) -> dict[str, Any]:
    """Everything this person has here, each in one of three states.

    The page used to show the one discoverable thought and nothing else, so a
    person could not see what they had shared over time, what was still
    private, or what they had taken back -- and "am I sharing anything?" is
    the first thing this page owes them.

    The three states are the chat's: `resonance_whoami` sorts the same rows
    into discoverable, private and withdrawn with `_in_state`, and this uses
    that function on those rows rather than restating the rule. The two halves
    disagreed once already (a withdrawn thought reported as "kept private
    here"); sharing the rule is how they stay agreed.

    Withdrawn is not private, and private is not shared: a private thought was
    prepared and never made discoverable, a withdrawn one was discoverable and
    is not any more. A deleted thought is in neither list, because the record
    it lived in is gone from `owned_sessions` -- the chat does not see it
    either.
    """
    actor = product.identity.authenticate(token)
    rows = list(product.owned_sessions(token))
    state_of: dict[str, str] = {}
    for word, bucket in (("discoverable", _SHARED), ("withdrawn", _WITHDRAWN),
                         ("private", _PRIVATE)):
        for session_id in _in_state(rows, bucket):
            state_of.setdefault(str(session_id), word)
    shared_at = _when_last_shared(product, actor.user_id)

    thoughts: list[dict[str, Any]] = []
    for row in rows:
        session_id = str(row.get("session_id") or "")
        dna = row.get("thought_dna") or {}
        nodes = [n for n in (dna.get("nodes") or []) if isinstance(n, Mapping)]
        labels = {str(n.get("id")): str(n.get("label") or "").strip() for n in nodes}
        presentation = row.get("presentation") or {}
        thoughts.append({
            # The page needs this to say "stop sharing this one" and for
            # nothing else. It is never shown: an identifier on screen reads
            # as debug output to the person whose thought it is.
            "session_id": session_id,
            "state": state_of.get(session_id, "private"),
            "topic": str(presentation.get("topic") or "").strip(),
            "domain": str(presentation.get("domain") or "").strip(),
            "nodes": [{"label": labels[str(n.get("id"))], "role": str(n.get("role") or "")}
                      for n in nodes],
            "relations": [
                {"from": labels.get(str(r.get("source")), ""),
                 "type": str(r.get("type") or ""),
                 "to": labels.get(str(r.get("target")), "")}
                for r in (dna.get("relations") or []) if isinstance(r, Mapping)
            ],
            "prepared_at": row.get("created_at"),
            "shared_at": shared_at.get(session_id),
            "withdrawn_at": row.get("revoked_at") or row.get("deleted_at"),
        })
    # Newest first: the thing a person did most recently is the thing they
    # are most likely asking about.
    thoughts.sort(key=lambda t: str(t.get("prepared_at") or ""), reverse=True)
    counts = {word: sum(1 for t in thoughts if t["state"] == word)
              for word in ("discoverable", "private", "withdrawn")}
    return {"contract_version": MINE_CONTRACT, "thoughts": thoughts, "counts": counts}


def _discovery_view(live: Mapping[str, Any]) -> dict[str, Any]:
    """The shape the page reads; rank/score/evidence are not recomputed."""
    return {
        "contract_version": live.get("discovery_contract") or "resonance-discovery/0.1",
        "query": live.get("query", {}),
        "matches": list(live.get("matches", [])),
        "rejected": list(live.get("rejected", [])),
    }


GEO_CONTRACT = "resonance-geo-view/0.1"


def _place(location: Any) -> dict[str, Any] | None:
    """A location as the page may show it: the city and region the person
    agreed to, and coordinates already rounded to a tenth of a degree by the
    identity layer. The record's own bookkeeping (`kind`, `precision`) stays
    behind; it says how the row was made, not where anyone is."""
    if not isinstance(location, Mapping):
        return None
    lat, lon = location.get("lat"), location.get("lon")
    if isinstance(lat, bool) or isinstance(lon, bool) \
            or not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
        return None
    return {
        "city": str(location.get("city") or ""),
        "region": str(location.get("region") or ""),
        "lat": round(float(lat), 1),
        "lon": round(float(lon), 1),
    }


def _geo_view(product, token: str, session_id: str) -> dict[str, Any]:
    """Where the people in the viewer's result are, for the page to draw.

    The same authorized discovery the page already reads, reduced to what a
    map needs. Nothing here is decided: every row is one the viewer already
    has in `/api/discover`, the region counts are the service's k-anonymous
    buckets untouched, and location was never an input to any of it.

    A person who did not share a location is still in the list, with no
    place, so the page can say that they chose not to say -- which is a
    different fact from there being nobody. Rows the page itself never
    shows (not discoverable, or hard-rejected) are left out here too.
    """
    live = product.discover(token, session_id, mode=CANONICAL_MODE, k=CANONICAL_K)

    # The viewer's own place, under the viewer's own current consent -- the
    # same gate `/api/context` applies. Distances only exist when both sides
    # consented, which the service already enforced per row.
    you = None
    consent = product.identity.policy_source.session_consent(session_id)
    if consent.get("share_coarse_location"):
        session = product.identity.backend.get_session(session_id)
        you = _place(dict(getattr(session, "location", {}) or {}))

    people: list[dict[str, Any]] = []
    for row in live.get("matches", []):
        display = row.get("display") or {}
        if display.get("share_state") != "discoverable" or row.get("hard_rejection") is not None:
            continue
        distance = display.get("distance_context") or {}
        km = distance.get("approx_km")
        people.append({
            # For the page to select the same person on the resonance map and
            # in the evidence. Never rendered as text.
            "session_id": str(row.get("session_id", "")),
            "name": str(row.get("person_pseudonym") or "anonymous"),
            "resonance": row.get("mode_classification") != "negative",
            "example": display.get("demo_persona") is True,
            "place": _place(display.get("location")),
            "about_km": int(km) if isinstance(km, (int, float)) and not isinstance(km, bool) else None,
        })

    aggregation = live.get("aggregation") or {}
    return {
        "contract_version": GEO_CONTRACT,
        "you": you,
        "people": people,
        "regions": {
            "minimum": int(aggregation.get("anti_inference_minimum", 0)),
            "hidden": int(aggregation.get("suppressed_bucket_count", 0)),
            "shown": [
                {"region": str(b.get("bucket_id", "")), "count": int(b.get("count", 0))}
                for b in aggregation.get("buckets", [])
            ],
        },
        "rounded_to_degrees": 0.1,
        "note": live.get("location_note", LOCATION_NOTE),
    }


# ---- shared topics on the page -------------------------------------------
#
# The topic service already does the real work — structure in, delta out, and
# the engine's account of where the sides agree and contradict each other.
# What the page needs on top is small, and all of it is translation: the
# engine names nodes and relations by their ids, and an id is not something a
# person should ever read. Everything below turns "r2" into "slack time
# prevents rework" before it leaves the server, so the page cannot show an
# identifier by forgetting to.

MAX_TOPIC_TEXT_CHARS = MAX_CONTEXT_CHARS

NO_STRUCTURE_MESSAGE = (
    "No structure could be read from that text. Say what causes what, what "
    "prevents what, or what requires what — the structure comes from those words.")


def _display(product, user_id: str) -> str:
    return product.workspaces._display(user_id)  # noqa: SLF001 - the one pseudonym rule


def _label_maps(row: Mapping[str, Any]) -> dict[str, str]:
    """Every id in one contribution's graph, as the words it stands for.

    A node is its label; a relation is the sentence it makes, so "r2" reads
    as "slack time prevents rework" — which is what a person disagreeing with
    it would actually say.
    """
    try:
        graph = json.loads(str(row.get("thought_dna_json") or "{}"))
    except ValueError:
        return {}
    nodes = {str(n.get("id")): str(n.get("label") or "").strip()
             for n in (graph.get("nodes") or []) if isinstance(n, Mapping)}
    labels = {node_id: label for node_id, label in nodes.items() if label}
    for relation in graph.get("relations") or []:
        if not isinstance(relation, Mapping):
            continue
        head = nodes.get(str(relation.get("source")), "")
        tail = nodes.get(str(relation.get("target")), "")
        kind = str(relation.get("type") or "").replace("_", " ")
        if head and tail and kind:
            labels[str(relation.get("id"))] = f"{head} {kind} {tail}"
    return labels


def _latest_labels_by_author(product, workspace_id: str) -> dict[str, dict[str, str]]:
    """The words behind each member's latest contribution, keyed by author.

    The standing compares latest against latest, so these are the graphs its
    ids refer to. Read from the same table the service writes, in the same
    order, so the two cannot disagree about which contribution is latest.
    """
    rows = sorted(product.topics.repo.list_workspace_rows(CONTRIBUTIONS_TABLE, workspace_id),
                  key=lambda r: (str(r.get("created_at") or ""), str(r.get("contribution_id") or "")))
    latest: dict[str, dict[str, str]] = {}
    for row in rows:
        author = str(row.get("author_user_id") or "")
        if author:
            latest[author] = _label_maps(row)
    return latest


def _worded(labels: Mapping[str, str], item: Any) -> str:
    """A label for an id; never the id itself when the label is missing."""
    return labels.get(str(item), "") or "one of the points"


def _readable_standing(product, workspace_id: str, viewer_id: str,
                       standing: Mapping[str, Any]) -> dict[str, Any]:
    """The standing with every id replaced by the words it stands for."""
    if not standing.get("available"):
        return {"available": False, "reason": str(standing.get("reason") or "")}
    by_author = _latest_labels_by_author(product, workspace_id)
    mine = by_author.get(viewer_id, {})
    by_pseudonym = {_display(product, author): labels
                    for author, labels in by_author.items() if author != viewer_id}
    sides = []
    for side in standing.get("sides") or []:
        theirs = by_pseudonym.get(str(side.get("with_pseudonym") or ""), {})
        sides.append({
            "with_pseudonym": side.get("with_pseudonym"),
            "agreed_nodes": [
                {"yours": _worded(mine, pair.get("yours")),
                 "theirs": _worded(theirs, pair.get("theirs"))}
                for pair in side.get("agreed_nodes") or []],
            "agreed_relations": int(side.get("agreed_relations") or 0),
            "contested": [
                {"kind": str(item.get("kind") or ""),
                 "yours": _worded(mine, item.get("yours")),
                 "theirs": _worded(theirs, item.get("theirs"))}
                for item in side.get("contested") or []],
            "yours_unanswered": [_worded(mine, i) for i in side.get("yours_unanswered") or []],
            "theirs_unanswered": [_worded(theirs, i) for i in side.get("theirs_unanswered") or []],
            "classification": side.get("classification"),
            "confidence": side.get("confidence"),
        })
    return {"available": True, "sides": sides}


def _topic_read(product, token: str, viewer_id: str, workspace_id: str,
                *, advance: bool) -> dict[str, Any]:
    """One topic as the page reads it: the service's answer, in words."""
    answer = product.read_topic(token, workspace_id, advance=advance)
    return {
        "workspace_id": workspace_id,
        "contributions_total": answer.get("contributions_total", 0),
        "new_for_you": answer.get("new_for_you", 0),
        "truncated": bool(answer.get("truncated")),
        "delta": [
            {"contribution_id": item.get("contribution_id"),
             "author_pseudonym": item.get("author_pseudonym"),
             "note": item.get("note") or "",
             "untrusted": True,
             "thought": {
                 "nodes": [{"id": n.get("id"), "label": n.get("label"), "role": n.get("role")}
                           for n in (item.get("thought") or {}).get("nodes") or []],
                 "relations": [{"source": r.get("source"), "target": r.get("target"),
                                "type": r.get("type")}
                               for r in (item.get("thought") or {}).get("relations") or []],
             },
             "created_at": item.get("created_at")}
            for item in answer.get("delta") or []],
        "standing": _readable_standing(product, workspace_id, viewer_id,
                                       answer.get("standing") or {}),
        "note": answer.get("note", ""),
    }


def _topic_listing(product, token: str, viewer_id: str) -> dict[str, Any]:
    """Every topic this person is in, and every one they are invited to.

    Listing is a glance: nothing is marked read by it. An invitation shows
    only the title and who asked, because nothing inside a topic is visible
    until the person joins.
    """
    listed = product.list_my_workspaces(token)
    topics, invitations = [], []
    for row in listed.get("workspaces") or []:
        workspace_id = str(row.get("workspace_id") or "")
        entry: dict[str, Any] = {"workspace_id": workspace_id,
                                 "title": row.get("title") or "",
                                 "role": row.get("role"), "state": row.get("state")}
        if row.get("state") == "invited":
            member = product.workspaces.repo.get_member(workspace_id, viewer_id)
            invited_by = getattr(member, "invited_by", None) if member else None
            entry["invited_by_pseudonym"] = _display(product, invited_by) if invited_by else ""
            invitations.append(entry)
            continue
        if row.get("state") != "active":
            continue
        try:
            full = product.get_workspace(token, workspace_id)
            glance = product.read_topic(token, workspace_id, advance=False)
        except Exception:  # noqa: BLE001 - a topic still listed is better than none
            full, glance = {}, {}
        entry["brief"] = full.get("brief") or ""
        entry["members"] = [
            {"pseudonym": m.get("display") or "", "state": m.get("state"),
             "you": m.get("user_id") == viewer_id}
            for m in full.get("members") or []]
        entry["new_for_you"] = int(glance.get("new_for_you") or 0)
        entry["contributions_total"] = int(glance.get("contributions_total") or 0)
        topics.append(entry)
    return {"viewer_pseudonym": _display(product, viewer_id),
            "topics": topics, "invitations": invitations}


def _extracted_structure(product, subject: str, context: str) -> dict[str, Any]:
    """The structure in a person's words, shown back before it goes anywhere.

    The same extractor a share uses, but nothing is prepared or stored: this
    is a look, not a draft, and a draft here would have become "the latest
    prepared thought" the share composer then offers to share. The text is
    not kept, and the graph comes back in the shape a contribution takes.
    """
    result = product.ingestion.core.extractor.extract(
        context, source_id=f"{subject}:topic-preview")
    graph = result.graph
    thought = {
        "nodes": [{"id": n.id, "label": n.label, "role": n.role} for n in graph.nodes],
        "relations": [{"source": r.source, "target": r.target, "type": r.type}
                      for r in graph.relations],
    }
    if not _has_usable_structure(_structure_summary(thought)):
        raise ValueError(NO_STRUCTURE_MESSAGE)
    return {"thought": thought, "warnings": list(result.warnings)}


class WebHandler(ProductHandler):
    bridge: LiveWebMCPBridge

    def _subject(self, token: str) -> str:
        return self.runtime.product.identity.authenticate(token).user_id

    def _request_id(self, body: Mapping[str, Any]) -> str:
        request_id = body.get("request_id")
        if not isinstance(request_id, str) or not REQUEST_ID_RE.fullmatch(request_id):
            raise ValueError("request_id must be 1-128 characters from A-Z a-z 0-9 _ . : -")
        return request_id

    def _operation_start(self, token: str, operation: str,
                         body: Mapping[str, Any]):
        request_id = self._request_id(body)
        subject = self._subject(token)
        fingerprint = _fingerprint(body)
        existing = self.bridge.operation(subject, operation, request_id)
        if existing is not None:
            if existing["fingerprint"] != fingerprint:
                raise PersistenceConflictError(
                    "request_id was already used with different input")
            return subject, request_id, fingerprint, dict(existing["result"])
        return subject, request_id, fingerprint, None

    def _operation_finish(self, subject: str, operation: str, request_id: str,
                          fingerprint: str, result: Mapping[str, Any]) -> None:
        self.bridge.remember(subject, operation, request_id, fingerprint, result)
        self._send_json(dict(result))

    def _send_share_required(self) -> None:
        # A visitor who has not shared a thought is a product state, not a
        # server fault: the WebMCP discover tool used to raise an unmapped
        # PermissionError here and surface as a 500 "unexpected product error"
        # on the very first read anyone makes (same mapping the /api/discover
        # view already uses).
        self._send_json(
            {"error": "share_required",
             "message": "discovery needs a shared thought first: run "
                        "resonance_prepare_thought → resonance_get_share_preview → "
                        "resonance_share_prepared_thought (explicit confirm), then "
                        "resonance_discover again."},
            HTTPStatus.CONFLICT)

    def _visitor_token(self) -> str | None:
        """The visitor's bearer, or None when this browser has no session yet.

        A first load has no session cookie: `webmcp_live.mjs` creates the guest
        session, and the page's own boot fetches race it. "No session" and "no
        shared thought" are the same fact to a reader — nothing of theirs is
        discoverable — so the read routes answer with the same product state
        instead of an authentication fault. Any other identity error still
        propagates.
        """
        try:
            return self._token()
        except AuthenticationError:
            return None

    def _initial_app_state(self, params: Mapping[str, list[str]]) -> str:
        """Serve the state the page will settle in, so it is painted once.

        A visitor with no session cookie has certainly shared nothing, which is
        the common case and costs no lookup at all. With a cookie, one indexed
        read answers it.
        """
        token = self._visitor_token()
        if token is None:
            return "unshared"
        try:
            return "loading" if _owned_live_session(self.runtime.product, token) else "unshared"
        except Exception:                      # never fail a page load over this
            return "loading"

    def _initial_account(self) -> dict[str, str]:
        """The masthead's contents, stamped into the HTML it is part of.

        Rendering this from a fetch meant the bar was one height, then another,
        a moment later -- every load, for everyone. Reading it here costs the
        lookup the page was going to make anyway.
        """
        token = self._visitor_token()
        if token is None:
            return {}
        try:
            state = self.runtime.product.state(token)
        except Exception:                      # never fail a page load over this
            return {}
        account = (state or {}).get("account") or {}
        if not account.get("user_id"):
            return {}
        return {
            "account-label": str(account.get("display_label") or ""),
            "account-email": str(account.get("sign_in_email") or ""),
            "account-signed-in": "true" if account.get("signed_in") else "false",
        }

    def _route_get(self, path: str, params: dict[str, list[str]]) -> None:
        product = self.runtime.product

        # These two routes translate the page's presentation contract to the
        # live product without any shadow DB.
        if path == "/api/context":
            context = None
            token = self._visitor_token()
            if token is not None:
                try:
                    context = _live_context(product, token)
                except Exception:
                    context = None
            if context is None:
                # A visitor who has shared nothing has no active thought. Fail
                # closed with the same product state the discovery routes use,
                # rather than showing them somebody else's thought as if it
                # were their own.
                self._send_share_required()
                return
            self._send_json(context)
            return
        if path == "/api/discover":
            token = self._visitor_token()
            session_id = _owned_live_session(product, token) if token else None
            if not session_id:
                # Not an error in the product: the visitor simply has not shared
                # a thought yet. PermissionError was unmapped and surfaced as a
                # 500 "unexpected product error" in the page's view.
                self._send_json(
                    {"error": "share_required",
                     "message": "discovery needs a shared thought first: run "
                                "resonance_prepare_thought → resonance_get_share_preview → "
                                "resonance_share_prepared_thought (or use the Collaboration "
                                "panel)."},
                    HTTPStatus.CONFLICT)
                return
            live = product.discover(token, session_id, mode=CANONICAL_MODE, k=CANONICAL_K)
            self._send_json(_discovery_view(live))
            return
        if path == "/api/geo":
            # The geographic view of the same result, for geo.mjs. Read under
            # the same cookie and the same "nothing shared, nothing to show"
            # answer as /api/discover: a visitor without a shared thought has
            # no result, so nobody to place.
            token = self._visitor_token()
            session_id = _owned_live_session(product, token) if token else None
            if not session_id:
                self._send_share_required()
                return
            self._send_json(_geo_view(product, token, session_id))
            return

        # The browser tools are the live implementation of the same tool names
        # the standalone demo server under demo/ui/ registers from webmcp.mjs.
        if path == "/webmcp.mjs":
            self._send_bytes((UI_DIR / "webmcp_live.mjs").read_bytes(),
                             "text/javascript; charset=utf-8")
            return

        if path == "/api/webmcp/state":
            try:
                token = self._token()
                product.identity.authenticate(token)
            except Exception:
                self._send_json({
                    "contract_version": WEBMCP_CONTRACT,
                    "draft_ready": False, "draft_id": None, "shared": False,
                    "authenticated": False,
                })
                return
            draft_id = _latest_prepared_draft(product, token)
            self._send_json({
                "contract_version": WEBMCP_CONTRACT,
                "draft_ready": draft_id is not None,
                "draft_id": draft_id,
                "shared": _has_shared(product, token),
                "authenticated": True,
                "freshness": product.freshness(),
            })
            return

        if path == "/api/webmcp/operation":
            token = self._token()
            subject = self._subject(token)
            operation = (params.get("operation") or [""])[0]
            request_id = (params.get("request_id") or [""])[0]
            if operation not in WRITE_OPERATIONS or not REQUEST_ID_RE.fullmatch(request_id):
                raise ValueError("valid operation and request_id are required")
            record = self.bridge.operation(subject, operation, request_id)
            if record is None:
                self._send_json({
                    "error": "operation_not_committed",
                    "message": "no committed result exists for this operation key",
                    "retryable": True,
                }, HTTPStatus.NOT_FOUND)
                return
            self._send_json({
                "contract_version": WEBMCP_CONTRACT,
                "operation": operation,
                "request_id": request_id,
                "committed": True,
                "result": record["result"],
            })
            return

        if path == "/api/webmcp/preview":
            token = self._token()
            draft_id = _latest_prepared_draft(product, token)
            if not draft_id:
                raise PersistenceConflictError("no prepared private draft exists")
            preview = product.preview(token, draft_id, client_id="live-browser-webmcp")
            self._send_json({
                "contract_version": WEBMCP_CONTRACT,
                "draft_id": draft_id,
                "confirmation_token": preview["confirmation_token"],
                "will_become_discoverable": {
                    "thought": preview.get("thought_dna"),
                    "presentation": preview.get("presentation"),
                    "location": preview.get("coarse_location"),
                },
                "currently_shared": _has_shared(product, token),
                "requires_explicit_confirmation": True,
                "source_retention": preview.get("source_retention", "not_retained"),
            })
            return

        if path == "/api/webmcp/discover":
            token = self._token()
            session_id = _owned_live_session(product, token)
            if not session_id:
                self._send_share_required()
                return
            live = product.discover(token, session_id, mode=CANONICAL_MODE, k=CANONICAL_K,
                                    client_id="live-browser-webmcp")
            self._send_json({
                "contract_version": WEBMCP_CONTRACT,
                "result_id": live["result_id"],
                "source": "live",
                "discovery_contract": live.get("discovery_contract"),
                "query": live.get("query", {}),
                "matches_in_backend_order": list(live.get("matches", [])),
                "aggregation": live.get("aggregation", {}),
                "freshness": live.get("freshness", {}),
                "location_note": live.get("location_note", ""),
            })
            return

        if path == "/api/webmcp/match":
            result_id = (params.get("result_id") or [""])[0]
            session_id = (params.get("session_id") or [""])[0]
            token = self._token()
            result = product.get_match(token, result_id, session_id)
            self._send_json({"contract_version": WEBMCP_CONTRACT,
                             "result_id": result_id, "source": "live",
                             "freshness": result.get("freshness"),
                             "match": result["match"]})
            return

        if path == "/api/product/mine":
            # A read of the person's own record: the session cookie is the
            # whole authorisation, exactly as for /api/product/sessions, and a
            # missing or unknown cookie is a 401 rather than an empty list --
            # "nothing here" must never be said to someone we cannot identify.
            self._send_json(_everything_here(product, self._token()))
            return

        # Shared topics, for the page. Reads authenticate by cookie like the
        # other /api/product reads; a topic read that advances the cursor is
        # still a read of this person's own record, not a change anyone else
        # can see, so it needs no more than that.
        if path == "/api/product/topics":
            token = self._token()
            self._send_json(_topic_listing(product, token, self._subject(token)))
            return
        if path == "/api/product/topic":
            token = self._token()
            workspace_id = (params.get("workspace_id") or [""])[0]
            advance = (params.get("advance") or ["1"])[0] not in ("0", "false", "no")
            self._send_json(_topic_read(product, token, self._subject(token),
                                        workspace_id, advance=advance))
            return

        super()._route_get(path, params)

    def _route_topic_post(self, path: str) -> None:
        """The writes a topic takes from the page.

        Cookie plus CSRF, checked by the services underneath through the same
        security kwargs every other /api/product write passes; nothing here
        re-implements that. A contribution is the one write worth making
        idempotent: it is the one a person retries after a flaky connection,
        and two copies of the same understanding would read as emphasis.
        """
        product = self.runtime.product
        token = self._token()
        body = self._body()
        security = self._security_kwargs()
        # Cookie and CSRF before anything is looked up, so a cross-site POST
        # learns nothing from which error it gets back. The services check the
        # same thing again on the write; that costs nothing and keeps the rule
        # in one place.
        actor = product.workspaces._actor(  # noqa: SLF001 - the seam the services share
            token, csrf_token=security["csrf_token"], origin=security["origin"],
            cookie_authenticated=True)
        subject = actor.user_id

        if path == "/api/product/topic/preview":
            # A look, not a write: the words go in a body because they are the
            # person's own text and do not belong in a URL.
            context = body.get("context")
            if not isinstance(context, str) or not context.strip():
                raise ValueError("write what you now understand, in your own words")
            if len(context) > MAX_TOPIC_TEXT_CHARS:
                raise ValueError(f"the text must be at most {MAX_TOPIC_TEXT_CHARS} characters")
            self._send_json(_extracted_structure(product, subject, context))
            return

        if path == "/api/product/topic/contribute":
            _, request_id, fingerprint, committed = self._operation_start(
                token, "contribute", body)
            if committed is not None:
                self._send_json(committed)
                return
            workspace_id = str(body.get("workspace_id") or "")
            result = product.contribute_to_topic(
                token, workspace_id, thought=body.get("thought"),
                note=str(body.get("note") or ""),
                confirmed=body.get("confirmed") is True, **security)
            wire = {"workspace_id": workspace_id,
                    "contribution_id": result.get("contribution_id"),
                    "created_at": result.get("created_at"),
                    "note": result.get("note", ""),
                    "nodes": result.get("nodes", 0),
                    "relations": result.get("relations", 0)}
            self._operation_finish(subject, "contribute", request_id, fingerprint,
                                   {**wire, "say": phrasing.say("resonance_contribute_to_topic", wire)})
            return

        if path == "/api/product/topic/invite":
            # The page names the person by the introduction, never by an
            # account id: an introduction is the only way two people here know
            # each other, and its id is the one thing the page already holds.
            intro = product.collaboration._intro_for_participant(  # noqa: SLF001
                subject, str(body.get("intro_id") or ""))
            if intro.state != "accepted":
                raise ValueError("only someone who accepted an introduction can be invited")
            counterpart = intro.to_user_id if intro.from_user_id == subject else intro.from_user_id
            workspace_id = str(body.get("workspace_id") or "")
            invited = product.workspace_invite(token, workspace_id, counterpart, **security)
            wire = {"workspace_id": workspace_id,
                    "invited_pseudonym": _display(product, counterpart),
                    "state": invited.get("state")}
            self._send_json({**wire, "say": phrasing.say("resonance_invite_to_topic", wire)})
            return

        self._send_error_json(HTTPStatus.NOT_FOUND, "not_found", "unknown path")

    def _route_post(self, path: str) -> None:
        if path.startswith("/api/product/topic/"):
            self._route_topic_post(path)
            return
        if path not in {"/api/webmcp/prepare", "/api/webmcp/share",
                        "/api/webmcp/consent"}:
            super()._route_post(path)
            return

        product = self.runtime.product
        token = self._token()
        body = self._body()
        operation = path.rsplit("/", 1)[-1]
        subject, request_id, fingerprint, committed = self._operation_start(
            token, operation, body)
        if committed is not None:
            self._send_json(committed)
            return
        security = self._security_kwargs()
        security["client_id"] = "live-browser-webmcp"

        if operation == "prepare":
            # An assistant drives this surface through the browser, so it owes
            # the same answer the MCP bridge asks for: whose reasoning is this?
            # Enforcing it in one place and not the other is not enforcing it.
            try:
                authorship_rule.require(body)
            except authorship_rule.AuthorshipError as exc:
                raise ValueError(str(exc)) from exc
            # A coarse location travels with the thought only when the person
            # gave one, and giving one is the consent to show it -- the same
            # rule the MCP bridge applies. This route used to drop the field
            # on the floor and record no consent, so every browser share was
            # placeless whatever the assistant had been told, and the map of
            # where people are had nobody on it.
            coarse = _coarse_location(body.get("coarse_location"))
            intent = ShareIntent(
                share_display_profile=True,
                share_coarse_location=coarse is not None,
                receive_intro_requests=True,
            )
            thought = body.get("thought")
            context = body.get("context")
            if thought is not None and context:
                raise ValueError("provide either thought or context, not both")
            if thought is None and not context:
                # There is no stand-in content to fall back on. A prepare with
                # nothing in it used to clone a fixture thought, which made the
                # visitor's first durable row a thought they never had.
                raise ValueError("provide the person's own reasoning as either "
                                 "thought (a labelled causal graph) or context (their text)")
            # The agent hands over the person's REAL reasoning: a labelled
            # causal graph it extracted (preferred) or raw text for the cue
            # extractor. Same contract as remote MCP; the text is never
            # retained.
            presentation = _presentation_for(thought)
            if thought is not None:
                candidate = build_thought_dna(thought, human_id=subject)
                result = product.prepare_structured(
                    token, candidate, presentation=presentation,
                    coarse_location=coarse, intent=intent, **security)
            else:
                if not isinstance(context, str) or len(context) > MAX_CONTEXT_CHARS:
                    raise ValueError(f"context must be text of at most {MAX_CONTEXT_CHARS} characters")
                # Per-prepare namespace: the extracted id must not collide
                # with a reserved/revoked id for the same sentences.
                result = product.prepare_raw_text(
                    token, context, source_id=f"{subject}:{request_id}",
                    presentation=presentation, coarse_location=coarse,
                    intent=intent, **security)
                preview = product.preview(token, str(result["draft_id"]),
                                          client_id="live-browser-webmcp")
                structure = _structure_summary(preview.get("thought_dna"))
                if not _has_usable_structure(structure):
                    # Empty graphs must not become shareable drafts (the
                    # extractor abstains on implicit prose).
                    try:
                        product.discard(token, str(result["draft_id"]), confirmed=True, **security)
                    except Exception:  # noqa: BLE001 - best effort clean-up
                        pass
                    raise ValueError(_insufficient_structure_message(
                        structure, result.get("abstentions", [])))
            wire = {
                "contract_version": WEBMCP_CONTRACT,
                "draft_id": result["draft_id"],
                "session_id": result.get("session_id"),
                "discoverable": False,
                "source_retention": result.get("source_retention", "not_retained"),
                "input_kind": result.get("input_kind"),
                "next_step": "Preview exactly what will be shared, then confirm.",
            }
            self._operation_finish(subject, operation, request_id, fingerprint,
                                   _spoken(operation, wire))
            return

        if operation == "share":
            if body.get("confirm") is not True:
                raise ValueError("confirm=true is required after preview")
            draft_id = _latest_prepared_draft(product, token)
            if not draft_id:
                raise PersistenceConflictError("no prepared private draft exists")
            result = product.share_prepared(
                token, draft_id,
                confirmation_token=str(body.get("confirmation_token", "")),
                confirmed=True, **security,
            )
            _name_after_its_structure(product, token, result.get("session_id"), security)
            wire = {
                "contract_version": WEBMCP_CONTRACT,
                "draft_id": draft_id,
                "session_id": result.get("session_id"),
                "shared": True,
                "discoverable": True,
            }
            self._operation_finish(subject, operation, request_id, fingerprint,
                                   _spoken(operation, wire))
            return

        # The consent tool is intentionally revoke-only unless already shared.
        shared = body.get("shared") is True
        session_id = _owned_live_session(product, token)
        if shared:
            if not session_id:
                raise PersistenceConflictError(
                    "restoring sharing requires prepare, preview, and explicit share")
            wire = {"contract_version": WEBMCP_CONTRACT,
                    "session_id": session_id, "shared": True,
                    "revoked": False, "discoverable": True}
        else:
            if session_id:
                product.revoke_session(token, session_id, confirmed=True, **security)
            wire = {"contract_version": WEBMCP_CONTRACT,
                    "session_id": session_id, "shared": False,
                    "revoked": True, "discoverable": False}
        self._operation_finish(subject, operation, request_id, fingerprint,
                               _spoken(operation, wire))


def serve(host: str, port: int, *, runtime: ProductRuntime) -> ThreadingHTTPServer:
    bridge = LiveWebMCPBridge()
    handler = type("BoundWebHandler", (WebHandler,),
                   {"runtime": runtime, "bridge": bridge})
    return ThreadingHTTPServer((host, port), handler)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Resonance: live product + browser WebMCP")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--db", default="live-product.sqlite3")
    parser.add_argument("--origin", action="append", default=None)
    parser.add_argument("--secret-file", default=None)
    parser.add_argument("--seed-demo", action="store_true",
                        help="seed the R7 demo corpus into this database (RESONANCE_SEED_DEMO=1 "
                             "has the same effect); persistent databases are never seeded by default")
    args = parser.parse_args(argv)
    seed = True if args.db == ":memory:" else (
        args.seed_demo or os.environ.get("RESONANCE_SEED_DEMO", "").strip().lower() in ("1", "true", "yes", "on"))
    origins = frozenset(args.origin or [f"http://{args.host}:{args.port}"])
    try:
        secret = _resolve_secret(args.secret_file, os.environ, args.db)
    except ValueError as exc:
        parser.error(str(exc))
    runtime = build_runtime(args.db, allowed_origins=origins,
                            confirmation_secret=secret,
                            seed=seed)
    startup_purge_demo(runtime)
    startup_purge_sessions(runtime)
    startup_purge_unsigned(runtime)
    startup_assign_pseudonyms(runtime)
    # R15C (#136): canonical OAuth for hosted MCP clients on this same origin.
    # Per request the issuer is re-derived from the host actually addressed
    # (`ProductHandler._issuer`), so every allowed origin serves its own
    # metadata. This value only labels the startup log, and `public_issuer()`
    # would pick the alphabetically first https origin — which stops being the
    # canonical one the moment a custom domain is added alongside the platform
    # host. The FIRST declared --origin is the canonical one, so say that.
    oauth_mount.attach_core(
        runtime, issuer=oauth_mount.canonical_origin(args.origin, origins))
    server = serve(args.host, args.port, runtime=runtime)
    print(f"resonance on http://{args.host}:{args.port} "
          f"(origins: {sorted(origins)}; db: {_redact_db(args.db)}; mode: LIVE+WebMCP)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    main()
