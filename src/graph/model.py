"""Typed immutable Python model for Thought DNA v0.1."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from .canonical import canonical_dict
from .validation import validate_thought
from .versioning import SCHEMA_VERSION


@dataclass(frozen=True, slots=True)
class Span:
    start: int
    end: int
    text: str

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Span":
        return cls(int(data["start"]), int(data["end"]), str(data["text"]))

    def to_dict(self) -> dict[str, Any]:
        return {"start": self.start, "end": self.end, "text": self.text}


@dataclass(frozen=True, slots=True)
class KnowledgeRef:
    id: str
    conf: float
    via: str | None = None

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "KnowledgeRef":
        return cls(str(data["id"]), float(data["conf"]), data.get("via"))

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"id": self.id, "conf": self.conf}
        if self.via is not None:
            out["via"] = self.via
        return out


@dataclass(frozen=True, slots=True)
class Knowledge:
    about: tuple[KnowledgeRef, ...] = ()
    requires: tuple[KnowledgeRef, ...] = ()

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Knowledge":
        return cls(
            tuple(KnowledgeRef.from_dict(x) for x in data.get("about", [])),
            tuple(KnowledgeRef.from_dict(x) for x in data.get("requires", [])),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "about": [x.to_dict() for x in self.about],
            "requires": [x.to_dict() for x in self.requires],
        }


@dataclass(frozen=True, slots=True)
class Node:
    id: str
    label: str
    role: str
    spans: tuple[Span, ...]
    extract_conf: float
    atomic: bool
    assertion: str = "asserted"
    modality: str = "actual"
    knowledge: Knowledge | None = None

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Node":
        return cls(
            id=str(data["id"]),
            label=str(data["label"]),
            role=str(data["role"]),
            spans=tuple(Span.from_dict(x) for x in data.get("spans", [])),
            extract_conf=float(data["extract_conf"]),
            atomic=bool(data["atomic"]),
            assertion=str(data.get("assertion", "asserted")),
            modality=str(data.get("modality", "actual")),
            knowledge=Knowledge.from_dict(data["knowledge"]) if data.get("knowledge") is not None else None,
        )

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "id": self.id,
            "label": self.label,
            "role": self.role,
            "spans": [x.to_dict() for x in self.spans],
            "extract_conf": self.extract_conf,
            "atomic": self.atomic,
            "assertion": self.assertion,
            "modality": self.modality,
        }
        if self.knowledge is not None:
            out["knowledge"] = self.knowledge.to_dict()
        return out


@dataclass(frozen=True, slots=True)
class Relation:
    id: str
    source: str
    target: str
    type: str
    extract_conf: float
    spans: tuple[Span, ...]
    assertion: str = "asserted"
    modality: str = "actual"
    cue: Span | None = None
    provenance_refs: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Relation":
        return cls(
            id=str(data["id"]),
            source=str(data["source"]),
            target=str(data["target"]),
            type=str(data["type"]),
            extract_conf=float(data["extract_conf"]),
            spans=tuple(Span.from_dict(x) for x in data.get("spans", [])),
            assertion=str(data.get("assertion", "asserted")),
            modality=str(data.get("modality", "actual")),
            cue=Span.from_dict(data["cue"]) if data.get("cue") is not None else None,
            provenance_refs=tuple(str(x) for x in data.get("provenance_refs", [])),
        )

    @property
    def polarity(self) -> str:
        """A convenience view; polarity stays encoded in canonical type/assertion."""
        if self.assertion == "negated" or self.type in {"prevents", "contradicts"}:
            return "negative"
        return "positive"

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "id": self.id,
            "source": self.source,
            "target": self.target,
            "type": self.type,
            "extract_conf": self.extract_conf,
            "spans": [x.to_dict() for x in self.spans],
            "assertion": self.assertion,
            "modality": self.modality,
        }
        if self.cue is not None:
            out["cue"] = self.cue.to_dict()
        if self.provenance_refs:
            out["provenance_refs"] = list(self.provenance_refs)
        return out


@dataclass(frozen=True, slots=True)
class Source:
    text: str
    sha256: str

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Source":
        return cls(str(data["text"]), str(data["sha256"]))

    def to_dict(self) -> dict[str, Any]:
        return {"text": self.text, "sha256": self.sha256}


@dataclass(frozen=True, slots=True)
class Provenance:
    kind: str
    extractor: Mapping[str, str] | None = None
    human_id: str | None = None

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Provenance":
        extractor = data.get("extractor")
        frozen_extractor = None if extractor is None else {
            "id": str(extractor["id"]),
            "version": str(extractor["version"]),
        }
        return cls(str(data["kind"]), frozen_extractor, data.get("human_id"))

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"kind": self.kind, "extractor": None if self.extractor is None else dict(self.extractor)}
        if self.human_id is not None:
            out["human_id"] = self.human_id
        return out


@dataclass(frozen=True, slots=True)
class ThoughtGraph:
    thought_id: str
    source: Source
    provenance: Provenance
    nodes: tuple[Node, ...] = field(default_factory=tuple)
    relations: tuple[Relation, ...] = field(default_factory=tuple)
    schema_version: str = SCHEMA_VERSION

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], *, validate: bool = True) -> "ThoughtGraph":
        normalized = canonical_dict(data, validate=validate)
        return cls(
            thought_id=str(normalized["thought_id"]),
            source=Source.from_dict(normalized["source"]),
            provenance=Provenance.from_dict(normalized["provenance"]),
            nodes=tuple(Node.from_dict(x) for x in normalized["nodes"]),
            relations=tuple(Relation.from_dict(x) for x in normalized["relations"]),
            schema_version=str(normalized["schema_version"]),
        )

    def to_dict(self, *, validate: bool = True) -> dict[str, Any]:
        raw = {
            "schema_version": self.schema_version,
            "thought_id": self.thought_id,
            "source": self.source.to_dict(),
            "provenance": self.provenance.to_dict(),
            "nodes": [x.to_dict() for x in self.nodes],
            "relations": [x.to_dict() for x in self.relations],
        }
        return canonical_dict(raw, validate=validate)

    def validate(self) -> None:
        validate_thought(self.to_dict(validate=False))
