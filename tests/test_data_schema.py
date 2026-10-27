
import pandas as pd
import pytest

from data.schema import (
    standardize_ohlcv,
    make_market_data_info,
)


def sample_data():
    return pd.DataFrame({
        "date": ["2026-10-26", "2026-10-23"],
        "open": [2420, 2400],
        "high": [2450, 2430],
        "low": [2410, 2390],
        "close": [2440, 2420],
        "volume": [180000, 150000],
    })


def test_standardize_columns_and_sort_dates():
    result = standardize_ohlcv(
        sample_data(),
        symbol="hindunilvr",
        source="csv",
    )

    assert list(result["Date"].dt.strftime("%Y-%m-%d")) == [
        "2026-10-23",
        "2026-10-26",
    ]
    assert result["Symbol"].tolist() == [
        "HINDUNILVR",
        "HINDUNILVR",
    ]
    assert result["Source"].tolist() == ["csv", "csv"]
    assert result["Close"].tolist() == [2420, 2440]


def test_missing_column_is_rejected():
    data = sample_data().drop(columns=["volume"])

    with pytest.raises(ValueError, match="Missing required columns"):
        standardize_ohlcv(data, symbol="TEST", source="csv")


def test_duplicate_dates_are_rejected():
    data = sample_data()
    data.loc[1, "date"] = "2026-10-26"

    with pytest.raises(ValueError, match="Duplicate dates"):
        standardize_ohlcv(data, symbol="TEST", source="csv")


def test_invalid_ohlc_is_rejected():
    data = sample_data()
    data.loc[0, "high"] = 2000

    with pytest.raises(ValueError, match="Inconsistent OHLC"):
        standardize_ohlcv(data, symbol="TEST", source="csv")


def test_market_data_info():
    info = make_market_data_info(
        symbol="hindunilvr",
        source="yahoo",
        exchange="nse",
        timeframe="1d",
        currency="inr",
    )

    assert info.symbol == "HINDUNILVR"
    assert info.source == "yahoo"
    assert info.exchange == "NSE"
    assert info.timeframe == "1d"
    assert info.currency == "INR"
