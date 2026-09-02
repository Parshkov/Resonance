"""R15: authenticated Streamable HTTP MCP over the product service seam."""

from .auth import AuthStore
from .server import PROTOCOL_VERSION, REMOTE_VERSION, TOOLS, RemoteMCP, build_httpd
from .service import AuthorizationError, ProductService, RateLimiter

__all__ = ["AuthStore", "PROTOCOL_VERSION", "REMOTE_VERSION", "TOOLS",
           "RemoteMCP", "build_httpd", "AuthorizationError", "ProductService",
           "RateLimiter"]
