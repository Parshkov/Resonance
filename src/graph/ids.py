"""Deterministic helper IDs for Thought DNA authors.

IDs are never silently rewritten by the parser. These helpers are optional for
writers that need reproducible local identifiers.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping

from .versioning import SCHEMA_VERSION


def _digest(prefix: str, payload: object) -> str:
    raw = json.dumps(
        {"id_algorithm": "thought-dna-id/0.1", "schema": SCHEMA_VERSION, "payload": payload},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"{prefix}_{hashlib.sha256(raw).hexdigest()[:20]}"


def make_thought_id(source_text: str, *, namespace: str = "") -> str:
    if not isinstance(source_text, str):
        raise TypeError("source_text must be str")
    return _digest("t", {"namespace": namespace, "source_sha256": hashlib.sha256(source_text.encode("utf-8")).hexdigest()})


def _span_key(spans: Iterable[Mapping[str, object]]) -> list[dict[str, object]]:
    out = []
    for span in spans:
        out.append({"start": span["start"], "end": span["end"], "text": span["text"]})
    return sorted(out, key=lambda x: (x["start"], x["end"], x["text"]))


def make_node_id(
    role: str,
    *,
    spans: Iterable[Mapping[str, object]] = (),
    manual_key: str | None = None,
    namespace: str = "",
) -> str:
    """Create a stable node ID from grounding, not display-label wording.

    Extracted nodes should use exact source spans. Manual nodes, which may have
    no spans, must provide a stable caller-owned ``manual_key``.
    """
    span_key = _span_key(spans)
    if not span_key and not manual_key:
        raise ValueError("manual/unspanned node IDs require manual_key")
    return _digest(
        "n",
        {"namespace": namespace, "role": role, "spans": span_key, "manual_key": manual_key},
    )


def make_relation_id(
    source: str,
    target: str,
    relation_type: str,
    *,
    spans: Iterable[Mapping[str, object]] = (),
    assertion: str = "asserted",
    modality: str = "actual",
    manual_key: str | None = None,
    namespace: str = "",
) -> str:
    """Create a stable relation/proposition ID.

    Direction, type, assertion and modality are intentionally part of identity,
    so polarity/direction changes cannot silently reuse an ID.
    """
    span_key = _span_key(spans)
    if not span_key and not manual_key:
        raise ValueError("manual/unspanned relation IDs require manual_key")
    return _digest(
        "r",
        {
            "namespace": namespace,
            "source": source,
            "target": target,
            "type": relation_type,
            "assertion": assertion,
            "modality": modality,
            "spans": span_key,
            "manual_key": manual_key,
        },
    )
