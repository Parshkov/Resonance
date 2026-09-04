"""Remote MCP bridge for real chat clients (R17).

The accepted stdio adapter (`src/mcp/server.py`) drives the bare engine on a
developer machine and the WebMCP page tools only exist inside Chrome.  Neither
lets a person sitting in their own chat (Claude, Cursor, ChatGPT with a
connector, ...) hand *their* conversation to Resonance.  This module exposes the
live product — identity, consent gates, durable sessions, discovery, intros,
relay channels — as a stateless MCP server over Streamable HTTP:

    POST /mcp            JSON-RPC 2.0 request or notification
    Authorization: Bearer <mcp key>      (or POST /mcp/<mcp key> for clients
                                          that cannot set headers)

The key is minted by the account owner in the browser (`POST
/api/product/mcp_key`, cookie + CSRF authenticated) and is a second identity
session for the same person, so everything the chat does lands in the same
account the Collaboration panel shows.  Bearer requests are the R12 non-cookie
path (`cookie_authenticated=False`): no CSRF, authorization and consent policy
exactly as for the browser.

Tools take the *real* content: the chat's model extracts the causal structure
of what the person is working on into a small labelled graph (roles and
relation types are the accepted Thought DNA vocabulary) and the bridge builds
a canonical manual-provenance Thought DNA around it.  Raw text is accepted as
a fallback through the accepted cue extractor.  Sharing stays two-step
(prepare+preview -> explicit confirm) exactly like the browser and WebMCP
paths; nothing becomes discoverable without `confirm=true` and the preview's
confirmation token.  stdlib only; no matching logic lives here.
"""
from __future__ import annotations

import hashlib
import json
import secrets
from typing import Any, Callable, Mapping

from src.collaboration import CollaborationError
from src.graph.validation import NODE_ROLES, RELATION_TYPES
from src.graph.versioning import SCHEMA_VERSION
from src.identity.models import (
    AuthenticationError,
    AuthorizationError,
    ConfirmationRequiredError,
    CsrfError,
    IdentityValidationError,
)
from src.ingestion.service import ConfirmationError, DraftNotFound, IngestionError, ShareIntent
from src.persistence.errors import (
    PersistenceConflictError,
    PersistenceStaleIndexError,
    PersistenceStateError,
    PersistenceValidationError,
)
from src.product.service import ProductError, StaleResultError
from src.security.models import ConfirmationRequired as PolicyConfirmationRequired
from src.workspaces import WorkspaceError

PROTOCOL_VERSIONS = ("2025-06-18", "2025-03-26", "2024-11-05")
BRIDGE_CONTRACT = "resonance-remote-mcp/0.1"
CLIENT_ID = "remote-mcp-bridge"
EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()
MAX_NODES = 40
MAX_RELATIONS = 80

# JSON-RPC error codes
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603


class BridgeError(Exception):
    """A tool-level failure the caller can act on (isError result)."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def classify_error(exc: Exception) -> tuple[str, bool]:
    """Map product exceptions to a stable error code; second item says whether
    the failure is the caller's (tool isError) rather than a server fault."""
    if isinstance(exc, BridgeError):
        return exc.code, True
    # Same classes and codes as the HTTP layer (`ProductHandler._handle_error`).
    mapping: list[tuple[tuple[type[Exception], ...], str]] = [
        ((AuthenticationError,), "authentication_failed"),
        ((AuthorizationError, DraftNotFound), "authorization_failed"),
        ((CsrfError,), "csrf_rejected"),
        ((ConfirmationRequiredError, ConfirmationError, PolicyConfirmationRequired),
         "confirmation_required"),
        ((StaleResultError, PersistenceStaleIndexError), "stale_result"),
        ((PersistenceConflictError,), "conflict"),
        ((CollaborationError,), "collaboration_unavailable"),
        ((WorkspaceError,), "workspace_unavailable"),
        ((IdentityValidationError, PersistenceValidationError, IngestionError,
          ProductError, ValueError, KeyError, TypeError), "validation_failed"),
        ((PersistenceStateError,), "state_conflict"),
    ]
    for types, code in mapping:
        if isinstance(exc, types):
            return code, True
    return "internal_error", False


