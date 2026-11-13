"""Tests for the Market Intelligence index data service."""

import pandas as pd
import pytest

from data.market_intelligence.index_service import (
    IndexDataValidationError,
    fetch_index_history,
    validate_index_history,
)


@pytest.fixture
def valid_index_data():
    return pd.DataFrame({
        "Date": pd.to_datetime(["2026-01-01", "2026-01-02"]),
        "Open": [100.0, 101.0],
        "High": [103.0, 104.0],
        "Low": [99.0, 100.0],
        "Close": [102.0, 103.0],
        "Volume": [None, None],
        "Symbol": ["^NSEI", "^NSEI"],
        "Source": ["NSE", "NSE"],
        "Exchange": ["NSE", "NSE"],
        "Timeframe": ["1d", "1d"],
        "Fallback Reason": ["", ""],
        "Fetched At UTC": [
            "2026-01-02T10:00:00Z",
            "2026-01-02T10:00:00Z",
        ],
        "Validation Status": ["PASS", "PASS"],
    })


def test_valid_nse_index_data_passes(valid_index_data):
    result = validate_index_history(valid_index_data, "^NSEI")
    assert len(result) == 2
    assert result["Source"].iloc[0] == "NSE"


def test_yahoo_fallback_with_reason_passes(valid_index_data):
    valid_index_data["Source"] = "Yahoo"
    valid_index_data["Fallback Reason"] = "NSE source unavailable"
    result = validate_index_history(valid_index_data, "^NSEI")
    assert result["Source"].iloc[0] == "Yahoo"


def test_unknown_index_is_blocked(valid_index_data):
    with pytest.raises(IndexDataValidationError):
        validate_index_history(valid_index_data, "^UNKNOWN")


def test_bse_exchange_is_rejected(valid_index_data):
    valid_index_data["Exchange"] = "BSE"
    with pytest.raises(IndexDataValidationError):
        validate_index_history(valid_index_data, "^NSEI")


def test_non_daily_timeframe_is_rejected(valid_index_data):
    valid_index_data["Timeframe"] = "1h"
    with pytest.raises(IndexDataValidationError):
        validate_index_history(valid_index_data, "^NSEI")


def test_review_status_is_rejected(valid_index_data):
    valid_index_data["Validation Status"] = "REVIEW"
    with pytest.raises(IndexDataValidationError):
        validate_index_history(valid_index_data, "^NSEI")


def test_duplicate_dates_are_rejected(valid_index_data):
    valid_index_data.loc[1, "Date"] = valid_index_data.loc[0, "Date"]
    with pytest.raises(IndexDataValidationError):
        validate_index_history(valid_index_data, "^NSEI")


def test_invalid_close_is_rejected(valid_index_data):
    valid_index_data.loc[0, "Close"] = -1
    with pytest.raises(IndexDataValidationError):
        validate_index_history(valid_index_data, "^NSEI")


def test_yahoo_without_fallback_reason_is_rejected(valid_index_data):
    valid_index_data["Source"] = "Yahoo"
    valid_index_data["Fallback Reason"] = ""
    with pytest.raises(IndexDataValidationError):
        validate_index_history(valid_index_data, "^NSEI")


def test_reversed_date_range_is_rejected(monkeypatch):
    def unexpected_fetch(**kwargs):
        pytest.fail("Adapter must not be called for reversed dates.")

    monkeypatch.setattr(
        "data.market_intelligence.index_service.fetch_market_history",
        unexpected_fetch,
    )

    with pytest.raises(ValueError):
        fetch_index_history("^NSEI", "2026-02-01", "2026-01-01")
