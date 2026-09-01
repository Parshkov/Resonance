"""Strict MCP tool schemas for the accepted Resonance engine facade."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from src.interfaces import RESONANCE_MODES, SCORE_WIRE_NAMES


def _object(
    properties: dict[str, Any],
    required: tuple[str, ...] | list[str] = (),
    *,
    description: str | None = None,
) -> dict[str, Any]:
    schema: dict[str, Any] = {
        "type": "object",
        "properties": properties,
        "required": list(required),
        "additionalProperties": False,
    }
    if description is not None:
        schema["description"] = description
    return schema


_SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schemas" / "thought-dna-0.1.schema.json"
THOUGHT_DNA_SCHEMA: dict[str, Any] = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))

STRING = {"type": "string"}
NONEMPTY_STRING = {"type": "string", "minLength": 1}
NUMBER = {"type": "number"}
INTEGER = {"type": "integer"}
BOOLEAN = {"type": "boolean"}

CONFIG_REF_SCHEMA = _object(
    {
        "component": NONEMPTY_STRING,
        "component_version": NONEMPTY_STRING,
        "config_hash": NONEMPTY_STRING,
        "schema_version": NONEMPTY_STRING,
    },
    ("component", "component_version", "config_hash", "schema_version"),
)

ITEM_PROVENANCE_SCHEMA = _object(
    {
        "thought_id": NONEMPTY_STRING,
        "item_id": NONEMPTY_STRING,
        "provenance_kind": NONEMPTY_STRING,
        "spans": {
            "type": "array",
            "items": _object(
                {"start": INTEGER, "end": INTEGER, "text": STRING},
                ("start", "end", "text"),
            ),
        },
    },
    ("thought_id", "item_id", "provenance_kind", "spans"),
)

NODE_MATCH_SCHEMA = _object(
    {
        "query_node": NONEMPTY_STRING,
        "candidate_node": NONEMPTY_STRING,
        "support": NUMBER,
        "query_provenance": ITEM_PROVENANCE_SCHEMA,
        "candidate_provenance": ITEM_PROVENANCE_SCHEMA,
    },
    ("query_node", "candidate_node", "support", "query_provenance", "candidate_provenance"),
)

RELATION_MATCH_SCHEMA = _object(
    {
        "query_relation": NONEMPTY_STRING,
        "candidate_relation": NONEMPTY_STRING,
        "support": NUMBER,
        "query_provenance": ITEM_PROVENANCE_SCHEMA,
        "candidate_provenance": ITEM_PROVENANCE_SCHEMA,
    },
    (
        "query_relation",
        "candidate_relation",
        "support",
        "query_provenance",
        "candidate_provenance",
    ),
)

EDGE_PATH_MATCH_SCHEMA = _object(
    {
        "query_relation": NONEMPTY_STRING,
        "candidate_relations": {"type": "array", "items": NONEMPTY_STRING},
        "realizes_nodes": {"type": "array", "items": NONEMPTY_STRING},
        "support": NUMBER,
        "query_provenance": ITEM_PROVENANCE_SCHEMA,
        "candidate_provenances": {"type": "array", "items": ITEM_PROVENANCE_SCHEMA},
        "realizes_node_provenances": {"type": "array", "items": ITEM_PROVENANCE_SCHEMA},
    },
    (
        "query_relation",
        "candidate_relations",
        "realizes_nodes",
        "support",
        "query_provenance",
        "candidate_provenances",
        "realizes_node_provenances",
    ),
)

CONTRADICTION_SCHEMA = _object(
    {
        "kind": NONEMPTY_STRING,
        "query_item": NONEMPTY_STRING,
        "candidate_item": NONEMPTY_STRING,
        "contribution": NUMBER,
        "rule_version": NONEMPTY_STRING,
        "query_provenance": ITEM_PROVENANCE_SCHEMA,
        "candidate_provenance": ITEM_PROVENANCE_SCHEMA,
    },
    (
        "kind",
        "query_item",
        "candidate_item",
        "contribution",
        "rule_version",
        "query_provenance",
        "candidate_provenance",
    ),
)

RETRIEVAL_FLAGS_SCHEMA = _object(
    {
        "requires_structural_verification": BOOLEAN,
        "polarity_reliable": BOOLEAN,
    },
    ("requires_structural_verification", "polarity_reliable"),
)

SCORE_PROPERTIES: dict[str, Any] = {
    wire_name: (
        BOOLEAN
        if field_name in {"h_sign_conflict", "knowledge_evidence_present", "rarity_weighting"}
        else NUMBER
    )
    for field_name, wire_name in SCORE_WIRE_NAMES.items()
}
SCORE_PROPERTIES["extras"] = {"type": "object", "additionalProperties": NUMBER}
SCORE_VECTOR_SCHEMA = _object(SCORE_PROPERTIES, tuple(SCORE_WIRE_NAMES.values()))

EXPLANATION_SCHEMA = _object(
    {
        "mapping": {"type": "array", "items": NODE_MATCH_SCHEMA},
        "matched_relations": {"type": "array", "items": RELATION_MATCH_SCHEMA},
        "edge_path_matches": {"type": "array", "items": EDGE_PATH_MATCH_SCHEMA},
        "unmatched_query_nodes": {"type": "array", "items": NONEMPTY_STRING},
        "unmatched_candidate_nodes": {"type": "array", "items": NONEMPTY_STRING},
        "unmatched_query_relations": {"type": "array", "items": NONEMPTY_STRING},
        "unmatched_candidate_relations": {"type": "array", "items": NONEMPTY_STRING},
        "contradictions": {"type": "array", "items": CONTRADICTION_SCHEMA},
        "retrieval_channels": {"type": "array", "items": NONEMPTY_STRING},
        "systematicity_systems": {
            "type": "array",
            "items": {"type": "array", "items": NONEMPTY_STRING},
        },
        "score_model_version": NONEMPTY_STRING,
        "schema_version": NONEMPTY_STRING,
        "config_hash": NONEMPTY_STRING,
    },
    (
        "mapping",
        "matched_relations",
        "edge_path_matches",
        "unmatched_query_nodes",
        "unmatched_candidate_nodes",
        "unmatched_query_relations",
        "unmatched_candidate_relations",
        "contradictions",
        "retrieval_channels",
        "systematicity_systems",
        "score_model_version",
        "schema_version",
        "config_hash",
    ),
)

VERIFIER_RESULT_SCHEMA = _object(
    {
        "contract_version": NONEMPTY_STRING,
        "query_id": NONEMPTY_STRING,
        "candidate_id": NONEMPTY_STRING,
        "candidate_config": NONEMPTY_STRING,
        "mapping": {"type": "array", "items": NODE_MATCH_SCHEMA},
        "matched_relations": {"type": "array", "items": RELATION_MATCH_SCHEMA},
        "edge_path_matches": {"type": "array", "items": EDGE_PATH_MATCH_SCHEMA},
        "unmatched_query_nodes": {"type": "array", "items": NONEMPTY_STRING},
        "unmatched_candidate_nodes": {"type": "array", "items": NONEMPTY_STRING},
        "unmatched_query_relations": {"type": "array", "items": NONEMPTY_STRING},
        "unmatched_candidate_relations": {"type": "array", "items": NONEMPTY_STRING},
        "contradictions": {"type": "array", "items": CONTRADICTION_SCHEMA},
        "hard_rejection": {"type": ["string", "null"]},
        "components": SCORE_VECTOR_SCHEMA,
        "classification": NONEMPTY_STRING,
        "confidence": NONEMPTY_STRING,
        "explanation": EXPLANATION_SCHEMA,
        "solver_config": CONFIG_REF_SCHEMA,
        "retrieval_flags": RETRIEVAL_FLAGS_SCHEMA,
    },
    (
        "contract_version",
        "query_id",
        "candidate_id",
        "candidate_config",
        "mapping",
        "matched_relations",
        "edge_path_matches",
        "unmatched_query_nodes",
        "unmatched_candidate_nodes",
        "unmatched_query_relations",
        "unmatched_candidate_relations",
        "contradictions",
        "hard_rejection",
        "components",
        "classification",
        "confidence",
        "explanation",
        "solver_config",
        "retrieval_flags",
    ),
)

CANDIDATE_RESULT_SCHEMA = _object(
    {
        "candidate_id": NONEMPTY_STRING,
        "channel_scores": {"type": "object", "additionalProperties": NUMBER},
        "channel_ranks": {"type": "object", "additionalProperties": INTEGER},
        "seed_correspondences": {
            "type": "array",
            "items": _object(
                {
                    "query_node": NONEMPTY_STRING,
                    "candidate_node": NONEMPTY_STRING,
                    "support": NUMBER,
                    "channel": NONEMPTY_STRING,
                },
                ("query_node", "candidate_node", "support", "channel"),
            ),
        },
        "usable_query_evidence": NUMBER,
        "requires_structural_verification": BOOLEAN,
        "polarity_reliable": BOOLEAN,
        "index_version": NONEMPTY_STRING,
        "feature_version": NONEMPTY_STRING,
        "corpus_snapshot": NONEMPTY_STRING,
        "config": CONFIG_REF_SCHEMA,
    },
    (
        "candidate_id",
        "channel_scores",
        "channel_ranks",
        "seed_correspondences",
        "usable_query_evidence",
        "requires_structural_verification",
        "polarity_reliable",
        "index_version",
        "feature_version",
        "corpus_snapshot",
        "config",
    ),
)

HIT_SCHEMA = _object(
    {"candidate": CANDIDATE_RESULT_SCHEMA, "verification": VERIFIER_RESULT_SCHEMA},
    ("candidate", "verification"),
)

METADATA_SCHEMA = _object(
    {
        "adapter_version": NONEMPTY_STRING,
        "engine_version": NONEMPTY_STRING,
        "interface_version": NONEMPTY_STRING,
        "schema_version": NONEMPTY_STRING,
        "score_contract_version": NONEMPTY_STRING,
        "corpus_snapshot": NONEMPTY_STRING,
        "thought_count": {"type": "integer", "minimum": 0},
        "index_config": CONFIG_REF_SCHEMA,
        "verifier_config": _object(
            {"component": NONEMPTY_STRING, "config_hash": NONEMPTY_STRING},
            ("component", "config_hash"),
        ),
        "persistence": _object(
            {
                "mode": {"enum": ["memory", "manifest_snapshot"]},
                "auto_save_after_index": BOOLEAN,
            },
            ("mode", "auto_save_after_index"),
        ),
    },
    (
        "adapter_version",
        "engine_version",
        "interface_version",
        "schema_version",
        "score_contract_version",
        "corpus_snapshot",
        "thought_count",
        "index_config",
        "verifier_config",
        "persistence",
    ),
)


def _thought_schema(resource_name: str) -> dict[str, Any]:
    """Embed Thought DNA as a distinct JSON-Schema resource.

    Its internal ``#/$defs`` references remain local because each embedding has
    a unique ``$id``; compare_thoughts can therefore contain two graph schemas
    without duplicate canonical resource identifiers.
    """
    schema = copy.deepcopy(THOUGHT_DNA_SCHEMA)
    schema["$id"] = f"urn:resonance:mcp:thought-dna:{resource_name}"
    return schema


def _graph_input_schema(resource_name: str) -> dict[str, Any]:
    return {
        "oneOf": [
            _thought_schema(resource_name),
            _object({"id": NONEMPTY_STRING}, ("id",), description="Reference an indexed thought."),
        ]
    }


def _envelope(operation: str, result_schema: dict[str, Any]) -> dict[str, Any]:
    return _object(
        {
            "operation": {"const": operation},
            "result": result_schema,
            "metadata": METADATA_SCHEMA,
        },
        ("operation", "result", "metadata"),
    )


TOOL_DEFINITIONS: tuple[dict[str, Any], ...] = (
    {
        "name": "ingest_thought",
        "title": "Ingest thought context",
        "description": "Extract a validated Thought DNA graph through EngineFacade.ingest.",
        "inputSchema": _object(
            {"context": NONEMPTY_STRING, "source_id": NONEMPTY_STRING},
            ("context",),
        ),
        "outputSchema": _envelope("ingest_thought", _thought_schema("ingest-output")),
    },
    {
        "name": "index_thought",
        "title": "Index Thought DNA",
        "description": "Validate and index a complete Thought DNA graph through EngineFacade.index.",
        "inputSchema": _object({"thought": _thought_schema("index-input")}, ("thought",)),
        "outputSchema": _envelope(
            "index_thought",
            _object(
                {
                    "indexed": {"const": True},
                    "persisted": BOOLEAN,
                    "thought": _thought_schema("index-output"),
                },
                ("indexed", "persisted", "thought"),
            ),
        ),
    },
    {
        "name": "find_resonance",
        "title": "Find resonance",
        "description": "Retrieve and verify indexed candidates through EngineFacade.find.",
        "inputSchema": _object(
            {
                "thought": _graph_input_schema("find-input"),
                "mode": {"enum": list(RESONANCE_MODES)},
                "k": {"type": "integer", "minimum": 1, "maximum": 100},
            },
            ("thought", "mode"),
        ),
        "outputSchema": _envelope(
            "find_resonance",
            _object(
                {
                    "query_id": NONEMPTY_STRING,
                    "mode": {"enum": list(RESONANCE_MODES)},
                    "requested_k": {"type": "integer", "minimum": 1, "maximum": 100},
                    "returned": {"type": "integer", "minimum": 0},
                    "hits": {"type": "array", "items": HIT_SCHEMA},
                },
                ("query_id", "mode", "requested_k", "returned", "hits"),
            ),
        ),
    },
    {
        "name": "compare_thoughts",
        "title": "Compare thoughts",
        "description": "Structurally compare two Thought DNA graphs through EngineFacade.compare.",
        "inputSchema": _object(
            {
                "a": _graph_input_schema("compare-input-a"),
                "b": _graph_input_schema("compare-input-b"),
                "mode": {"enum": list(RESONANCE_MODES)},
            },
            ("a", "b", "mode"),
        ),
        "outputSchema": _envelope("compare_thoughts", VERIFIER_RESULT_SCHEMA),
    },
    {
        "name": "explain_resonance",
        "title": "Explain resonance",
        "description": "Return the process-local structured result cached by compare/find.",
        "inputSchema": _object({"a": NONEMPTY_STRING, "b": NONEMPTY_STRING}, ("a", "b")),
        "outputSchema": _envelope(
            "explain_resonance",
            {"oneOf": [VERIFIER_RESULT_SCHEMA, {"type": "null"}]},
        ),
    },
    {
        "name": "get_thought",
        "title": "Get indexed thought",
        "description": "Fetch an indexed Thought DNA graph through EngineFacade.get.",
        "inputSchema": _object({"id": NONEMPTY_STRING}, ("id",)),
        "outputSchema": _envelope(
            "get_thought",
            {"oneOf": [_thought_schema("get-output"), {"type": "null"}]},
        ),
    },
)


TOOL_NAMES = tuple(tool["name"] for tool in TOOL_DEFINITIONS)


def list_tools() -> list[dict[str, Any]]:
    """Return an isolated copy so callers cannot mutate server schemas."""
    return copy.deepcopy(list(TOOL_DEFINITIONS))
