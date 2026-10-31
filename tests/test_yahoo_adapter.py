import pandas as pd
import pytest

from unittest.mock import patch

from data.yahoo_adapter import (
    fetch_yahoo_history,
    resolve_yahoo_symbol,
    validate_intraday_date_range,
    YahooDownloadError,
    YahooDataUnavailableError,
    YahooDataValidationError,
)


# ---------------------------------
# Sample Data
# ---------------------------------

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


def assert_diagnostic(error, expected_code):
    assert error.diagnostic["source"] == "yahoo"
    assert error.diagnostic["code"] == expected_code
    assert error.diagnostic["symbol"] == "HINDUNILVR"
    assert error.diagnostic["ticker"] == "HINDUNILVR.NS"
    assert error.diagnostic["exchange"] == "NSE"
    assert error.diagnostic["message"]
    assert error.diagnostic["suggested_action"]


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
# Basic Adapter Validation Tests
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


# ---------------------------------
# Valid Yahoo Data Tests
# ---------------------------------

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
        with pytest.raises(
            YahooDataValidationError,
            match="Duplicate dates",
        ):
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
        with pytest.raises(
            YahooDataValidationError,
            match="Inconsistent OHLC",
        ):
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
            ["2026-09-30", "2026-10-05", "2026-10-11"],
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


# ---------------------------------
# Intraday Data Handling Tests
# ---------------------------------

