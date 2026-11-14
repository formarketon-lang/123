"""Tests for historical daily Advance / Decline classification."""

import pandas as pd
import pytest

from core.market_intelligence.advance_decline import (
    AdvanceDeclineClassificationError,
    classify_historical_daily_advance_decline,
)


def observation_frame(rows):
    return pd.DataFrame(
        rows,
        columns=[
            "Date",
            "Symbol",
            "ISIN",
            "Previous Close",
            "Current Close",
        ],
    )


def record(
    day="2026-11-13",
    status="PASS",
    observations=None,
    expected=3,
    verified=3,
    missing=0,
    exceptions=0,
    coverage=100.0,
):
    if observations is None:
        observations = observation_frame([
            (day, "AAA", "INE000A01010", 100, 110),
            (day, "BBB", "INE000B01010", 100, 90),
            (day, "CCC", "INE000C01010", 100, 100),
        ])
    return {
        "observation_date": day,
        "status": status,
        "expected_symbols": expected,
        "verified_symbols": verified,
        "missing_count": missing,
        "identity_exception_count": exceptions,
        "coverage_pct": coverage,
        "verified_observations": observations,
        "error": None,
    }


def test_daily_advancing_declining_unchanged_counts_reconcile():
    result = classify_historical_daily_advance_decline({
        "per_date": [record()],
    })
    row = result["summary"].iloc[0]
    assert row["advancing"] == 1
    assert row["declining"] == 1
    assert row["unchanged"] == 1
    assert row["missing"] == 0
    assert row["analysis_status"] == "PASS"
    assert result["analysis_status"] == "PASS"


def test_missing_member_is_not_counted_as_unchanged():
    observations = observation_frame([
        ("2026-11-13", "AAA", "INE000A01010", 100, 100),
        ("2026-11-13", "BBB", "INE000B01010", 100, 100),
    ])
    result = classify_historical_daily_advance_decline({
        "per_date": [record(
            status="REVIEW",
            observations=observations,
            expected=3,
            verified=2,
            missing=1,
            coverage=66.6666667,
        )],
    })
    row = result["summary"].iloc[0]
    assert row["unchanged"] == 2
    assert row["missing"] == 1
    assert row["unchanged"] + row["missing"] == 3
    assert row["analysis_status"] == "REVIEW"


def test_zero_verified_observations_reports_all_missing_not_unchanged():
    result = classify_historical_daily_advance_decline({
        "per_date": [record(
            status="REVIEW",
            observations=observation_frame([]),
            expected=3,
            verified=0,
            missing=3,
            coverage=0.0,
        )],
    })
    row = result["summary"].iloc[0]
    assert row["advancing"] == 0
    assert row["declining"] == 0
    assert row["unchanged"] == 0
    assert row["missing"] == 3
    assert row["analysis_status"] == "REVIEW"


def test_identity_exceptions_keep_date_in_review_even_at_full_coverage():
    result = classify_historical_daily_advance_decline({
        "per_date": [record(
            status="REVIEW",
            exceptions=1,
        )],
    })
    assert result["summary"].iloc[0]["analysis_status"] == "REVIEW"


def test_unavailable_date_has_no_fabricated_counts():
    result = classify_historical_daily_advance_decline({
        "per_date": [{
            "observation_date": "2026-11-13",
            "status": "UNAVAILABLE",
            "error": "NSE archive unavailable",
        }],
    })
    row = result["summary"].iloc[0]
    assert pd.isna(row["advancing"])
    assert pd.isna(row["unchanged"])
    assert pd.isna(row["missing"])
    assert row["analysis_status"] == "UNAVAILABLE"


def test_blocked_date_has_no_classification_counts():
    result = classify_historical_daily_advance_decline({
        "per_date": [{
            "observation_date": "2026-11-13",
            "status": "BLOCKED",
            "missing_count": 0,
            "identity_exception_count": 1,
            "verified_symbols": 2,
            "expected_symbols": 3,
            "coverage_pct": 66.7,
        }],
    })
    row = result["summary"].iloc[0]
    assert pd.isna(row["advancing"])
    assert row["analysis_status"] == "BLOCKED"


def test_dates_are_sorted_chronologically():
    first = record(day="2026-11-12")
    second = record(day="2026-11-13")
    result = classify_historical_daily_advance_decline({
        "per_date": [second, first],
    })
    assert result["summary"]["observation_date"].tolist() == [
        "2026-11-12",
        "2026-11-13",
    ]


def test_duplicate_observation_dates_are_rejected():
    with pytest.raises(AdvanceDeclineClassificationError, match="Duplicate"):
        classify_historical_daily_advance_decline({
            "per_date": [record(), record()],
        })


def test_verified_observation_count_must_match_retrieval_metadata():
    with pytest.raises(AdvanceDeclineClassificationError, match="count mismatch"):
        classify_historical_daily_advance_decline({
            "per_date": [record(verified=2, missing=1, coverage=66.6666667)],
        })


def test_invalid_prices_are_rejected_by_existing_breadth_classifier():
    observations = observation_frame([
        ("2026-11-13", "AAA", "INE000A01010", 0, 100),
        ("2026-11-13", "BBB", "INE000B01010", 100, 90),
        ("2026-11-13", "CCC", "INE000C01010", 100, 100),
    ])
    with pytest.raises(ValueError, match="must be positive"):
        classify_historical_daily_advance_decline({
            "per_date": [record(observations=observations)],
        })


def test_unexpected_observation_status_is_rejected():
    with pytest.raises(AdvanceDeclineClassificationError, match="Unsupported"):
        classify_historical_daily_advance_decline({
            "per_date": [record(status="UNKNOWN")],
        })


def test_overall_status_uses_strictest_date_status():
    unavailable = {
        "observation_date": "2026-11-12",
        "status": "UNAVAILABLE",
        "error": "archive unavailable",
    }
    result = classify_historical_daily_advance_decline({
        "per_date": [record(), unavailable],
    })
    assert result["analysis_status"] == "UNAVAILABLE"
    assert result["pass_count"] == 1
    assert result["unavailable_count"] == 1



def test_missing_count_must_reconcile_with_verified_and_expected():
    with pytest.raises(AdvanceDeclineClassificationError, match="counts are inconsistent"):
        classify_historical_daily_advance_decline({
            "per_date": [record(
                status="REVIEW",
                verified=2,
                missing=2,
                coverage=66.6666667,
            )],
        })


def test_reported_coverage_must_match_verified_universe_count():
    with pytest.raises(AdvanceDeclineClassificationError, match="inconsistent"):
        classify_historical_daily_advance_decline({
            "per_date": [record(coverage=99.0)],
        })



def test_verified_observations_must_match_requested_observation_date():
    observations = observation_frame([
        ("2026-11-12", "AAA", "INE000A01010", 100, 110),
        ("2026-11-13", "BBB", "INE000B01010", 100, 90),
        ("2026-11-13", "CCC", "INE000C01010", 100, 100),
    ])
    with pytest.raises(AdvanceDeclineClassificationError, match="mismatched date"):
        classify_historical_daily_advance_decline({
            "per_date": [record(observations=observations)],
        })
