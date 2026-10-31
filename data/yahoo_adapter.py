
"""Yahoo Finance historical market-data adapter."""

import pandas as pd
import yfinance as yf

from data.schema import (
    REQUIRED_COLUMNS,
    standardize_ohlcv,
)


SUPPORTED_INTERVALS = {
    "1d",
    "1wk",
    "1mo",
    "5m",
    "15m",
    "30m",
    "60m",
}

OHLCV_COLUMNS = {
    "Open",
    "High",
    "Low",
    "Close",
    "Volume",
}


def resolve_yahoo_symbol(symbol: str, exchange: str) -> str:
    """Convert NSE/BSE symbols into Yahoo Finance ticker format."""

    symbol = symbol.strip().upper()

    if not symbol:
        raise ValueError("Stock symbol must not be empty.")

    if exchange not in {"NSE", "BSE"}:
        raise ValueError("Exchange must be NSE or BSE.")

    if symbol.startswith("^"):
        return symbol

    if symbol.endswith((".NS", ".BO")):
        return symbol

    suffix = ".NS" if exchange == "NSE" else ".BO"

    return symbol + suffix


def normalize_yahoo_columns(data: pd.DataFrame) -> pd.DataFrame:
    """Normalize Yahoo Finance single-level or MultiIndex columns."""

    data = data.copy()

    if not isinstance(data.columns, pd.MultiIndex):
        return data

    for level in range(data.columns.nlevels):
        level_values = set(data.columns.get_level_values(level))

        if OHLCV_COLUMNS.issubset(level_values):
            data.columns = data.columns.get_level_values(level)
            return data

    raise ValueError(
        "Unable to identify OHLCV columns "
        "in Yahoo Finance MultiIndex response."
    )


def fetch_yahoo_history(
    symbol: str,
    start_date,
    end_date,
    interval: str = "1d",
    exchange: str = "NSE",
) -> pd.DataFrame:
    """
    Fetch historical OHLCV data from Yahoo Finance.

    Returns the six canonical columns:
    Date, Open, High, Low, Close, Volume.
    """

    # 1. INPUT VALIDATION

    if not isinstance(symbol, str):
        raise ValueError("Symbol must be a string.")

    symbol = symbol.strip().upper()

    if not symbol:
        raise ValueError("Stock symbol must not be empty.")

    if exchange not in {"NSE", "BSE"}:
        raise ValueError("Exchange must be NSE or BSE.")

    if interval not in SUPPORTED_INTERVALS:
        raise ValueError(
            f"Unsupported interval: {interval}. "
            f"Supported intervals: {sorted(SUPPORTED_INTERVALS)}"
        )

    try:
        start = pd.Timestamp(start_date)
        end = pd.Timestamp(end_date)

    except Exception as error:
        raise ValueError(
            f"Invalid date input: {error}"
        ) from error

    if pd.isna(start) or pd.isna(end):
        raise ValueError("Start date and end date are required.")

    # 2. TIMEZONE NORMALIZATION
    # Convert timezone-aware inputs to UTC-naive timestamps.

    if start.tzinfo is not None:
        start = start.tz_convert("UTC").tz_localize(None)

    if end.tzinfo is not None:
        end = end.tz_convert("UTC").tz_localize(None)

    if start > end:
        raise ValueError(
            "Start date must not be after end date."
        )

    # Yahoo Finance end date is exclusive.
    exclusive_end = end + pd.Timedelta(days=1)

    # 3. SYMBOL RESOLUTION

    ticker = resolve_yahoo_symbol(
        symbol=symbol,
        exchange=exchange,
    )

    # 4. FETCH MARKET DATA

    try:
        data = yf.download(
            ticker,
            start=start.strftime("%Y-%m-%d"),
            end=exclusive_end.strftime("%Y-%m-%d"),
            interval=interval,
            auto_adjust=False,
            progress=False,
            threads=False,
        )

    except Exception as error:
        raise RuntimeError(
            f"Yahoo Finance download failed for {ticker}: {error}"
        ) from error

    if data is None or data.empty:
        raise ValueError(
            f"No Yahoo Finance data returned for {ticker}. "
            "Check symbol, exchange, date range and interval."
        )

    # 5. NORMALIZE YAHOO RESPONSE

    data = normalize_yahoo_columns(data)

    data = data.reset_index()

    data.columns = [
        str(column) for column in data.columns
    ]

    if "Datetime" in data.columns and "Date" not in data.columns:
        data = data.rename(
            columns={"Datetime": "Date"}
        )

    if "Date" not in data.columns:
        raise ValueError(
            "Yahoo Finance response has no Date column."
        )

    # 6. COMMON DATA VALIDATION

    standardized = standardize_ohlcv(
        data=data,
        symbol=symbol,
        source="yahoo",
        exchange=exchange,
        timeframe=interval,
    )

    # Preserve the existing six-column interface.
    result = standardized[REQUIRED_COLUMNS].copy()

    # 7. REQUESTED DATE RANGE VALIDATION

    result = result[
        (result["Date"] >= start)
        & (result["Date"] < exclusive_end)
    ].copy()

    if result.empty:
        raise ValueError(
            "No valid Yahoo Finance rows remain "
            "within the requested date range."
        )

    # 8. FINAL OUTPUT

    return result.reset_index(drop=True)
