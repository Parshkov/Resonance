"""R13 live product boundary.

One authenticated, transport-neutral service composing the accepted layers:
R11 durable corpus, R12 identity/consent (+R12B policy/guards), R12C ingestion,
R8 discovery DTO, and the R10 result_id fidelity pattern. No matching, scoring,
or ranking logic is implemented here.
"""

from .service import (
    LIVE_PRODUCT_CONTRACT,
    LOCATION_NOTE,
    LiveProductService,
    ProductError,
    StaleResultError,
)

__all__ = [
    "LIVE_PRODUCT_CONTRACT",
    "LOCATION_NOTE",
    "LiveProductService",
    "ProductError",
    "StaleResultError",
]
