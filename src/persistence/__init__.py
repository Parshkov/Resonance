"""R11 persistence: durable multi-user store behind an internal repository seam.

SQLite is the deterministic local/judge backend; PostgreSQL is the hosted-pilot
backend. The accepted structural engine remains authoritative. Transport-facing
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
from .postgres_store import PostgresRepository, postgres_available
from .repository import PersistenceRepository
from .service import LiveCorpusService, PersistenceHealth
from .sqlite_store import SQLiteRepository
from .review_hardening import install as _install_review_hardening

# Independent exact-head review found two boundary failures after the original
# recovery fixes. Install the focused guards at package initialization so all
# existing import paths/classes keep their identity while the recovery remains
# a small, auditable delta.
_install_review_hardening()
del _install_review_hardening

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
    "SQLiteRepository",
    "PostgresRepository",
    "postgres_available",
]
