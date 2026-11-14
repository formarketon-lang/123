"""Tests for prior NSE session Previous Close validation."""

import pandas as pd
import pytest

from services.market_intelligence.prior_session_validation import (
    PriorSessionValidationError,
    validate_prior_session_prices,
)


CALENDAR = ["2026-11-12", "2026-11-13", "2026-11-16"]
SOURCE = "Official NSE CM trading calendar, verified test fixture"


def frame(rows):
    return pd.DataFrame(rows, columns=[
        "Date", "Symbol", "ISIN", "Previous Close", "Current Close"
    ])


def validate(data, calendar=CALENDAR, observation_dates=None, **kwargs):
    targets = observation_dates or ["2026-11-13"]
    return validate_prior_session_prices(
        data,
        calendar,
        observation_dates=targets,
        calendar_verified=True,
        calendar_source=SOURCE,
        **kwargs,
    )


def test_previous_close_matches_immediately_prior_nse_session():
    data = frame([
        ("2026-11-12", "AAA", "INE000A01010", 95, 100),
        ("2026-11-13", "AAA", "INE000A01010", 100, 105),
    ])
    result = validate(data, observation_dates=["2026-11-13"])
    assert result["analysis_status"] == "PASS"
    row = result["per_symbol"].iloc[0]
    assert row["previous_session_date"] == "2026-11-12"
    assert row["prior_session_close"] == 100
    assert row["difference"] == 0


def test_holiday_and_weekend_are_skipped_using_calendar_not_weekdays():
    data = frame([
        ("2026-11-12", "AAA", "INE000A01010", 90, 100),
        ("2026-11-16", "AAA", "INE000A01010", 100, 110),
    ])
    result = validate(
        data,
        calendar=["2026-11-12", "2026-11-16"],
        observation_dates=["2026-11-16"],
    )
    row = result["per_symbol"].iloc[0]
    assert row["previous_session_date"] == "2026-11-12"
    assert result["analysis_status"] == "PASS"


def test_special_session_is_respected_when_in_official_calendar():
    calendar = ["2026-11-12", "2026-11-15", "2026-11-16"]
    data = frame([
        ("2026-11-12", "AAA", "INE000A01010", 95, 100),
        ("2026-11-15", "AAA", "INE000A01010", 100, 103),
        ("2026-11-16", "AAA", "INE000A01010", 103, 105),
    ])
    result = validate(data, calendar=calendar, observation_dates=["2026-11-16"])
    assert result["per_symbol"].iloc[0]["previous_session_date"] == "2026-11-15"
    assert result["analysis_status"] == "PASS"


def test_price_difference_over_tolerance_is_blocked():
    data = frame([
        ("2026-11-12", "AAA", "INE000A01010", 95, 100),
        ("2026-11-13", "AAA", "INE000A01010", 100.02, 105),
    ])
    result = validate(data, observation_dates=["2026-11-13"])
    assert result["analysis_status"] == "BLOCKED"
    assert result["per_symbol"].iloc[0]["status"] == "BLOCKED"


def test_difference_within_tolerance_passes():
    data = frame([
        ("2026-11-12", "AAA", "INE000A01010", 95, 100),
        ("2026-11-13", "AAA", "INE000A01010", 100.01, 105),
    ])
    assert validate(data, observation_dates=["2026-11-13"])["analysis_status"] == "PASS"


def test_missing_symbol_on_prior_session_is_review_not_unchanged():
    data = frame([
        ("2026-11-12", "BBB", "INE000B01010", 95, 100),
        ("2026-11-13", "AAA", "INE000A01010", 100, 105),
    ])
    result = validate(data, observation_dates=["2026-11-13"])
    assert result["analysis_status"] == "REVIEW"
    assert result["per_symbol"].iloc[0]["status"] == "REVIEW"


def test_same_symbol_different_isin_is_blocked():
    data = frame([
        ("2026-11-12", "AAA", "INE000A01010", 95, 100),
        ("2026-11-13", "AAA", "INE000Z01010", 100, 105),
    ])
    result = validate(data, observation_dates=["2026-11-13"])
    assert result["analysis_status"] == "BLOCKED"
    assert "ISIN differs" in result["per_symbol"].iloc[0]["reason"]


def test_missing_prior_session_archive_is_unavailable():
    data = frame([
        ("2026-11-13", "AAA", "INE000A01010", 100, 105),
    ])
    result = validate(data, observation_dates=["2026-11-13"])
    assert result["analysis_status"] == "UNAVAILABLE"
    assert result["per_date"].iloc[0]["status"] == "UNAVAILABLE"


def test_unverified_or_missing_calendar_never_passes():
    data = frame([
        ("2026-11-12", "AAA", "INE000A01010", 95, 100),
        ("2026-11-13", "AAA", "INE000A01010", 100, 105),
    ])
    result = validate_prior_session_prices(
        data,
        CALENDAR,
        observation_dates=["2026-11-13"],
        calendar_verified=False,
        calendar_source=None,
    )
    assert result["analysis_status"] == "UNAVAILABLE"
    assert result["calendar_status"] == "UNVERIFIED"


def test_duplicate_calendar_dates_are_rejected():
    data = frame([
        ("2026-11-12", "AAA", "INE000A01010", 95, 100),
        ("2026-11-13", "AAA", "INE000A01010", 100, 105),
    ])
    with pytest.raises(PriorSessionValidationError, match="Duplicate"):
        validate(data, calendar=CALENDAR + ["2026-11-13"], observation_dates=["2026-11-13"])


def test_duplicate_symbol_in_one_session_is_rejected():
    data = frame([
        ("2026-11-12", "AAA", "INE000A01010", 95, 100),
        ("2026-11-12", "AAA", "INE000A01010", 95, 100),
        ("2026-11-13", "AAA", "INE000A01010", 100, 105),
    ])
    with pytest.raises(PriorSessionValidationError, match="Duplicate"):
        validate(data, observation_dates=["2026-11-13"])


def test_invalid_price_is_blocked():
    data = frame([
        ("2026-11-12", "AAA", "INE000A01010", 95, 100),
        ("2026-11-13", "AAA", "INE000A01010", float("nan"), 105),
    ])
    result = validate(data, observation_dates=["2026-11-13"])
    assert result["analysis_status"] == "BLOCKED"


def test_observation_date_not_in_calendar_is_rejected():
    data = frame([
        ("2026-11-12", "AAA", "INE000A01010", 95, 100),
        ("2026-11-14", "AAA", "INE000A01010", 100, 105),
    ])
    with pytest.raises(PriorSessionValidationError, match="calendar"):
        validate(data, observation_dates=["2026-11-14"])


def test_no_prior_session_in_supplied_calendar_is_unavailable():
    data = frame([
        ("2026-11-12", "AAA", "INE000A01010", 95, 100),
    ])
    result = validate(data, calendar=["2026-11-12"], observation_dates=["2026-11-12"])
    assert result["analysis_status"] == "UNAVAILABLE"



def test_duplicate_isin_in_one_session_is_rejected():
    data = frame([
        ("2026-11-12", "AAA", "INE000A01010", 95, 100),
        ("2026-11-12", "BBB", "INE000A01010", 95, 100),
        ("2026-11-13", "AAA", "INE000A01010", 100, 105),
    ])
    with pytest.raises(PriorSessionValidationError, match="Duplicate ISIN"):
        validate(data, observation_dates=["2026-11-13"])
