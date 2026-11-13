"""Validated NSE index history service."""

from __future__ import annotations

import pandas as pd

from data.market_data_adapter import (
    NSE_INDEX_SYMBOLS,
    fetch_market_history,
)


REQUIRED_METADATA = {
    "Date",
    "Open",
    "High",
    "Low",
    "Close",
    "Volume",
    "Symbol",
    "Source",
    "Exchange",
    "Timeframe",
    "Fallback Reason",
    "Fetched At UTC",
    "Validation Status",
}


class IndexDataValidationError(ValueError):
    """Raised when index data fails validation."""


def _single_value(data: pd.DataFrame, column: str) -> str:
    values = data[column].dropna().astype(str).unique()
    if len(values) != 1:
        raise IndexDataValidationError(
            f"{column} must contain exactly one consistent value."
        )
    return values[0]


def validate_index_history(
    data: pd.DataFrame,
    symbol: str,
) -> pd.DataFrame:
    """Validate adapter output without silently repairing it."""

    if symbol not in NSE_INDEX_SYMBOLS:
        raise IndexDataValidationError(
            f"Unmapped NSE index symbol: {symbol}"
        )

    if not isinstance(data, pd.DataFrame) or data.empty:
        raise IndexDataValidationError("Index data is empty or invalid.")

    missing = REQUIRED_METADATA.difference(data.columns)
    if missing:
        raise IndexDataValidationError(
            "Missing required fields: " + ", ".join(sorted(missing))
        )

    result = data.copy()
    result["Date"] = pd.to_datetime(result["Date"], errors="coerce")

    if result["Date"].isna().any():
        raise IndexDataValidationError("Invalid index dates.")

    if result["Date"].duplicated().any():
        raise IndexDataValidationError("Duplicate index dates.")

    result = result.sort_values("Date").reset_index(drop=True)

    for column in ("Open", "High", "Low", "Close"):
        result[column] = pd.to_numeric(
            result[column], errors="coerce"
        )
        if result[column].isna().any():
            raise IndexDataValidationError(
                f"Invalid values in {column}."
            )
        if (result[column] <= 0).any():
            raise IndexDataValidationError(
                f"{column} prices must be positive."
            )

    if (result["High"] < result[
        ["Open", "Low", "Close"]
    ].max(axis=1)).any():
        raise IndexDataValidationError("Invalid High values.")

    if (result["Low"] > result[
        ["Open", "High", "Close"]
    ].min(axis=1)).any():
        raise IndexDataValidationError("Invalid Low values.")

    if _single_value(result, "Symbol").upper() != symbol:
        raise IndexDataValidationError("Symbol mismatch.")

    if _single_value(result, "Exchange").upper() != "NSE":
        raise IndexDataValidationError("Exchange must be NSE.")

    source = _single_value(result, "Source").upper()
    if source not in {"NSE", "YAHOO"}:
        raise IndexDataValidationError("Unsupported data source.")

    if _single_value(result, "Timeframe") != "1d":
        raise IndexDataValidationError("Only daily index data is allowed.")

    if _single_value(result, "Validation Status").upper() != "PASS":
        raise IndexDataValidationError("Data validation did not PASS.")

    fallback_reason = _single_value(result, "Fallback Reason")
    if source == "YAHOO" and not fallback_reason.strip():
        raise IndexDataValidationError(
            "Yahoo fallback requires a recorded reason."
        )

    _single_value(result, "Fetched At UTC")

    return result


def fetch_index_history(
    symbol: str,
    start_date,
    end_date,
) -> pd.DataFrame:
    """Fetch verified NSE index history through the shared adapter."""

    normalized_symbol = str(symbol).strip().upper()

    if normalized_symbol not in NSE_INDEX_SYMBOLS:
        raise IndexDataValidationError(
            f"No verified NSE index mapping for {normalized_symbol}."
        )

    start = pd.Timestamp(start_date)
    end = pd.Timestamp(end_date)

    if pd.isna(start) or pd.isna(end) or start > end:
        raise ValueError("Invalid index date range.")

    data = fetch_market_history(
        symbol=normalized_symbol,
        start_date=start_date,
        end_date=end_date,
        interval="1d",
        exchange="NSE",
    )

    return validate_index_history(data, normalized_symbol)
