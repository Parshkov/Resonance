"""Remote MCP: canonical OAuth 2.1 core (R15A) plus a thin factory over the
product server. The tool vocabulary lives in `src.product.mcp_bridge`."""

from .oauth import CodeStore, GrantStore, OAuthCore, OAuthError, OAuthResult
from .server import build_httpd

__all__ = ["GrantStore", "OAuthCore", "OAuthError", "OAuthResult", "CodeStore", "build_httpd"]
