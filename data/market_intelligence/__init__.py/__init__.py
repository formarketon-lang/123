"""Market Intelligence data services."""

from data.market_intelligence.index_service import (
    MarketIntelligenceDataError,
    fetch_index_history,
)

__all__ = [
    "MarketIntelligenceDataError",
    "fetch_index_history",
]
