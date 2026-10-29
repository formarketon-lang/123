
"""Yahoo Finance historical market-data adapter."""

import pandas as pd
import yfinance as yf

from data.schema import REQUIRED_COLUMNS


def fetch_yahoo_history(
    symbol: str,
    start_date,
    end_date,
    interval: str = "1d",
    exchange: str = "NSE",
) -> pd.DataFrame:
    """Fetch historical OHLCV data and validate its basic structure."""

    symbol = symbol.strip().upper()

    if not symbol:
        raise ValueError("Stock symbol must not be empty.")

    if exchange not in {"NSE", "BSE"}:
        raise ValueError("Exchange must be NSE or BSE.")

    if interval not in {"1d", "5m", "15m", "30m", "60m"}:
        raise ValueError("Unsupported data interval.")

    start = pd.Timestamp(start_date)
    end = pd.Timestamp(end_date)

    if start > end:
        raise ValueError("Start date must not be after end date.")

    suffix = ".NS" if exchange == "NSE" else ".BO"
    ticker = symbol if symbol.endswith((".NS", ".BO")) else symbol + suffix

    # yfinance's end date is exclusive, so include the selected end date.
    data = yf.download(
        ticker,
        start=start.strftime("%Y-%m-%d"),
        end=(end + pd.Timedelta(days=1)).strftime("%Y-%m-%d"),
        interval=interval,
        auto_adjust=False,
        progress=False,
        threads=False,
    )

    if data.empty:
        raise ValueError(
            f"No Yahoo Finance data returned for {ticker}. "
            "Check the symbol, exchange, date range and interval."
        )

    # Recent yfinance versions may return MultiIndex columns.
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)

    data = data.reset_index()

    if "Datetime" in data.columns and "Date" not in data.columns:
        data = data.rename(columns={"Datetime": "Date"})

    data.columns = [str(column) for column in data.columns]

    if "Date" not in data.columns:
        raise ValueError("Yahoo Finance response has no Date column.")

    data["Date"] = pd.to_datetime(data["Date"], errors="raise")

    missing = [
        column for column in REQUIRED_COLUMNS
        if column not in data.columns
    ]

    if missing:
        raise ValueError(
            "Yahoo Finance response is missing columns: "
            + ", ".join(missing)
        )

    data = data[REQUIRED_COLUMNS].copy()

    for column in ["Open", "High", "Low", "Close", "Volume"]:
        data[column] = pd.to_numeric(data[column], errors="coerce")

    data = data.dropna(subset=["Date", "Open", "High", "Low", "Close"])
    data = data.sort_values("Date").reset_index(drop=True)

    if data.empty:
        raise ValueError("No valid OHLCV rows remain after validation.")

    return data
  
