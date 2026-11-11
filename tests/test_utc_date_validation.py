import pandas as pd
import pytest

from core.validation import normalize_price_data
from data.schema import standardize_ohlcv


def sample_data():
    return pd.DataFrame({
        "Date": [
            "2026-11-11T00:30:00+05:30",
            "2026-11-11T01:30:00+05:30",
        ],
        "Open": [100, 101],
        "High": [103, 104],
        "Low": [99, 100],
        "Close": [102, 103],
        "Volume": [1000, 1200],
    })


def test_schema_converts_timezone_aware_dates_to_utc():
    result = standardize_ohlcv(
        sample_data(),
        symbol="MARICO",
        source="nse",
    )

    assert result["Date"].iloc[0] == pd.Timestamp("2026-11-10 19:00:00")
    assert result["Date"].iloc[1] == pd.Timestamp("2026-11-10 20:00:00")


def test_core_validation_converts_timezone_aware_dates_to_utc():
    result = normalize_price_data(sample_data())

    assert result["Date"].iloc[0] == pd.Timestamp("2026-11-10 19:00:00")
    assert result["Date"].iloc[1] == pd.Timestamp("2026-11-10 20:00:00")


def test_schema_and_core_agree_on_utc_calendar_date():
    schema_result = standardize_ohlcv(
        sample_data(),
        symbol="MARICO",
        source="nse",
    )
    core_result = normalize_price_data(sample_data())

    assert (
        schema_result["Date"].iloc[0].normalize()
        == core_result["Date"].iloc[0].normalize()
    )


def test_utc_conversion_detects_duplicate_calendar_dates():
    data = pd.DataFrame({
        "Date": [
            "2026-11-11T00:30:00+05:30",
            "2026-11-10T19:00:00Z",
        ],
        "Open": [100, 101],
        "High": [103, 104],
        "Low": [99, 100],
        "Close": [102, 103],
        "Volume": [1000, 1200],
    })

    with pytest.raises(ValueError, match="Duplicate dates"):
        standardize_ohlcv(
            data,
            symbol="MARICO",
            source="nse",
        )


def test_naive_dates_remain_naive():
    data = sample_data()
    data["Date"] = pd.to_datetime(["2026-11-10", "2026-11-11"])

    result = standardize_ohlcv(
        data,
        symbol="MARICO",
        source="nse",
    )

    assert result["Date"].dt.tz is None
    assert result["Date"].iloc[0] == pd.Timestamp("2026-11-10")
    