@pytest.mark.parametrize(
    "interval",
    ["5m", "15m", "30m", "60m"],
)
def test_intraday_interval_is_passed_to_yahoo(interval):
    with patch(
        "data.yahoo_adapter.yf.download",
        return_value=sample_intraday_data(),
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
    with patch(
        "data.yahoo_adapter.yf.download",
        return_value=sample_intraday_data(),
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
    with patch(
        "data.yahoo_adapter.yf.download",
        return_value=sample_intraday_data(),
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


def test_intraday_rows_are_sorted_chronologically():
    fake_data = sample_intraday_data().iloc[::-1]

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

    assert result["Date"].is_monotonic_increasing
    assert result["Close"].tolist() == [100.5, 101.5, 102.5]


def test_rejects_duplicate_intraday_timestamps():
    fake_data = sample_intraday_data().iloc[:2].copy()
    fake_data.index = pd.DatetimeIndex(
        ["2026-10-05 09:15:00", "2026-10-05 09:15:00"],
        name="Datetime",
    )

    with patch(
        "data.yahoo_adapter.yf.download",
        return_value=fake_data,
    ):
        with pytest.raises(
            YahooDataValidationError,
            match="Duplicate dates",
        ):
            fetch_yahoo_history(
                "RELIANCE",
                "2026-10-05",
                "2026-10-05",
                interval="5m",
            )


def test_intraday_timezone_is_normalized_to_utc():
    fake_data = pd.DataFrame(
        {
            "Open": [100.0],
            "High": [101.0],
            "Low": [99.0],
            "Close": [100.5],
            "Volume": [500],
        },
        index=pd.DatetimeIndex(
            ["2026-10-05 09:15:00"],
            tz="Asia/Kolkata",
            name="Datetime",
        ),
    )

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

    assert result["Date"].dt.tz is None
    assert result["Date"].iloc[0] == pd.Timestamp(
        "2026-10-05 03:45:00"
    )


# ---------------------------------
# Intraday Availability Guard Tests
# ---------------------------------

@pytest.mark.parametrize(
    "interval",
    ["5m", "15m", "30m", "60m"],
)
def test_rejects_intraday_data_older_than_60_days(interval):
    today = (
        pd.Timestamp.now(tz="UTC")
        .tz_localize(None)
        .normalize()
    )

    old_start = today - pd.Timedelta(days=61)

    with pytest.raises(ValueError, match="configured 60-day window"):
        validate_intraday_date_range(old_start, interval)


@pytest.mark.parametrize(
    "interval",
    ["5m", "15m", "30m", "60m"],
)
def test_accepts_recent_intraday_date_range(interval):
    today = (
        pd.Timestamp.now(tz="UTC")
        .tz_localize(None)
        .normalize()
    )

    recent_start = today - pd.Timedelta(days=30)

    validate_intraday_date_range(recent_start, interval)


@pytest.mark.parametrize(
    "interval",
    ["1d", "1wk", "1mo"],
)
def test_daily_and_higher_intervals_are_not_blocked(interval):
    validate_intraday_date_range(
        pd.Timestamp("2020-01-01"),
        interval,
    )


def test_old_intraday_request_is_rejected_before_yahoo_download():
    today = (
        pd.Timestamp.now(tz="UTC")
        .tz_localize(None)
        .normalize()
    )

    old_start = today - pd.Timedelta(days=61)

    with patch(
        "data.yahoo_adapter.yf.download"
    ) as mock_download:
        with pytest.raises(
            YahooDataUnavailableError,
            match="INTRADAY_LOOKBACK_EXCEEDED",
        ):
            fetch_yahoo_history(
                "RELIANCE",
                old_start,
                today,
                interval="5m",
            )

    mock_download.assert_not_called()


# ---------------------------------
# Yahoo Diagnostics Tests
# ---------------------------------

def test_reports_yahoo_download_failure():
    with patch(
        "data.yahoo_adapter.yf.download",
        side_effect=Exception("Connection timeout"),
    ):
        with pytest.raises(YahooDownloadError) as exc_info:
            fetch_yahoo_history(
                "HINDUNILVR",
                "2026-10-01",
                "2026-10-10",
            )

    assert_diagnostic(
        exc_info.value,
        "YAHOO_DOWNLOAD_FAILED",
    )
    assert "Connection timeout" in exc_info.value.diagnostic["message"]


def test_reports_empty_yahoo_response():
    with patch(
        "data.yahoo_adapter.yf.download",
        return_value=pd.DataFrame(),
    ):
        with pytest.raises(YahooDataUnavailableError) as exc_info:
            fetch_yahoo_history(
                "HINDUNILVR",
                "2026-10-01",
                "2026-10-10",
            )

    assert_diagnostic(
        exc_info.value,
        "NO_DATA_RETURNED",
    )


def test_reports_data_validation_failure():
    fake_data = sample_yahoo_data()
    fake_data.loc[fake_data.index[0], "High"] = 90.0

    with patch(
        "data.yahoo_adapter.yf.download",
        return_value=fake_data,
    ):
        with pytest.raises(YahooDataValidationError) as exc_info:
            fetch_yahoo_history(
                "HINDUNILVR",
                "2026-10-01",
                "2026-10-10",
            )

    assert_diagnostic(
        exc_info.value,
        "DATA_VALIDATION_FAILED",
    )


def test_reports_duplicate_date_validation_failure():
    fake_data = sample_yahoo_data()
    fake_data.index = pd.DatetimeIndex(
        ["2026-10-05", "2026-10-05"],
        name="Date",
    )

    with patch(
        "data.yahoo_adapter.yf.download",
        return_value=fake_data,
    ):
        with pytest.raises(YahooDataValidationError) as exc_info:
            fetch_yahoo_history(
                "HINDUNILVR",
                "2026-10-01",
                "2026-10-10",
            )

    assert_diagnostic(
        exc_info.value,
        "DATA_VALIDATION_FAILED",
    )


def test_reports_no_valid_rows_in_requested_date_range():
    fake_data = pd.DataFrame(
        {
            "Open": [100.0],
            "High": [103.0],
            "Low": [99.0],
            "Close": [102.0],
            "Volume": [1000],
        },
        index=pd.DatetimeIndex(
            ["2026-09-30"],
            name="Date",
        ),
    )

    with patch(
        "data.yahoo_adapter.yf.download",
        return_value=fake_data,
    ):
        with pytest.raises(YahooDataUnavailableError) as exc_info:
            fetch_yahoo_history(
                "HINDUNILVR",
                "2026-10-01",
                "2026-10-10",
            )

    assert_diagnostic(
        exc_info.value,
        "NO_VALID_ROWS_IN_DATE_RANGE",
            )
    
