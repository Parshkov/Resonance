"""Thin MCP tool adapter over the accepted :class:`ResonanceEngine`.

This module translates transport-shaped dictionaries to public engine calls.
It deliberately contains no extraction, retrieval, alignment, or scoring logic.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from pathlib import Path
from typing import Any

from src.engine import ENGINE_VERSION, EngineIntegrityError, ResonanceEngine
from src.graph import SCHEMA_VERSION, ThoughtGraph
from src.interfaces import (
    INTERFACE_VERSION,
    RESONANCE_MODES,
    SCORE_CONTRACT_VERSION,
    RetrievalFlags,
    ScoreVector,
    require_mode,
)

from .schemas import TOOL_NAMES, list_tools

ADAPTER_VERSION = "resonance-mcp/0.1-q7v2"
SNAPSHOT_FILES = frozenset({"manifest.json", "store.json", "index.json"})


class UnknownToolError(ValueError):
    """A tools/call request named a tool this adapter does not expose."""


def to_wire(value: Any) -> Any:
    """Convert accepted immutable engine types into stable JSON data."""
    if isinstance(value, ThoughtGraph):
        return value.to_dict()
    if isinstance(value, ScoreVector):
        return value.to_wire()
    if isinstance(value, RetrievalFlags):
        return value.to_wire()
    if is_dataclass(value) and not isinstance(value, type):
        return {field.name: to_wire(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, Mapping):
        return {str(key): to_wire(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [to_wire(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    raise TypeError(f"cannot serialize {type(value).__name__} to the MCP wire format")


def _require_arguments(
    arguments: Any,
    *,
    required: frozenset[str],
    optional: frozenset[str] = frozenset(),
) -> dict[str, Any]:
    if not isinstance(arguments, Mapping):
        raise ValueError("tool arguments must be an object")
    args = dict(arguments)
    unknown = sorted(set(args) - required - optional)
    missing = sorted(required - set(args))
    if unknown:
        raise ValueError("unknown tool arguments: " + ", ".join(unknown))
    if missing:
        raise ValueError("missing required tool arguments: " + ", ".join(missing))
    return args


def _nonempty_string(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


class ResonanceMCPAdapter:
    """Own one engine instance and expose exactly the six R6 operations."""

    def __init__(
        self,
        *,
        engine: ResonanceEngine | None = None,
        data_dir: Path | str | None = None,
    ) -> None:
        self.data_dir = Path(data_dir).resolve() if data_dir is not None else None
        if engine is not None:
            self.engine = engine
        elif self.data_dir is not None:
            self.engine = self._load_or_create(self.data_dir)
        else:
            self.engine = ResonanceEngine()

    @staticmethod
    def _load_or_create(data_dir: Path) -> ResonanceEngine:
        present = {name for name in SNAPSHOT_FILES if (data_dir / name).exists()}
        if present and present != SNAPSHOT_FILES:
            missing = ", ".join(sorted(SNAPSHOT_FILES - present))
            raise EngineIntegrityError(
                f"incomplete MCP engine snapshot in {data_dir}; missing: {missing}"
            )
        if present == SNAPSHOT_FILES:
            return ResonanceEngine.load(data_dir)
        return ResonanceEngine()

    def tools(self) -> list[dict[str, Any]]:
        return list_tools()

    def metadata(self) -> dict[str, Any]:
        index_config = self.engine.candidate_index.config
        return {
            "adapter_version": ADAPTER_VERSION,
            "engine_version": ENGINE_VERSION,
            "interface_version": INTERFACE_VERSION,
            "schema_version": SCHEMA_VERSION,
            "score_contract_version": SCORE_CONTRACT_VERSION,
            "corpus_snapshot": self.engine.candidate_index.corpus_snapshot,
            "thought_count": len(self.engine.store.thought_ids()),
            "index_config": to_wire(index_config),
            "verifier_config": {
                "component": type(self.engine.verifier).__name__,
                "config_hash": self.engine.verifier.config_hash,
            },
            "persistence": {
                "mode": "manifest_snapshot" if self.data_dir is not None else "memory",
                "auto_save_after_index": self.data_dir is not None,
            },
        }

    def _resolve_graph(self, value: Any, name: str) -> ThoughtGraph:
        if not isinstance(value, Mapping):
            raise ValueError(f"{name} must be a Thought DNA object or an indexed-thought reference")
        payload = dict(value)
        if set(payload) == {"id"}:
            thought_id = _nonempty_string(payload["id"], f"{name}.id")
            graph = self.engine.get(thought_id)
            if graph is None:
                raise ValueError(f"indexed thought not found: {thought_id}")
            return graph
        return ThoughtGraph.from_dict(payload)

    def _persist(self) -> bool:
        if self.data_dir is None:
            return False
        self.engine.dump(self.data_dir)
        return True

    def _envelope(self, operation: str, result: Any) -> dict[str, Any]:
        return {
            "operation": operation,
            "result": to_wire(result),
            "metadata": self.metadata(),
        }

    def _dispatch(self, name: str, arguments: Any) -> dict[str, Any]:
        if name == "ingest_thought":
            args = _require_arguments(
                arguments,
                required=frozenset({"context"}),
                optional=frozenset({"source_id"}),
            )
            context = _nonempty_string(args["context"], "context")
            source_id = args.get("source_id")
            if source_id is not None:
                source_id = _nonempty_string(source_id, "source_id")
            return self._envelope(
                name,
                self.engine.ingest(context, source_id=source_id),
            )

        if name == "index_thought":
            args = _require_arguments(arguments, required=frozenset({"thought"}))
            if not isinstance(args["thought"], Mapping):
                raise ValueError("thought must be a complete Thought DNA object")
            graph = ThoughtGraph.from_dict(dict(args["thought"]))
            self.engine.index(graph)
            persisted = self._persist()
            return self._envelope(
                name,
                {"indexed": True, "persisted": persisted, "thought": graph},
            )

        if name == "find_resonance":
            args = _require_arguments(
                arguments,
                required=frozenset({"thought", "mode"}),
                optional=frozenset({"k"}),
            )
            graph = self._resolve_graph(args["thought"], "thought")
            mode = require_mode(_nonempty_string(args["mode"], "mode"))
            k = args.get("k", 20)
            if isinstance(k, bool) or not isinstance(k, int) or not 1 <= k <= 100:
                raise ValueError("k must be an integer in [1, 100]")
            hits = tuple(self.engine.find(graph, mode=mode, k=k))
            return self._envelope(
                name,
                {
                    "query_id": graph.thought_id,
                    "mode": mode,
                    "requested_k": k,
                    "returned": len(hits),
                    "hits": hits,
                },
            )

        if name == "compare_thoughts":
            args = _require_arguments(arguments, required=frozenset({"a", "b", "mode"}))
            a = self._resolve_graph(args["a"], "a")
            b = self._resolve_graph(args["b"], "b")
            mode = require_mode(_nonempty_string(args["mode"], "mode"))
            return self._envelope(name, self.engine.compare(a, b, mode=mode))

        if name == "explain_resonance":
            args = _require_arguments(arguments, required=frozenset({"a", "b"}))
            a_id = _nonempty_string(args["a"], "a")
            b_id = _nonempty_string(args["b"], "b")
            return self._envelope(name, self.engine.explain(a_id, b_id))

        if name == "get_thought":
            args = _require_arguments(arguments, required=frozenset({"id"}))
            thought_id = _nonempty_string(args["id"], "id")
            return self._envelope(name, self.engine.get(thought_id))

        raise UnknownToolError(f"unknown MCP tool: {name}")

    def call_tool(self, name: str, arguments: Any) -> dict[str, Any]:
        """Return an MCP CallToolResult; tool failures stay inside the result."""
        if name not in TOOL_NAMES:
            raise UnknownToolError(f"unknown MCP tool: {name}")
        try:
            payload = self._dispatch(name, arguments)
        except Exception as exc:  # MCP tool failures are model-visible results.
            error = {
                "operation": name,
                "error": {"type": type(exc).__name__, "message": str(exc)},
                "metadata": self.metadata(),
            }
            return {
                "content": [{"type": "text", "text": json.dumps(error, sort_keys=True)}],
                "structuredContent": error,
                "isError": True,
            }
        return {
            "content": [{"type": "text", "text": json.dumps(payload, sort_keys=True)}],
            "structuredContent": payload,
            "isError": False,
        }
