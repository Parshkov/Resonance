"""Thought DNA schema-version policy."""

SCHEMA_VERSION = "thought-dna/0.1"
SUPPORTED_SCHEMA_VERSIONS = frozenset({SCHEMA_VERSION})


class MigrationRequired(ValueError):
    """Raised when an object uses a schema version this runtime cannot consume."""


def ensure_supported_version(version: object) -> str:
    if not isinstance(version, str) or not version:
        raise MigrationRequired("schema_version is required and must be a non-empty string")
    if version not in SUPPORTED_SCHEMA_VERSIONS:
        supported = ", ".join(sorted(SUPPORTED_SCHEMA_VERSIONS))
        raise MigrationRequired(
            f"unsupported schema_version {version!r}; supported: {supported}. "
            "Version changes require an explicit migration rather than silent coercion."
        )
    return version


def migration_path(from_version: str, to_version: str = SCHEMA_VERSION) -> tuple[str, ...]:
    """Return the explicit migration path.

    v0.1 is the first executable schema, so there are no migrations yet.
    """
    if from_version == to_version == SCHEMA_VERSION:
        return ()
    raise MigrationRequired(
        f"no migration is registered from {from_version!r} to {to_version!r}"
    )
