
"""Application service integrating validated index data and regime Core."""

from data.market_intelligence.index_service import fetch_index_history
from data.market_data_adapter import NSE_INDEX_SYMBOLS
from core.market_intelligence.regime import analyze_market_regime


SUPPORTED_NSE_INDEXES = dict(NSE_INDEX_SYMBOLS)


def analyze_index_market_regime(
    symbol,
    start_date,
    end_date,
    short_window=50,
    long_window=200,
):
    """Fetch validated NSE index data and run regime analysis."""

    normalized_symbol = str(symbol).strip().upper()

    if normalized_symbol not in NSE_INDEX_SYMBOLS:
        raise ValueError(
            f"Unsupported or unverified NSE index: {normalized_symbol}"
        )

    index_data = fetch_index_history(
        symbol=normalized_symbol,
        start_date=start_date,
        end_date=end_date,
    )

    result = analyze_market_regime(
        index_data=index_data,
        short_window=short_window,
        long_window=long_window,
    )

    result["index_symbol"] = normalized_symbol
    result["index_name"] = NSE_INDEX_SYMBOLS[normalized_symbol]

    return result
  
