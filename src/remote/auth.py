"""Deprecated shim. The demo-grade PKCE `CodeStore` that lived here is retired;
the canonical OAuth 2.1 core and its grant store now live in `src.remote.oauth`.

`CodeStore` is kept as an alias of `GrantStore` so any lingering import keeps
resolving, but new code should import from `src.remote.oauth` directly.
"""

from __future__ import annotations

from .oauth import CodeStore, GrantStore

__all__ = ["CodeStore", "GrantStore"]
