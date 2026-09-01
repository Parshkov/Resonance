"""The six required MCP tools (plus explicit snapshot persistence), each a
direct pass-through to the accepted EngineFacade. Handlers parse arguments,
call the facade, serialize the result -- nothing else (contract section 7)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from src.engine import ENGINE_VERSION, ResonanceEngine
from src.interfaces import INTERFACE_VERSION, RESONANCE_MODES
from . import wire

MCP_ADAPTER_VERSION = "resonance-mcp/0.1"

_MODE_SCHEMA = {"type": "string", "enum": list(RESONANCE_MODES)}
_THOUGHT_SCHEMA = {"type": "object", "description": "Thought DNA (thought-dna/0.1) document"}

TOOLS: list[dict[str, Any]] = [
    {"name": "ingest_thought",
     "description": "Extract a grounded Thought Graph from context text via the "
                    "accepted cue extractor (no LLM). Returns Thought DNA.",
     "inputSchema": {"type": "object", "required": ["context"],
                     "properties": {"context": {"type": "string"},
                                    "source_id": {"type": ["string", "null"]}},
                     "additionalProperties": False}},
    {"name": "index_thought",
     "description": "Validate and index a Thought DNA document (extracted or "
                    "manual; manual works without any LLM).",
     "inputSchema": {"type": "object", "required": ["thought"],
                     "properties": {"thought": _THOUGHT_SCHEMA},
                     "additionalProperties": False}},
    {"name": "find_resonance",
     "description": "Retrieve candidates for a Thought and verify each; returns "
                    "hits with mappings, score vectors, explanations, provenance "
                    "and version/config metadata.",
     "inputSchema": {"type": "object", "required": ["thought", "mode"],
                     "properties": {"thought": _THOUGHT_SCHEMA, "mode": _MODE_SCHEMA,
                                    "k": {"type": "integer", "minimum": 1, "default": 20}},
                     "additionalProperties": False}},
    {"name": "compare_thoughts",
     "description": "Verify two Thought DNA documents directly; returns the full "
                    "VerifierResult (score vector, mapping, contradictions, "
                    "explanation).",
     "inputSchema": {"type": "object", "required": ["a", "b", "mode"],
                     "properties": {"a": _THOUGHT_SCHEMA, "b": _THOUGHT_SCHEMA,
                                    "mode": _MODE_SCHEMA},
                     "additionalProperties": False}},
    {"name": "explain_resonance",
     "description": "Return the cached VerifierResult for a previously compared/"
                    "found pair of thought ids, or null.",
     "inputSchema": {"type": "object", "required": ["a_id", "b_id"],
                     "properties": {"a_id": {"type": "string"}, "b_id": {"type": "string"}},
                     "additionalProperties": False}},
    {"name": "get_thought",
     "description": "Return the stored Thought DNA document for an id, or null.",
     "inputSchema": {"type": "object", "required": ["thought_id"],
                     "properties": {"thought_id": {"type": "string"}},
                     "additionalProperties": False}},
    {"name": "save_snapshot",
     "description": "Persist the engine as ONE manifest-verified snapshot "
                    "directory (store + index + component configs).",
     "inputSchema": {"type": "object", "required": ["directory"],
                     "properties": {"directory": {"type": "string"}},
                     "additionalProperties": False}},
    {"name": "load_snapshot",
     "description": "Replace the engine with one loaded from a snapshot "
                    "directory; fails closed on any integrity mismatch.",
     "inputSchema": {"type": "object", "required": ["directory"],
                     "properties": {"directory": {"type": "string"}},
                     "additionalProperties": False}},
]


class ResonanceAdapter:
    def __init__(self, engine: ResonanceEngine | None = None) -> None:
        self.engine = engine or ResonanceEngine()

    def metadata(self) -> dict[str, Any]:
        return {"adapter_version": MCP_ADAPTER_VERSION,
                "engine_version": ENGINE_VERSION,
                "interface_version": INTERFACE_VERSION,
                "verifier_config_hash": self.engine.verifier.config_hash,
                "corpus_snapshot": self.engine.candidate_index.corpus_snapshot}

    # -- one handler per tool; pass-through only ----------------------------
    def ingest_thought(self, *, context: str, source_id: str | None = None) -> dict:
        graph = self.engine.ingest(context, source_id=source_id)
        return {"thought": wire.thought(graph), "metadata": self.metadata()}

    def index_thought(self, *, thought: dict) -> dict:
        from src.graph import ThoughtGraph
        graph = ThoughtGraph.from_dict(thought)
        self.engine.index(graph)
        return {"thought_id": graph.thought_id, "indexed": True,
                "metadata": self.metadata()}

    def find_resonance(self, *, thought: dict, mode: str, k: int = 20) -> dict:
        from src.graph import ThoughtGraph
        graph = ThoughtGraph.from_dict(thought)
        hits = self.engine.find(graph, mode=mode, k=k)
        return {"hits": [wire.resonance_hit(h) for h in hits],
                "metadata": self.metadata()}

    def compare_thoughts(self, *, a: dict, b: dict, mode: str) -> dict:
        from src.graph import ThoughtGraph
        result = self.engine.compare(ThoughtGraph.from_dict(a),
                                     ThoughtGraph.from_dict(b), mode=mode)
        return {"result": wire.verifier_result(result), "metadata": self.metadata()}

    def explain_resonance(self, *, a_id: str, b_id: str) -> dict:
        result = self.engine.explain(a_id, b_id)
        return {"result": wire.verifier_result(result) if result else None,
                "metadata": self.metadata()}

    def get_thought(self, *, thought_id: str) -> dict:
        graph = self.engine.get(thought_id)
        return {"thought": wire.thought(graph) if graph else None,
                "metadata": self.metadata()}

    def save_snapshot(self, *, directory: str) -> dict:
        self.engine.dump(Path(directory))
        return {"saved": True, "directory": directory, "metadata": self.metadata()}

    def load_snapshot(self, *, directory: str) -> dict:
        self.engine = type(self.engine).load(Path(directory))
        return {"loaded": True, "directory": directory, "metadata": self.metadata()}

    def dispatch(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        handler: Callable[..., dict] | None = getattr(self, name, None)
        if handler is None or name not in {t["name"] for t in TOOLS}:
            raise KeyError(f"unknown tool: {name}")
        return handler(**arguments)
