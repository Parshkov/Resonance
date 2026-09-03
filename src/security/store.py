"""Authoritative-policy seam and deterministic in-memory test adapter.

Production adapters should read the accepted R11 persistence and R12 identity /
consent state.  This module intentionally does not become a second product
store: :class:`PolicySource` is the seam, while :class:`InMemoryPolicySource`
is only a deterministic test/pilot adapter.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol


class PolicySource(Protocol):
    def generation_for(self, subject: str) -> int: ...
    def owner_of(self, kind: str, resource_id: str) -> str | None: ...
    def workspace_of(self, kind: str, resource_id: str) -> str | None: ...
    def session_consent(self, session_id: str) -> Mapping[str, bool]: ...
    def workspace_role(self, workspace_id: str, subject: str) -> str | None: ...
    def peer_action_allowed(self, subject: str, peer_id: str, action: str) -> bool: ...
    def is_blocked(self, subject: str, peer_id: str) -> bool: ...
    def auth_session_active(self, subject: str, auth_session_id: str) -> bool: ...


@dataclass
class InMemoryPolicySource:
    """Deterministic authoritative-state adapter used by security tests.

    Mutations increment the affected subject policy generation.  The security
    kernel reads this source on every protected call; cached token claims never
    override it.
    """

    owners: dict[tuple[str, str], str] = field(default_factory=dict)
    consents: dict[str, dict[str, bool]] = field(default_factory=dict)
    workspace_roles: dict[str, dict[str, str]] = field(default_factory=dict)
    workspace_links: dict[tuple[str, str], str] = field(default_factory=dict)
    peer_permissions: set[tuple[str, str, str]] = field(default_factory=set)
    blocks: set[tuple[str, str]] = field(default_factory=set)
    reports: list[dict[str, str]] = field(default_factory=list)
    generations: dict[str, int] = field(default_factory=dict)

    def generation_for(self, subject: str) -> int:
        return self.generations.get(subject, 0)

    def _touch(self, *subjects: str) -> None:
        for subject in set(filter(None, subjects)):
            self.generations[subject] = self.generation_for(subject) + 1

    def set_owner(self, kind: str, resource_id: str, owner_id: str) -> None:
        previous = self.owners.get((kind, resource_id))
        self.owners[(kind, resource_id)] = owner_id
        self._touch(previous or "", owner_id)

    def owner_of(self, kind: str, resource_id: str) -> str | None:
        return self.owners.get((kind, resource_id))

    def set_session_consent(self, session_id: str, owner_id: str, **choices: bool) -> None:
        if self.owner_of("session", session_id) not in (None, owner_id):
            raise ValueError("session owner mismatch")
        self.owners[("session", session_id)] = owner_id
        current = {
            "share_thought_dna": False,
            "share_display_profile": False,
            "share_coarse_location": False,
            "allow_intro_requests": False,
            "revoked": False,
            "deleted": False,
        }
        current.update(self.consents.get(session_id, {}))
        current.update({key: bool(value) for key, value in choices.items()})
        self.consents[session_id] = current
        self._touch(owner_id)

    def revoke_session(self, session_id: str) -> None:
        owner = self.owner_of("session", session_id)
        current = dict(self.consents.get(session_id, {}))
        current.update({
            "share_thought_dna": False,
            "share_display_profile": False,
            "share_coarse_location": False,
            "allow_intro_requests": False,
            "revoked": True,
        })
        self.consents[session_id] = current
        self._touch(owner or "")

    def session_consent(self, session_id: str) -> Mapping[str, bool]:
        return dict(self.consents.get(session_id, {}))

    def link_workspace_resource(self, kind: str, resource_id: str, workspace_id: str) -> None:
        self.workspace_links[(kind, resource_id)] = workspace_id

    def workspace_of(self, kind: str, resource_id: str) -> str | None:
        if kind == "workspace":
            return resource_id
        return self.workspace_links.get((kind, resource_id))

    def set_workspace_role(self, workspace_id: str, subject: str, role: str | None) -> None:
        roles = self.workspace_roles.setdefault(workspace_id, {})
        if role is None:
            roles.pop(subject, None)
        else:
            roles[subject] = role
        self._touch(subject)

    def workspace_role(self, workspace_id: str, subject: str) -> str | None:
        return self.workspace_roles.get(workspace_id, {}).get(subject)

    def set_peer_permission(self, subject: str, peer_id: str, action: str, allowed: bool = True) -> None:
        key = (subject, peer_id, action)
        if allowed:
            self.peer_permissions.add(key)
        else:
            self.peer_permissions.discard(key)
        self._touch(subject, peer_id)

    def peer_action_allowed(self, subject: str, peer_id: str, action: str) -> bool:
        return (subject, peer_id, action) in self.peer_permissions

    def block(self, subject: str, peer_id: str) -> None:
        if subject == peer_id:
            raise ValueError("cannot block self")
        self.blocks.add(tuple(sorted((subject, peer_id))))
        self._touch(subject, peer_id)

    def unblock(self, subject: str, peer_id: str) -> None:
        self.blocks.discard(tuple(sorted((subject, peer_id))))
        self._touch(subject, peer_id)

    def is_blocked(self, subject: str, peer_id: str) -> bool:
        if not subject or not peer_id:
            return False
        return tuple(sorted((subject, peer_id))) in self.blocks

    def auth_session_active(self, subject: str, auth_session_id: str) -> bool:
        # The deterministic kernel adapter has no authentication store. Product
        # adapters must override this with their current durable auth state.
        return True

    def report(self, subject: str, peer_id: str, reason_code: str) -> None:
        self.reports.append({"subject": subject, "peer_id": peer_id, "reason_code": reason_code})
        self._touch(subject)

    def snapshot(self) -> dict[str, Any]:
        """Test-adapter export used to prove access-control restore fidelity."""
        return {
            "owners": [[kind, rid, owner] for (kind, rid), owner in sorted(self.owners.items())],
            "consents": {key: dict(value) for key, value in sorted(self.consents.items())},
            "workspace_roles": {
                key: dict(sorted(value.items())) for key, value in sorted(self.workspace_roles.items())
            },
            "workspace_links": [
                [kind, rid, workspace] for (kind, rid), workspace in sorted(self.workspace_links.items())
            ],
            "peer_permissions": [list(value) for value in sorted(self.peer_permissions)],
            "blocks": [list(value) for value in sorted(self.blocks)],
            "reports": [dict(value) for value in self.reports],
            "generations": dict(sorted(self.generations.items())),
        }

    @classmethod
    def from_snapshot(cls, snapshot: Mapping[str, Any]) -> "InMemoryPolicySource":
        source = cls()
        source.owners = {
            (str(kind), str(rid)): str(owner)
            for kind, rid, owner in snapshot.get("owners", [])
        }
        source.consents = {
            str(key): {str(k): bool(v) for k, v in dict(value).items()}
            for key, value in dict(snapshot.get("consents", {})).items()
        }
        source.workspace_roles = {
            str(key): {str(k): str(v) for k, v in dict(value).items()}
            for key, value in dict(snapshot.get("workspace_roles", {})).items()
        }
        source.workspace_links = {
            (str(kind), str(rid)): str(workspace)
            for kind, rid, workspace in snapshot.get("workspace_links", [])
        }
        source.peer_permissions = {
            (str(subject), str(peer), str(action))
            for subject, peer, action in snapshot.get("peer_permissions", [])
        }
        source.blocks = {
            tuple(sorted((str(pair[0]), str(pair[1]))))
            for pair in snapshot.get("blocks", [])
        }
        source.reports = [
            {str(k): str(v) for k, v in dict(value).items()}
            for value in snapshot.get("reports", [])
        ]
        source.generations = {
            str(key): int(value)
            for key, value in dict(snapshot.get("generations", {})).items()
        }
        return source