# ---------------------------------------------------------------------------
# Thought DNA construction from what a chat model can realistically produce
# ---------------------------------------------------------------------------

def _slug(text: str) -> str:
    return "".join(ch if ch.isalnum() else "-" for ch in text.lower()).strip("-")[:48]


def _coarse_location(value: Any) -> dict[str, Any] | None:
    """City-level only: the durable layer requires the full coarse record and
    rejects anything finer than 0.1 degree."""
    if not value:
        return None
    if not isinstance(value, Mapping):
        raise BridgeError("validation_failed", "coarse_location must be an object")
    try:
        lat = round(float(value["lat"]), 1)
        lon = round(float(value["lon"]), 1)
    except (KeyError, TypeError, ValueError) as exc:
        raise BridgeError("validation_failed", "coarse_location needs numeric lat and lon") from exc
    city = str(value.get("city") or "").strip()
    region = str(value.get("region") or "").strip()
    if not city or not region:
        raise BridgeError("validation_failed", "coarse_location needs city and region labels")
    return {"kind": "consented_coarse", "precision": "city",
            "city": city[:80], "region": region[:80], "lat": lat, "lon": lon}


def _structure_summary(thought_dna: Any) -> dict[str, int]:
    dna = thought_dna if isinstance(thought_dna, Mapping) else {}
    return {"nodes": len(dna.get("nodes") or []), "relations": len(dna.get("relations") or [])}


def _has_usable_structure(structure: Mapping[str, int]) -> bool:
    return structure.get("nodes", 0) >= 2 and structure.get("relations", 0) >= 1


def _insufficient_structure_message(structure: Mapping[str, int], abstentions: Any) -> str:
    notes = "; ".join(str(a) for a in (abstentions or [])) or "no explicit causal cues found"
    return (f"no shareable structure could be extracted from the text "
            f"({structure.get('nodes', 0)} nodes, {structure.get('relations', 0)} relations: {notes}). "
            "The extractor only follows explicit cues and never invents structure. Extract the "
            "causal structure yourself and call again with `thought`: nodes with roles "
            f"{sorted(NODE_ROLES)} and relations typed {sorted(RELATION_TYPES)}.")


