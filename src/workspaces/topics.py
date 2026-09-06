"""The shared topic: what two assistants build between two people.

Person one talks to their assistant. That assistant talks to Resonance.
Resonance is read by a second assistant, which talks to person two — and back.
The obvious way to build that is a chat relay, and it is the wrong way:

- it makes each assistant a postman, when the thing an assistant is uniquely
  good at is explaining a stranger's idea in its own person's terms;
- prose that passes through two language models drifts a little each hop, so
  after a few exchanges the two sides are discussing different things;
- and a list of messages never becomes an understanding. A month in there are a
  hundred replies and no answer to "where did we get to?".

So what accumulates here is not a transcript but a structure. Each side
contributes the shape of what it now understands — a small causal graph plus a
short note its person approved — and the topic is what those shapes say
together:

    agreed      nodes and relations both sides' graphs carry
    contested   where the graphs contradict each other, which is usually the
                reason the introduction was worth making at all
    offered     what one side has that the other has not answered yet

Every read is a delta. A reader's cursor is the last contribution they were
shown, so nobody replays history to catch up and an assistant spends its
context on the new thing rather than on the archive.

Consent is unchanged: only members of the workspace can contribute or read, and
membership still requires an introduction both people accepted. The raw
conversation never arrives here and is never stored.
"""

from __future__ import annotations

import json
import secrets
from datetime import datetime, timezone
from typing import Any, Mapping

from src.graph import ThoughtGraph

CONTRIBUTIONS_TABLE = "workspace_contributions"
CURSOR_KIND = "topic_cursor"
MAX_NOTE_CHARS = 1000
MAX_DELTA = 25


