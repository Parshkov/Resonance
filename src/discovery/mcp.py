"""MCP exposure decision (issue #73 asked for it documented):

We add ONE tool -- `discover_resonance` -- because the acceptance gate needs a
single clean-client call returning the visualization-ready response.
`request_intro` remains a service capability with tests and audit but is NOT
exposed in v0.1: the smallest additive surface wins until R9's UX actually
wires the button, at which point exposure is one schema + three lines here.

Fully additive: the accepted R6 adapter/server are subclassed, not modified;
the six accepted tools (plus snapshot tools) are inherited byte-identical.
"""

from __future__ import annotations

from typing import Any

from src.graph import ThoughtGraph
from src.mcp.adapter import TOOLS as BASE_TOOLS, ResonanceAdapter

from .service import DiscoveryService

DISCOVER_TOOL = {
    "name": "discover_resonance",
    "description": "Visualization-ready discovery: consented matches for a "
                   "Thought with scores, evidence, display metadata, "
                   "engine-rejected correspondences surfaced separately, and "
                   "leak-safe map aggregation.",
    "inputSchema": {"type": "object", "required": ["thought", "mode"],
                    "properties": {"thought": {"type": "object"},
                                   "mode": {"type": "string",
                                            "enum": ["structural", "analogical",
                                                     "complementary"]},
                                   "k": {"type": "integer", "minimum": 1,
                                         "default": 8}},
                    "additionalProperties": False},
}

TOOLS: list[dict[str, Any]] = BASE_TOOLS + [DISCOVER_TOOL]


class DiscoveryAdapter(ResonanceAdapter):
    """Accepted adapter + one read-model tool over the discovery service."""

    def __init__(self, discovery: DiscoveryService):
        super().__init__(discovery.engine)
        self.discovery = discovery

    def discover_resonance(self, *, thought: dict, mode: str, k: int = 8) -> dict:
        graph = ThoughtGraph.from_dict(thought)
        response = self.discovery.discover(graph, mode=mode, k=k)
        return {**response, "metadata": self.metadata()}

    def dispatch(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if name == "discover_resonance":
            return self.discover_resonance(**arguments)
        return super().dispatch(name, arguments)