def build_thought_dna(thought: Mapping[str, Any], *, human_id: str) -> dict[str, Any]:
    """Turn `{nodes:[{label, role, id?}], relations:[{source, target, type}]}`
    into canonical manual-provenance Thought DNA.  `source`/`target` may name a
    node id or a node label.  Raises BridgeError with a precise message."""
    if not isinstance(thought, Mapping):
        raise BridgeError("validation_failed", "thought must be an object")
    raw_nodes = thought.get("nodes")
    raw_relations = thought.get("relations", [])
    if not isinstance(raw_nodes, list) or not raw_nodes:
        raise BridgeError("validation_failed", "thought.nodes must be a non-empty array")
    if not isinstance(raw_relations, list):
        raise BridgeError("validation_failed", "thought.relations must be an array")
    if len(raw_nodes) > MAX_NODES or len(raw_relations) > MAX_RELATIONS:
        raise BridgeError("validation_failed",
                          f"at most {MAX_NODES} nodes and {MAX_RELATIONS} relations")
    nodes: list[dict[str, Any]] = []
    by_key: dict[str, str] = {}
    for index, item in enumerate(raw_nodes):
        if not isinstance(item, Mapping):
            raise BridgeError("validation_failed", f"nodes[{index}] must be an object")
        label = str(item.get("label", "")).strip()
        role = str(item.get("role", "")).strip()
        if not label or len(label) > 120:
            raise BridgeError("validation_failed", f"nodes[{index}].label must be 1..120 characters")
        if role not in NODE_ROLES:
            raise BridgeError("validation_failed",
                              f"nodes[{index}].role must be one of {sorted(NODE_ROLES)}")
        node_id = str(item.get("id") or f"n{index}")
        if node_id in by_key:
            raise BridgeError("validation_failed", f"duplicate node id {node_id!r}")
        by_key[node_id] = node_id
        by_key.setdefault(label.lower(), node_id)
        node: dict[str, Any] = {
            "id": node_id, "label": label, "role": role,
            "assertion": "negated" if item.get("negated") is True else "asserted",
            "modality": str(item.get("modality") or "actual"),
            "atomic": True, "extract_conf": 1.0, "spans": [],
        }
        nodes.append(node)
    relations: list[dict[str, Any]] = []
    for index, item in enumerate(raw_relations):
        if not isinstance(item, Mapping):
            raise BridgeError("validation_failed", f"relations[{index}] must be an object")
        rtype = str(item.get("type", "")).strip()
        if rtype not in RELATION_TYPES:
            raise BridgeError("validation_failed",
                              f"relations[{index}].type must be one of {sorted(RELATION_TYPES)}")
        ends = []
        for end in ("source", "target"):
            key = str(item.get(end, "")).strip()
            resolved = by_key.get(key) or by_key.get(key.lower())
            if not resolved:
                raise BridgeError("validation_failed",
                                  f"relations[{index}].{end} {key!r} names no node id or label")
            ends.append(resolved)
        if ends[0] == ends[1]:
            raise BridgeError("validation_failed", f"relations[{index}] must connect two different nodes")
        relations.append({
            "id": f"r{index}", "source": ends[0], "target": ends[1], "type": rtype,
            "assertion": "negated" if item.get("negated") is True else "asserted",
            "modality": str(item.get("modality") or "actual"),
            "extract_conf": 1.0, "spans": [],
        })
    topic = str(thought.get("topic") or nodes[0]["label"]).strip()
    thought_id = f"thought-mcp-{_slug(topic) or 'shared'}-{secrets.token_hex(4)}"
    return {
        "schema_version": SCHEMA_VERSION,
        "thought_id": thought_id,
        # The source text is never stored: manual provenance, empty source.
        "source": {"text": "", "sha256": EMPTY_SHA256},
        "provenance": {"kind": "manual", "extractor": None, "human_id": human_id},
        "nodes": nodes,
        "relations": relations,
    }


# ---------------------------------------------------------------------------
# Tool table
# ---------------------------------------------------------------------------

_CONFIRM = {"type": "boolean",
            "description": "Must be true only after the person explicitly approved this action in the chat."}
_REQUEST_ID = {"type": "string", "minLength": 1, "maxLength": 128, "pattern": "^[A-Za-z0-9_.:-]+$",
               "description": "Stable idempotency key; reuse it when retrying the same logical write."}

THOUGHT_SCHEMA = {
    "type": "object",
    "description": "The causal structure of what the person is actually working on, "
                   "extracted from the conversation. Labels are short noun phrases "
                   "(no sentences, no personal data). Roles/types are the Thought DNA vocabulary.",
    "required": ["nodes", "relations"],
    "properties": {
        "topic": {"type": "string", "maxLength": 120,
                  "description": "3-8 word public title of the thought."},
        "domain": {"type": "string", "maxLength": 60,
                   "description": "Field, e.g. 'distributed-systems', 'plasma-optics', 'urban-logistics'."},
        "nodes": {
            "type": "array", "minItems": 2, "maxItems": MAX_NODES,
            "items": {"type": "object", "required": ["label", "role"],
                      "properties": {
                          "id": {"type": "string", "maxLength": 32},
                          "label": {"type": "string", "maxLength": 120},
                          "role": {"type": "string", "enum": sorted(NODE_ROLES)},
                          "negated": {"type": "boolean"},
                          "modality": {"type": "string", "enum": ["actual", "possible", "conditional"]},
                      }, "additionalProperties": False},
        },
        "relations": {
            "type": "array", "minItems": 1, "maxItems": MAX_RELATIONS,
            "items": {"type": "object", "required": ["source", "target", "type"],
                      "properties": {
                          "source": {"type": "string", "description": "node id or label"},
                          "target": {"type": "string", "description": "node id or label"},
                          "type": {"type": "string", "enum": sorted(RELATION_TYPES)},
                          "negated": {"type": "boolean"},
                          "modality": {"type": "string", "enum": ["actual", "possible", "conditional"]},
                      }, "additionalProperties": False},
        },
    },
    "additionalProperties": False,
}

