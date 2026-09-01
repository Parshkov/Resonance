"""Python validator for resonance-demo-corpus/0.1 sessions.

JSON Schema is the portable shape. This module additionally enforces
cross-field invariants JSON Schema does not conveniently capture: unique IDs,
Thought DNA validity, consent/location coarseness, and the ban on contact or
precise-location fields.
"""

from __future__ import annotations

import math
import re
from typing import Any, Mapping

from src.graph import ThoughtDNAValidationError, validate_thought

CORPUS_SCHEMA_VERSION = "resonance-demo-corpus/0.1"
SESSION_ID_RE = re.compile(r"^ses-[a-z0-9-]+$")
PERSON_ID_RE = re.compile(r"^person-[a-z0-9-]+$")
EMAIL_RE = re.compile(r"[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}", re.I)
PHONE_RE = re.compile(r"(?:\+|tel:)\d[\d\-\s().]{6,}\d")
SKIP_CONTACT_SCAN_KEYS = frozenset({"sha256", "thought_dna", "lat", "lon"})
CONTACT_KEYS = frozenset({
    "email", "phone", "telephone", "address", "street", "geo_hash",
    "contact", "handle", "real_name",
})
SESSION_KEYS = frozenset({
    "schema_version", "session_id", "person", "consent", "location",
    "presentation", "record_provenance", "thought_dna",
})
PERSON_KEYS = frozenset({"person_id", "display_label", "avatar_placeholder"})
CONSENT_KEYS = frozenset({
    "share_enabled", "share_thought_dna", "share_coarse_location",
    "share_display_profile",
})
LOCATION_KEYS = frozenset({"kind", "region", "city", "lat", "lon", "precision"})
PRESENTATION_KEYS = frozenset({"domain", "topic", "cluster_id"})
PROVENANCE_KEYS = frozenset({"record_kind", "builder_id", "notes"})
RECORD_KINDS = frozenset({"synthetic", "volunteer", "manually_curated"})


class CorpusValidationError(ValueError):
    def __init__(self, issues: list[str]):
        self.issues = tuple(issues)
        super().__init__("demo corpus validation failed:\n" + "\n".join(f"- {x}" for x in issues))


def _issue(issues: list[str], path: str, message: str) -> None:
    issues.append(f"{path}: {message}")


def _require_keys(value: Mapping[str, Any], allowed: frozenset[str], required: frozenset[str], path: str, issues: list[str]) -> None:
    if not isinstance(value, Mapping):
        _issue(issues, path, "must be an object")
        return
    for key in sorted(set(value) - set(allowed)):
        _issue(issues, f"{path}.{key}", "unknown field")
    for key in sorted(required - set(value)):
        _issue(issues, f"{path}.{key}", "is required")


def _scan_contact(value: Any, path: str, issues: list[str]) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            lowered = str(key).lower()
            if lowered in CONTACT_KEYS:
                _issue(issues, f"{path}.{key}", "contact/precise-identity fields are forbidden")
            if lowered in SKIP_CONTACT_SCAN_KEYS:
                continue
            _scan_contact(child, f"{path}.{key}", issues)
    elif isinstance(value, list):
        for i, child in enumerate(value):
            _scan_contact(child, f"{path}[{i}]", issues)
    elif isinstance(value, str):
        if EMAIL_RE.search(value):
            _issue(issues, path, "looks like an email address")
        if PHONE_RE.search(value):
            _issue(issues, path, "looks like a telephone number")


def _coarse_coordinate(value: Any, path: str, issues: list[str], *, lo: float, hi: float) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        _issue(issues, path, "must be a finite number")
        return
    number = float(value)
    if number < lo or number > hi:
        _issue(issues, path, f"must be in [{lo}, {hi}]")
        return
    # City-level coarseness: one decimal degree (~11 km), never a precise pin.
    if round(number, 1) != number:
        _issue(issues, path, "must be rounded to 0.1 degree (city-level, not a precise pin)")


