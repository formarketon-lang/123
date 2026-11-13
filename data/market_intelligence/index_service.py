
"""Validated NSE index history service."""

from __future__ import annotations

import math
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


def _single_value(
    data: pd.DataFrame,
    column: str,
    allow_empty: bool = False,
) -> str:
    values = (
        data[column]
        .dropna()
        .astype("string")
        .str.strip()
        .unique()
    )

    if len(values) != 1:
        raise IndexDataValidationError(
            f"{column} must contain exactly one consistent value."
        )

    value = str(values[0]).strip()

    if not value and not allow_empty:
        raise IndexDataValidationError(
            f"{column} must contain a non-empty value."
        )

    return value


def _validate_fetched_at_utc(value: str) -> None:
    """Require one valid timezone-aware fetch timestamp."""

    try:
        timestamp = pd.Timestamp(value)
    except (TypeError, ValueError, OverflowError):
        raise IndexDataValidationError(
            "Fetched At UTC must be a valid timestamp."
        )

    if pd.isna(timestamp) or timestamp.tzinfo is None:
        raise IndexDataValidationError(
            "Fetched At UTC must include a timezone."
        )


def validate_index_history(
    data: pd.DataFrame,
    symbol: str,
) -> pd.DataFrame:
    """Validate adapter output without silently repairing it."""

    normalized_symbol = str(symbol).strip().upper()

    if normalized_symbol not in NSE_INDEX_SYMBOLS:
        raise IndexDataValidationError(
            f"Unmapped NSE index symbol: {normalized_symbol}"
        )

    if not isinstance(data, pd.DataFrame) or data.empty:
        raise IndexDataValidationError(
            "Index data is empty or invalid."
        )

    missing = REQUIRED_METADATA.difference(data.columns)

    if missing:
        raise IndexDataValidationError(
            "Missing required fields: "
            + ", ".join(sorted(missing))
        )

    result = data.copy()

    try:
        result["Date"] = pd.to_datetime(
            result["Date"],
            errors="coerce",
        )
    except (TypeError, ValueError, OverflowError):
        raise IndexDataValidationError("Invalid index dates.")

    if result["Date"].isna().any():
        raise IndexDataValidationError("Invalid index dates.")

    if result["Date"].duplicated().any():
        raise IndexDataValidationError("Duplicate index dates.")

    if not result["Date"].is_monotonic_increasing:
        raise IndexDataValidationError(
            "Index dates must already be in ascending order."
        )

    for column in ("Open", "High", "Low", "Close"):
        result[column] = pd.to_numeric(
            result[column],
            errors="coerce",
        )

        if result[column].isna().any():
            raise IndexDataValidationError(
                f"Invalid values in {column}."
            )

        if not result[column].map(
            lambda value: math.isfinite(float(value))
        ).all():
            raise IndexDataValidationError(
                f"{column} values must be finite."
            )

        if (result[column] <= 0).any():
            raise IndexDataValidationError(
                f"{column} prices must be positive."
            )

    if (
        result["High"]
        < result[["Open", "Low", "Close"]].max(axis=1)
    ).any():
        raise IndexDataValidationError("Invalid High values.")

    if (
        result["Low"]
        > result[["Open", "High", "Close"]].min(axis=1)
    ).any():
        raise IndexDataValidationError("Invalid Low values.")

    raw_volume = result["Volume"]
    numeric_volume = pd.to_numeric(
        raw_volume,
        errors="coerce",
    )

    invalid_volume = raw_volume.notna() & numeric_volume.isna()

    if invalid_volume.any():
        raise IndexDataValidationError("Invalid Volume values.")

    non_null_volume = numeric_volume.dropna()

    if not non_null_volume.map(
        lambda value: math.isfinite(float(value))
    ).all():
        raise IndexDataValidationError(
            "Volume values must be finite."
        )

    if (non_null_volume < 0).any():
        raise IndexDataValidationError(
            "Volume values cannot be negative."
        )

    result["Volume"] = numeric_volume

    if (
        _single_value(result, "Symbol").upper()
        != normalized_symbol
    ):
        raise IndexDataValidationError("Symbol mismatch.")

    if _single_value(result, "Exchange").upper() != "NSE":
        raise IndexDataValidationError(
            "Exchange must be NSE."
        )

    source = _single_value(result, "Source").upper()

    if source not in {"NSE", "YAHOO"}:
        raise IndexDataValidationError(
            "Unsupported data source."
        )

    if _single_value(result, "Timeframe").lower() != "1d":
        raise IndexDataValidationError(
            "Only daily index data is allowed."
        )

    if (
        _single_value(result, "Validation Status").upper()
        != "PASS"
    ):
        raise IndexDataValidationError(
            "Data validation did not PASS."
        )

    fallback_reason = _single_value(
        result,
        "Fallback Reason",
        allow_empty=True,
    )

    if source == "YAHOO" and not fallback_reason:
        raise IndexDataValidationError(
            "Yahoo fallback requires a recorded reason."
        )

    fetched_at = _single_value(result, "Fetched At UTC")
    _validate_fetched_at_utc(fetched_at)

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

    try:
        start = pd.Timestamp(start_date)
        end = pd.Timestamp(end_date)
    except (TypeError, ValueError, OverflowError):
        raise ValueError("Invalid index date range.")

    if pd.isna(start) or pd.isna(end) or start > end:
        raise ValueError("Invalid index date range.")

    data = fetch_market_history(
        symbol=normalized_symbol,
        start_date=start_date,
        end_date=end_date,
        interval="1d",
        exchange="NSE",
    )

    return validate_index_history(
        data,
        normalized_symbol,
    )
