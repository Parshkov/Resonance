"""Remote-MCP adapter over the accepted live product (R15 completion).

Transport-neutral. Every tool call resolves to a `LiveProductService` method
with the authenticated subject — no R7 fixture, no parallel matching/scoring,
no transport shadow state. The remote bearer token IS the accepted R12 access
token, so remote MCP, WebMCP, the human UI and local stdio all authenticate
through one identity model and share the same authorization rules.
"""

from __future__ import annotations

from typing import Any

from src.identity.models import (
    AuthenticationError,
    AuthorizationError,
    ConfirmationRequiredError,
    ConsentChoices,
    CsrfError,
    IdentityValidationError,
)
from src.ingestion.service import ConfirmationError, DraftNotFound, IngestionError, ShareIntent
from src.product.service import ProductError, StaleResultError

# Errors that map to a tool-level isError (client-actionable), vs JSON-RPC.
TOOL_ERRORS = (
    AuthorizationError, ConfirmationRequiredError, ConfirmationError,
    DraftNotFound, IngestionError, ProductError, StaleResultError,
    IdentityValidationError, CsrfError, ValueError,
)


class RemoteError(ValueError):
    """Typed remote-boundary error."""


# Remote agent clients present a bearer token and no browser cookie, so cookie
# CSRF does not apply; authorization still runs through the accepted kernel.
_AGENT_CTX = {"cookie_authenticated": False, "client_id": "remote-mcp"}


class RemoteProductService:
    def __init__(self, runtime) -> None:
        self.runtime = runtime
        self.product = runtime.product
        self.identity = runtime.identity

    # -- auth ------------------------------------------------------------
    def subject_for(self, bearer: str | None) -> str | None:
        if not bearer:
            return None
        try:
            return self.identity.authenticate(bearer).user_id
        except AuthenticationError:
            return None

    def require_token(self, bearer: str | None) -> str:
        if self.subject_for(bearer) is None:
            raise AuthorizationError("valid bearer token required")
        return bearer

    def whoami(self, bearer: str) -> dict[str, Any]:
        actor = self.identity.authenticate(bearer)
        state = self.product.state(bearer)
        return {"user_id": actor.user_id, "actor_type": actor.actor_type,
                "owned_sessions": state["owned_sessions"],
                "freshness": state["freshness"]}

    # -- ingestion / share -----------------------------------------------
    def prepare(self, bearer: str, *, candidate=None, context=None,
                presentation=None, coarse_location=None, intent=None) -> dict[str, Any]:
        share_intent = ShareIntent(**intent) if isinstance(intent, dict) else None
        # Integration delta (R16 review of the exact head): a real chat passing
        # only `context` prepared fine but could never share — the durable
        # projection requires exactly {topic, domain, cluster_id}. Fill the
        # missing fields from whatever the caller gave so the raw-text path is
        # usable end to end; explicit values always win.
        given = dict(presentation or {})
        topic = str(given.get("topic") or (str(context).strip().split("\n", 1)[0][:120]
                                             if context else "") or "Shared thought")
        domain = str(given.get("domain") or "general")
        cluster = str(given.get("cluster_id") or
                      "".join(ch if ch.isalnum() else "-" for ch in topic.lower()).strip("-")[:48]
                      or "shared")
        presentation = {**given, "topic": topic, "domain": domain, "cluster_id": cluster}
        common = dict(presentation=presentation,
                      coarse_location=coarse_location, intent=share_intent, **_AGENT_CTX)
        if (candidate is None) == (context is None):
            raise IngestionError("provide exactly one of candidate or context")
        if candidate is not None:
            return self.product.prepare_structured(bearer, candidate, **common)
        return self.product.prepare_raw_text(bearer, str(context), **common)

    def preview(self, bearer: str, draft_id: str) -> dict[str, Any]:
        return self.product.preview(bearer, draft_id, client_id="remote-mcp")

    def share(self, bearer: str, draft_id: str, confirmation_token: str,
              confirmed: bool) -> dict[str, Any]:
        return dict(self.product.share_prepared(
            bearer, draft_id, confirmation_token=confirmation_token,
            confirmed=confirmed, **_AGENT_CTX))

    def revoke(self, bearer: str, session_id: str, confirmed: bool) -> dict[str, Any]:
        return self.product.revoke_session(bearer, session_id, confirmed=confirmed,
                                           **_AGENT_CTX)

    def set_consent(self, bearer: str, session_id: str, choices: dict,
                    confirmed: bool) -> dict[str, Any]:
        c = ConsentChoices(
            share_thought_dna=bool(choices.get("share_thought_dna", False)),
            share_display_profile=bool(choices.get("share_display_profile", False)),
            share_coarse_location=bool(choices.get("share_coarse_location", False)),
            allow_intro_requests=bool(choices.get("allow_intro_requests", False)))
        result = self.product.set_consent(bearer, session_id, c, confirmed=confirmed,
                                          **_AGENT_CTX)
        return {"session_id": session_id, "consent": result.to_corpus_consent(),
                "allow_intro_requests": result.allow_intro_requests}

    # -- discovery / rich results ----------------------------------------
    def discover(self, bearer: str, session_id: str, *, mode="analogical", k=8):
        # MCP content model: structuredContent + text + EmbeddedResource SVG,
        # sourced from the accepted R13B rich path (privacy-authorized).
        return self.product.mcp_rich_discover(bearer, session_id, mode=mode, k=k)

    def get_match(self, bearer: str, result_id: str, session_id: str):
        return self.product.get_match(bearer, result_id, session_id)

    # -- collaboration (R14) ---------------------------------------------
    def request_intro(self, bearer: str, *, from_session_id, target_session_id,
                      message, request_id=None, confirmed=False):
        return self.product.request_intro(
            bearer, from_session_id=from_session_id,
            target_session_id=target_session_id, message=message,
            request_id=request_id, confirmed=confirmed, **_AGENT_CTX)

    def list_requests(self, bearer: str):
        return self.product.list_requests(bearer)

    def respond_intro(self, bearer: str, intro_id: str, *, accept,
                     request_id=None, confirmed=False):
        return self.product.respond_intro(bearer, intro_id, accept=accept,
                                          request_id=request_id, confirmed=confirmed,
                                          **_AGENT_CTX)

    def send_message(self, bearer: str, channel_id: str, body: str, *,
                    request_id=None, confirmed=False):
        return self.product.send_message(bearer, channel_id, body,
                                        request_id=request_id, confirmed=confirmed,
                                        **_AGENT_CTX)

    def read_messages(self, bearer: str, channel_id: str):
        return self.product.read_messages(bearer, channel_id)

    # -- workspaces (R14B) -----------------------------------------------
    def create_workspace(self, bearer: str, intro_id: str, *, title, brief=""):
        return self.product.create_workspace(bearer, intro_id, title=title,
                                             brief=brief, **_AGENT_CTX)

    def get_workspace(self, bearer: str, workspace_id: str):
        return self.product.get_workspace(bearer, workspace_id)

    def list_workspaces(self, bearer: str):
        return self.product.list_my_workspaces(bearer)

    def add_workspace_note(self, bearer: str, workspace_id: str, body: str):
        return self.product.workspace_add_note(bearer, workspace_id, body, **_AGENT_CTX)