def validate_session(session: Mapping[str, Any], *, issues: list[str] | None = None) -> list[str]:
    own = issues is None
    issues = [] if issues is None else issues
    _require_keys(session, SESSION_KEYS, SESSION_KEYS, "$", issues)
    if not isinstance(session, Mapping):
        return issues
    if session.get("schema_version") != CORPUS_SCHEMA_VERSION:
        _issue(issues, "$.schema_version", f"must be {CORPUS_SCHEMA_VERSION}")
    sid = session.get("session_id")
    if not isinstance(sid, str) or not SESSION_ID_RE.match(sid):
        _issue(issues, "$.session_id", "must match ses-[a-z0-9-]+")

    person = session.get("person")
    if isinstance(person, Mapping):
        _require_keys(person, PERSON_KEYS, PERSON_KEYS, "$.person", issues)
        pid = person.get("person_id")
        if not isinstance(pid, str) or not PERSON_ID_RE.match(pid):
            _issue(issues, "$.person.person_id", "must match person-[a-z0-9-]+")
        for field in ("display_label", "avatar_placeholder"):
            if not isinstance(person.get(field), str) or not person.get(field):
                _issue(issues, f"$.person.{field}", "must be a non-empty string")

    consent = session.get("consent")
    if isinstance(consent, Mapping):
        _require_keys(consent, CONSENT_KEYS, CONSENT_KEYS, "$.consent", issues)
        for field in CONSENT_KEYS:
            if not isinstance(consent.get(field), bool):
                _issue(issues, f"$.consent.{field}", "must be a boolean")

    location = session.get("location")
    if isinstance(location, Mapping):
        _require_keys(location, LOCATION_KEYS, LOCATION_KEYS, "$.location", issues)
        if location.get("kind") != "synthetic_coarse":
            _issue(issues, "$.location.kind", "must be synthetic_coarse")
        if location.get("precision") != "city":
            _issue(issues, "$.location.precision", "must be city")
        for field in ("region", "city"):
            if not isinstance(location.get(field), str) or not location.get(field):
                _issue(issues, f"$.location.{field}", "must be a non-empty string")
        _coarse_coordinate(location.get("lat"), "$.location.lat", issues, lo=-90.0, hi=90.0)
        _coarse_coordinate(location.get("lon"), "$.location.lon", issues, lo=-180.0, hi=180.0)

    presentation = session.get("presentation")
    if isinstance(presentation, Mapping):
        _require_keys(presentation, PRESENTATION_KEYS, PRESENTATION_KEYS, "$.presentation", issues)
        for field in PRESENTATION_KEYS:
            if not isinstance(presentation.get(field), str) or not presentation.get(field):
                _issue(issues, f"$.presentation.{field}", "must be a non-empty string")

    provenance = session.get("record_provenance")
    if isinstance(provenance, Mapping):
        _require_keys(provenance, PROVENANCE_KEYS, PROVENANCE_KEYS, "$.record_provenance", issues)
        if provenance.get("record_kind") not in RECORD_KINDS:
            _issue(issues, "$.record_provenance.record_kind", f"must be one of {sorted(RECORD_KINDS)}")
        if not isinstance(provenance.get("builder_id"), str) or not provenance.get("builder_id"):
            _issue(issues, "$.record_provenance.builder_id", "must be a non-empty string")
        if not isinstance(provenance.get("notes"), str):
            _issue(issues, "$.record_provenance.notes", "must be a string")

    thought = session.get("thought_dna")
    if isinstance(thought, Mapping):
        try:
            validate_thought(thought)
        except ThoughtDNAValidationError as exc:
            for item in exc.issues:
                _issue(issues, f"$.thought_dna{item.path[1:] if item.path.startswith('$') else '.' + item.path}", item.message)
        thought_id = thought.get("thought_id")
        if isinstance(sid, str) and isinstance(thought_id, str):
            expected = "thought-" + sid[len("ses-"):] if sid.startswith("ses-") else None
            if expected and thought_id != expected:
                _issue(issues, "$.thought_dna.thought_id", f"must equal {expected!r} (stable pairing with session_id)")
        if thought.get("provenance", {}).get("kind") != "manual":
            _issue(issues, "$.thought_dna.provenance.kind", "demo corpus seeds are manual Thought DNA")
        leaked = {"domain", "topic", "cluster_id", "city", "lat", "lon", "person_id", "session_id"}
        extra = leaked & set(thought)
        if extra:
            _issue(issues, "$.thought_dna", f"presentation metadata leaked into Thought DNA: {sorted(extra)}")
    else:
        _issue(issues, "$.thought_dna", "must be a Thought DNA object")

    _scan_contact(session, "$", issues)
    if own and issues:
        raise CorpusValidationError(issues)
    return issues


def validate_corpus(sessions: list[Mapping[str, Any]]) -> None:
    issues: list[str] = []
    if not isinstance(sessions, list) or not sessions:
        raise CorpusValidationError(["$: corpus must be a non-empty list of sessions"])
    if not (20 <= len(sessions) <= 50):
        issues.append(f"$: session count {len(sessions)} is outside the 20–50 demo window")
    seen_sessions: set[str] = set()
    seen_thoughts: set[str] = set()
    seen_people: set[str] = set()
    for i, session in enumerate(sessions):
        validate_session(session, issues=issues)
        sid = session.get("session_id") if isinstance(session, Mapping) else None
        if isinstance(sid, str):
            if sid in seen_sessions:
                issues.append(f"$[{i}].session_id: duplicate {sid}")
            seen_sessions.add(sid)
        if isinstance(session, Mapping):
            thought_id = session.get("thought_dna", {}).get("thought_id") if isinstance(session.get("thought_dna"), Mapping) else None
            if isinstance(thought_id, str):
                if thought_id in seen_thoughts:
                    issues.append(f"$[{i}].thought_dna.thought_id: duplicate {thought_id}")
                seen_thoughts.add(thought_id)
            pid = session.get("person", {}).get("person_id") if isinstance(session.get("person"), Mapping) else None
            if isinstance(pid, str):
                seen_people.add(pid)
    if len(seen_people) < 8:
        issues.append(f"$: expected several distinct people; found {len(seen_people)}")
    if issues:
        raise CorpusValidationError(issues)
