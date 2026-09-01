"""R6: thin MCP transport over the accepted Resonance engine."""

from .adapter import MCP_ADAPTER_VERSION, TOOLS, ResonanceAdapter
from .server import PROTOCOL_VERSION, MCPServer

__all__ = ["MCP_ADAPTER_VERSION", "TOOLS", "ResonanceAdapter", "MCPServer", "PROTOCOL_VERSION"]
