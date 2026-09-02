"""R11 persistence: durable multi-user store behind a repository interface.

The accepted structural engine is unchanged. This package stores users,
sessions, validated Thought DNA, consent, coarse location, and audit events.
Only discoverable, validated Thought DNA is ingested into the accepted index.
Display/location metadata never enters retrieval, alignment, or scoring.

SQLite is the always-available durable backend used by tests and the judge
reset path. PostgreSQL is the hosted-pilot backend behind the same interface.
The R7 JSONL corpus remains a deterministic seed/replay fixture only.
"""

from .models import (
    PERSISTENCE_SCHEMA_VERSION,
    AuditEvent,
    ConsentState,
    SessionRecord,
    UserRecord,
)
from .repository import PersistenceRepository
from .service import LiveCorpusService, PersistenceHealth
from .sqlite_store import SQLiteRepository
from .postgres_store import PostgresRepository, postgres_available

__all__ = [
    "PERSISTENCE_SCHEMA_VERSION",
    "AuditEvent",
    "ConsentState",
    "SessionRecord",
    "UserRecord",
    "PersistenceRepository",
    "LiveCorpusService",
    "PersistenceHealth",
    "SQLiteRepository",
    "PostgresRepository",
    "postgres_available",
]
