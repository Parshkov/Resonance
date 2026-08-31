"""Semantic validation for executable Thought DNA v0.1."""

from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass
from typing import Any, Mapping

from .versioning import MigrationRequired, ensure_supported_version

NODE_ROLES = frozenset(
    {"problem", "mechanism", "state", "outcome", "constraint", "method", "evidence", "resource", "agent"}
)
RELATION_TYPES = frozenset(
    {"causes", "prevents", "requires", "part_of", "constrains", "supports", "contradicts"}
)
ASSERTIONS = frozenset({"asserted", "negated"})
MODALITIES = frozenset({"actual", "possible", "conditional"})
PROVENANCE_KINDS = frozenset({"extracted", "manual"})
CONCEPT_RE = re.compile(r"^(wd|openalex|acmccs|local):[^\s:][^\s]*$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    path: str
    message: str

    def __str__(self) -> str:
        return f"{self.path}: {self.message}"


class ThoughtDNAValidationError(ValueError):
    def __init__(self, issues: list[ValidationIssue]):
        self.issues = tuple(issues)
        super().__init__("Thought DNA validation failed:\n" + "\n".join(f"- {x}" for x in issues))


def _issue(issues: list[ValidationIssue], path: str, message: str) -> None:
    issues.append(ValidationIssue(path, message))


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _validate_span(span: Any, path: str, source_text: str, issues: list[ValidationIssue]) -> None:
    if not isinstance(span, Mapping):
        _issue(issues, path, "must be an object")
        return
    for field in ("start", "end", "text"):
        if field not in span:
            _issue(issues, f"{path}.{field}", "is required")
    if not isinstance(span.get("start"), int) or isinstance(span.get("start"), bool):
        _issue(issues, f"{path}.start", "must be an integer")
        return
    if not isinstance(span.get("end"), int) or isinstance(span.get("end"), bool):
        _issue(issues, f"{path}.end", "must be an integer")
        return
    start, end = span["start"], span["end"]
    if start < 0 or end < start or end > len(source_text):
        _issue(issues, path, f"range [{start},{end}) is outside source text of length {len(source_text)}")
        return
    if not isinstance(span.get("text"), str):
        _issue(issues, f"{path}.text", "must be a string")
    elif source_text[start:end] != span["text"]:
        _issue(issues, path, "text does not equal source.text[start:end]")


def _validate_conf(value: Any, path: str, issues: list[ValidationIssue], *, minimum: float = 0.0) -> None:
    if not _is_number(value):
        _issue(issues, path, "must be a finite number")
    elif not minimum <= float(value) <= 1.0:
        _issue(issues, path, f"must be in [{minimum},1]")


def _validate_knowledge(value: Any, path: str, issues: list[ValidationIssue]) -> None:
    if value is None:
        return
    if not isinstance(value, Mapping):
        _issue(issues, path, "must be an object")
        return
    unknown = set(value) - {"about", "requires"}
    for key in sorted(unknown):
        _issue(issues, f"{path}.{key}", "unknown knowledge field")
    for bucket in ("about", "requires"):
        refs = value.get(bucket, [])
        if not isinstance(refs, list):
            _issue(issues, f"{path}.{bucket}", "must be an array")
            continue
        if len(refs) > 8:
            _issue(issues, f"{path}.{bucket}", "must contain at most 8 references")
        seen: set[str] = set()
        for i, ref in enumerate(refs):
            rpath = f"{path}.{bucket}[{i}]"
            if not isinstance(ref, Mapping):
                _issue(issues, rpath, "must be an object")
                continue
            rid = ref.get("id")
            if not isinstance(rid, str) or not CONCEPT_RE.match(rid):
                _issue(issues, f"{rpath}.id", "must be a namespaced wd:/openalex:/acmccs:/local: identifier")
            elif rid in seen:
                _issue(issues, f"{rpath}.id", "duplicate identifier in knowledge bucket")
            else:
                seen.add(rid)
            _validate_conf(ref.get("conf"), f"{rpath}.conf", issues, minimum=0.5)
            if "via" in ref and not isinstance(ref["via"], str):
                _issue(issues, f"{rpath}.via", "must be a string")


def validate_thought(data: Mapping[str, Any], *, raise_on_error: bool = True) -> tuple[ValidationIssue, ...]:
    """Validate structural, grounding and provenance invariants.

    The JSON Schema captures the portable shape. This validator enforces the
    cross-field rules JSON Schema cannot express compactly: source hashes,
    exact spans, endpoint existence, uniqueness and manual/extracted grounding.
    """
    issues: list[ValidationIssue] = []
    if not isinstance(data, Mapping):
        issues.append(ValidationIssue("$", "must be an object"))
        if raise_on_error:
            raise ThoughtDNAValidationError(issues)
        return tuple(issues)

    try:
        ensure_supported_version(data.get("schema_version"))
    except MigrationRequired as exc:
        _issue(issues, "$.schema_version", str(exc))

    thought_id = data.get("thought_id")
    if not isinstance(thought_id, str) or not thought_id:
        _issue(issues, "$.thought_id", "must be a non-empty string")

    source = data.get("source")
    source_text = ""
    if not isinstance(source, Mapping):
        _issue(issues, "$.source", "must be an object")
    else:
        source_text = source.get("text", "")
        if not isinstance(source_text, str):
            _issue(issues, "$.source.text", "must be a string")
            source_text = ""
        sha = source.get("sha256")
        if not isinstance(sha, str) or not SHA256_RE.fullmatch(sha):
            _issue(issues, "$.source.sha256", "must be 64 lowercase hex characters")
        elif hashlib.sha256(source_text.encode("utf-8")).hexdigest() != sha:
            _issue(issues, "$.source.sha256", "does not match UTF-8 SHA-256 of source.text")

    provenance = data.get("provenance")
    kind = None
    if not isinstance(provenance, Mapping):
        _issue(issues, "$.provenance", "must be an object")
    else:
        kind = provenance.get("kind")
        if kind not in PROVENANCE_KINDS:
            _issue(issues, "$.provenance.kind", f"must be one of {sorted(PROVENANCE_KINDS)}")
        extractor = provenance.get("extractor", "__missing__")
        if kind == "extracted":
            if not isinstance(extractor, Mapping):
                _issue(issues, "$.provenance.extractor", "must be an object for extracted thoughts")
            else:
                if not isinstance(extractor.get("id"), str) or not extractor.get("id"):
                    _issue(issues, "$.provenance.extractor.id", "must be a non-empty string")
                if not isinstance(extractor.get("version"), str) or not extractor.get("version"):
                    _issue(issues, "$.provenance.extractor.version", "must be a non-empty string")
        elif kind == "manual":
            if extractor is not None:
                _issue(issues, "$.provenance.extractor", "must be null for manual thoughts")
        if "human_id" in provenance and provenance["human_id"] is not None and not isinstance(provenance["human_id"], str):
            _issue(issues, "$.provenance.human_id", "must be a string or null")

    nodes = data.get("nodes")
    node_ids: set[str] = set()
    if not isinstance(nodes, list):
        _issue(issues, "$.nodes", "must be an array")
        nodes = []
    for i, node in enumerate(nodes):
        path = f"$.nodes[{i}]"
        if not isinstance(node, Mapping):
            _issue(issues, path, "must be an object")
            continue
        nid = node.get("id")
        if not isinstance(nid, str) or not nid:
            _issue(issues, f"{path}.id", "must be a non-empty string")
        elif nid in node_ids:
            _issue(issues, f"{path}.id", "duplicate node id")
        else:
            node_ids.add(nid)
        if not isinstance(node.get("label"), str):
            _issue(issues, f"{path}.label", "must be a string")
        if node.get("role") not in NODE_ROLES:
            _issue(issues, f"{path}.role", f"must be one of {sorted(NODE_ROLES)}")
        _validate_conf(node.get("extract_conf"), f"{path}.extract_conf", issues)
        if not isinstance(node.get("atomic"), bool):
            _issue(issues, f"{path}.atomic", "must be boolean")
        if node.get("assertion", "asserted") not in ASSERTIONS:
            _issue(issues, f"{path}.assertion", f"must be one of {sorted(ASSERTIONS)}")
        if node.get("modality", "actual") not in MODALITIES:
            _issue(issues, f"{path}.modality", f"must be one of {sorted(MODALITIES)}")
        spans = node.get("spans")
        if not isinstance(spans, list):
            _issue(issues, f"{path}.spans", "must be an array")
            spans = []
        if kind == "extracted" and not spans:
            _issue(issues, f"{path}.spans", "must not be empty for extracted nodes")
        for j, span in enumerate(spans):
            _validate_span(span, f"{path}.spans[{j}]", source_text, issues)
        _validate_knowledge(node.get("knowledge"), f"{path}.knowledge", issues)

    relations = data.get("relations")
    relation_ids: set[str] = set()
    if not isinstance(relations, list):
        _issue(issues, "$.relations", "must be an array")
        relations = []
    for i, rel in enumerate(relations):
        path = f"$.relations[{i}]"
        if not isinstance(rel, Mapping):
            _issue(issues, path, "must be an object")
            continue
        rid = rel.get("id")
        if not isinstance(rid, str) or not rid:
            _issue(issues, f"{path}.id", "must be a non-empty string")
        elif rid in relation_ids:
            _issue(issues, f"{path}.id", "duplicate relation id")
        else:
            relation_ids.add(rid)
        src, dst = rel.get("source"), rel.get("target")
        if not isinstance(src, str) or src not in node_ids:
            _issue(issues, f"{path}.source", "must reference an existing node id")
        if not isinstance(dst, str) or dst not in node_ids:
            _issue(issues, f"{path}.target", "must reference an existing node id")
        if rel.get("type") not in RELATION_TYPES:
            _issue(issues, f"{path}.type", f"must be one of {sorted(RELATION_TYPES)}")
        _validate_conf(rel.get("extract_conf"), f"{path}.extract_conf", issues)
        if rel.get("assertion", "asserted") not in ASSERTIONS:
            _issue(issues, f"{path}.assertion", f"must be one of {sorted(ASSERTIONS)}")
        if rel.get("modality", "actual") not in MODALITIES:
            _issue(issues, f"{path}.modality", f"must be one of {sorted(MODALITIES)}")
        spans = rel.get("spans")
        if not isinstance(spans, list):
            _issue(issues, f"{path}.spans", "must be an array")
            spans = []
        if kind == "extracted" and not spans:
            _issue(issues, f"{path}.spans", "must not be empty for extracted relations")
        for j, span in enumerate(spans):
            _validate_span(span, f"{path}.spans[{j}]", source_text, issues)
        if "cue" in rel and rel["cue"] is not None:
            _validate_span(rel["cue"], f"{path}.cue", source_text, issues)

    if issues and raise_on_error:
        raise ThoughtDNAValidationError(issues)
    return tuple(issues)
