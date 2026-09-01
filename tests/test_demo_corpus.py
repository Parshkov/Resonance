"""R7-CORPUS: consented demo corpus, consent filter, and ranking invariance."""

from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from demo.corpus.build import V01_MANIFEST_SHA, build_sessions
from demo.corpus.discovery import discover, is_discoverable, load_sessions, presentation_view
from demo.corpus.validate import CorpusValidationError, validate_corpus, validate_session
from src.engine import ResonanceEngine
from src.graph import ThoughtGraph

CORPUS = REPO / "demo" / "corpus"
FLAGSHIP = "ses-aria-plasma-lens"
HIDDEN = "ses-ravi-irrigation"
UNSHARED = "ses-nico-tracing-private"
V01_MANIFEST = REPO / "benchmark" / "r0-v0.1" / "manifest.sha256"


class SchemaAndRebuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sessions = load_sessions()
        cls.by_id = {s["session_id"]: s for s in cls.sessions}

    def test_session_window_and_clusters(self):
        self.assertTrue(20 <= len(self.sessions) <= 50)
        clusters = {s["presentation"]["cluster_id"] for s in self.sessions}
        self.assertGreaterEqual(len(clusters), 3)
        self.assertIn("accumulating-intermediary-failure", clusters)
        self.assertIn("method-resource-hub", clusters)
        self.assertIn("evidence-corroboration", clusters)

    def test_flagship_and_hidden_present(self):
        self.assertIn(FLAGSHIP, self.by_id)
        self.assertIn(HIDDEN, self.by_id)
        self.assertFalse(is_discoverable(self.by_id[HIDDEN]))
        self.assertFalse(is_discoverable(self.by_id[UNSHARED]))
        self.assertTrue(is_discoverable(self.by_id[FLAGSHIP]))

    def test_rebuild_is_byte_stable(self):
        rebuilt = build_sessions()
        blob = "\n".join(
            json.dumps(s, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            for s in rebuilt
        ) + "\n"
        committed = (CORPUS / "sessions.jsonl").read_text(encoding="utf-8")
        self.assertEqual(hashlib.sha256(blob.encode()).hexdigest(),
                         hashlib.sha256(committed.encode()).hexdigest())
        self.assertEqual(blob, committed)
        manifest = json.loads((CORPUS / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["sessions_sha256"],
                         hashlib.sha256(committed.encode()).hexdigest())
        self.assertEqual(manifest["frozen_v0_1_manifest_sha256"], V01_MANIFEST_SHA)

    def test_module_rebuild_matches_committed_manifest(self):
        proc = subprocess.run(
            [sys.executable, "-m", "demo.corpus.build"],
            cwd=REPO, capture_output=True, text=True, timeout=60,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        committed = (CORPUS / "sessions.jsonl").read_bytes()
        self.assertEqual(hashlib.sha256(committed).hexdigest(),
                         json.loads((CORPUS / "manifest.json").read_text())["sessions_sha256"])

    def test_thought_dna_is_engine_valid_and_manual(self):
        for session in self.sessions:
            graph = ThoughtGraph.from_dict(session["thought_dna"])
            self.assertEqual(graph.provenance.kind, "manual")
            self.assertEqual(graph.thought_id, session["thought_dna"]["thought_id"])

    def test_no_contact_or_precise_pins(self):
        raw = (CORPUS / "sessions.jsonl").read_text(encoding="utf-8")
        self.assertNotIn("@", raw)
        self.assertNotIn('"email"', raw.lower())
        self.assertNotIn('"phone"', raw.lower())
        self.assertNotIn('"telephone"', raw.lower())
        for session in self.sessions:
            lat, lon = session["location"]["lat"], session["location"]["lon"]
            self.assertEqual(round(lat, 1), lat)
            self.assertEqual(round(lon, 1), lon)
            self.assertEqual(session["location"]["precision"], "city")

    def test_presentation_fields_absent_from_thought_dna(self):
        for session in self.sessions:
            thought = session["thought_dna"]
            for key in ("domain", "topic", "cluster_id", "city", "lat", "lon", "person_id"):
                self.assertNotIn(key, thought)

    def test_invalid_session_rejected(self):
        bad = copy.deepcopy(self.sessions[0])
        bad["person"]["email"] = "secret@example.com"
        with self.assertRaises(CorpusValidationError):
            validate_session(bad)
        with self.assertRaises(CorpusValidationError):
            validate_corpus(self.sessions[:5])


class ConsentAndRankingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sessions = load_sessions()
        cls.by_id = {s["session_id"]: s for s in cls.sessions}
        cls.query = cls.by_id[FLAGSHIP]
        cls.engine = ResonanceEngine()
        cls.hits = discover(cls.query, cls.sessions, mode="analogical", k=20, engine=cls.engine)

    def test_hidden_and_unshared_never_returned(self):
        ids = {h["session"]["session_id"] for h in self.hits}
        thoughts = {h["thought_id"] for h in self.hits}
        self.assertNotIn(HIDDEN, ids)
        self.assertNotIn(UNSHARED, ids)
        self.assertNotIn(self.by_id[HIDDEN]["thought_dna"]["thought_id"], thoughts)
        self.assertNotIn(FLAGSHIP, ids)
        hidden_graph = ThoughtGraph.from_dict(self.by_id[HIDDEN]["thought_dna"])
        self.assertIsNone(self.engine.get(hidden_graph.thought_id))

    def test_flagship_has_two_to_four_useful_cross_domain_analogs(self):
        useful = [
            h for h in self.hits
            if h["classification"] == "analogical"
            and h["session"]["presentation"]["cluster_id"] == "accumulating-intermediary-failure"
            and h["session"]["session_id"] not in {FLAGSHIP, HIDDEN}
        ]
        analog_ids = {h["session"]["session_id"] for h in useful}
        self.assertIn("ses-noah-org-overload", analog_ids)
        self.assertIn("ses-mei-battery-heat", analog_ids)
        self.assertIn("ses-kwame-traffic", analog_ids)
        self.assertGreaterEqual(len(useful), 2)
        self.assertGreaterEqual(len(useful), 4)  # org, battery, traffic, warehouse

    def test_same_words_wrong_structure_is_negative(self):
        query = ThoughtGraph.from_dict(self.query["thought_dna"])
        rewire = ThoughtGraph.from_dict(self.by_id["ses-sam-plasma-rewire"]["thought_dna"])
        result = ResonanceEngine().compare(query, rewire, mode="structural")
        self.assertEqual(result.classification, "negative")
        self.assertGreater(result.components.semantic, 0.9)
        self.assertLess(result.components.structural, 0.85)

    def test_polarity_inversion_is_hard_rejection(self):
        query = ThoughtGraph.from_dict(self.query["thought_dna"])
        polarity = ThoughtGraph.from_dict(self.by_id["ses-lea-plasma-polarity"]["thought_dna"])
        result = ResonanceEngine().compare(query, polarity, mode="structural")
        self.assertIsNotNone(result.hard_rejection)
        self.assertTrue(result.components.h_sign_conflict)
        self.assertEqual(result.classification, "negative")

    def test_lens_vocabulary_trap_is_not_analogical(self):
        query = ThoughtGraph.from_dict(self.query["thought_dna"])
        portrait = ThoughtGraph.from_dict(self.by_id["ses-camille-portrait"]["thought_dna"])
        result = ResonanceEngine().compare(query, portrait, mode="analogical")
        self.assertEqual(result.classification, "negative")

    def test_other_clusters_do_not_false_analogize_to_flagship(self):
        query = ThoughtGraph.from_dict(self.query["thought_dna"])
        engine = ResonanceEngine()
        for sid in ("ses-priya-tracing", "ses-omar-chronology", "ses-marc-sourdough"):
            other = ThoughtGraph.from_dict(self.by_id[sid]["thought_dna"])
            result = engine.compare(query, other, mode="analogical")
            self.assertEqual(result.classification, "negative", sid)

    def test_complementary_bridge_recovers(self):
        query = ThoughtGraph.from_dict(self.query["thought_dna"])
        chiller = ThoughtGraph.from_dict(self.by_id["ses-diego-chiller"]["thought_dna"])
        result = ResonanceEngine().compare(query, chiller, mode="complementary")
        self.assertEqual(result.classification, "complementary")
        self.assertGreaterEqual(result.components.complement_query_to_candidate, 0.3)

    def test_partial_and_granularity_are_recoverable(self):
        query = ThoughtGraph.from_dict(self.query["thought_dna"])
        engine = ResonanceEngine()
        partial = engine.compare(query, ThoughtGraph.from_dict(self.by_id["ses-sora-plasma-partial"]["thought_dna"]), mode="structural")
        granular = engine.compare(query, ThoughtGraph.from_dict(self.by_id["ses-theo-plasma-granular"]["thought_dna"]), mode="structural")
        self.assertEqual(partial.classification, "approximate")
        self.assertEqual(granular.classification, "approximate")
        self.assertGreater(granular.components.r_path, 0.0)

    def test_within_cluster_analogs_hold_for_b_and_c(self):
        engine = ResonanceEngine()
        t2 = engine.compare(
            ThoughtGraph.from_dict(self.by_id["ses-priya-tracing"]["thought_dna"]),
            ThoughtGraph.from_dict(self.by_id["ses-jonas-diagnostics"]["thought_dna"]),
            mode="analogical",
        )
        t4 = engine.compare(
            ThoughtGraph.from_dict(self.by_id["ses-omar-chronology"]["thought_dna"]),
            ThoughtGraph.from_dict(self.by_id["ses-elena-litigation"]["thought_dna"]),
            mode="analogical",
        )
        self.assertEqual(t2.classification, "analogical")
        self.assertEqual(t4.classification, "analogical")

    def test_presentation_metadata_cannot_change_ranking(self):
        original = discover(self.query, self.sessions, mode="analogical", k=20)
        original_ids = [h["thought_id"] for h in original]
        original_cls = [h["classification"] for h in original]
        mutated = copy.deepcopy(self.sessions)
        for i, session in enumerate(mutated):
            session["presentation"]["domain"] = f"mutated-domain-{i}"
            session["presentation"]["topic"] = f"mutated-topic-{i}"
            session["presentation"]["cluster_id"] = f"mutated-cluster-{i}"
            session["location"]["city"] = f"City{i}"
            session["location"]["lat"] = round((i % 80) + 0.1, 1)
            session["location"]["lon"] = round((i % 80) - 40.0, 1)
            session["person"]["display_label"] = f"Alias {i}"
        shuffled = discover(self.query, mutated, mode="analogical", k=20)
        self.assertEqual([h["thought_id"] for h in shuffled], original_ids)
        self.assertEqual([h["classification"] for h in shuffled], original_cls)

    def test_unshared_location_is_stripped_from_view(self):
        warehouse = self.by_id["ses-gabe-warehouse"]
        view = presentation_view(warehouse)
        self.assertNotIn("location", view)
        self.assertTrue(is_discoverable(warehouse))

    def test_frozen_v0_1_gold_untouched(self):
        self.assertEqual(V01_MANIFEST.read_text(encoding="utf-8").strip(), V01_MANIFEST_SHA)
        graphs = REPO / "benchmark" / "r0-v0.1" / "graphs.jsonl"
        self.assertTrue(graphs.exists())
        # Builder records the same pin the tests just read.
        manifest = json.loads((CORPUS / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["frozen_v0_1_manifest_sha256"], V01_MANIFEST_SHA)


class EngineIsolationTests(unittest.TestCase):
    def test_discovery_does_not_import_matcher_internals(self):
        source = (REPO / "demo" / "corpus" / "discovery.py").read_text(encoding="utf-8")
        for banned in ("src.alignment", "src.fingerprint", "src.index", "src.scoring", "src.mcp"):
            self.assertNotIn(banned, source)
        build = (REPO / "demo" / "corpus" / "build.py").read_text(encoding="utf-8")
        for banned in ("src.alignment", "src.fingerprint", "src.index", "src.scoring", "src.mcp"):
            self.assertNotIn(banned, build)


if __name__ == "__main__":
    unittest.main()
