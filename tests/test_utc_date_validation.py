import pandas as pd
import pytest

from core.validation import (
    normalize_price_data,
    validate_date_range,
)


def test_aware_date_converts_to_utc_before_normalizing():
    data = pd.DataFrame({
        "Date": ["2026-11-11T00:30:00+05:30"],
        "Close": [100],
    })

    result = normalize_price_data(data)

    assert result["Date"].iloc[0] == pd.Timestamp("2026-11-10")


def test_utc_date_matches_schema_date_behavior():
    from data.schema import standardize_ohlcv

    data = pd.DataFrame({
        "Date": ["2026-11-11T00:30:00+05:30"],
        "Open": [100],
        "High": [103],
        "Low": [99],
        "Close": [102],
        "Volume": [1000],
    })

    schema_result = standardize_ohlcv(
        data,
        symbol="TEST",
        source="NSE",
    )

    core_result = normalize_price_data(
        data[["Date", "Close"]]
    )

    assert (
        schema_result["Date"].iloc[0]
        == core_result["Date"].iloc[0]
    )


def test_naive_dates_remain_naive_calendar_dates():
    data = pd.DataFrame({
        "Date": ["2026-11-11 15:30:00"],
        "Close": [100],
    })

    result = normalize_price_data(data)

    assert result["Date"].iloc[0] == pd.Timestamp("2026-11-11")


def test_date_range_converts_both_dates_to_utc():
    start, end = validate_date_range(
        "2026-11-11T00:30:00+05:30",
        "2026-11-12T00:30:00+05:30",
    )

    assert start == pd.Timestamp("2026-11-10")
    assert end == pd.Timestamp("2026-11-11")


def test_date_range_rejects_reversed_dates():
    with pytest.raises(ValueError, match="End date cannot be earlier"):
        validate_date_range("2026-11-12", "2026-11-11")


def test_invalid_date_is_rejected():
    with pytest.raises(ValueError, match="invalid dates"):
        validate_date_range("not-a-date", "2026-11-11")


def test_utc_conversion_detects_duplicate_calendar_dates():
    data = pd.DataFrame({
        "Date": [
            "2026-11-11T00:30:00+05:30",
            "2026-11-10T19:00:00Z",
        ],
        "Close": [100, 101],
    })

    with pytest.raises(ValueError, match="duplicate dates"):
        normalize_price_data(data)
      
