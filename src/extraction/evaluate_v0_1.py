"""Benchmark adapter for CueExtractor against frozen extraction_runs.jsonl.

Does not mutate frozen gold. Prints coverage plus official runner metrics.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

from src.extraction import (
    EXTRACTOR_ID,
    EXTRACTOR_VERSION,
    CueExtractor,
    frozen_v0_1_coverage,
    frozen_v0_1_predictions,
    repeat_extraction_f1,
)

REPO = Path(__file__).resolve().parents[2]
BENCHMARK = REPO / "benchmark" / "r0-v0.1"
REPORT = Path(__file__).resolve().parent / "reports" / "r0-v0.1-cue-extractor.json"
CUED_REPEAT = "Heat accumulation causes degradation but cooling prevents failure."


def _load_runner():
    sys.path.insert(0, str(BENCHMARK))
    spec = importlib.util.spec_from_file_location("resonance_benchmark_runner", BENCHMARK / "runner.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def measure() -> dict[str, object]:
    extractor = CueExtractor()
    predictions = frozen_v0_1_predictions(extractor)
    coverage = frozen_v0_1_coverage(predictions)
    runner = _load_runner()
    bundle = runner.validate_fixtures()
    official = runner.evaluate_extraction(bundle, predictions)
    first = extractor.extract(CUED_REPEAT, source_id="run-1")
    second = extractor.extract(CUED_REPEAT, source_id="run-2")
    cued = repeat_extraction_f1(first.graph, second.graph)
    extraction_prerequisite_claimed = bool(
        official
        and official["span_hash_schema_rate"] == 1.0
        and official["ungrounded_extracted_objects"] == 0
        and coverage["nonempty_graph_rate"] > 0
        and cued["node_f1"] == 1.0
        and cued["edge_f1"] == 1.0
    )
    report = {
        "extractor_id": EXTRACTOR_ID,
        "extractor_version": EXTRACTOR_VERSION,
        "config_hash": first.config.config_hash,
        "frozen_coverage": coverage,
        "official_runner": official,
        "cued_repeat_across_source_id": {
            "text": CUED_REPEAT,
            "node_f1": cued["node_f1"],
            "edge_f1": cued["edge_f1"],
            "nodes": len(first.graph.nodes),
            "relations": len(first.graph.relations),
        },
        "extraction_prerequisite_claimed": extraction_prerequisite_claimed,
        "notes": (
            "Frozen v0.1 extraction inputs contain no explicit relation cues. "
            "Cue-only extraction therefore has zero coverage on that corpus. "
            "Duplicate empty/empty F1 is not used as a pass. The non-vacuous "
            "repeat is the cued sentence under two source_id namespaces."
        ),
    }
    return report


def main() -> None:
    report = measure()
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
