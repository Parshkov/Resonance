"""How concentrated a Resonance corpus is on its exact shapes.

The safeguard in `src/product/shapes.py` sets aside matches that rest on a
skeleton held by a large share of every account on the service. Its thresholds
were set from the one corpus there was to measure -- the R7 demo personas --
and they err permissive, because a real match wrongly set aside is invisible
to everyone. This is the measurement an operator runs on a real corpus before
anyone tightens them:

    python3 ops/shape_census.py var/resonance-pilot.sqlite
    python3 ops/shape_census.py postgresql://...

It prints counts only, over real participants (seeded demo personas are not
people and are not counted). No signature, session, account or label leaves
it, and shapes held by fewer than three accounts are folded into one number,
the same rule the heat map uses, so the output cannot single out one person's
thought.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.persistence.factory import open_repository  # noqa: E402
from src.product.shapes import census_of_repository


def main() -> int:
    target = sys.argv[1] if len(sys.argv) > 1 else None
    repo = open_repository(target)
    try:
        summary = census_of_repository(repo).summary(minimum=3)
    finally:
        repo.close()
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
