"""Validated index-based market regime analysis."""

import pandas as pd

from core.validation import normalize_price_data


def _provenance(data):
    source = "UNKNOWN"
    validation_status = "REVIEW"
    fallback_reason = ""

    if "Source" in data.columns:
        values = data["Source"].dropna().astype(str).unique()
        if len(values) == 1:
            source = values[0]

    if "Validation Status" in data.columns:
        values = (
            data["Validation Status"]
            .dropna()
            .astype(str)
            .str.upper()
            .unique()
        )
        if len(values) == 1:
            validation_status = values[0]

    if "Fallback Reason" in data.columns:
        values = (
            data["Fallback Reason"]
            .dropna()
            .astype(str)
            .unique()
        )
        if len(values) == 1:
            fallback_reason = values[0]

    return source, validation_status, fallback_reason


def analyze_market_regime(
    index_data: pd.DataFrame,
    short_window: int = 50,
    long_window: int = 200,
) -> dict:
    """Classify an index using close and moving-average alignment."""

    if not isinstance(index_data, pd.DataFrame):
        raise TypeError("index_data must be a pandas DataFrame.")

    if (
        not isinstance(short_window, int)
        or isinstance(short_window, bool)
        or not isinstance(long_window, int)
        or isinstance(long_window, bool)
        or short_window < 2
        or long_window <= short_window
    ):
        raise ValueError(
            "Windows must be integers: 2 <= short_window < long_window."
        )

    prices = normalize_price_data(index_data, "Index")

    if len(prices) < long_window + 1:
        raise ValueError(
            f"At least {long_window + 1} observations are required."
        )

    close = prices["Close"]
    short_sma = close.rolling(short_window).mean()
    long_sma = close.rolling(long_window).mean()

    latest_close = float(close.iloc[-1])
    latest_short = float(short_sma.iloc[-1])
    latest_long = float(long_sma.iloc[-1])
    previous_long = float(long_sma.iloc[-2])

    if (
        latest_close > latest_short > latest_long
        and latest_long > previous_long
    ):
        regime = "BULLISH"
    elif (
        latest_close < latest_short < latest_long
        and latest_long < previous_long
    ):
        regime = "BEARISH"
    else:
        regime = "NEUTRAL"

    source, validation_status, fallback_reason = _provenance(
        index_data
    )

    analysis_status = (
        "PASS"
        if source.upper() in {"NSE", "YAHOO"}
        and validation_status == "PASS"
        else "REVIEW"
    )

    return {
        "regime": regime,
        "analysis_status": analysis_status,
        "method": "Close + SMA alignment + Long SMA direction",
        "observation_date": prices["Date"].iloc[-1].strftime(
            "%Y-%m-%d"
        ),
        "close": latest_close,
        "short_sma": latest_short,
        "long_sma": latest_long,
        "previous_long_sma": previous_long,
        "source": source,
        "validation_status": validation_status,
        "fallback_reason": fallback_reason,
        "observations": len(prices),
    }
