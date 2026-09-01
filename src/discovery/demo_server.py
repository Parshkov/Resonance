"""Discovery-enabled MCP server over the ACCEPTED R7 demo corpus.

    python3 -m src.discovery.demo_server
"""

from __future__ import annotations

import sys

from src.mcp.server import MCPServer

from .fixtures.r7_corpus import build
from .mcp import TOOLS, DiscoveryAdapter
from .service import DiscoveryService


def build_service() -> DiscoveryService:
    engine, registry, _by_session = build()
    return DiscoveryService(engine, registry)


class DiscoveryMCPServer(MCPServer):
    def handle(self, message):
        reply = super().handle(message)
        if (reply and message.get("method") == "tools/list" and "result" in reply):
            reply["result"]["tools"] = TOOLS
        return reply


def main() -> int:
    DiscoveryMCPServer(DiscoveryAdapter(build_service())).serve(sys.stdin, sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
