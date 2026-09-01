"""R8: visualization-ready resonance discovery over the accepted engine."""

from .metadata import METADATA_SCHEMA_VERSION, ConsentRegistry, SessionProfile
from .service import DISCOVERY_CONTRACT_VERSION, DiscoveryService

__all__ = ["METADATA_SCHEMA_VERSION", "ConsentRegistry", "SessionProfile",
           "DISCOVERY_CONTRACT_VERSION", "DiscoveryService"]
