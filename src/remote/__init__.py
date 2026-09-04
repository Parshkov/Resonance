"""R15: authenticated Streamable HTTP remote MCP over the accepted live product,
with a standards-compatible OAuth 2.1 authorization core (R15A)."""

from .oauth import CodeStore, GrantStore, OAuthCore, OAuthError, OAuthResult
from .server import (PROTOCOL_VERSION, REMOTE_VERSION, TOOLS, RemoteMCP,
                     build_httpd)
from .service import RemoteError, RemoteProductService

__all__ = ["GrantStore", "OAuthCore", "OAuthError", "OAuthResult", "CodeStore",
           "PROTOCOL_VERSION", "REMOTE_VERSION", "TOOLS",
           "RemoteMCP", "build_httpd", "RemoteError", "RemoteProductService"]
