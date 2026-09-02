"""Persistence errors. Fail closed; never skip validation."""


class PersistenceError(RuntimeError):
    """Base persistence failure."""


class PersistenceValidationError(PersistenceError, ValueError):
    """Thought DNA or product-record validation failed."""


class PersistenceStateError(PersistenceError):
    """Requested mutation is illegal in the current record state."""


class PersistenceNotFoundError(PersistenceError, KeyError):
    """Referenced user or session does not exist."""
