"""Run the discovery-enabled MCP server over the deterministic demo corpus.

    python3 -m src.discovery.demo_server
"""

from __future__ import annotations

import json
import sys

from src.mcp.server import MCPServer

from .metadata import ConsentRegistry
from .mcp import TOOLS, DiscoveryAdapter
from .service import DiscoveryService
from .fixtures.demo_corpus import build_engine
from .fixtures.metadata_payload import METADATA_PAYLOAD


def build_service() -> DiscoveryService:
    engine, thought_ids = build_engine()
    payload = json.loads(json.dumps(METADATA_PAYLOAD))
    for record in payload["sessions"]:
        record["session_id"] = thought_ids[record["session_id"]]
    return DiscoveryService(engine, ConsentRegistry.from_payload(payload))


class DiscoveryMCPServer(MCPServer):
    def handle(self, message):
        # identical protocol; only the tools/list payload grows by one
        reply = super().handle(message)
        if (reply and message.get("method") == "tools/list"
                and "result" in reply):
            reply["result"]["tools"] = TOOLS
        return reply


def main() -> int:
    DiscoveryMCPServer(DiscoveryAdapter(build_service())).serve(sys.stdin, sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
