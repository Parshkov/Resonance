"""Persistence errors. Fail closed; never skip validation or ownership checks."""


class PersistenceError(RuntimeError):
    """Base persistence failure."""


class PersistenceValidationError(PersistenceError, ValueError):
    """Thought DNA or product-record validation failed."""


class PersistenceStateError(PersistenceError):
    """Requested mutation is illegal in the current record state."""


class PersistenceNotFoundError(PersistenceError, KeyError):
    """Referenced user or session does not exist."""


class PersistenceConflictError(PersistenceStateError):
    """Optimistic version or idempotency conflict."""


class PersistenceOwnershipError(PersistenceConflictError):
    """A stable object identifier cannot be reassigned to a different owner."""


class PersistenceStaleIndexError(PersistenceStateError):
    """Durable DB state is newer than the currently serving discovery index."""
