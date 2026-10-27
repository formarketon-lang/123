"""
TradeLab Pro - Common Market Data Schema
Phase 2 | Step 1

Purpose:
- Standardize OHLCV market data
- Normalize column names
- Normalize dates and numeric values
- Attach symbol and source metadata

This module does not fetch live market data.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd


# --------------------------------------------------
# 1. Canonical OHLCV columns
# --------------------------------------------------

OHLCV_COLUMNS = [
    "Open",
    "High",
    "Low",
    "Close",
    "Volume",
]

REQUIRED_COLUMNS = ["Date", *OHLCV_COLUMNS]

SUPPORTED_SOURCES = {
    "yahoo",
    "csv",
    "broker",
    "manual",
    "demo",
    "unknown",
}


# --------------------------------------------------
# 2. Metadata for a standardized dataset
# --------------------------------------------------

@dataclass(frozen=True)
class MarketDataInfo:
    symbol: str
    source: str = "unknown"
    exchange: Optional[str] = None
    timeframe: Optional[str] = None
    currency: Optional[str] = None


# --------------------------------------------------
# 3. Normalize column names
# --------------------------------------------------

def _normalize_column_name(column: object) -> str:
    """Convert common OHLCV column aliases to canonical names."""

    name = str(column).strip().lower()
    name = name.replace("_", " ").replace("-", " ")
    name = " ".join(name.split())

    aliases = {
        "date": "Date",
        "datetime": "Date",
        "timestamp": "Date",
        "time": "Date",
        "open": "Open",
        "high": "High",
        "low": "Low",
        "close": "Close",
        "adj close": "Adj Close",
        "adjusted close": "Adj Close",
        "adjclose": "Adj Close",
        "volume": "Volume",
        "vol": "Volume",
    }

    return aliases.get(name, str(column).strip())


# --------------------------------------------------
# 4. Standardize market data
# --------------------------------------------------

def standardize_ohlcv(
    data: pd.DataFrame,
    symbol: str,
    source: str = "unknown",
    exchange: Optional[str] = None,
    timeframe: Optional[str] = None,
    currency: Optional[str] = None,
    keep_adj_close: bool = False,
) -> pd.DataFrame:
    """
    Return a standardized OHLCV DataFrame.

    Rules:
    - Requires Date, Open, High, Low, Close, Volume.
    - Accepts common column-name variations.
    - Converts dates and numeric columns.
    - Sorts dates in ascending order.
    - Rejects duplicate column names after normalization.
    - Does not silently remove duplicate dates or invalid prices.
    - Does not claim that data is live or exchange-verified.
    """

    if not isinstance(data, pd.DataFrame):
        raise TypeError("data must be a pandas DataFrame.")

    if data.empty:
        raise ValueError("Market data is empty.")

    if not isinstance(symbol, str) or not symbol.strip():
        raise ValueError("A valid stock symbol is required.")

    source = str(source).strip().lower()

    if source not in SUPPORTED_SOURCES:
        raise ValueError(
            f"Unsupported source '{source}'. "
            f"Choose one of: {sorted(SUPPORTED_SOURCES)}"
        )

    df = data.copy()

    # Normalize column names.
    df.columns = [_normalize_column_name(c) for c in df.columns]

    if not df.columns.is_unique:
        raise ValueError(
            "Duplicate column names found after normalization."
        )

    # If Date is absent, allow a DatetimeIndex or a named date index.
    if "Date" not in df.columns:
        index_name = str(df.index.name or "").strip().lower()

        if isinstance(df.index, pd.DatetimeIndex) or index_name in {
            "date", "datetime", "timestamp"
        }:
            df = df.reset_index()
            df.columns = [
                _normalize_column_name(c) for c in df.columns
            ]

    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]

    if missing:
        raise ValueError(
            "Missing required columns: " + ", ".join(missing)
        )

    # Parse dates. Invalid dates are rejected rather than discarded.
    parsed_dates = pd.to_datetime(df["Date"], errors="coerce")

    if parsed_dates.isna().any():
        raise ValueError("Invalid or missing dates found in market data.")

    # Convert timezone-aware dates to timezone-naive timestamps in UTC.
    # This avoids mixing timezone-aware and timezone-naive values.
    try:
        if parsed_dates.dt.tz is not None:
            parsed_dates = (
                parsed_dates.dt.tz_convert("UTC").dt.tz_localize(None)
            )
    except (AttributeError, TypeError, ValueError) as exc:
        raise ValueError(
            "Dates must use a consistent timezone format."
        ) from exc

    df["Date"] = parsed_dates

    # Convert OHLCV values to numeric.
    for column in OHLCV_COLUMNS:
        df[column] = pd.to_numeric(df[column], errors="coerce")

        if df[column].isna().any():
            raise ValueError(
                f"Missing or non-numeric values found in {column}."
            )

    # Basic data sanity checks.
    if (df[["Open", "High", "Low", "Close"]] <= 0).any().any():
        raise ValueError("OHLC prices must be greater than zero.")

    if (df["Volume"] < 0).any():
        raise ValueError("Volume cannot be negative.")

    invalid_high = df["High"] < df[
        ["Open", "Low", "Close"]
    ].max(axis=1)

    invalid_low = df["Low"] > df[
        ["Open", "High", "Close"]
    ].min(axis=1)

    if invalid_high.any() or invalid_low.any():
        raise ValueError("Inconsistent OHLC candle values found.")

    # Preserve the original observation count.
    # Do not silently drop repeated dates.
    if df["Date"].duplicated().any():
        raise ValueError(
            "Duplicate dates found. Resolve duplicate candles "
            "in the adapter before standardization."
        )

    # Sort oldest to newest.
    df = df.sort_values("Date").reset_index(drop=True)

    # Optional adjusted-close field.
    output_columns = REQUIRED_COLUMNS.copy()

    if keep_adj_close and "Adj Close" in df.columns:
        df["Adj Close"] = pd.to_numeric(
            df["Adj Close"], errors="coerce"
        )

        if df["Adj Close"].isna().any():
            raise ValueError("Invalid values found in Adj Close.")

        if (df["Adj Close"] <= 0).any():
            raise ValueError("Adj Close must be greater than zero.")

        output_columns.append("Adj Close")

    df = df[output_columns].copy()

    # Standardized metadata.
    df["Symbol"] = symbol.strip().upper()
    df["Source"] = source

    if exchange:
        df["Exchange"] = exchange.strip().upper()

    if timeframe:
        df["Timeframe"] = timeframe.strip()

    if currency:
        df["Currency"] = currency.strip().upper()

    return df


# --------------------------------------------------
# 5. Create an explicit metadata object
# --------------------------------------------------

def make_market_data_info(
    symbol: str,
    source: str = "unknown",
    exchange: Optional[str] = None,
    timeframe: Optional[str] = None,
    currency: Optional[str] = None,
) -> MarketDataInfo:
    """Create validated, normalized dataset metadata."""

    normalized_source = str(source).strip().lower()

    if normalized_source not in SUPPORTED_SOURCES:
        raise ValueError(
            f"Unsupported source: {normalized_source}"
        )

    if not isinstance(symbol, str) or not symbol.strip():
        raise ValueError("A valid stock symbol is required.")

    return MarketDataInfo(
        symbol=symbol.strip().upper(),
        source=normalized_source,
        exchange=exchange.strip().upper() if exchange else None,
        timeframe=timeframe.strip() if timeframe else None,
        currency=currency.strip().upper() if currency else None,
  )
      
