"""Tests for date-isolated historical NSE observation retrieval."""

from datetime import date

import pandas as pd
import pytest

from data.providers.nse_udiff_downloader import NSEUdiFFDownloadError
from services.market_intelligence import historical_observation_service as history


def make_result(day, status="PASS"):
    observations = pd.DataFrame({
        "Date": [day],
        "Symbol": ["AAA"],
        "ISIN": ["INE000A01010"],
        "Previous Close": [100.0],
        "Current Close": [101.0],
    })
    reconciliation = {
        "mii_snapshot_date": day,
        "expected_symbols": 1,
        "observed_symbols": 1,
        "missing_count": 0,
        "identity_exceptions": [],
        "coverage_pct": 100.0,
    }
    return {
        "analysis_status": status,
        "source": "NSE",
        "source_url": f"https://nsearchives.nseindia.com/{day}.zip",
        "source_filename": f"{day}.zip",
        "source_sha256": "a" * 64,
        "fetched_at_utc": f"{day}T12:00:00Z",
        "reconciliation": reconciliation,
        "verified_observations": observations,
        "unverified_observations": pd.DataFrame(),
    }


def test_normalizes_and_sorts_unique_dates():
    result = history._normalize_observation_dates([
        "2026-11-13",
        date(2026, 11, 11),
        "2026-11-12",
    ])
    assert result == [
        date(2026, 11, 11),
        date(2026, 11, 12),
        date(2026, 11, 13),
    ]


@pytest.mark.parametrize("value", ["2026-11-13", None, [], [""], ["not-a-date"]])
def test_rejects_invalid_date_collections(value):
    if value == []:
        with pytest.raises(history.NSEHistoricalObservationError):
            history._normalize_observation_dates(value)
    else:
        with pytest.raises(history.NSEHistoricalObservationError):
            history._normalize_observation_dates(value)


def test_rejects_duplicate_dates():
    with pytest.raises(history.NSEHistoricalObservationError, match="Duplicate"):
        history._normalize_observation_dates([
            "2026-11-13",
            date(2026, 11, 13),
        ])


def test_retrieves_each_date_independently_and_preserves_provenance(monkeypatch):
    calls = []

    def fake_service(day, *, session=None):
        calls.append(day.isoformat())
        return make_result(day.isoformat())

    monkeypatch.setattr(
        history,
        "analyze_nse_market_breadth_from_udiff",
        fake_service,
    )

    result = history.retrieve_nse_historical_observations([
        "2026-11-13",
        "2026-11-11",
    ])

    assert calls == ["2026-11-11", "2026-11-13"]
    assert result["analysis_status"] == "PASS"
    assert result["date_count"] == 2
    assert result["pass_count"] == 2
    assert result["summary"]["source_sha256"].tolist() == ["a" * 64] * 2
    assert result["summary"]["mii_snapshot_date"].tolist() == [
        "2026-11-11",
        "2026-11-13",
    ]
    assert result["verified_observations"]["Date"].tolist() == [
        "2026-11-11",
        "2026-11-13",
    ]


def test_failed_date_is_unavailable_and_later_date_is_still_attempted(monkeypatch):
    calls = []

    def fake_service(day, *, session=None):
        calls.append(day.isoformat())
        if day.isoformat() == "2026-11-11":
            raise NSEUdiFFDownloadError("archive unavailable")
        return make_result(day.isoformat())

    monkeypatch.setattr(
        history,
        "analyze_nse_market_breadth_from_udiff",
        fake_service,
    )

    result = history.retrieve_nse_historical_observations([
        "2026-11-11",
        "2026-11-12",
    ])

    assert calls == ["2026-11-11", "2026-11-12"]
    assert result["analysis_status"] == "UNAVAILABLE"
    assert result["unavailable_count"] == 1
    assert result["per_date"][0]["error_type"] == "NSEUdiFFDownloadError"
    assert result["per_date"][1]["status"] == "PASS"


def test_review_status_propagates_to_overall_history(monkeypatch):
    monkeypatch.setattr(
        history,
        "analyze_nse_market_breadth_from_udiff",
        lambda day, **kwargs: make_result(day.isoformat(), "REVIEW"),
    )

    result = history.retrieve_nse_historical_observations([
        "2026-11-13",
    ])

    assert result["analysis_status"] == "REVIEW"
    assert result["review_count"] == 1


def test_does_not_reuse_one_date_for_another(monkeypatch):
    seen = []

    def fake_service(day, **kwargs):
        seen.append(day.isoformat())
        return make_result(day.isoformat())

    monkeypatch.setattr(
        history,
        "analyze_nse_market_breadth_from_udiff",
        fake_service,
    )

    result = history.retrieve_nse_historical_observations([
        "2026-11-12",
        "2026-11-13",
    ])

    assert seen == ["2026-11-12", "2026-11-13"]
    assert result["per_date"][0]["mii_snapshot_date"] == "2026-11-12"
    assert result["per_date"][1]["mii_snapshot_date"] == "2026-11-13"
