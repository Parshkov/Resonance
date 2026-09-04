"""Consent-safe multi-person idea workspaces (R14B).

A workspace is bootstrapped ONLY from an accepted R14 intro; membership derives
from that intro's two subjects, never a client-supplied id. Every membership
and content operation re-checks the caller's current membership and role at
write/read time — membership changes move no global counter, so authorization
is verified per access (the R13B/get_match discipline). Invitees see nothing
workspace-private until they explicitly accept; a removed or departed member
loses access immediately. Workspace ids are opaque and participant-only: a
non-member gets one uniform "unavailable" error for foreign, missing, and
not-a-member references. No workspace write touches the corpus generation.

All member/note/task/message text is user-generated and returned with an
`untrusted: true` marker; it is never interpreted by the product.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timezone
from typing import Any, Mapping

from src.identity import IdentityService
from src.persistence.errors import PersistenceConflictError
from src.persistence.models import AuditEvent, MemberRecord, WorkspaceRecord

MAX_TITLE = 200
MAX_BRIEF = 4000
MAX_NOTE = 4000
MAX_TASK_TITLE = 300
UNAVAILABLE = "workspace unavailable to authenticated subject"
WRITE_ROLES = {"owner", "member"}
ADMIN_ROLES = {"owner"}


class WorkspaceError(ValueError):
    """Typed workspace-boundary error (uniform for leak-free negatives)."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _oid(prefix: str) -> str:
    return f"{prefix}-" + secrets.token_hex(12)