class TopicError(ValueError):
    """A contribution or a read could not be carried out."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _order_key(row: Mapping[str, Any]) -> tuple[str, str]:
    return (str(row.get("created_at") or ""), str(row.get("contribution_id") or ""))


class SharedTopicService:
    """Contributions to a workspace, and what they say together."""

    def __init__(self, workspaces: Any) -> None:
        self.workspaces = workspaces
        self.identity = workspaces.identity
        self.repo = workspaces.repo

    # -- writing --------------------------------------------------------
    def contribute(self, access_token: str, workspace_id: str, *,
                   thought: Mapping[str, Any], note: str = "",
                   confirmed: bool = False, csrf_token: str | None = None,
                   origin: str | None = None, cookie_authenticated: bool = False,
                   client_id: str | None = None) -> dict[str, Any]:
        """Add what this side now understands to the shared topic.

        Requires the person's explicit approval, like every other act that
        another human being will see.
        """
        if not confirmed:
            raise TopicError("explicit confirmation is required before contributing")
        actor = self.workspaces._actor(  # noqa: SLF001 - same seam the rest of the service uses
            access_token, csrf_token=csrf_token, origin=origin,
            cookie_authenticated=cookie_authenticated, client_id=client_id)
        member = self.workspaces._active_member(workspace_id, actor.user_id)  # noqa: SLF001
        self.workspaces._require_role(member, {"owner", "member"})  # noqa: SLF001

        graph = self._validated_graph(thought, actor.user_id)
        text = str(note or "").strip()
        if len(text) > MAX_NOTE_CHARS:
            raise TopicError(f"note must be at most {MAX_NOTE_CHARS} characters")

        contribution_id = f"contrib-{secrets.token_hex(10)}"
        created_at = _now()
        self.repo.add_workspace_row(
            CONTRIBUTIONS_TABLE,
            ("contribution_id", "workspace_id", "author_user_id",
             "thought_dna_json", "note", "created_at"),
            (contribution_id, workspace_id, actor.user_id,
             json.dumps(graph.to_dict(), sort_keys=True), text, created_at))
        self.workspaces._log(  # noqa: SLF001
            workspace_id, actor.user_id, "contributed", contribution_id)
        # The contributor has, by definition, seen their own contribution.
        self._set_cursor(workspace_id, actor.user_id, contribution_id)
        return {"workspace_id": workspace_id, "contribution_id": contribution_id,
                "created_at": created_at, "note": text,
                "nodes": len(graph.nodes), "relations": len(graph.relations)}

    def _validated_graph(self, thought: Mapping[str, Any], author: str) -> ThoughtGraph:
        """Accept the same shape an assistant already uses to prepare a thought.

        There is one vocabulary for describing reasoning to Resonance — labelled
        nodes and typed relations — and a contribution to a shared topic is not
        a second one. The builder that turns that shape into full Thought DNA is
        imported here rather than at module load, because the product layer
        imports this package and the reverse would close a cycle.
        """
        if not isinstance(thought, Mapping):
            raise TopicError("a contribution must carry a thought graph")
        from src.product.mcp_bridge import build_thought_dna

        try:
            graph = ThoughtGraph.from_dict(
                build_thought_dna(dict(thought), human_id=author))
        except TopicError:
            raise
        except Exception as exc:  # noqa: BLE001 - the caller gets the reason, not a stack
            raise TopicError(f"the thought graph is not usable: {exc}") from exc
        if len(graph.nodes) < 2 or not graph.relations:
            raise TopicError("a contribution needs at least two nodes and one relation")
        return graph

    # -- reading --------------------------------------------------------
    def read(self, access_token: str, workspace_id: str, *,
             advance: bool = True, mode: str = "analogical",
             from_start: bool = False) -> dict[str, Any]:
        """What is new for this reader, and what the topic now says.

        `advance` moves this reader's cursor to the end of what it returns. An
        assistant that shows the person the delta should advance; one that is
        only glancing should not.
        """
        actor = self.identity.authenticate(access_token)
        self.workspaces._active_member(workspace_id, actor.user_id)  # noqa: SLF001

        rows = sorted(
            self.repo.list_workspace_rows(CONTRIBUTIONS_TABLE, workspace_id),
            key=_order_key)
        # A page shows the whole topic, not what is new since a chat last
        # looked: `from_start` reads every contribution and moves no cursor.
        cursor = "" if from_start else self._get_cursor(workspace_id, actor.user_id)
        after = self._after(rows, cursor)
        delta = [self._present(row) for row in after[-MAX_DELTA:]]
        if advance and after and not from_start:
            self._set_cursor(workspace_id, actor.user_id,
                             str(after[-1]["contribution_id"]))
        return {
            "workspace_id": workspace_id,
            "contributions_total": len(rows),
            "new_for_you": len(after),
            "truncated": len(after) > len(delta),
            "delta": delta,
            "standing": self._standing(rows, actor.user_id, mode=mode),
            "note": "Structure only. The conversation each person has with their "
                    "own assistant is never sent here.",
        }

    @staticmethod
    def _after(rows: list[Mapping[str, Any]], cursor: str) -> list[Mapping[str, Any]]:
        if not cursor:
            return list(rows)
        for index, row in enumerate(rows):
            if str(row.get("contribution_id")) == cursor:
                return list(rows[index + 1:])
        # The cursor names something no longer here; showing everything again is
        # better than silently showing nothing.
        return list(rows)

    def _present(self, row: Mapping[str, Any]) -> dict[str, Any]:
        author = str(row.get("author_user_id") or "")
        return {
            "contribution_id": row.get("contribution_id"),
            "author_pseudonym": self.workspaces._display(author),  # noqa: SLF001
            "note": row.get("note") or "",
            # Another person's words, and an assistant must treat them as such.
            "untrusted": True,
            "thought": self._readable(json.loads(str(row.get("thought_dna_json") or "{}"))),
            "created_at": row.get("created_at"),
        }

    @staticmethod
    def _readable(thought: Mapping[str, Any]) -> dict[str, Any]:
        """The reasoning, and nothing that identifies who wrote it.

        Thought DNA carries a provenance block naming the account it was built
        for. A reader needs the nodes and the relations; the pseudonym beside
        them already says whose they are. Projected field by field rather than
        by removing known identifiers, so a field added later cannot leak by
        being forgotten here.
        """
        return {
            "thought_id": thought.get("thought_id"),
            "schema_version": thought.get("schema_version"),
            "nodes": thought.get("nodes") or [],
            "relations": thought.get("relations") or [],
        }

    # -- what the topic says --------------------------------------------
    def _standing(self, rows: list[Mapping[str, Any]], viewer_id: str,
                  *, mode: str) -> dict[str, Any]:
        """Agreement and contradiction between this reader and each other side.

        Computed rather than stored: the engine that decides two people resonate
        is the same one that says where they now disagree, so the answer cannot
        drift away from the match that introduced them.
        """
        mine = self._latest_by(rows, viewer_id)
        if mine is None:
            return {"available": False,
                    "reason": "contribute your own understanding first, and the "
                              "topic can say where it agrees with theirs"}
        others = {}
        for row in rows:
            author = str(row.get("author_user_id") or "")
            if author and author != viewer_id:
                others[author] = row
        engine = getattr(getattr(self.identity, "backend", None), "live_corpus", None)
        engine = getattr(engine, "engine", None)
        if engine is None:
            return {"available": False, "reason": "comparison is unavailable here"}

        my_graph = ThoughtGraph.from_dict(json.loads(str(mine["thought_dna_json"])))
        sides = []
        for author, row in sorted(others.items()):
            try:
                their_graph = ThoughtGraph.from_dict(
                    json.loads(str(row["thought_dna_json"])))
                verdict = engine.compare(my_graph, their_graph, mode=mode)
            except Exception:  # noqa: BLE001 - one unusable side must not hide the rest
                continue
            sides.append({
                "with_pseudonym": self.workspaces._display(author),  # noqa: SLF001
                "agreed_nodes": [
                    {"yours": m.query_node, "theirs": m.candidate_node}
                    for m in verdict.mapping],
                "agreed_relations": len(verdict.matched_relations),
                # The point of the introduction: where the two accounts of the
                # same shape disagree.
                "contested": [
                    {"kind": c.kind, "yours": c.query_item, "theirs": c.candidate_item}
                    for c in verdict.contradictions],
                "yours_unanswered": list(verdict.unmatched_query_nodes),
                "theirs_unanswered": list(verdict.unmatched_candidate_nodes),
                "classification": verdict.classification,
                "confidence": verdict.confidence,
            })
        return {"available": True, "your_latest": mine.get("contribution_id"),
                "sides": sides}

    @staticmethod
    def _latest_by(rows: list[Mapping[str, Any]], user_id: str):
        owned = [r for r in rows if str(r.get("author_user_id")) == user_id]
        return owned[-1] if owned else None

    # -- cursors --------------------------------------------------------
    def _cursor_key(self, workspace_id: str, user_id: str) -> str:
        return f"{workspace_id}|{user_id}"

    def _get_cursor(self, workspace_id: str, user_id: str) -> str:
        record = self.repo.get_grant(CURSOR_KIND, self._cursor_key(workspace_id, user_id))
        return str((record or {}).get("contribution_id") or "")

    def _set_cursor(self, workspace_id: str, user_id: str, contribution_id: str) -> None:
        self.repo.put_grant(
            CURSOR_KIND, self._cursor_key(workspace_id, user_id),
            {"workspace_id": workspace_id, "contribution_id": contribution_id,
             "at": _now()},
            user_id=user_id)
