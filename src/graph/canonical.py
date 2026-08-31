"""Canonical Thought DNA serialization."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from .validation import validate_thought


def _sort_spans(spans: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(spans, key=lambda s: (s["start"], s["end"], s["text"]))


def _normalize_knowledge(value: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for bucket in ("about", "requires"):
        refs = value.get(bucket, [])
        out[bucket] = sorted(
            (dict(ref) for ref in refs),
            key=lambda ref: (ref["id"], ref["conf"], ref.get("via", "")),
        )
    return out


def canonical_dict(data: Mapping[str, Any], *, validate: bool = True) -> dict[str, Any]:
    """Return the semantic canonical form without mutating the input.

    Defaults for assertion/modality are materialized so they cannot disappear
    during a parse/serialize cycle. Semantically unordered collections are
    sorted. Labels and asserted graph content are never rewritten or inferred.
    """
    if validate:
        validate_thought(data)
    out = deepcopy(dict(data))

    nodes = []
    for node in out.get("nodes", []):
        n = dict(node)
        n["assertion"] = n.get("assertion", "asserted")
        n["modality"] = n.get("modality", "actual")
        n["spans"] = _sort_spans(list(n.get("spans", [])))
        if "knowledge" in n and n["knowledge"] is not None:
            n["knowledge"] = _normalize_knowledge(dict(n["knowledge"]))
        nodes.append(n)
    out["nodes"] = sorted(nodes, key=lambda n: n["id"])

    relations = []
    for rel in out.get("relations", []):
        r = dict(rel)
        r["assertion"] = r.get("assertion", "asserted")
        r["modality"] = r.get("modality", "actual")
        r["spans"] = _sort_spans(list(r.get("spans", [])))
        if "provenance_refs" in r:
            r["provenance_refs"] = sorted(r["provenance_refs"])
        relations.append(r)
    out["relations"] = sorted(relations, key=lambda r: r["id"])
    return out


def canonical_json(data: Mapping[str, Any], *, validate: bool = True) -> str:
    return json.dumps(
        canonical_dict(data, validate=validate),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def canonical_sha256(data: Mapping[str, Any], *, validate: bool = True) -> str:
    return hashlib.sha256(canonical_json(data, validate=validate).encode("utf-8")).hexdigest()