class WorkspaceService:
    def __init__(self, identity: IdentityService) -> None:
        self.identity = identity
        self.backend = identity.backend
        self.repo = identity.backend.repo

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------
    def _actor(self, access_token, *, csrf_token=None, origin=None,
               cookie_authenticated=False, client_id=None):
        actor = self.identity.authenticate(access_token)
        if cookie_authenticated:
            self.identity._require_csrf(actor, csrf_token, origin)
        return actor

    def _display(self, user_id: str) -> str:
        user = self.backend.get_user(user_id)
        label = getattr(user, "display_label", None) if user is not None else None
        return str(label) if label else "anonymous"

    def _audit(self, event_type, *, user_id, workspace_id, detail=""):
        return AuditEvent(event_id="wsev-" + secrets.token_hex(12),
                          event_type=event_type, user_id=user_id,
                          session_id=None,
                          payload={"workspace_id": workspace_id, "detail": detail},
                          created_at=_now())

    def _active_member(self, workspace_id: str, user_id: str) -> MemberRecord:
        """Current-state authorization: caller must be an ACTIVE member now."""
        member = self.repo.get_member(workspace_id, user_id)
        if member is None or member.state != "active":
            raise WorkspaceError(UNAVAILABLE)
        return member

    def _require_role(self, member: MemberRecord, roles: set[str]) -> None:
        if member.role not in roles:
            raise WorkspaceError("your workspace role cannot perform this action")

    def _log(self, workspace_id, actor_id, event_type, detail=""):
        self.repo.add_workspace_row(
            "workspace_activity",
            ("activity_id", "workspace_id", "actor_user_id", "event_type",
             "detail", "created_at"),
            (_oid("act"), workspace_id, actor_id, event_type, detail, _now()))

    # ------------------------------------------------------------------
    # creation from an accepted intro
    # ------------------------------------------------------------------
    def create_from_intro(self, access_token, intro_id, *, title, brief="",
                          csrf_token=None, origin=None, cookie_authenticated=False, client_id=None):
        actor = self._actor(access_token, csrf_token=csrf_token, origin=origin,
                            cookie_authenticated=cookie_authenticated)
        if not isinstance(title, str) or not title.strip() or len(title) > MAX_TITLE:
            raise WorkspaceError("title must be 1..200 characters")
        if len(brief) > MAX_BRIEF:
            raise WorkspaceError("brief exceeds the product bound")
        intro = self.repo.get_intro(intro_id)
        # Bootstrap seam: only a genuinely accepted intro the caller is part of,
        # and both parties still unblocked, may seed a workspace.
        if (intro is None or intro.state != "accepted"
                or actor.user_id not in (intro.from_user_id, intro.to_user_id)):
            raise WorkspaceError(UNAVAILABLE)
        peer = (intro.to_user_id if actor.user_id == intro.from_user_id
                else intro.from_user_id)
        if self.identity.policy_source.is_blocked(actor.user_id, peer):
            raise WorkspaceError(UNAVAILABLE)
        now = _now()
        workspace = WorkspaceRecord(
            workspace_id=_oid("ws"), title=title.strip(), brief=brief,
            owner_user_id=actor.user_id, origin_intro_id=intro_id,
            created_at=now, updated_at=now, version=1)
        members = [
            MemberRecord(workspace.workspace_id, actor.user_id, "owner",
                         "active", actor.user_id, now, now),
            # The peer is INVITED, not active: no workspace-private content is
            # visible to them until they explicitly accept.
            MemberRecord(workspace.workspace_id, peer, "member", "invited",
                         actor.user_id, now, None),
        ]
        self.repo.create_workspace(
            workspace, members,
            audit=self._audit("workspace.created", user_id=actor.user_id,
                              workspace_id=workspace.workspace_id))
        self._log(workspace.workspace_id, actor.user_id, "created",
                  self._display(peer))
        return self._workspace_dto(actor.user_id, workspace)

    # ------------------------------------------------------------------
    # membership
    # ------------------------------------------------------------------
    def invite(self, access_token, workspace_id, invitee_user_id, *,
               role="member", csrf_token=None, origin=None,
               cookie_authenticated=False, client_id=None):
        actor = self._actor(access_token, csrf_token=csrf_token, origin=origin,
                            cookie_authenticated=cookie_authenticated)
        member = self._active_member(workspace_id, actor.user_id)
        self._require_role(member, WRITE_ROLES)
        if role not in {"member", "viewer"}:
            raise WorkspaceError("invited role must be member or viewer")
        if invitee_user_id == actor.user_id:
            raise WorkspaceError("cannot invite yourself")
        if self.backend.get_user(invitee_user_id) is None:
            raise WorkspaceError(UNAVAILABLE)
        # Only an already-connected (mutually accepted) & unblocked user may be
        # invited — no cold adds.
        if self.identity.policy_source.is_blocked(actor.user_id, invitee_user_id):
            raise WorkspaceError(UNAVAILABLE)
        if not self._mutually_connected(actor.user_id, invitee_user_id):
            raise WorkspaceError("you can only invite a connected Resonance user")
        existing = self.repo.get_member(workspace_id, invitee_user_id)
        if existing is not None and existing.state in {"invited", "active"}:
            raise WorkspaceError("already a member or invited")
        now = _now()
        self.repo.upsert_member(
            MemberRecord(workspace_id, invitee_user_id, role, "invited",
                         actor.user_id, now, None),
            audit=self._audit("workspace.invited", user_id=actor.user_id,
                              workspace_id=workspace_id,
                              detail=self._display(invitee_user_id)))
        self._log(workspace_id, actor.user_id, "invited",
                  self._display(invitee_user_id))
        return {"workspace_id": workspace_id, "invited": invitee_user_id,
                "role": role, "state": "invited"}

    def respond_invite(self, access_token, workspace_id, *, accept,
                       csrf_token=None, origin=None, cookie_authenticated=False, client_id=None):
        actor = self._actor(access_token, csrf_token=csrf_token, origin=origin,
                            cookie_authenticated=cookie_authenticated)
        member = self.repo.get_member(workspace_id, actor.user_id)
        if member is None or member.state != "invited":
            raise WorkspaceError(UNAVAILABLE)
        now = _now()
        new_state = "active" if accept else "left"
        self.repo.upsert_member(
            MemberRecord(workspace_id, actor.user_id, member.role, new_state,
                         member.invited_by, member.invited_at,
                         now if accept else None),
            audit=self._audit(f"workspace.invite_{new_state}",
                              user_id=actor.user_id, workspace_id=workspace_id))
        self._log(workspace_id, actor.user_id,
                  "joined" if accept else "declined")
        if accept:
            return self.get_workspace(access_token, workspace_id)
        return {"workspace_id": workspace_id, "state": new_state}

    def remove_member(self, access_token, workspace_id, target_user_id, *,
                      csrf_token=None, origin=None, cookie_authenticated=False, client_id=None):
        actor = self._actor(access_token, csrf_token=csrf_token, origin=origin,
                            cookie_authenticated=cookie_authenticated)
        member = self._active_member(workspace_id, actor.user_id)
        self._require_role(member, ADMIN_ROLES)
        target = self.repo.get_member(workspace_id, target_user_id)
        if target is None or target.state not in {"invited", "active"}:
            raise WorkspaceError(UNAVAILABLE)
        if target_user_id == actor.user_id:
            raise WorkspaceError("owner cannot remove themselves; transfer or leave")
        now = _now()
        self.repo.upsert_member(
            MemberRecord(workspace_id, target_user_id, target.role, "removed",
                         target.invited_by, target.invited_at, target.joined_at),
            audit=self._audit("workspace.removed", user_id=actor.user_id,
                              workspace_id=workspace_id,
                              detail=self._display(target_user_id)))
        self._log(workspace_id, actor.user_id, "removed",
                  self._display(target_user_id))
        return {"workspace_id": workspace_id, "removed": target_user_id}

    def leave(self, access_token, workspace_id, *, csrf_token=None, origin=None,
              cookie_authenticated=False, client_id=None):
        actor = self._actor(access_token, csrf_token=csrf_token, origin=origin,
                            cookie_authenticated=cookie_authenticated)
        member = self._active_member(workspace_id, actor.user_id)
        if member.role == "owner":
            raise WorkspaceError("owner cannot leave; remove others or archive")
        now = _now()
        self.repo.upsert_member(
            MemberRecord(workspace_id, actor.user_id, member.role, "left",
                         member.invited_by, member.invited_at, member.joined_at),
            audit=self._audit("workspace.left", user_id=actor.user_id,
                              workspace_id=workspace_id))
        self._log(workspace_id, actor.user_id, "left")
        return {"workspace_id": workspace_id, "state": "left"}

    # ------------------------------------------------------------------
    # shared work
    # ------------------------------------------------------------------
    def update_brief(self, access_token, workspace_id, brief, *,
                     expected_version, csrf_token=None, origin=None,
                     cookie_authenticated=False, client_id=None):
        actor = self._actor(access_token, csrf_token=csrf_token, origin=origin,
                            cookie_authenticated=cookie_authenticated)
        member = self._active_member(workspace_id, actor.user_id)
        self._require_role(member, WRITE_ROLES)
        if len(brief) > MAX_BRIEF:
            raise WorkspaceError("brief exceeds the product bound")
        self.repo.bump_workspace(workspace_id, expected_version=expected_version,
                                 brief=brief, now=_now())
        self._log(workspace_id, actor.user_id, "brief_updated")
        return self.get_workspace(access_token, workspace_id)

    def add_note(self, access_token, workspace_id, body, *, csrf_token=None,
                 origin=None, cookie_authenticated=False, client_id=None):
        actor = self._actor(access_token, csrf_token=csrf_token, origin=origin,
                            cookie_authenticated=cookie_authenticated)
        member = self._active_member(workspace_id, actor.user_id)
        self._require_role(member, WRITE_ROLES)
        if not body.strip() or len(body) > MAX_NOTE:
            raise WorkspaceError("note must be 1..4000 characters")
        note_id = _oid("note")
        self.repo.add_workspace_row(
            "workspace_notes",
            ("note_id", "workspace_id", "author_user_id", "body", "created_at"),
            (note_id, workspace_id, actor.user_id, body, _now()),
            audit=self._audit("workspace.note", user_id=actor.user_id,
                              workspace_id=workspace_id))
        self._log(workspace_id, actor.user_id, "note_added")
        return {"note_id": note_id, "workspace_id": workspace_id}

    def add_task(self, access_token, workspace_id, title, *, csrf_token=None,
                 origin=None, cookie_authenticated=False, client_id=None):
        actor = self._actor(access_token, csrf_token=csrf_token, origin=origin,
                            cookie_authenticated=cookie_authenticated)
        member = self._active_member(workspace_id, actor.user_id)
        self._require_role(member, WRITE_ROLES)
        if not title.strip() or len(title) > MAX_TASK_TITLE:
            raise WorkspaceError("task title must be 1..300 characters")
        task_id = _oid("task")
        now = _now()
        self.repo.add_workspace_row(
            "workspace_tasks",
            ("task_id", "workspace_id", "title", "state", "created_by",
             "created_at", "updated_at"),
            (task_id, workspace_id, title, "todo", actor.user_id, now, now),
            audit=self._audit("workspace.task", user_id=actor.user_id,
                              workspace_id=workspace_id))
        self._log(workspace_id, actor.user_id, "task_added")
        return {"task_id": task_id, "workspace_id": workspace_id, "state": "todo"}

    def set_task_state(self, access_token, workspace_id, task_id, state, *,
                       csrf_token=None, origin=None, cookie_authenticated=False, client_id=None):
        actor = self._actor(access_token, csrf_token=csrf_token, origin=origin,
                            cookie_authenticated=cookie_authenticated)
        member = self._active_member(workspace_id, actor.user_id)
        self._require_role(member, WRITE_ROLES)
        if state not in {"todo", "doing", "done"}:
            raise WorkspaceError("task state must be todo, doing, or done")
        # the task must belong to this workspace (participant-scoped)
        tasks = {t["task_id"] for t in self.repo.list_workspace_rows(
            "workspace_tasks", workspace_id)}
        if task_id not in tasks:
            raise WorkspaceError(UNAVAILABLE)
        self.repo.update_task_state(task_id, state, _now())
        self._log(workspace_id, actor.user_id, "task_state", state)
        return {"task_id": task_id, "state": state}

    def link_match(self, access_token, workspace_id, session_id, why, *,
                   csrf_token=None, origin=None, cookie_authenticated=False, client_id=None):
        actor = self._actor(access_token, csrf_token=csrf_token, origin=origin,
                            cookie_authenticated=cookie_authenticated)
        member = self._active_member(workspace_id, actor.user_id)
        self._require_role(member, WRITE_ROLES)
        if not why.strip() or len(why) > MAX_NOTE:
            raise WorkspaceError("a consent-safe explanation is required")
        link_id = _oid("link")
        self.repo.add_workspace_row(
            "workspace_links",
            ("link_id", "workspace_id", "session_id", "why", "linked_by", "created_at"),
            (link_id, workspace_id, session_id, why, actor.user_id, _now()),
            audit=self._audit("workspace.link", user_id=actor.user_id,
                              workspace_id=workspace_id))
        self._log(workspace_id, actor.user_id, "match_linked")
        return {"link_id": link_id, "workspace_id": workspace_id}

    def add_artifact(self, access_token, workspace_id, *, label, kind, sha256,
                     size_bytes, csrf_token=None, origin=None,
                     cookie_authenticated=False, client_id=None):
        actor = self._actor(access_token, csrf_token=csrf_token, origin=origin,
                            cookie_authenticated=cookie_authenticated)
        member = self._active_member(workspace_id, actor.user_id)
        self._require_role(member, WRITE_ROLES)
        if not label.strip() or len(label) > MAX_TITLE:
            raise WorkspaceError("artifact label must be 1..200 characters")
        if not isinstance(size_bytes, int) or size_bytes < 0:
            raise WorkspaceError("artifact size must be a non-negative integer")
        # Metadata only — no raw contact-bearing filenames; the label is the
        # caller-provided display name, the sha256 identifies content stored
        # out of band.
        artifact_id = _oid("art")
        self.repo.add_workspace_row(
            "workspace_artifacts",
            ("artifact_id", "workspace_id", "label", "kind", "sha256",
             "size_bytes", "added_by", "created_at"),
            (artifact_id, workspace_id, label, kind, sha256, int(size_bytes),
             actor.user_id, _now()),
            audit=self._audit("workspace.artifact", user_id=actor.user_id,
                              workspace_id=workspace_id))
        self._log(workspace_id, actor.user_id, "artifact_added")
        return {"artifact_id": artifact_id, "workspace_id": workspace_id}

    # ------------------------------------------------------------------
    # reads (member-only, re-checked per access)
    # ------------------------------------------------------------------
    def list_my_workspaces(self, access_token):
        actor = self.identity.authenticate(access_token)
        result = []
        for ws in self.repo.list_workspaces_for_user(actor.user_id):
            member = self.repo.get_member(ws.workspace_id, actor.user_id)
            result.append({"workspace_id": ws.workspace_id, "title": ws.title,
                           "role": member.role if member else None,
                           "state": member.state if member else None})
        return {"workspaces": result}

    def get_workspace(self, access_token, workspace_id):
        actor = self.identity.authenticate(access_token)
        member = self._active_member(workspace_id, actor.user_id)
        ws = self.repo.get_workspace(workspace_id)
        if ws is None:
            raise WorkspaceError(UNAVAILABLE)
        members = [
            {"user_id": m.user_id, "display": self._display(m.user_id),
             "role": m.role, "state": m.state}
            for m in self.repo.list_members(workspace_id)
            if m.state in {"invited", "active"}
        ]
        notes = [{"note_id": n["note_id"],
                  "author_display": self._display(n["author_user_id"]),
                  "body": n["body"], "untrusted": True,
                  "created_at": n["created_at"]}
                 for n in self.repo.list_workspace_rows("workspace_notes", workspace_id)]
        tasks = [{"task_id": t["task_id"], "title": t["title"],
                  "state": t["state"], "untrusted": True}
                 for t in self.repo.list_workspace_rows("workspace_tasks", workspace_id)]
        artifacts = [{"artifact_id": a["artifact_id"], "label": a["label"],
                      "kind": a["kind"], "sha256": a["sha256"],
                      "size_bytes": a["size_bytes"], "untrusted": True}
                     for a in self.repo.list_workspace_rows("workspace_artifacts", workspace_id)]
        links = [{"link_id": l["link_id"], "session_id": l["session_id"],
                  "why": l["why"], "untrusted": True}
                 for l in self.repo.list_workspace_rows("workspace_links", workspace_id)]
        activity = [{"event_type": a["event_type"], "detail": a["detail"],
                     "actor_display": self._display(a["actor_user_id"]),
                     "created_at": a["created_at"]}
                    for a in self.repo.list_workspace_rows("workspace_activity", workspace_id)]
        return {
            "workspace_id": ws.workspace_id, "title": ws.title,
            "brief": ws.brief, "version": ws.version, "role": member.role,
            "members": members, "notes": notes, "tasks": tasks,
            "artifacts": artifacts, "links": links, "activity": activity,
            "note": "member/note/task/message text is user-generated and untrusted",
        }

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _mutually_connected(self, a: str, b: str) -> bool:
        latest = self.repo.latest_intro_between(a, b)
        return latest is not None and latest.state == "accepted"

    def _workspace_dto(self, viewer_id, ws: WorkspaceRecord) -> dict[str, Any]:
        member = self.repo.get_member(ws.workspace_id, viewer_id)
        return {"workspace_id": ws.workspace_id, "title": ws.title,
                "brief": ws.brief, "version": ws.version,
                "role": member.role if member else None,
                "origin_intro_id": ws.origin_intro_id}
