
"""
TradeLab Pro - Common Market Data Schema

Purpose:
- Standardize OHLCV market data.
- Normalize column names, dates and numeric values.
- Support NSE and other approved data sources.
- Keep Equity and Index Volume validation distinct.

This module does not fetch live market data.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd


OHLCV_COLUMNS = ["Open", "High", "Low", "Close", "Volume"]
REQUIRED_COLUMNS = ["Date", *OHLCV_COLUMNS]

SUPPORTED_SOURCES = {
    "nse",
    "yahoo",
    "csv",
    "broker",
    "manual",
    "demo",
    "unknown",
}


@dataclass(frozen=True)
class MarketDataInfo:
    symbol: str
    source: str = "unknown"
    exchange: Optional[str] = None
    timeframe: Optional[str] = None
    currency: Optional[str] = None


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


def standardize_ohlcv(
    data: pd.DataFrame,
    symbol: str,
    source: str = "unknown",
    exchange: Optional[str] = None,
    timeframe: Optional[str] = None,
    currency: Optional[str] = None,
    keep_adj_close: bool = False,
    instrument_type: str = "equity",
) -> pd.DataFrame:
    """
    Return standardized market data.

    Equity:
    - Date, OHLC and Volume are mandatory.
    - Volume must be numeric and non-negative.

    Index:
    - Date and OHLC are mandatory.
    - Volume may be absent because many index feeds do not publish it.
    - Missing index Volume is represented as nullable NA, never fabricated.
    """

    if not isinstance(data, pd.DataFrame):
        raise TypeError("data must be a pandas DataFrame.")

    if data.empty:
        raise ValueError("Market data is empty.")

    if not isinstance(symbol, str) or not symbol.strip():
        raise ValueError("A valid stock symbol is required.")

    normalized_source = str(source).strip().lower()
    if normalized_source not in SUPPORTED_SOURCES:
        raise ValueError(
            f"Unsupported source '{normalized_source}'. "
            f"Choose one of: {sorted(SUPPORTED_SOURCES)}"
        )

    normalized_type = str(instrument_type).strip().lower()
    if normalized_type not in {"equity", "index"}:
        raise ValueError(
            "instrument_type must be either 'equity' or 'index'."
        )

    df = data.copy()
    df.columns = [_normalize_column_name(c) for c in df.columns]

    if not df.columns.is_unique:
        raise ValueError(
            "Duplicate column names found after normalization."
        )

    if "Date" not in df.columns:
        index_name = str(df.index.name or "").strip().lower()
        if isinstance(df.index, pd.DatetimeIndex) or index_name in {
            "date", "datetime", "timestamp"
        }:
            df = df.reset_index()
            df.columns = [_normalize_column_name(c) for c in df.columns]

    required = ["Date", "Open", "High", "Low", "Close"]
    if normalized_type == "equity":
        required.append("Volume")

    missing = [column for column in required if column not in df.columns]
    if missing:
        raise ValueError(
            "Missing required columns: " + ", ".join(missing)
        )

    parsed_dates = pd.to_datetime(df["Date"], errors="coerce")
    if parsed_dates.isna().any():
        raise ValueError("Invalid or missing dates found in market data.")

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

    price_columns = ["Open", "High", "Low", "Close"]
    for column in price_columns:
        df[column] = pd.to_numeric(df[column], errors="coerce")
        if df[column].isna().any():
            raise ValueError(
                f"Missing or non-numeric values found in {column}."
            )

    if normalized_type == "equity":
        df["Volume"] = pd.to_numeric(df["Volume"], errors="coerce")
        if df["Volume"].isna().any():
            raise ValueError(
                "Missing or non-numeric values found in Volume."
            )
    elif "Volume" not in df.columns:
        df["Volume"] = pd.Series(
            pd.NA,
            index=df.index,
            dtype="Float64",
        )
    else:
        df["Volume"] = pd.to_numeric(df["Volume"], errors="coerce")
        if df["Volume"].isna().any():
            raise ValueError(
                "Index Volume must be either fully available or absent."
            )

    if (df[price_columns] <= 0).any().any():
        raise ValueError("OHLC prices must be greater than zero.")

    if df["Volume"].notna().any() and (df["Volume"].dropna() < 0).any():
        raise ValueError("Volume cannot be negative.")

    invalid_high = df["High"] < df[
        ["Open", "Low", "Close"]
    ].max(axis=1)

    invalid_low = df["Low"] > df[
        ["Open", "High", "Close"]
    ].min(axis=1)

    if invalid_high.any() or invalid_low.any():
        raise ValueError("Inconsistent OHLC candle values found.")

    if df["Date"].duplicated().any():
        raise ValueError(
            "Duplicate dates found. Resolve duplicate candles "
            "in the adapter before standardization."
        )

    df = df.sort_values("Date").reset_index(drop=True)

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
    df["Symbol"] = symbol.strip().upper()
    df["Source"] = normalized_source

    if exchange:
        df["Exchange"] = exchange.strip().upper()
    if timeframe:
        df["Timeframe"] = timeframe.strip()
    if currency:
        df["Currency"] = currency.strip().upper()

    return df


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
        raise ValueError(f"Unsupported source: {normalized_source}")

    if not isinstance(symbol, str) or not symbol.strip():
        raise ValueError("A valid stock symbol is required.")

    return MarketDataInfo(
        symbol=symbol.strip().upper(),
        source=normalized_source,
        exchange=exchange.strip().upper() if exchange else None,
        timeframe=timeframe.strip() if timeframe else None,
        currency=currency.strip().upper() if currency else None,
    )
    
