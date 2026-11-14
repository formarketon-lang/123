"""Tests for historical A-D difference and A/D ratio metrics."""


import pandas as pd
import pytest

from core.market_intelligence.ad_metrics import (
    AdvanceDeclineMetricsError,
    calculate_historical_ad_metrics,
)


def classification(rows):
    columns = [
        "observation_date",
        "advancing",
        "declining",
        "unchanged",
        "verified_observations",
        "analysis_status",
    ]
    return {
        "analysis_status": "PASS",
        "summary": pd.DataFrame(rows, columns=columns),
    }


def test_ad_difference_and_ratio_are_calculated():
    result = calculate_historical_ad_metrics(classification([
        ("2026-11-13", 8, 4, 3, 15, "PASS"),
    ]))
    row = result["summary"].iloc[0]
    assert row["ad_difference"] == 4
    assert row["ad_ratio"] == 2.0
    assert row["ratio_status"] == "CALCULATED"
    assert result["analysis_status"] == "PASS"


def test_zero_decliners_has_explicit_state_and_no_infinite_ratio():
    result = calculate_historical_ad_metrics(classification([
        ("2026-11-13", 8, 0, 2, 10, "PASS"),
    ]))
    row = result["summary"].iloc[0]
    assert row["ad_difference"] == 8
    assert pd.isna(row["ad_ratio"])
    assert row["ratio_status"] == "NO_DECLINERS"


def test_zero_advancers_returns_zero_ratio_when_decliners_exist():
    result = calculate_historical_ad_metrics(classification([
        ("2026-11-13", 0, 5, 2, 7, "PASS"),
    ]))
    row = result["summary"].iloc[0]
    assert row["ad_difference"] == -5
    assert row["ad_ratio"] == 0.0
    assert row["ratio_status"] == "NO_ADVANCERS"


def test_no_advances_and_no_declines_has_explicit_undefined_state():
    result = calculate_historical_ad_metrics(classification([
        ("2026-11-13", 0, 0, 10, 10, "PASS"),
    ]))
    row = result["summary"].iloc[0]
    assert row["ad_difference"] == 0
    assert pd.isna(row["ad_ratio"])
    assert row["ratio_status"] == "NO_ADVANCES_OR_DECLINES"


def test_all_missing_review_row_is_not_relabelled_pass():
    result = calculate_historical_ad_metrics(classification([
        ("2026-11-13", 0, 0, 0, 0, "REVIEW"),
    ]))
    row = result["summary"].iloc[0]
    assert row["ad_difference"] == 0
    assert pd.isna(row["ad_ratio"])
    assert row["analysis_status"] == "REVIEW"


def test_review_metrics_are_calculated_only_on_verified_subset():
    result = calculate_historical_ad_metrics(classification([
        ("2026-11-13", 3, 2, 1, 6, "REVIEW"),
    ]))
    row = result["summary"].iloc[0]
    assert row["ad_difference"] == 1
    assert row["ad_ratio"] == 1.5
    assert row["analysis_status"] == "REVIEW"


@pytest.mark.parametrize("status", ["BLOCKED", "UNAVAILABLE"])
def test_blocked_and_unavailable_dates_have_no_fabricated_metrics(status):
    result = calculate_historical_ad_metrics(classification([
        ("2026-11-13", None, None, None, None, status),
    ]))
    row = result["summary"].iloc[0]
    assert pd.isna(row["ad_difference"])
    assert pd.isna(row["ad_ratio"])
    assert row["ratio_status"] == "NOT_CALCULATED"
    assert row["analysis_status"] == status


def test_count_reconciliation_is_mandatory():
    with pytest.raises(AdvanceDeclineMetricsError, match="do not reconcile"):
        calculate_historical_ad_metrics(classification([
            ("2026-11-13", 3, 2, 1, 7, "PASS"),
        ]))


@pytest.mark.parametrize("field,value", [
    ("advancing", -1),
    ("declining", 1.5),
    ("unchanged", True),
    ("verified_observations", -2),
])
def test_counts_must_be_non_negative_integers(field, value):
    row = {
        "observation_date": "2026-11-13",
        "advancing": 1,
        "declining": 1,
        "unchanged": 1,
        "verified_observations": 3,
        "analysis_status": "PASS",
    }
    row[field] = value
    with pytest.raises(AdvanceDeclineMetricsError, match="non-negative integer"):
        calculate_historical_ad_metrics(classification([
            tuple(row[column] for column in [
                "observation_date", "advancing", "declining",
                "unchanged", "verified_observations", "analysis_status",
            ]),
        ]))


def test_duplicate_dates_are_rejected():
    with pytest.raises(AdvanceDeclineMetricsError, match="Duplicate"):
        calculate_historical_ad_metrics(classification([
            ("2026-11-13", 1, 1, 1, 3, "PASS"),
            ("2026-11-13", 1, 1, 1, 3, "PASS"),
        ]))


def test_dates_are_sorted_chronologically():
    result = calculate_historical_ad_metrics(classification([
        ("2026-11-14", 2, 1, 0, 3, "PASS"),
        ("2026-11-12", 1, 2, 0, 3, "PASS"),
    ]))
    assert result["summary"]["observation_date"].tolist() == [
        "2026-11-12",
        "2026-11-14",
    ]


def test_overall_status_uses_strictest_date_status():
    result = calculate_historical_ad_metrics(classification([
        ("2026-11-12", 2, 1, 0, 3, "PASS"),
        ("2026-11-13", 2, 1, 0, 3, "REVIEW"),
    ]))
    assert result["analysis_status"] == "REVIEW"
    assert result["pass_count"] == 1
    assert result["review_count"] == 1


def test_unsupported_analysis_status_is_rejected():
    with pytest.raises(AdvanceDeclineMetricsError, match="Unsupported analysis status"):
        calculate_historical_ad_metrics(classification([
            ("2026-11-13", 1, 1, 1, 3, "UNKNOWN"),
        ]))
