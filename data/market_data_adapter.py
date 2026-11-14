"""NSE Primary and Yahoo Secondary market-data adapter."""

import numpy as np
import pandas as pd

from data.providers.nse_downloader import download_equity_history
from data.providers.nse_index_downloader import download_index_history
from data.yahoo_adapter import fetch_yahoo_history
from data.schema import standardize_ohlcv
from data.provenance import attach_data_provenance


NSE_INDEX_SYMBOLS = {
    "^NSEI": "NIFTY 50",
    "^NSMIDCP": "NIFTY NEXT 50",
    "^CNX100": "NIFTY 100",
    "^CNX200": "NIFTY 200",
    "^CRSLDX": "NIFTY 500",
    "^CNXFMCG": "NIFTY FMCG",
}


class MarketDataUnavailableError(RuntimeError):
    """Both primary and secondary market-data sources failed."""


def _standardize_adapter_result(
    data,
    symbol,
    source,
    exchange,
    interval,
    instrument_type,
    fallback_reason="",
    fetched_at_utc=None,
):
    """Apply common schema and attach provenance metadata."""

    standardized = standardize_ohlcv(
        data=data,
        symbol=symbol,
        source=source,
        exchange=exchange,
        timeframe=interval,
        instrument_type=instrument_type,
    )

    standardized["Source"] = source
    standardized["Exchange"] = exchange
    standardized["Timeframe"] = interval
    standardized["Fallback Reason"] = fallback_reason

    return attach_data_provenance(
        data=standardized,
        symbol=symbol,
        source=source,
        exchange=exchange,
        timeframe=interval,
        fallback_reason=fallback_reason,
        validation_status="PASS",
        fetched_at_utc=fetched_at_utc,
    )


def _validate_nse_data(data, symbol, is_index):
    """Validate NSE data through the common schema."""

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

    fetched_at_utc = data.attrs.get("fetched_at_utc")
    result = data.copy()
    result["Date"] = pd.to_datetime(result["Date"], errors="coerce")

    if result["Date"].isna().any():
        raise ValueError("NSE data contains invalid trading dates.")

    if result["Date"].duplicated().any():
        raise ValueError("NSE data contains duplicate trading dates.")

    for column in ["Open", "High", "Low", "Close"]:
        result[column] = pd.to_numeric(result[column], errors="coerce")
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
        raise ValueError(
            "NSE data contains Inconsistent OHLC candle values."
        )

    if "Volume" in result.columns:
        original_volume = result["Volume"].copy()
        result["Volume"] = pd.to_numeric(
            result["Volume"], errors="coerce"
        )

        invalid_volume = (
            original_volume.notna() & result["Volume"].isna()
        )

        if invalid_volume.any():
            raise ValueError("NSE data contains invalid Volume values.")

        if not is_index and result["Volume"].isna().any():
            raise ValueError("NSE equity data contains missing Volume.")

        if (result["Volume"].dropna() < 0).any():
            raise ValueError("NSE Volume cannot be negative.")

    elif is_index:
        result["Volume"] = pd.NA

    return _standardize_adapter_result(
        data=result,
        symbol=symbol,
        source="NSE",
        exchange="NSE",
        interval="1d",
        instrument_type="index" if is_index else "equity",
        fetched_at_utc=fetched_at_utc,
    )


def _add_yahoo_metadata(data, symbol, exchange, interval, reason, fetched_at_utc):
    """Validate Yahoo data and attach fallback provenance."""

    if not isinstance(data, pd.DataFrame) or data.empty:
        raise ValueError("Yahoo returned empty market data.")

    return _standardize_adapter_result(
        data=data,
        symbol=symbol,
        source="Yahoo",
        exchange=exchange,
        interval=interval,
        instrument_type="index" if symbol.startswith("^") else "equity",
        fallback_reason=reason,
        fetched_at_utc=fetched_at_utc,
    )


def fetch_market_history(
    symbol,
    start_date,
    end_date,
    interval="1d",
    exchange="NSE",
):
    """
    Fetch data using NSE Primary and Yahoo Secondary.

    BSE scanning remains disabled.
    Unknown index symbols are rejected before fallback.
    """

    if not isinstance(symbol, str) or not symbol.strip():
        raise ValueError("A valid market symbol is required.")

    symbol = symbol.strip().upper()

    if exchange != "NSE":
        raise ValueError(
            "This market-data adapter currently supports NSE only. "
            "BSE scanning remains disabled."
        )

    # An unknown index must never bypass the verified mapping
    # through Yahoo fallback.
    if symbol.startswith("^") and symbol not in NSE_INDEX_SYMBOLS:
        raise ValueError(
            f"No verified NSE index mapping exists for {symbol}. "
            "Yahoo fallback is not permitted for unmapped indices."
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
                index_name = NSE_INDEX_SYMBOLS[symbol]

                raw_data = download_index_history(
                    index_name, start_text, end_text
                )

                return _validate_nse_data(
                    raw_data, symbol, is_index=True
                )

            raw_data = download_equity_history(
                symbol, start_text, end_text
            )

            return _validate_nse_data(
                raw_data, symbol, is_index=False
            )

        except Exception as error:
            primary_error = f"{type(error).__name__}: {error}"

    else:
        primary_error = (
            f"NSE Primary does not support interval {interval}."
        )

    try:
        yahoo_data = fetch_yahoo_history(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            interval=interval,
            exchange=exchange,
        )

        yahoo_fetched_at_utc = pd.Timestamp.now(tz="UTC").isoformat().replace("+00:00", "Z")
        return _add_yahoo_metadata(
            yahoo_data,
            symbol,
            exchange,
            interval,
            primary_error,
            yahoo_fetched_at_utc,
        )

    except Exception as yahoo_error:
        raise MarketDataUnavailableError(
            f"Market data unavailable for {symbol}. "
            f"NSE Primary failed: {primary_error}. "
            f"Yahoo Secondary failed: "
            f"{type(yahoo_error).__name__}: {yahoo_error}"
        ) from yahoo_error
    
