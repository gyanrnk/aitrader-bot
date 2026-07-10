"""24/7 market-data collector. Builds YOUR OWN point-in-time dataset (price, funding,
open interest) that isn't freely downloadable as history — the one real data edge
retail can build, and the foundation for honest forward-testing."""
from .snapshot import fetch_snapshot, FIELDS

__all__ = ["fetch_snapshot", "FIELDS"]
