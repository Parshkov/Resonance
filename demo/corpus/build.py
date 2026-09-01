#!/usr/bin/env python3
"""Deterministic R7 demo-corpus builder.

Seeds 25 consented/unconsented sessions. Matching structure lives only in
Thought DNA; topic/location/display fields are presentation metadata.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from src.graph import ThoughtGraph, canonical_sha256

from .validate import CORPUS_SCHEMA_VERSION, validate_corpus

PACKAGE_DIR = Path(__file__).resolve().parent
REPO = PACKAGE_DIR.parents[1]
BUILDER_ID = "parshkov-xai-grok46-t2n9"
V01_MANIFEST_SHA = "1700935134235ab1a376779c54b0fbc70db19cc72d9c93bc5f06f9485cd7e49e"

T1_NODES = [
    ("n0", "problem"), ("n1", "mechanism"), ("n2", "state"), ("n3", "constraint"),
    ("n4", "method"), ("n5", "outcome"), ("n6", "evidence"), ("n7", "resource"),
    ("n8", "agent"), ("n9", "mechanism"),
]
T1_RELS = [
    ("r0", "n0", "causes", "n1"), ("r1", "n1", "causes", "n2"),
    ("r2", "n2", "causes", "n5"), ("r3", "n3", "constrains", "n4"),
    ("r4", "n4", "prevents", "n5"), ("r5", "n4", "requires", "n7"),
    ("r6", "n6", "supports", "n4"), ("r7", "n9", "part_of", "n1"),
    ("r8", "n9", "causes", "n2"), ("r9", "n8", "supports", "n4"),
]
T2_NODES = [
    ("n0", "problem"), ("n1", "method"), ("n2", "resource"), ("n3", "evidence"),
    ("n4", "constraint"), ("n5", "outcome"), ("n6", "agent"), ("n7", "state"),
]
T2_RELS = [
    ("r0", "n1", "supports", "n0"), ("r1", "n1", "requires", "n2"),
    ("r2", "n3", "supports", "n1"), ("r3", "n4", "constrains", "n1"),
    ("r4", "n1", "causes", "n5"), ("r5", "n6", "supports", "n1"),
    ("r6", "n7", "part_of", "n0"), ("r7", "n4", "constrains", "n5"),
]
T3_NODES = [
    ("n0", "outcome"), ("n1", "problem"), ("n2", "mechanism"), ("n3", "state"),
    ("n4", "method"), ("n5", "resource"), ("n6", "agent"), ("n7", "evidence"),
]
T3_RELS = [
    ("r0", "n0", "causes", "n1"), ("r1", "n0", "causes", "n2"),
    ("r2", "n0", "causes", "n3"), ("r3", "n0", "causes", "n4"),
    ("r4", "n0", "causes", "n5"), ("r5", "n0", "causes", "n6"),
    ("r6", "n0", "causes", "n7"),
]
T4_NODES = [
    ("n0", "problem"), ("n1", "evidence"), ("n2", "evidence"), ("n3", "evidence"),
    ("n4", "method"), ("n5", "outcome"), ("n6", "constraint"), ("n7", "agent"),
]
T4_RELS = [
    ("r0", "n1", "supports", "n0"), ("r1", "n2", "supports", "n0"),
    ("r2", "n3", "supports", "n0"), ("r3", "n4", "supports", "n0"),
    ("r4", "n6", "constrains", "n4"), ("r5", "n7", "supports", "n4"),
    ("r6", "n4", "causes", "n5"), ("r7", "n1", "supports", "n4"),
]


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _thought(slug: str, nodes, rels, labels, caption, *, knowledge=None, extra_nodes=(), extra_rels=(), drop=(), atomic=None):
    knowledge = knowledge or {}
    atomic = atomic or {}
    drop = set(drop)
    node_specs = [x for x in list(nodes) + list(extra_nodes) if x[0] not in drop]
    rel_specs = [x for x in list(rels) + list(extra_rels) if x[1] not in drop and x[3] not in drop]
    payload = {
        "schema_version": "thought-dna/0.1",
        "thought_id": f"thought-{slug}",
        "source": {"text": caption, "sha256": _sha(caption)},
        "provenance": {"kind": "manual", "extractor": None, "human_id": BUILDER_ID},
        "nodes": [
            {
                "id": nid, "label": labels[nid], "role": role, "spans": [],
                "extract_conf": 1.0, "atomic": atomic.get(nid, True),
                "assertion": "asserted", "modality": "actual",
                **({"knowledge": knowledge[nid]} if nid in knowledge else {}),
            }
            for nid, role in node_specs
        ],
        "relations": [
            {
                "id": rid, "source": src, "target": tgt, "type": typ,
                "extract_conf": 1.0, "spans": [], "assertion": "asserted",
                "modality": "actual",
            }
            for rid, src, typ, tgt in rel_specs
        ],
    }
    return ThoughtGraph.from_dict(payload).to_dict()


def _session(slug, person, location, presentation, thought, *, consent=None, record_kind="synthetic", notes=""):
    share = {
        "share_enabled": True,
        "share_thought_dna": True,
        "share_coarse_location": True,
        "share_display_profile": True,
    }
    if consent:
        share.update(consent)
    return {
        "schema_version": CORPUS_SCHEMA_VERSION,
        "session_id": f"ses-{slug}",
        "person": {
            "person_id": f"person-{person[0]}",
            "display_label": person[1],
            "avatar_placeholder": person[0],
        },
        "consent": share,
        "location": {
            "kind": "synthetic_coarse",
            "region": location[0],
            "city": location[1],
            "lat": location[2],
            "lon": location[3],
            "precision": "city",
        },
        "presentation": {
            "domain": presentation[0],
            "topic": presentation[1],
            "cluster_id": presentation[2],
        },
        "record_provenance": {
            "record_kind": record_kind,
            "builder_id": BUILDER_ID,
            "notes": notes,
        },
        "thought_dna": thought,
    }


def _k_req(*ids):
    return {"about": [], "requires": [{"id": i, "conf": 1.0, "via": "seed"} for i in ids]}


def _k_about(*ids):
    return {"about": [{"id": i, "conf": 1.0, "via": "seed"} for i in ids], "requires": []}


def build_sessions() -> list[dict]:
    cool, stab = "local:demo:adaptive-cooling", "local:demo:stabilization"
    plasma_labels = {
        "n0": "plasma lens heat", "n1": "ionization cascade", "n2": "beam wander",
        "n3": "aperture budget", "n4": "adaptive cooling", "n5": "focal collapse",
        "n6": "interferometry", "n7": "coolant loop", "n8": "optics operator",
        "n9": "recombination loop",
    }
    plasma_know = {"n4": _k_req(cool), "n5": _k_req(stab)}
    t1 = [
        ("aria-plasma-lens", ("aria", "Aria K."), ("Pacific Northwest", "Portland", 45.5, -122.7),
         ("plasma-optics", "plasma lens thermal bloom", "accumulating-intermediary-failure"),
         _thought("aria-plasma-lens", T1_NODES, T1_RELS, plasma_labels, "Public caption: plasma-lens thermal bloom.", knowledge=plasma_know),
         {"record_kind": "manually_curated", "notes": "Flagship query. Requires cooling/stabilization knowledge."}),
        ("noah-org-overload", ("noah", "Noah R."), ("Central Europe", "Berlin", 52.5, 13.4),
         ("organizations", "inbox overload cascade", "accumulating-intermediary-failure"),
         _thought("noah-org-overload", T1_NODES, T1_RELS, {
             "n0": "inbox overload", "n1": "meeting cascade", "n2": "coordination lag",
             "n3": "headcount freeze", "n4": "delegation protocol", "n5": "delivery collapse",
             "n6": "cycle-time chart", "n7": "staffing buffer", "n8": "ops lead",
             "n9": "status-meeting loop",
         }, "Public caption: coordination collapse from information pile-up."),
         {"notes": "Cross-domain analog of the plasma-lens structure."}),
        ("mei-battery-heat", ("mei", "Mei L."), ("Texas", "Austin", 30.3, -97.7),
         ("energy-storage", "cell heat degradation", "accumulating-intermediary-failure"),
         _thought("mei-battery-heat", T1_NODES, T1_RELS, {
             "n0": "cell heat", "n1": "electrolyte breakdown", "n2": "rising resistance",
             "n3": "charge-rate cap", "n4": "thermal control", "n5": "capacity fade",
             "n6": "impedance log", "n7": "cooling plate", "n8": "pack controller",
             "n9": "side-reaction loop",
         }, "Public caption: battery heat to capacity fade."),
         {"notes": "Energy-domain analog."}),
        ("kwame-traffic", ("kwame", "Kwame A."), ("East Africa", "Nairobi", -1.3, 36.8),
         ("urban-mobility", "peak-hour spillback", "accumulating-intermediary-failure"),
         _thought("kwame-traffic", T1_NODES, T1_RELS, {
             "n0": "peak inflow", "n1": "spillback wave", "n2": "queue saturation",
             "n3": "green-time budget", "n4": "adaptive signal timing", "n5": "gridlock",
             "n6": "loop-detector counts", "n7": "offset plan", "n8": "traffic operator",
             "n9": "turn-pocket overflow",
         }, "Public caption: traffic spillback to gridlock."),
         {"notes": "Urban-mobility analog."}),
        ("gabe-warehouse", ("gabe", "Gabe S."), ("Great Lakes", "Chicago", 41.9, -87.6),
         ("logistics", "inbound staging pile-up", "accumulating-intermediary-failure"),
         _thought("gabe-warehouse", T1_NODES, T1_RELS, {
             "n0": "inbound surge", "n1": "staging pile-up", "n2": "dock congestion",
             "n3": "labor cap", "n4": "wave planning", "n5": "missed SLA",
             "n6": "scanner log", "n7": "overtime pool", "n8": "shift lead",
             "n9": "recirculation loop",
         }, "Public caption: warehouse inbound surge."),
         {"consent": {"share_coarse_location": False},
          "notes": "Discoverable analog; coarse location is stored but not shareable."}),
        ("ravi-irrigation", ("ravi", "Ravi P."), ("Indus basin", "Lahore", 31.5, 74.3),
         ("agriculture", "canal silt cascade", "accumulating-intermediary-failure"),
         _thought("ravi-irrigation", T1_NODES, T1_RELS, {
             "n0": "canal silt load", "n1": "sediment cascade", "n2": "channel shoaling",
             "n3": "irrigation quota", "n4": "flushing schedule", "n5": "crop failure",
             "n6": "depth gauge", "n7": "sluice reserve", "n8": "canal warden",
             "n9": "bank-collapse loop",
         }, "Public caption: irrigation silt (unshared)."),
         {"consent": {"share_enabled": False, "share_thought_dna": False,
                      "share_coarse_location": False, "share_display_profile": False},
          "notes": "Structural analog that must remain undiscoverable."}),
        ("sora-plasma-partial", ("sora", "Sora N."), ("Kansai", "Kyoto", 35.0, 135.8),
         ("plasma-optics", "partial plasma-lens chain", "accumulating-intermediary-failure"),
         _thought("sora-plasma-partial", T1_NODES, T1_RELS, plasma_labels,
                  "Public caption: partial plasma-lens observation.", drop=("n6", "n7")),
         {"notes": "Partial observation of the flagship structure."}),
        ("theo-plasma-granular", ("theo", "Theo M."), ("Pacific Northwest", "Seattle", 47.6, -122.3),
         ("plasma-optics", "transparent thermal mediator", "accumulating-intermediary-failure"),
         _thought("theo-plasma-granular", T1_NODES, [r for r in T1_RELS if r[0] != "r0"],
                  {**plasma_labels, "x0": "transparent thermal step"},
                  "Public caption: plasma-lens with one transparent step.",
                  extra_nodes=(("x0", "mechanism"),),
                  extra_rels=(("r0a", "n0", "causes", "x0"), ("r0b", "x0", "causes", "n1")),
                  atomic={"x0": False}),
         {"notes": "Transparent-granularity variant."}),
        ("sam-plasma-rewire", ("sam", "Sam D."), ("California", "San Diego", 32.7, -117.2),
         ("plasma-optics", "plasma words rewired", "same-words-wrong-structure"),
         _thought("sam-plasma-rewire", T1_NODES, [
             ("r0", "n0", "causes", "n5"), ("r1", "n1", "causes", "n2"),
             ("r2", "n2", "causes", "n1"), ("r3", "n3", "constrains", "n4"),
             ("r4", "n4", "prevents", "n5"), ("r5", "n4", "requires", "n7"),
             ("r6", "n6", "supports", "n4"), ("r7", "n9", "part_of", "n1"),
             ("r8", "n9", "causes", "n2"), ("r9", "n8", "supports", "n4"),
         ], plasma_labels, "Public caption: same plasma words, rewired causes."),
         {"notes": "Hard negative: same vocabulary, wrong structure."}),
        ("lea-plasma-polarity", ("lea", "Lea V."), ("Low Countries", "Ghent", 51.1, 3.7),
         ("plasma-optics", "causal inversion of heat cascade", "polarity-inversion"),
         _thought("lea-plasma-polarity", T1_NODES,
                  [("r0", "n0", "prevents", "n1")] + list(T1_RELS[1:]),
                  plasma_labels, "Public caption: polarity-flipped plasma cascade."),
         {"notes": "Hard negative: causes/prevents inversion."}),
    ]
    t2 = [
        ("priya-tracing", ("priya", "Priya S."), ("South India", "Bengaluru", 13.0, 77.6),
         ("reliability-engineering", "blind production incidents", "method-resource-hub"),
         _thought("priya-tracing", T2_NODES, T2_RELS, {
             "n0": "blind production incidents", "n1": "distributed tracing",
             "n2": "span store", "n3": "p99 dashboard", "n4": "cardinality budget",
             "n5": "mttr drop", "n6": "sre oncall", "n7": "error budget burn",
         }, "Public caption: tracing as the missing reliability method."),
         {"notes": "Cluster B seed (observability)."}),
        ("jonas-diagnostics", ("jonas", "Jonas H."), ("Nordics", "Stockholm", 59.3, 18.1),
         ("clinical-diagnostics", "undiagnosed inflammatory fever", "method-resource-hub"),
         _thought("jonas-diagnostics", T2_NODES, T2_RELS, {
             "n0": "undiagnosed fever", "n1": "panel sequencing", "n2": "biobank",
             "n3": "pathology slide", "n4": "sample volume cap", "n5": "treatment lock",
             "n6": "clinician", "n7": "inflammatory state",
         }, "Public caption: diagnostic panel as the missing method."),
         {"notes": "Medicine-domain analog of the method-resource hub."}),
        ("lina-scaffold", ("lina", "Lina F."), ("Iberia", "Lisbon", 38.7, -9.1),
         ("education", "missing prerequisite module", "method-resource-hub"),
         _thought("lina-scaffold", T2_NODES, T2_RELS, {
             "n0": "missing prerequisite", "n1": "scaffolded studio", "n2": "worked examples",
             "n3": "mastery quiz", "n4": "contact-hour cap", "n5": "course completion",
             "n6": "instructor", "n7": "confidence gap",
         }, "Public caption: scaffolding as the missing teaching method."),
         {"notes": "Education-domain analog of the method-resource hub."}),
        ("nico-tracing-private", ("nico", "Nico B."), ("Andes", "Bogota", 4.7, -74.1),
         ("reliability-engineering", "private tracing notes", "method-resource-hub"),
         _thought("nico-tracing-private", T2_NODES, T2_RELS, {
             "n0": "silent customer regressions", "n1": "request tracing",
             "n2": "trace warehouse", "n3": "slo burn chart", "n4": "ingest cap",
             "n5": "faster recovery", "n6": "platform engineer", "n7": "error-budget debt",
         }, "Public caption: unshared tracing analog."),
         {"consent": {"share_enabled": True, "share_thought_dna": False},
          "notes": "Share enabled but Thought DNA not shared — not discoverable."}),
    ]
    t4 = [
        ("omar-chronology", ("omar", "Omar Y."), ("Nile", "Cairo", 30.0, 31.2),
         ("archaeology", "uncertain occupation date", "evidence-corroboration"),
         _thought("omar-chronology", T4_NODES, T4_RELS, {
             "n0": "uncertain site date", "n1": "ceramic sherd", "n2": "charcoal sample",
             "n3": "typology chart", "n4": "bayesian chronology", "n5": "occupation phase",
             "n6": "field season cap", "n7": "field lead",
         }, "Public caption: corroborating dates from mixed evidence."),
         {"notes": "Cluster C seed (archaeology)."}),
        ("elena-litigation", ("elena", "Elena M."), ("Iberia", "Madrid", 40.4, -3.7),
         ("law", "disputed timeline", "evidence-corroboration"),
         _thought("elena-litigation", T4_NODES, T4_RELS, {
             "n0": "disputed claim", "n1": "witness statement", "n2": "bank record",
             "n3": "call record", "n4": "timeline reconstruction", "n5": "verdict",
             "n6": "disclosure deadline", "n7": "counsel",
         }, "Public caption: legal timeline from mixed records."),
         {"notes": "Law-domain analog of evidence corroboration."}),
        ("wei-climate", ("wei", "Wei C."), ("Pacific Canada", "Vancouver", 49.3, -123.1),
         ("climate-science", "event attribution", "evidence-corroboration"),
         _thought("wei-climate", T4_NODES, T4_RELS, {
             "n0": "disputed storm cause", "n1": "reanalysis field", "n2": "station record",
             "n3": "satellite plume", "n4": "attribution ensemble", "n5": "likelihood statement",
             "n6": "compute budget", "n7": "climate scientist",
         }, "Public caption: climate attribution from mixed observations."),
         {"notes": "Climate-domain analog of evidence corroboration."}),
    ]
    complementary = [
        ("diego-chiller", ("diego", "Diego R."), ("North Atlantic", "Reykjavik", 64.1, -21.9),
         ("thermal-engineering", "closed-loop chiller design", "complementary-bridge"),
         _thought("diego-chiller", T1_NODES, T1_RELS, {
             "n0": "thermal-budget gap", "n1": "heat-path analysis", "n2": "hot-spot map",
             "n3": "lab time limit", "n4": "closed-loop chiller design", "n5": "run abort",
             "n6": "thermocouple log", "n7": "chiller capacity", "n8": "thermal engineer",
             "n9": "pump-cavitation loop",
         }, "Public caption: chiller design that fills a cooling knowledge gap.",
            knowledge={"n0": _k_about(cool), "n4": _k_req(cool), "n5": _k_req(stab)}),
         {"notes": "Complementary: about adaptive-cooling, which the flagship requires."}),
        ("yuki-stabilization", ("yuki", "Yuki T."), ("Kanto", "Tsukuba", 36.1, 140.1),
         ("beam-control", "wavefront stabilization", "complementary-bridge"),
         _thought("yuki-stabilization", T1_NODES, T1_RELS, {
             "n0": "wavefront jitter", "n1": "sensor lag", "n2": "pointing wander",
             "n3": "actuator stroke limit", "n4": "adaptive-optics loop", "n5": "lock loss",
             "n6": "hartmann spots", "n7": "deformable mirror", "n8": "ao operator",
             "n9": "vibration path",
         }, "Public caption: stabilization method that fills the flagship knowledge gap.",
            knowledge={"n0": _k_about(stab), "n4": _k_req(cool), "n5": _k_req(stab)}),
         {"notes": "Complementary: about stabilization, which the flagship requires."}),
    ]
    distractors = [
        ("camille-portrait", ("camille", "Camille B."), ("Île-de-France", "Paris", 48.9, 2.3),
         ("photography", "portrait lens choice", "unrelated-distractor"),
         _thought("camille-portrait", T3_NODES, T3_RELS, {
             "n0": "contest win", "n1": "soft portrait light", "n2": "bokeh preference",
             "n3": "shallow focus", "n4": "prime lens choice", "n5": "studio strobe",
             "n6": "photographer", "n7": "histogram check",
         }, "Public caption: photography lens choice (vocabulary trap)."),
         {"notes": "Same-word 'lens' distractor with star topology."}),
        ("marc-sourdough", ("marc", "Marc P."), ("Auvergne-Rhône-Alpes", "Lyon", 45.8, 4.8),
         ("baking", "gluten development", "unrelated-distractor"),
         _thought("marc-sourdough", T3_NODES, T3_RELS, {
             "n0": "open crumb", "n1": "weak gluten", "n2": "short knead",
             "n3": "slack dough", "n4": "stretch and fold", "n5": "bench flour",
             "n6": "baker", "n7": "windowpane test",
         }, "Public caption: sourdough gluten development."),
         {"notes": "Unrelated distractor."}),
        ("nina-alpine", ("nina", "Nina G."), ("Alps", "Zermatt", 46.0, 7.7),
         ("mountaineering", "ridge-route choice", "unrelated-distractor"),
         _thought("nina-alpine", T3_NODES, T3_RELS, {
             "n0": "summit day", "n1": "weather window", "n2": "cornice risk",
             "n3": "fatigue state", "n4": "early start", "n5": "rope kit",
             "n6": "guide", "n7": "forecast note",
         }, "Public caption: alpine ridge planning."),
         {"notes": "Unrelated distractor."}),
        ("franz-counterpoint", ("franz", "Franz W."), ("Vienna Basin", "Vienna", 48.2, 16.4),
         ("music-theory", "species counterpoint", "unrelated-distractor"),
         _thought("franz-counterpoint", T3_NODES, T3_RELS, {
             "n0": "jury pass", "n1": "parallel fifths", "n2": "voice crossing",
             "n3": "dissonance stress", "n4": "species drill", "n5": "cantus firmus",
             "n6": "composition tutor", "n7": "exercise book",
         }, "Public caption: counterpoint exercise."),
         {"notes": "Unrelated distractor."}),
        ("dev-tax", ("dev", "Dev K."), ("Malay Peninsula", "Singapore", 1.4, 103.8),
         ("tax-administration", "year-end filing pack", "unrelated-distractor"),
         _thought("dev-tax", T3_NODES, T3_RELS, {
             "n0": "on-time filing", "n1": "missing receipt", "n2": "basis mismatch",
             "n3": "deadline pressure", "n4": "checklist pass", "n5": "ledger export",
             "n6": "preparer", "n7": "prior-year return",
         }, "Public caption: year-end tax pack."),
         {"notes": "Unrelated distractor."}),
        ("luz-tomato", ("luz", "Luz H."), ("Oaxaca", "Oaxaca", 17.1, -96.7),
         ("horticulture", "tomato blight watch", "unrelated-distractor"),
         _thought("luz-tomato", T3_NODES, T3_RELS, {
             "n0": "harvest saved", "n1": "leaf spotting", "n2": "humid nights",
             "n3": "wilting state", "n4": "spacing and prune", "n5": "seed stock",
             "n6": "grower", "n7": "field note",
         }, "Public caption: tomato blight watch."),
         {"notes": "Unrelated distractor."}),
    ]
    sessions = []
    for group in (t1, t2, t4, complementary, distractors):
        for slug, person, location, presentation, thought, extra in group:
            sessions.append(_session(
                slug, person, location, presentation, thought,
                consent=extra.get("consent"),
                record_kind=extra.get("record_kind", "synthetic"),
                notes=extra.get("notes", ""),
            ))
    sessions.sort(key=lambda s: s["session_id"])
    validate_corpus(sessions)
    return sessions


def write_artifacts(sessions: list[dict] | None = None) -> dict:
    sessions = sessions or build_sessions()
    lines = [json.dumps(s, ensure_ascii=False, sort_keys=True, separators=(",", ":")) for s in sessions]
    blob = "\n".join(lines) + "\n"
    sessions_path = PACKAGE_DIR / "sessions.jsonl"
    sessions_path.write_text(blob, encoding="utf-8")
    sessions_sha = hashlib.sha256(blob.encode("utf-8")).hexdigest()
    thought_hashes = {s["session_id"]: canonical_sha256(s["thought_dna"]) for s in sessions}
    discoverable = [s["session_id"] for s in sessions if s["consent"]["share_enabled"] and s["consent"]["share_thought_dna"]]
    clusters: dict[str, list[str]] = {}
    for s in sessions:
        clusters.setdefault(s["presentation"]["cluster_id"], []).append(s["session_id"])
    v01 = REPO / "benchmark" / "r0-v0.1" / "manifest.sha256"
    live_v01 = v01.read_text(encoding="utf-8").strip()
    if live_v01 != V01_MANIFEST_SHA:
        raise RuntimeError(f"frozen v0.1 manifest hash changed: {live_v01}")
    manifest = {
        "corpus_id": "resonance-demo-corpus/0.1",
        "schema_version": CORPUS_SCHEMA_VERSION,
        "builder_id": BUILDER_ID,
        "session_count": len(sessions),
        "discoverable_count": len(discoverable),
        "flagship_query_session_id": "ses-aria-plasma-lens",
        "sessions_sha256": sessions_sha,
        "thought_hashes": dict(sorted(thought_hashes.items())),
        "clusters": {k: sorted(v) for k, v in sorted(clusters.items())},
        "hidden_session_ids": sorted(s["session_id"] for s in sessions if s["session_id"] not in discoverable),
        "frozen_v0_1_manifest_sha256": live_v01,
        "matching_rule": "Thought DNA only; presentation/location/topic never enter the engine",
    }
    manifest_text = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    (PACKAGE_DIR / "manifest.json").write_text(manifest_text, encoding="utf-8")
    (PACKAGE_DIR / "manifest.sha256").write_text(
        hashlib.sha256(manifest_text.encode("utf-8")).hexdigest() + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    manifest = write_artifacts()
    print(f"wrote {manifest['session_count']} sessions sha256={manifest['sessions_sha256']}")


if __name__ == "__main__":
    main()
