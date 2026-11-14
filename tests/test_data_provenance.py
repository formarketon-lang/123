
import pandas as pd
import pytest

from data.provenance import (
    build_data_provenance,
    attach_data_provenance,
)


def sample_data():
    return pd.DataFrame({
        "Date": pd.to_datetime([
            "2026-10-02",
            "2026-10-01",
        ]),
        "Open": [101, 100],
        "High": [104, 103],
        "Low": [100, 99],
        "Close": [103, 102],
        "Volume": [1200, 1000],
    })


def test_provenance_contains_source_and_observation_range():
    result = build_data_provenance(
        sample_data(),
        symbol="marico",
        source="NSE",
        exchange="NSE",
        timeframe="1d",
        fetched_at_utc="2026-11-11T05:00:00Z",
    )

    assert result.symbol == "MARICO"
    assert result.source == "NSE"
    assert result.exchange == "NSE"
    assert result.timeframe == "1d"
    assert result.fetched_at_utc == "2026-11-11T05:00:00Z"
    assert result.validation_status == "PASS"
    assert result.observation_start == "2026-10-01"
    assert result.observation_end == "2026-10-02"


def test_naive_fetch_timestamp_is_rejected():
    with pytest.raises(ValueError, match="timezone-aware"):
        build_data_provenance(
            sample_data(),
            symbol="MARICO",
            source="NSE",
            exchange="NSE",
            timeframe="1d",
            fetched_at_utc="2026-11-11 05:00:00",
        )


def test_missing_fetch_timestamp_is_rejected():
    with pytest.raises(ValueError, match="explicit fetched_at_utc"):
        build_data_provenance(
            sample_data(),
            symbol="MARICO",
            source="NSE",
            exchange="NSE",
            timeframe="1d",
        )


def test_timezone_aware_fetch_timestamp_converts_to_utc():
    result = build_data_provenance(
        sample_data(),
        symbol="MARICO",
        source="NSE",
        exchange="NSE",
        timeframe="1d",
        fetched_at_utc="2026-11-11T10:30:00+05:30",
    )

    assert result.fetched_at_utc == "2026-11-11T05:00:00Z"


def test_fallback_reason_is_preserved():
    result = build_data_provenance(
        sample_data(),
        symbol="MARICO",
        source="Yahoo",
        exchange="NSE",
        timeframe="1d",
        fallback_reason="NSE unavailable",
        fetched_at_utc="2026-11-11T05:00:00Z",
    )

    assert result.source == "YAHOO"
    assert result.fallback_reason == "NSE unavailable"


@pytest.mark.parametrize("status", ["PASS", "REVIEW", "FAIL"])
def test_supported_validation_statuses(status):
    result = build_data_provenance(
        sample_data(),
        symbol="MARICO",
        source="NSE",
        exchange="NSE",
        timeframe="1d",
        fetched_at_utc="2026-11-11T05:00:00Z",
        validation_status=status,
    )

    assert result.validation_status == status


def test_invalid_validation_status_is_rejected():
    with pytest.raises(ValueError, match="Invalid validation status"):
        build_data_provenance(
            sample_data(),
            symbol="MARICO",
            source="NSE",
            exchange="NSE",
            timeframe="1d",
            validation_status="UNKNOWN",
        )


def test_empty_data_is_rejected():
    with pytest.raises(ValueError, match="empty"):
        build_data_provenance(
            pd.DataFrame(),
            symbol="MARICO",
            source="NSE",
            exchange="NSE",
            timeframe="1d",
        )


def test_attach_provenance_does_not_modify_original_data():
    original = sample_data()

    result = attach_data_provenance(
        original,
        symbol="MARICO",
        source="NSE",
        exchange="NSE",
        timeframe="1d",
        fetched_at_utc="2026-11-11T05:00:00Z",
    )

    assert "Fetched At UTC" not in original.columns
    assert "Validation Status" not in original.columns

    assert result["Fetched At UTC"].eq(
        "2026-11-11T05:00:00Z"
    ).all()

    assert result["Validation Status"].eq("PASS").all()
    assert result["Observation Start"].eq("2026-10-01").all()
    assert result["Observation End"].eq("2026-10-02").all()
  
