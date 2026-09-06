"""R11 persistence: durable multi-user store behind an internal repository seam.

PostgreSQL is the only backend, everywhere: production, local development and
the test suite, so the store that is tested is the store that ships. `SQLite`
was the second implementation of this protocol and is gone -- it was what 45%
of the suite ran on while production ran the other one. Use `:ephemeral:`
(`factory.open_repository`) for a throwaway schema.

The accepted structural engine remains authoritative. Transport-facing
mutations must pass through the authenticated R12/R12B service, not directly
through this package.
"""

from .errors import (
    PersistenceConflictError,
    PersistenceError,
    PersistenceNotFoundError,
    PersistenceOwnershipError,
    PersistenceStaleIndexError,
    PersistenceStateError,
    PersistenceValidationError,
)
from .models import (
    PERSISTENCE_SCHEMA_VERSION,
    AuditEvent,
    ConsentState,
    IdempotencyKey,
    IdempotencyRecord,
    SessionRecord,
    UserRecord,
)
from .factory import EPHEMERAL, ephemeral_dsn, open_repository
from .postgres_store import PostgresRepository, postgres_available
from .repository import PersistenceRepository
from .service import LiveCorpusService, PersistenceHealth

__all__ = [
    "PERSISTENCE_SCHEMA_VERSION",
    "AuditEvent",
    "ConsentState",
    "IdempotencyKey",
    "IdempotencyRecord",
    "SessionRecord",
    "UserRecord",
    "PersistenceError",
    "PersistenceValidationError",
    "PersistenceStateError",
    "PersistenceNotFoundError",
    "PersistenceConflictError",
    "PersistenceOwnershipError",
    "PersistenceStaleIndexError",
    "PersistenceRepository",
    "LiveCorpusService",
    "PersistenceHealth",
        "PostgresRepository",
    "postgres_available",
]
