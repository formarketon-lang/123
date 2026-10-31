
import pandas as pd
import pytest

from unittest.mock import patch

from data.yahoo_adapter import (
    fetch_yahoo_history,
    resolve_yahoo_symbol,
)


def sample_yahoo_data():
    return pd.DataFrame(
        {
            "Open": [100.0, 105.0],
            "High": [103.0, 108.0],
            "Low": [99.0, 104.0],
            "Close": [102.0, 107.0],
            "Volume": [1000, 1200],
        },
        index=pd.DatetimeIndex(
            ["2026-10-05", "2026-10-06"],
            name="Date",
        ),
    )


# ---------------------------------
# Symbol Resolution Tests
# ---------------------------------

@pytest.mark.parametrize(
    "symbol, exchange, expected",
    [
        ("RELIANCE", "NSE", "RELIANCE.NS"),
        ("HINDUNILVR", "NSE", "HINDUNILVR.NS"),
        ("RELIANCE", "BSE", "RELIANCE.BO"),
        ("RELIANCE.NS", "NSE", "RELIANCE.NS"),
        ("RELIANCE.BO", "BSE", "RELIANCE.BO"),
        ("^NSEI", "NSE", "^NSEI"),
    ],
)
def test_resolves_yahoo_symbols(symbol, exchange, expected):
    assert resolve_yahoo_symbol(symbol, exchange) == expected


def test_rejects_empty_symbol_in_resolution():
    with pytest.raises(ValueError):
        resolve_yahoo_symbol("", "NSE")


def test_rejects_invalid_exchange_in_resolution():
    with pytest.raises(ValueError):
        resolve_yahoo_symbol("RELIANCE", "Both")


# ---------------------------------
# Yahoo Adapter Validation Tests
# ---------------------------------

def test_rejects_empty_symbol():
    with pytest.raises(ValueError, match="Stock symbol"):
        fetch_yahoo_history("", "2026-10-01", "2026-10-10")


def test_rejects_invalid_exchange():
    with pytest.raises(ValueError, match="Exchange"):
        fetch_yahoo_history(
            "HINDUNILVR",
            "2026-10-01",
            "2026-10-10",
            exchange="Both",
        )


def test_rejects_invalid_interval():
    with pytest.raises(ValueError, match="interval"):
        fetch_yahoo_history(
            "HINDUNILVR",
            "2026-10-01",
            "2026-10-10",
            interval="2h",
        )


def test_rejects_reversed_dates():
    with pytest.raises(ValueError, match="Start date"):
        fetch_yahoo_history(
            "HINDUNILVR",
            "2026-10-10",
            "2026-10-01",
        )


def test_validates_and_returns_yahoo_ohlcv_data():
    with patch(
        "data.yahoo_adapter.yf.download",
        return_value=sample_yahoo_data(),
    ):
        result = fetch_yahoo_history(
            "HINDUNILVR",
            "2026-10-01",
            "2026-10-10",
        )

    assert list(result.columns) == [
        "Date", "Open", "High", "Low", "Close", "Volume"
    ]
    assert len(result) == 2
    assert result["Close"].tolist() == [102.0, 107.0]


def test_normalizes_multiindex_yahoo_columns():
    fake_data = sample_yahoo_data()

    fake_data.columns = pd.MultiIndex.from_product(
        [
            fake_data.columns,
            ["HINDUNILVR.NS"],
        ]
    )

    with patch(
        "data.yahoo_adapter.yf.download",
        return_value=fake_data,
    ):
        result = fetch_yahoo_history(
            "HINDUNILVR",
            "2026-10-01",
            "2026-10-10",
        )

    assert len(result) == 2
    assert result["Close"].tolist() == [102.0, 107.0]


def test_rejects_duplicate_dates():
    fake_data = sample_yahoo_data()
    fake_data.index = pd.DatetimeIndex(
        ["2026-10-05", "2026-10-05"],
        name="Date",
    )

    with patch(
        "data.yahoo_adapter.yf.download",
        return_value=fake_data,
    ):
        with pytest.raises(ValueError, match="Duplicate dates"):
            fetch_yahoo_history(
                "HINDUNILVR",
                "2026-10-01",
                "2026-10-10",
            )


def test_rejects_invalid_ohlc_candle():
    fake_data = sample_yahoo_data()
    fake_data.loc[fake_data.index[0], "High"] = 90.0

    with patch(
        "data.yahoo_adapter.yf.download",
        return_value=fake_data,
    ):
        with pytest.raises(ValueError, match="Inconsistent OHLC"):
            fetch_yahoo_history(
                "HINDUNILVR",
                "2026-10-01",
                "2026-10-10",
            )


