"""R12C ingestion contract tests.

These tests intentionally use a fake ShareSink: durable persistence and
authenticated identity are separate gates. The contract proves that preparation
cannot itself publish and that the eventual durable sink receives only the
sanitized, explicitly confirmed artifact under a server-supplied subject.
"""

from __future__ import annotations

import hashlib
import unittest
from pathlib import Path

from src.ingestion import (
    ConfirmationError,
    DraftNotFound,
    IngestionError,
    IngestionLimits,
    IngestionService,
    ShareIntent,
)

EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()


def thought(text: str = "heat accumulation causes failure") -> dict:
    return {
        "schema_version": "thought-dna/0.1",
        "thought_id": "thought-ingestion-test",
        "source": {
            "text": text,
            "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        },
        "provenance": {"kind": "manual", "extractor": None, "human_id": "test"},
        "nodes": [
            {
                "id": "n-heat",
                "label": "heat accumulation",
                "role": "state",
                "spans": [{"start": 0, "end": 17, "text": "heat accumulation"}],
                "extract_conf": 1.0,
                "atomic": True,
                "assertion": "asserted",
                "modality": "actual",
            },
            {
                "id": "n-failure",
                "label": "failure",
                "role": "outcome",
                "spans": [{"start": 25, "end": 32, "text": "failure"}],
                "extract_conf": 1.0,
                "atomic": True,
                "assertion": "asserted",
                "modality": "actual",
            },
        ],
        "relations": [
            {
                "id": "r-causes",
                "source": "n-heat",
                "target": "n-failure",
                "type": "causes",
                "extract_conf": 1.0,
                "spans": [{"start": 18, "end": 24, "text": "causes"}],
                "cue": {"start": 18, "end": 24, "text": "causes"},
                "assertion": "asserted",
                "modality": "actual",
            }
        ],
    }


class RecordingSink:
    def __init__(self, *, fail: bool = False):
        self.fail = fail
        self.commits = []

    def commit_prepared(self, commit):
        self.commits.append(commit)
        if self.fail:
            raise RuntimeError("durable transaction failed")
        return {
            "session_id": "ses-server-assigned",
            "shared": True,
            "thought_dna": dict(commit.thought_dna),
        }


class IngestionTests(unittest.TestCase):
    def setUp(self):
        self.service = IngestionService(secret=b"x" * 32)

    def test_structured_prepare_is_private_and_preview_is_sanitized(self):
        prepared = self.service.prepare_structured(
            thought(),
            presentation={"topic": "thermal overload"},
            coarse_location={"region": "US-West", "precision": "region"},
            intent=ShareIntent(
                share_display_profile=True,
                share_coarse_location=False,
                receive_intro_requests=True,
            ),
        )
        self.assertEqual(prepared["status"], "prepared_private")
        self.assertFalse(prepared["discoverable"])
        preview = self.service.preview(prepared["draft_id"])
        self.assertTrue(preview["requires_explicit_confirmation"])
        self.assertEqual(preview["source_retention"], "not_retained")
        self.assertIsNone(preview["coarse_location"])
        graph = preview["thought_dna"]
        self.assertEqual(graph["source"], {"text": "", "sha256": EMPTY_SHA256})
        self.assertTrue(all(not n["spans"] for n in graph["nodes"]))
        self.assertTrue(all(not r["spans"] for r in graph["relations"]))
        self.assertTrue(all("cue" not in r for r in graph["relations"]))
        self.assertEqual(graph["relations"][0]["type"], "causes")

    def test_raw_fallback_is_deterministic_and_implicit_text_abstains(self):
        first = self.service.prepare_raw_text(
            "heat accumulation causes failure", source_id="fallback-explicit"
        )
        first_preview = self.service.preview(first["draft_id"])
        self.assertEqual(first["input_kind"], "raw_text_fallback")
        self.assertEqual(len(first_preview["thought_dna"]["relations"]), 1)
        self.assertEqual(first_preview["thought_dna"]["provenance"]["kind"], "manual")
        self.assertEqual(
            first_preview["thought_dna"]["provenance"]["human_id"],
            "r12c-sanitized-preview",
        )

        weak = self.service.prepare_raw_text(
            "heat keeps building in the device and eventually everything goes wrong",
            source_id="fallback-implicit",
        )
        weak_preview = self.service.preview(weak["draft_id"])
        self.assertEqual(weak_preview["thought_dna"]["relations"], [])
        self.assertTrue(
            any("implicit structure not emitted" in x for x in weak_preview["abstentions"])
        )

    def test_spoofed_product_control_fields_are_rejected(self):
        candidate = thought()
        candidate["user_id"] = "person-victim"
        candidate["consent"] = {"share_enabled": True}
        with self.assertRaises(IngestionError):
            self.service.prepare_structured(candidate)

    def test_malformed_and_oversized_inputs_fail_before_share(self):
        with self.assertRaises(Exception):
            self.service.prepare_structured({"schema_version": "thought-dna/0.1"})

        tiny = IngestionService(
            limits=IngestionLimits(max_payload_bytes=100),
            secret=b"y" * 32,
        )
        with self.assertRaises(IngestionError):
            tiny.prepare_structured(thought())

        with self.assertRaises(IngestionError):
            self.service.prepare_raw_text("x" * 20_001)

    def test_preview_token_and_subject_are_required_for_share(self):
        prepared = self.service.prepare_structured(thought())
        draft_id = prepared["draft_id"]
        sink = RecordingSink()
        with self.assertRaises(ConfirmationError):
            self.service.share_prepared(
                draft_id,
                subject="person-a",
                confirmation_token="wrong",
                sink=sink,
            )
        preview = self.service.preview(draft_id)
        with self.assertRaises(IngestionError):
            self.service.share_prepared(
                draft_id,
                subject="",
                confirmation_token=preview["confirmation_token"],
                sink=sink,
            )
        self.assertTrue(self.service.has_draft(draft_id))
        self.assertEqual(sink.commits, [])

    def test_successful_share_handoff_is_exact_and_contains_no_raw_source(self):
        prepared = self.service.prepare_structured(
            thought(),
            presentation={"topic": "thermal overload"},
            coarse_location={"region": "US-West"},
            intent=ShareIntent(share_coarse_location=True),
        )
        preview = self.service.preview(prepared["draft_id"])
        sink = RecordingSink()
        receipt = self.service.share_prepared(
            prepared["draft_id"],
            subject="person-authenticated",
            confirmation_token=preview["confirmation_token"],
            sink=sink,
        )
        self.assertEqual(receipt["session_id"], "ses-server-assigned")
        self.assertFalse(self.service.has_draft(prepared["draft_id"]))
        commit = sink.commits[0]
        self.assertEqual(commit.subject, "person-authenticated")
        self.assertEqual(dict(commit.thought_dna), preview["thought_dna"])
        self.assertEqual(commit.thought_dna["source"]["text"], "")
        self.assertEqual(commit.thought_dna["source"]["sha256"], EMPTY_SHA256)
        self.assertNotIn("source_sha256", commit.provenance)
        self.assertFalse(commit.provenance["source_retained"])
        self.assertEqual(commit.coarse_location, {"region": "US-West"})

    def test_failed_durable_commit_keeps_private_draft_for_safe_retry(self):
        prepared = self.service.prepare_structured(thought())
        preview = self.service.preview(prepared["draft_id"])
        sink = RecordingSink(fail=True)
        with self.assertRaises(RuntimeError):
            self.service.share_prepared(
                prepared["draft_id"],
                subject="person-a",
                confirmation_token=preview["confirmation_token"],
                sink=sink,
            )
        self.assertTrue(self.service.has_draft(prepared["draft_id"]))

    def test_discard_then_reprepare_cannot_reuse_old_confirmation_token(self):
        first = self.service.prepare_structured(thought())
        first_preview = self.service.preview(first["draft_id"])
        self.service.discard(first["draft_id"])
        second = self.service.prepare_structured(thought())
        self.assertNotEqual(first["draft_id"], second["draft_id"])
        sink = RecordingSink()
        with self.assertRaises(ConfirmationError):
            self.service.share_prepared(
                second["draft_id"],
                subject="person-a",
                confirmation_token=first_preview["confirmation_token"],
                sink=sink,
            )

    def test_discard_destroys_prepared_state_without_share(self):
        prepared = self.service.prepare_structured(thought())
        result = self.service.discard(prepared["draft_id"])
        self.assertTrue(result["discarded"])
        self.assertFalse(result["discoverable"])
        self.assertFalse(self.service.has_draft(prepared["draft_id"]))
        with self.assertRaises(DraftNotFound):
            self.service.preview(prepared["draft_id"])

    def test_ingestion_package_does_not_implement_matching(self):
        root = Path(__file__).parents[1] / "src" / "ingestion"
        text = "\n".join(p.read_text(encoding="utf-8") for p in root.glob("*.py"))
        for banned in (
            "src.alignment",
            "src.fingerprint",
            "src.index",
            "src.scoring",
            "src.discovery",
            "ResonanceEngine",
        ):
            self.assertNotIn(banned, text)


if __name__ == "__main__":
    unittest.main()
