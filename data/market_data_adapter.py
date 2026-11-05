
"""NSE Primary and Yahoo Secondary market-data adapter."""

import numpy as np
import pandas as pd

from data.providers.nse_downloader import download_equity_history
from data.providers.nse_index_downloader import download_index_history
from data.yahoo_adapter import fetch_yahoo_history


# Only index mappings supported by the current NSE downloader.
NSE_INDEX_SYMBOLS = {
    "^NSEI": "NIFTY 50",
    "^CNXFMCG": "NIFTY FMCG",
}


class MarketDataUnavailableError(RuntimeError):
    """Both primary and secondary market-data sources failed."""


def _validate_nse_data(data, symbol, is_index):
    """Validate NSE OHLCV data without dropping observations."""

    if not isinstance(data, pd.DataFrame) or data.empty:
        raise ValueError("NSE returned empty or invalid market data.")

    required = {"Date", "Open", "High", "Low", "Close"}

    if not is_index:
        required.add("Volume")

    missing = required.difference(data.columns)

    if missing:
        raise ValueError(
            "NSE data is missing required columns: "
            + ", ".join(sorted(missing))
        )

    result = data.copy()

    result["Date"] = pd.to_datetime(
        result["Date"],
        errors="coerce",
    )

    if result["Date"].isna().any():
        raise ValueError("NSE data contains invalid trading dates.")

    if result["Date"].duplicated().any():
        raise ValueError("NSE data contains duplicate trading dates.")

    for column in ["Open", "High", "Low", "Close"]:
        result[column] = pd.to_numeric(
            result[column],
            errors="coerce",
        )

        values = result[column].to_numpy(dtype=float)

        if not np.isfinite(values).all():
            raise ValueError(
                f"NSE data contains invalid values in {column}."
            )

        if (result[column] <= 0).any():
            raise ValueError(
                f"NSE {column} prices must be greater than zero."
            )

    invalid_high = result["High"] < result[
        ["Open", "Low", "Close"]
    ].max(axis=1)

    invalid_low = result["Low"] > result[
        ["Open", "High", "Close"]
    ].min(axis=1)

    if invalid_high.any() or invalid_low.any():
        raise ValueError("NSE data contains inconsistent OHLC candles.")

    if "Volume" not in result.columns:
        result["Volume"] = pd.NA
    else:
        original_volume = result["Volume"].copy()

        result["Volume"] = pd.to_numeric(
            result["Volume"],
            errors="coerce",
        )

        invalid_volume = (
            original_volume.notna()
            & result["Volume"].isna()
        )

        if invalid_volume.any():
            raise ValueError("NSE data contains invalid Volume values.")

        if not is_index and result["Volume"].isna().any():
            raise ValueError("NSE equity data contains missing Volume.")

        if (result["Volume"].dropna() < 0).any():
            raise ValueError("NSE Volume cannot be negative.")

    result = result[
        ["Date", "Open", "High", "Low", "Close", "Volume"]
    ].copy()

    result = result.sort_values("Date").reset_index(drop=True)

    result["Symbol"] = symbol.upper()
    result["Source"] = "NSE"
    result["Exchange"] = "NSE"
    result["Timeframe"] = "1d"
    result["Fallback Reason"] = ""

    return result


def _add_yahoo_metadata(data, symbol, exchange, interval, reason):
    """Attach Yahoo source and fallback metadata."""

    if not isinstance(data, pd.DataFrame) or data.empty:
        raise ValueError("Yahoo returned empty market data.")

    result = data.copy()

    result["Symbol"] = symbol.upper()
    result["Source"] = "Yahoo"
    result["Exchange"] = exchange
    result["Timeframe"] = interval
    result["Fallback Reason"] = reason

    return result


def fetch_market_history(
    symbol,
    start_date,
    end_date,
    interval="1d",
    exchange="NSE",
):
    """
    Fetch data using NSE Primary and Yahoo Secondary.

    Supported NSE primary data:
    - NSE equity symbols
    - NIFTY 50
    - NIFTY FMCG

    Unsupported NSE indexes use Yahoo Secondary.
    BSE is rejected.
    """

    if not isinstance(symbol, str) or not symbol.strip():
        raise ValueError("A valid market symbol is required.")

    symbol = symbol.strip().upper()

    if exchange != "NSE":
        raise ValueError(
            "This market-data adapter currently supports NSE only. "
            "BSE scanning remains disabled."
        )

    start = pd.Timestamp(start_date)
    end = pd.Timestamp(end_date)

    if pd.isna(start) or pd.isna(end):
        raise ValueError("Valid start and end dates are required.")

    if start > end:
        raise ValueError("Start date cannot be after end date.")

    primary_error = None

    if interval == "1d":
        try:
            start_text = start.strftime("%Y-%m-%d")
            end_text = end.strftime("%Y-%m-%d")

            if symbol.startswith("^"):
                index_name = NSE_INDEX_SYMBOLS.get(symbol)

                if index_name is None:
                    raise ValueError(
                        f"No verified NSE index mapping exists for "
                        f"{symbol}."
                    )

                raw_data = download_index_history(
                    index_name,
                    start_text,
                    end_text,
                )

                return _validate_nse_data(
                    raw_data,
                    symbol,
                    is_index=True,
                )

            raw_data = download_equity_history(
                symbol,
                start_text,
                end_text,
            )

            return _validate_nse_data(
                raw_data,
                symbol,
                is_index=False,
            )

        except Exception as error:
            primary_error = (
                f"{type(error).__name__}: {error}"
            )

    else:
        primary_error = (
            f"NSE Primary does not support interval {interval}."
        )

    # Secondary source: Yahoo Finance.
    try:
        yahoo_data = fetch_yahoo_history(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            interval=interval,
            exchange=exchange,
        )

        return _add_yahoo_metadata(
            yahoo_data,
            symbol,
            exchange,
            interval,
            primary_error,
        )

    except Exception as yahoo_error:
        raise MarketDataUnavailableError(
            f"Market data unavailable for {symbol}. "
            f"NSE Primary failed: {primary_error}. "
            f"Yahoo Secondary failed: "
            f"{type(yahoo_error).__name__}: {yahoo_error}"
        ) from yahoo_error
  
