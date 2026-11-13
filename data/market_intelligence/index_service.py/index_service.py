"""Validated index data service for Market Intelligence."""

import numpy as np
import pandas as pd

from data.market_data_adapter import (
    NSE_INDEX_SYMBOLS,
    fetch_market_history,
)


class MarketIntelligenceDataError(RuntimeError):
    """Raised when index data fails Market Intelligence validation."""


REQUIRED_COLUMNS = {
    "Date",
    "Close",
    "Symbol",
    "Source",
    "Exchange",
    "Timeframe",
    "Fallback Reason",
    "Fetched At UTC",
    "Validation Status",
}


def _single_value(data, column):
    values = data[column].dropna().astype(str).unique()

    if len(values) != 1:
        raise MarketIntelligenceDataError(
            f"Inconsistent {column} metadata."
        )

    return values[0].strip()


def fetch_index_history(
    index_symbol,
    start_date,
    end_date,
    exchange="NSE",
    interval="1d",
):
    """Fetch validated index history through the existing adapter.

    NSE is primary and Yahoo is secondary.
    Only configured NSE index symbols are accepted.
    """

    if not isinstance(index_symbol, str):
        raise MarketIntelligenceDataError(
            "A valid index symbol is required."
        )

    symbol = index_symbol.strip().upper()

    if symbol not in NSE_INDEX_SYMBOLS:
        raise MarketIntelligenceDataError(
            f"Unmapped NSE index is blocked: {symbol}"
        )

    if exchange != "NSE":
        raise MarketIntelligenceDataError(
            "Market Intelligence currently supports NSE only."
        )

    if interval != "1d":
        raise MarketIntelligenceDataError(
            "Only daily index data is supported in this step."
        )

    start = pd.to_datetime(start_date, errors="coerce")
    end = pd.to_datetime(end_date, errors="coerce")

    if pd.isna(start) or pd.isna(end):
        raise MarketIntelligenceDataError(
            "Valid start and end dates are required."
        )

    if start > end:
        raise MarketIntelligenceDataError(
            "Start date cannot be after end date."
        )

    try:
        data = fetch_market_history(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            interval=interval,
            exchange=exchange,
        )
    except Exception as error:
        raise MarketIntelligenceDataError(
            f"Index data unavailable for {symbol}: {error}"
        ) from error

    if not isinstance(data, pd.DataFrame) or data.empty:
        raise MarketIntelligenceDataError(
            "Index data is empty or invalid."
        )

    missing = REQUIRED_COLUMNS.difference(data.columns)

    if missing:
        raise MarketIntelligenceDataError(
            "Missing required metadata: "
            + ", ".join(sorted(missing))
        )

    result = data.copy()

    result["Symbol"] = (
        result["Symbol"].astype("string").str.strip().str.upper()
    )

    if not result["Symbol"].eq(symbol).all():
        raise MarketIntelligenceDataError(
            "Returned index identity does not match the request."
        )

    source = _single_value(result, "Source").upper()
    returned_exchange = _single_value(result, "Exchange").upper()
    timeframe = _single_value(result, "Timeframe")
    status = _single_value(
        result, "Validation Status"
    ).upper()
    fallback_reason = _single_value(
        result, "Fallback Reason"
    )

    if source not in {"NSE", "YAHOO"}:
        raise MarketIntelligenceDataError(
            f"Unsupported data source: {source}"
        )

    if returned_exchange != "NSE":
        raise MarketIntelligenceDataError(
            "Returned data is not from the NSE exchange."
        )

    if timeframe != "1d":
        raise MarketIntelligenceDataError(
            "Returned data timeframe is not daily."
        )

    if status != "PASS":
        raise MarketIntelligenceDataError(
            f"Data validation status is {status}, not PASS."
        )

    if source == "YAHOO" and not fallback_reason:
        raise MarketIntelligenceDataError(
            "Yahoo fallback reason is missing."
        )

    if source == "NSE" and fallback_reason:
        raise MarketIntelligenceDataError(
            "NSE primary data has an unexpected fallback reason."
        )

    result["Date"] = pd.to_datetime(
        result["Date"], errors="coerce"
    )

    if result["Date"].isna().any():
        raise MarketIntelligenceDataError(
            "Invalid observation dates found."
        )

    if result["Date"].duplicated().any():
        raise MarketIntelligenceDataError(
            "Duplicate index observations found."
        )

    result["Close"] = pd.to_numeric(
        result["Close"], errors="coerce"
    )

    close_values = result["Close"].to_numpy(dtype=float)

    if not np.isfinite(close_values).all():
        raise MarketIntelligenceDataError(
            "Invalid index closing prices found."
        )

    if (result["Close"] <= 0).any():
        raise MarketIntelligenceDataError(
            "Index closing prices must be positive."
        )

    fetched_at = pd.to_datetime(
        _single_value(result, "Fetched At UTC"),
        errors="coerce",
        utc=True,
    )

    if pd.isna(fetched_at):
        raise MarketIntelligenceDataError(
            "Invalid data fetch timestamp."
        )

    result = result.sort_values(
        "Date"
    ).reset_index(drop=True)

    result["Source"] = source
    result["Exchange"] = returned_exchange
    result["Validation Status"] = status

    return result
