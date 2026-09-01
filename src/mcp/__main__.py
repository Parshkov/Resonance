"""Allow ``python -m src.mcp`` to launch the stdio server."""

from .server import main

raise SystemExit(main())
