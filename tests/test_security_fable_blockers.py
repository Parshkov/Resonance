"""Focused regressions for Fable's R12B exact-head blockers."""

from __future__ import annotations

import unittest

from src.identity.security import IdentityPolicySource, SECURITY_DECISION
from src.security.guards import PayloadBounds
from src.security.models import Decision, PayloadRejected, PolicyDecision


class _AuditBackend:
    def __init__(self) -> None:
        self.events = []

    def append_identity_event(self, event) -> None:
        self.events.append(event)


class DurableDecisionMinimizationTests(unittest.TestCase):
    def test_durable_policy_event_omits_live_session_identifiers(self):
        backend = _AuditBackend()
        source = IdentityPolicySource(backend)
        source.record_decision(
            PolicyDecision(
                correlation_id="corr-1",
                subject="person-a",
                client_id="client-a",
                auth_session_id="auth-secret-graph-id",
                protocol_session_id="mcp-session-secret-graph-id",
                action="session:read",
                resource_kind="session",
                resource_id="ses-a",
                grant_version=7,
                decision=Decision.ALLOW,
                reason="owner",
            )
        )
        self.assertEqual(len(backend.events), 1)
        event = backend.events[0]
        self.assertEqual(event.event_type, SECURITY_DECISION)
        self.assertNotIn("auth_session_id", event.payload)
        self.assertNotIn("protocol_session_id", event.payload)
        self.assertEqual(event.payload["correlation_id"], "corr-1")
        self.assertEqual(event.payload["subject"], "person-a")


class ThoughtDnaRelationBoundTests(unittest.TestCase):
    def test_canonical_relations_field_is_bounded(self):
        bounds = PayloadBounds(max_edges=10)
        dna = {
            "schema_version": "thought-dna/0.1",
            "thought_id": "thought-a",
            "nodes": [],
            "relations": [{"source": "a", "target": "b"}] * 11,
        }
        with self.assertRaisesRegex(PayloadRejected, "relation bound"):
            bounds.validate_thought_dna(dna)

    def test_legacy_edges_alias_remains_bounded(self):
        bounds = PayloadBounds(max_edges=2)
        with self.assertRaises(PayloadRejected):
            bounds.validate_thought_dna({"nodes": [], "edges": [{}, {}, {}]})


if __name__ == "__main__":
    unittest.main()
