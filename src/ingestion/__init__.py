"""R12C private-first Thought DNA ingestion boundary."""

from .service import (
    INGESTION_VERSION,
    ConfirmationError,
    DraftNotFound,
    IngestionError,
    IngestionLimits,
    IngestionService,
    PreparedArtifact,
    ShareCommit,
    ShareIntent,
    ShareSink,
)
from .identity import (
    IdentityIngestionService,
    IngestionAdapter,
    ManualIngestionAdapter,
    RemoteMCPIngestionAdapter,
    WebMCPIngestionAdapter,
)

__all__ = [
    "INGESTION_VERSION",
    "ConfirmationError",
    "DraftNotFound",
    "IngestionError",
    "IngestionLimits",
    "IngestionService",
    "IdentityIngestionService",
    "IngestionAdapter",
    "ManualIngestionAdapter",
    "PreparedArtifact",
    "ShareCommit",
    "ShareIntent",
    "ShareSink",
    "RemoteMCPIngestionAdapter",
    "WebMCPIngestionAdapter",
]
