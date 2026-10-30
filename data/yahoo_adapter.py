"""Yahoo Finance historical market-data adapter."""

import pandas as pd
import yfinance as yf

from data.schema import REQUIRED_COLUMNS


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

    # Index symbols must remain unchanged.
    if symbol.startswith("^"):
        return symbol

    # Already formatted symbols must not receive another suffix.
    if symbol.endswith((".NS", ".BO")):
        return symbol

    suffix = ".NS" if exchange == "NSE" else ".BO"

    return symbol + suffix


def normalize_yahoo_columns(data: pd.DataFrame) -> pd.DataFrame:
    """Normalize Yahoo Finance single-level or MultiIndex columns."""

    if not isinstance(data.columns, pd.MultiIndex):
        return data

    for level in range(data.columns.nlevels):

        level_values = set(
            data.columns.get_level_values(level)
        )

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

    Supported:
        Daily:   1d
        Weekly:  1wk
        Monthly: 1mo
        Intraday: 5m, 15m, 30m, 60m
    """

    # -----------------------------------------------------
    # 1. INPUT VALIDATION
    # -----------------------------------------------------

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

    if start > end:
        raise ValueError(
            "Start date must not be after end date."
        )

    # -----------------------------------------------------
    # 2. SYMBOL RESOLUTION
    # -----------------------------------------------------

    ticker = resolve_yahoo_symbol(
        symbol=symbol,
        exchange=exchange,
    )

    # Yahoo Finance end date is exclusive.
    exclusive_end = end + pd.Timedelta(days=1)

    # -----------------------------------------------------
    # 3. FETCH MARKET DATA
    # -----------------------------------------------------

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

    # -----------------------------------------------------
    # 4. NORMALIZE DATA STRUCTURE
    # -----------------------------------------------------

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

    # -----------------------------------------------------
    # 5. REQUIRED COLUMN VALIDATION
    # -----------------------------------------------------

    missing = [
        column
        for column in REQUIRED_COLUMNS
        if column not in data.columns
    ]

    if missing:

        raise ValueError(
            "Yahoo Finance response is missing columns: "
            + ", ".join(missing)
        )

    data = data[REQUIRED_COLUMNS].copy()

    # -----------------------------------------------------
    # 6. DATA TYPE VALIDATION
    # -----------------------------------------------------

    data["Date"] = pd.to_datetime(
        data["Date"],
        errors="coerce",
    )

    # Remove timezone without changing local timestamp.
    if data["Date"].dt.tz is not None:

        data["Date"] = data["Date"].dt.tz_localize(None)

    numeric_columns = [
        "Open",
        "High",
        "Low",
        "Close",
        "Volume",
    ]

    for column in numeric_columns:

        data[column] = pd.to_numeric(
            data[column],
            errors="coerce",
        )

    # -----------------------------------------------------
    # 7. DATA CLEANING
    # -----------------------------------------------------

    data = data.dropna(
        subset=REQUIRED_COLUMNS
    )

    data = data.drop_duplicates(
        subset=["Date"],
        keep="last",
    )

    data = data.sort_values(
        "Date"
    ).reset_index(drop=True)

    if data.empty:

        raise ValueError(
            "No valid OHLCV rows remain after validation."
        )

    # -----------------------------------------------------
    # 8. FINAL VALIDATION
    # -----------------------------------------------------

    invalid_prices = (
        (data["Open"] <= 0)
        | (data["High"] <= 0)
        | (data["Low"] <= 0)
        | (data["Close"] <= 0)
    )

    if invalid_prices.any():

        raise ValueError(
            "Invalid non-positive OHLC prices detected."
        )

    if (data["Volume"] < 0).any():

        raise ValueError(
            "Negative Volume values detected."
        )

    if (data["High"] < data["Low"]).any():

        raise ValueError(
            "Invalid OHLC data: High is below Low."
        )

    return data