def test_accepts_timezone_aware_dates():
    fake_data = pd.DataFrame(
        {
            "Open": [100.0],
            "High": [103.0],
            "Low": [99.0],
            "Close": [102.0],
            "Volume": [1000],
        },
        index=pd.DatetimeIndex(
            ["2026-10-05 00:00:00"],
            tz="Asia/Kolkata",
            name="Date",
        ),
    )

    with patch(
        "data.yahoo_adapter.yf.download",
        return_value=fake_data,
    ):
        result = fetch_yahoo_history(
            "HINDUNILVR",
            "2026-10-05T00:00:00+05:30",
            "2026-10-05T00:00:00+05:30",
        )

    assert len(result) == 1
    assert result["Date"].dt.tz is None
    assert result["Date"].iloc[0] == pd.Timestamp(
        "2026-10-04 18:30:00"
    )


def test_excludes_data_outside_requested_date_range():
    fake_data = pd.DataFrame(
        {
            "Open": [100.0, 105.0, 110.0],
            "High": [103.0, 108.0, 113.0],
            "Low": [99.0, 104.0, 109.0],
            "Close": [102.0, 107.0, 112.0],
            "Volume": [1000, 1200, 1400],
        },
        index=pd.DatetimeIndex(
            [
                "2026-09-30",
                "2026-10-05",
                "2026-10-11",
            ],
            name="Date",
        ),
    )

    with patch(
        "data.yahoo_adapter.yf.download",
        return_value=fake_data,
    ):
        result = fetch_yahoo_history(
            "HINDUNILVR",
            "2026-10-01",
            "2026-10-10",
        )

    assert len(result) == 1
    assert result["Date"].iloc[0] == pd.Timestamp("2026-10-05")


def test_end_date_is_inclusive_but_next_day_is_excluded():
    fake_data = pd.DataFrame(
        {
            "Open": [100.0, 105.0],
            "High": [103.0, 108.0],
            "Low": [99.0, 104.0],
            "Close": [102.0, 107.0],
            "Volume": [1000, 1200],
        },
        index=pd.DatetimeIndex(
            ["2026-10-06", "2026-10-07"],
            name="Date",
        ),
    )

    with patch(
        "data.yahoo_adapter.yf.download",
        return_value=fake_data,
    ):
        result = fetch_yahoo_history(
            "HINDUNILVR",
            "2026-10-01",
            "2026-10-06",
        )

    assert len(result) == 1
    assert result["Date"].iloc[0] == pd.Timestamp("2026-10-06")


def test_raises_error_when_yahoo_returns_no_data():
    with patch(
        "data.yahoo_adapter.yf.download",
        return_value=pd.DataFrame(),
    ):
        with pytest.raises(ValueError, match="No Yahoo Finance data"):
            fetch_yahoo_history(
                "HINDUNILVR",
                "2026-10-01",
                "2026-10-10",
            )
            
# ---------------------------------
# Intraday Data Handling Tests
# ---------------------------------

def sample_intraday_data():
    return pd.DataFrame(
        {
            "Open": [100.0, 101.0, 102.0],
            "High": [101.0, 102.0, 103.0],
            "Low": [99.0, 100.0, 101.0],
            "Close": [100.5, 101.5, 102.5],
            "Volume": [500, 600, 700],
        },
        index=pd.DatetimeIndex(
            [
                "2026-10-05 09:15:00",
                "2026-10-05 09:20:00",
                "2026-10-05 09:25:00",
            ],
            name="Datetime",
        ),
    )


@pytest.mark.parametrize(
    "interval",
    ["5m", "15m", "30m", "60m"],
)
def test_intraday_interval_is_passed_to_yahoo(interval):
    fake_data = sample_intraday_data()

    with patch(
        "data.yahoo_adapter.yf.download",
        return_value=fake_data,
    ) as mock_download:

        result = fetch_yahoo_history(
            "RELIANCE",
            "2026-10-05",
            "2026-10-05",
            interval=interval,
        )

    assert mock_download.call_args.kwargs["interval"] == interval
    assert len(result) == 3


def test_intraday_datetime_is_preserved():
    fake_data = sample_intraday_data()

    with patch(
        "data.yahoo_adapter.yf.download",
        return_value=fake_data,
    ):
        result = fetch_yahoo_history(
            "RELIANCE",
            "2026-10-05",
            "2026-10-05",
            interval="5m",
        )

    assert "Date" in result.columns
    assert result["Date"].dt.hour.tolist() == [9, 9, 9]
    assert result["Date"].dt.minute.tolist() == [15, 20, 25]


def test_intraday_output_keeps_canonical_ohlcv_columns():
    fake_data = sample_intraday_data()

    with patch(
        "data.yahoo_adapter.yf.download",
        return_value=fake_data,
    ):
        result = fetch_yahoo_history(
            "RELIANCE",
            "2026-10-05",
            "2026-10-05",
            interval="15m",
        )

    assert list(result.columns) == [
        "Date", "Open", "High", "Low", "Close", "Volume"
    ]
    