TOOLS: list[dict[str, Any]] = [
    {
        "name": "resonance_whoami",
        "title": "Who am I in Resonance",
        "description": "Return the connected Resonance account (pseudonymous id, display label) and "
                       "what is currently shared. Call first to confirm the key works.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
        "annotations": {"readOnlyHint": True},
    },
    {
        "name": "resonance_prepare_thought",
        "title": "Prepare the person's current thought for sharing",
        "description": (
            "Step 1 of 2. Build a private draft from the REAL reasoning in this conversation: pass "
            "`thought` (labelled causal graph you extracted) or, as a fallback, `context` (raw text, "
            "≤ 4000 chars; the deterministic cue extractor will try). Nothing becomes discoverable. "
            "The result includes the exact preview of what WOULD be shared and a one-time "
            "confirmation_token. Show the preview to the person and ask for explicit approval "
            "before calling resonance_share_thought."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "thought": THOUGHT_SCHEMA,
                "context": {"type": "string", "maxLength": 4000,
                            "description": "Raw text fallback when a graph cannot be extracted."},
                "receive_intro_requests": {
                    "type": "boolean", "default": True,
                    "description": "Whether other people may request an introduction (default true)."},
                "coarse_location": {
                    "type": "object", "required": ["city", "region", "lat", "lon"],
                    "description": "Optional city-level location, only if the person offers it "
                                   "(coordinates are rounded to 0.1 degree).",
                    "properties": {"city": {"type": "string", "maxLength": 80},
                                   "region": {"type": "string", "maxLength": 80},
                                   "lat": {"type": "number"}, "lon": {"type": "number"}},
                    "additionalProperties": False},
            },
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": False, "untrustedContentHint": True},
    },
    {
        "name": "resonance_share_thought",
        "title": "Share the prepared thought (explicit consent)",
        "description": (
            "Step 2 of 2. Publish the prepared Thought DNA so other people can find structural "
            "resonance with it. Requires the person's explicit approval of the preview: pass "
            "confirm=true and the confirmation_token from resonance_prepare_thought. Only the "
            "structural graph becomes discoverable; the conversation text is never stored."),
        "inputSchema": {
            "type": "object", "required": ["draft_id", "confirmation_token", "confirm", "request_id"],
            "properties": {"draft_id": {"type": "string"},
                           "confirmation_token": {"type": "string", "minLength": 1, "maxLength": 256},
                           "confirm": _CONFIRM, "request_id": _REQUEST_ID},
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": False},
    },
    {
        "name": "resonance_my_thoughts",
        "title": "List my shared thoughts",
        "description": "List the thought sessions this account owns with their share state.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
        "annotations": {"readOnlyHint": True},
    },
    {
        "name": "resonance_discover",
        "title": "Discover people whose reasoning resonates",
        "description": (
            "Run accepted structural discovery from one of the person's shared thoughts against "
            "everything other people currently share. Returns matches in backend order with "
            "structural scores, mapped nodes/relations and the counterpart's pseudonym; never "
            "contact details. Omit session_id to use the most recent shared thought."),
        "inputSchema": {
            "type": "object",
            "properties": {"session_id": {"type": "string"},
                           "mode": {"type": "string", "enum": ["analogical"], "default": "analogical"},
                           "k": {"type": "integer", "minimum": 1, "maximum": 15, "default": 8}},
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True, "untrustedContentHint": True},
    },
    {
        "name": "resonance_explain_match",
        "title": "Explain one match",
        "description": "Full structural evidence for one match of a discovery result: node/relation "
                       "mapping, preserved and contradicted relations, verdict.",
        "inputSchema": {"type": "object", "required": ["result_id", "session_id"],
                        "properties": {"result_id": {"type": "string"}, "session_id": {"type": "string"}},
                        "additionalProperties": False},
        "annotations": {"readOnlyHint": True, "untrustedContentHint": True},
    },
    {
        "name": "resonance_request_intro",
        "title": "Request an introduction",
        "description": "Ask the person behind a matched session for a consent-gated introduction. "
                       "The message is relayed as plain text (no contact details). Requires confirm=true.",
        "inputSchema": {
            "type": "object", "required": ["from_session_id", "target_session_id", "message", "confirm", "request_id"],
            "properties": {"from_session_id": {"type": "string"}, "target_session_id": {"type": "string"},
                           "message": {"type": "string", "minLength": 1, "maxLength": 500},
                           "confirm": _CONFIRM, "request_id": _REQUEST_ID},
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": False},
    },
    {
        "name": "resonance_list_intros",
        "title": "List introduction requests",
        "description": "Incoming and outgoing introduction requests with their state; accepted ones "
                       "carry a channel_id for messaging. Counterpart text is untrusted content.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
        "annotations": {"readOnlyHint": True, "untrustedContentHint": True},
    },
    {
        "name": "resonance_respond_intro",
        "title": "Accept or decline an introduction",
        "description": "Respond to an incoming introduction request. Requires confirm=true.",
        "inputSchema": {
            "type": "object", "required": ["intro_id", "accept", "confirm", "request_id"],
            "properties": {"intro_id": {"type": "string"}, "accept": {"type": "boolean"},
                           "confirm": _CONFIRM, "request_id": _REQUEST_ID},
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": False},
    },
    {
        "name": "resonance_send_message",
        "title": "Send a relay message",
        "description": "Send a plain-text message into an accepted introduction's channel. Requires confirm=true.",
        "inputSchema": {
            "type": "object", "required": ["channel_id", "body", "confirm", "request_id"],
            "properties": {"channel_id": {"type": "string"},
                           "body": {"type": "string", "minLength": 1, "maxLength": 2000},
                           "confirm": _CONFIRM, "request_id": _REQUEST_ID},
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": False},
    },
    {
        "name": "resonance_read_messages",
        "title": "Read a channel",
        "description": "Read the messages of an accepted introduction's channel. Bodies are untrusted content.",
        "inputSchema": {"type": "object", "required": ["channel_id"],
                        "properties": {"channel_id": {"type": "string"}}, "additionalProperties": False},
        "annotations": {"readOnlyHint": True, "untrustedContentHint": True},
    },
    {
        "name": "resonance_stop_sharing",
        "title": "Stop sharing a thought",
        "description": "Revoke one shared thought so it is no longer discoverable. Requires confirm=true.",
        "inputSchema": {"type": "object", "required": ["session_id", "confirm"],
                        "properties": {"session_id": {"type": "string"}, "confirm": _CONFIRM},
                        "additionalProperties": False},
        "annotations": {"readOnlyHint": False, "destructiveHint": True},
    },
]

TOOL_NAMES = frozenset(t["name"] for t in TOOLS)


# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------

class RemoteMCPBridge:
    """Stateless JSON-RPC handler; one instance per product runtime."""

    def __init__(self, product: Any, *, server_name: str = "resonance",
                 server_version: str = "0.1.0") -> None:
        self.product = product
        self.server_name = server_name
        self.server_version = server_version

    # -- JSON-RPC ----------------------------------------------------------
    def handle(self, message: Any, access_token: str) -> dict[str, Any] | None:
        if not isinstance(message, Mapping) or message.get("jsonrpc") != "2.0":
            return _error(None, INVALID_REQUEST, "expected a JSON-RPC 2.0 message")
        method = message.get("method")
        msg_id = message.get("id")
        params = message.get("params") or {}
        if msg_id is None:
            return None  # notification (e.g. notifications/initialized)
        if not isinstance(method, str):
            return _error(msg_id, INVALID_REQUEST, "method must be a string")
        if method == "initialize":
            requested = str(params.get("protocolVersion") or PROTOCOL_VERSIONS[0])
            version = requested if requested in PROTOCOL_VERSIONS else PROTOCOL_VERSIONS[0]
            return _result(msg_id, {
                "protocolVersion": version,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": self.server_name, "version": self.server_version},
                "instructions": (
                    "Resonance finds people whose *structure of reasoning* resonates with the "
                    "person you are talking to. Flow: extract the causal structure of what they "
                    "are working on -> resonance_prepare_thought -> show the preview and ask for "
                    "explicit approval -> resonance_share_thought(confirm=true) -> "
                    "resonance_discover -> resonance_explain_match -> resonance_request_intro "
                    "(only with approval). Never invent content; never pass contact details."),
            })
        if method == "ping":
            return _result(msg_id, {})
        if method == "tools/list":
            return _result(msg_id, {"tools": TOOLS})
        if method == "tools/call":
            return self._tool_call(msg_id, params, access_token)
        if method in {"resources/list", "prompts/list"}:
            key = method.split("/")[0]
            return _result(msg_id, {key: []})
        return _error(msg_id, METHOD_NOT_FOUND, f"unknown method {method}")

    def _tool_call(self, msg_id: Any, params: Mapping[str, Any], token: str) -> dict[str, Any]:
        name = params.get("name")
        arguments = params.get("arguments") or {}
        if name not in TOOL_NAMES:
            return _error(msg_id, INVALID_PARAMS, f"unknown tool {name!r}")
        if not isinstance(arguments, Mapping):
            return _error(msg_id, INVALID_PARAMS, "arguments must be an object")
        try:
            result = getattr(self, f"tool_{name[len('resonance_'):]}")(token, dict(arguments))
        except Exception as exc:  # noqa: BLE001 — one bad call never kills the session
            code, actionable = classify_error(exc)
            if not actionable:
                return _error(msg_id, INTERNAL_ERROR, "unexpected product error")
            payload = {"error": code, "message": str(exc) or code}
            return _result(msg_id, {
                "content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}],
                "structuredContent": payload,
                "isError": True,
            })
        return _result(msg_id, {
            "content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False, default=str)}],
            "structuredContent": result,
            "isError": False,
        })

    # -- helpers -------------------------------------------------------------
    def _security(self) -> dict[str, Any]:
        return {"cookie_authenticated": False, "client_id": CLIENT_ID}

    def _actor(self, token: str) -> Any:
        return self.product.identity.authenticate(token)

    def _owned(self, token: str) -> list[dict[str, Any]]:
        return list(self.product.owned_sessions(token))

    def _default_session(self, token: str) -> str:
        owned = self._owned(token)
        shared = [s for s in owned if s.get("share_state") == "discoverable"]
        if not shared:
            raise BridgeError("share_required",
                              "no shared thought yet: run resonance_prepare_thought, show the preview, "
                              "then resonance_share_thought with the person's approval")
        return str(shared[-1]["session_id"])

    @staticmethod
    def _require_confirm(arguments: Mapping[str, Any]) -> None:
        if arguments.get("confirm") is not True:
            raise BridgeError("confirmation_required",
                              "confirm=true is required after the person explicitly approved this action")

    @staticmethod
    def _request_id(arguments: Mapping[str, Any]) -> str:
        value = str(arguments.get("request_id") or "")
        if not value:
            raise BridgeError("validation_failed", "request_id is required")
        return value

    # -- tools ---------------------------------------------------------------
    def tool_whoami(self, token: str, _: dict[str, Any]) -> dict[str, Any]:
        actor = self._actor(token)
        user = self.product.identity.backend.get_user(actor.user_id)
        owned = self._owned(token)
        return {
            "contract_version": BRIDGE_CONTRACT,
            "user_id": actor.user_id,
            "display_label": getattr(user, "display_label", None) if user is not None else None,
            "actor_type": actor.actor_type,
            "shared_thoughts": [s["session_id"] for s in owned if s.get("share_state") == "discoverable"],
            "private_thoughts": [s["session_id"] for s in owned if s.get("share_state") != "discoverable"],
            "freshness": self.product.freshness(),
        }

    def tool_prepare_thought(self, token: str, arguments: dict[str, Any]) -> dict[str, Any]:
        actor = self._actor(token)
        thought = arguments.get("thought")
        context = arguments.get("context")
        if (thought is None) == (context is None):
            raise BridgeError("validation_failed", "provide exactly one of thought or context")
        intent = ShareIntent(
            share_display_profile=True,
            share_coarse_location=bool(arguments.get("coarse_location")),
            receive_intro_requests=arguments.get("receive_intro_requests", True) is not False,
        )
        # The durable projection requires exactly {topic, domain, cluster_id};
        # derive sensible values from what the chat provided.
        topic = (str(thought.get("topic") or "").strip() if isinstance(thought, Mapping) else "") \
            or "Shared thought"
        domain = (str(thought.get("domain") or "").strip() if isinstance(thought, Mapping) else "") \
            or "general"
        presentation = {"topic": topic[:120], "domain": domain[:60],
                        "cluster_id": (_slug(topic) or "shared")[:48]}
        common = dict(presentation=presentation,
                      coarse_location=_coarse_location(arguments.get("coarse_location")),
                      intent=intent, **self._security())
        if thought is not None:
            candidate = build_thought_dna(thought, human_id=actor.user_id)
            prepared = self.product.prepare_structured(token, candidate, **common)
        else:
            # A per-prepare namespace keeps the extracted Thought DNA id unique
            # per person and attempt: the same sentences prepared again (or by
            # another person) must not collide with a reserved/revoked id.
            prepared = self.product.prepare_raw_text(
                token, str(context), source_id=f"{actor.user_id}:{secrets.token_hex(8)}", **common)
        draft_id = str(prepared["draft_id"])
        preview = self.product.preview(token, draft_id, client_id=CLIENT_ID)
        structure = _structure_summary(preview.get("thought_dna"))
        if thought is None and not _has_usable_structure(structure):
            # The accepted extractor abstains on implicit prose instead of
            # inventing structure. An empty graph must not become a shareable
            # draft: discard it and tell the agent what to do instead.
            try:
                self.product.discard(token, draft_id, confirmed=True, **self._security())
            except Exception:  # noqa: BLE001 - best effort clean-up
                pass
            raise BridgeError("validation_failed", _insufficient_structure_message(
                structure, prepared.get("abstentions", [])))
        return {
            "contract_version": BRIDGE_CONTRACT,
            "draft_id": draft_id,
            "session_id": prepared.get("session_id"),
            "discoverable": False,
            "input_kind": prepared.get("input_kind"),
            "source_retention": prepared.get("source_retention", "not_retained"),
            "structure": structure,
            "abstentions": prepared.get("abstentions", []),
            "warnings": prepared.get("warnings", []),
            "will_become_discoverable": {
                "thought_dna": preview.get("thought_dna"),
                "presentation": preview.get("presentation"),
                "coarse_location": preview.get("coarse_location"),
                "intent": preview.get("intent"),
            },
            "confirmation_token": preview["confirmation_token"],
            "requires_explicit_confirmation": True,
            "next_step": "Show this preview to the person. Only if they approve, call "
                         "resonance_share_thought with confirm=true and this confirmation_token.",
        }

    def tool_share_thought(self, token: str, arguments: dict[str, Any]) -> dict[str, Any]:
        self._require_confirm(arguments)
        request_id = self._request_id(arguments)
        # The share commit is idempotent on the draft itself (one confirmation
        # token, one commit); request_id is kept in the contract for parity.
        result = self.product.share_prepared(
            token, str(arguments.get("draft_id", "")),
            confirmation_token=str(arguments.get("confirmation_token", "")),
            confirmed=True, **self._security())
        return {"contract_version": BRIDGE_CONTRACT, "shared": True, "discoverable": True,
                "request_id": request_id,
                "session_id": result.get("session_id"), "draft_id": arguments.get("draft_id"),
                "next_step": "Call resonance_discover to find resonating people."}

    def tool_my_thoughts(self, token: str, _: dict[str, Any]) -> dict[str, Any]:
        return {"contract_version": BRIDGE_CONTRACT, "sessions": self._owned(token)}

    def tool_discover(self, token: str, arguments: dict[str, Any]) -> dict[str, Any]:
        session_id = str(arguments.get("session_id") or "") or self._default_session(token)
        mode = str(arguments.get("mode") or "analogical")
        k = max(1, min(int(arguments.get("k") or 8), 15))
        response = self.product.discover(token, session_id, mode=mode, k=k, client_id=CLIENT_ID)
        return {
            "contract_version": BRIDGE_CONTRACT,
            "result_id": response["result_id"],
            "query_session_id": session_id,
            "source": response.get("source"),
            "discovery_contract": response.get("discovery_contract"),
            "matches_in_backend_order": list(response.get("matches", [])),
            "rejected": list(response.get("rejected", [])),
            "aggregation": response.get("aggregation", {}),
            "blocked_rows_removed": response.get("blocked_rows_removed", 0),
            "location_note": response.get("location_note", ""),
            "freshness": response.get("freshness", {}),
            "next_step": "resonance_explain_match(result_id, session_id) for evidence; "
                         "resonance_request_intro only with the person's approval.",
        }

    def tool_explain_match(self, token: str, arguments: dict[str, Any]) -> dict[str, Any]:
        return self.product.get_match(token, str(arguments.get("result_id", "")),
                                      str(arguments.get("session_id", "")))

    def tool_request_intro(self, token: str, arguments: dict[str, Any]) -> dict[str, Any]:
        self._require_confirm(arguments)
        return self.product.request_intro(
            token,
            from_session_id=str(arguments.get("from_session_id", "")),
            target_session_id=str(arguments.get("target_session_id", "")),
            message=str(arguments.get("message", "")),
            request_id=self._request_id(arguments), confirmed=True, **self._security())

    def tool_list_intros(self, token: str, _: dict[str, Any]) -> dict[str, Any]:
        return self.product.list_requests(token)

    def tool_respond_intro(self, token: str, arguments: dict[str, Any]) -> dict[str, Any]:
        self._require_confirm(arguments)
        return self.product.respond_intro(
            token, str(arguments.get("intro_id", "")), accept=arguments.get("accept") is True,
            request_id=self._request_id(arguments), confirmed=True, **self._security())

    def tool_send_message(self, token: str, arguments: dict[str, Any]) -> dict[str, Any]:
        self._require_confirm(arguments)
        return self.product.send_message(
            token, str(arguments.get("channel_id", "")), str(arguments.get("body", "")),
            request_id=self._request_id(arguments), confirmed=True, **self._security())

    def tool_read_messages(self, token: str, arguments: dict[str, Any]) -> dict[str, Any]:
        return self.product.read_messages(token, str(arguments.get("channel_id", "")))

    def tool_stop_sharing(self, token: str, arguments: dict[str, Any]) -> dict[str, Any]:
        self._require_confirm(arguments)
        session_id = str(arguments.get("session_id", ""))
        self.product.revoke_session(token, session_id, confirmed=True, **self._security())
        return {"contract_version": BRIDGE_CONTRACT, "session_id": session_id,
                "shared": False, "discoverable": False, "revoked": True}


def _result(msg_id: Any, result: Mapping[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": msg_id, "result": dict(result)}


def _error(msg_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}}


def bearer_token(authorization: str | None, path_token: str | None) -> str | None:
    """Prefer the Authorization header; accept a path-embedded key for clients
    that cannot set headers (capability URL, shown once to the account owner)."""
    if authorization:
        scheme, _, value = authorization.strip().partition(" ")
        if scheme.lower() == "bearer" and value.strip():
            return value.strip()
    if path_token:
        return path_token
    return None


ResponseWriter = Callable[[int, Mapping[str, Any] | None, Mapping[str, str]], None]
