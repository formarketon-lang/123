"""Tests for cumulative A-D line and verified-session gap policy."""

import pandas as pd
import pytest

from core.market_intelligence.cumulative_ad_line import (
    CumulativeADLineError,
    calculate_cumulative_ad_line,
)


def metrics(rows):
    return {
        "summary": pd.DataFrame(
            rows,
            columns=["observation_date", "ad_difference", "analysis_status"],
        )
    }


def test_cumulative_line_uses_daily_ad_difference_in_order():
    result = calculate_cumulative_ad_line(
        metrics([
            ("2026-11-12", 3, "PASS"),
            ("2026-11-13", -2, "PASS"),
            ("2026-11-16", 4, "PASS"),
        ]),
        ["2026-11-12", "2026-11-13", "2026-11-16"],
    )
    assert result["summary"]["cumulative_ad"].tolist() == [3, 1, 5]
    assert result["summary"]["segment_id"].tolist() == [1, 1, 1]
    assert result["analysis_status"] == "PASS"


def test_initial_anchor_is_applied_to_first_pass_session():
    result = calculate_cumulative_ad_line(
        metrics([("2026-11-12", 3, "PASS")]),
        ["2026-11-12"],
        initial_anchor=100,
    )
    assert result["summary"].iloc[0]["cumulative_ad"] == 103
    assert result["initial_anchor"] == 100


def test_missing_expected_session_breaks_segment_and_resets_next_pass():
    result = calculate_cumulative_ad_line(
        metrics([
            ("2026-11-12", 3, "PASS"),
            ("2026-11-16", 4, "PASS"),
        ]),
        ["2026-11-12", "2026-11-13", "2026-11-16"],
    )
    rows = result["summary"]
    assert rows["cumulative_ad"].iloc[0] == 3
    assert pd.isna(rows["cumulative_ad"].iloc[1])
    assert rows["analysis_status"].iloc[1] == "MISSING"
    assert rows["cumulative_ad"].iloc[2] == 4
    assert rows["segment_id"].iloc[2] == 2
    assert result["analysis_status"] == "REVIEW"


@pytest.mark.parametrize("status", ["REVIEW", "BLOCKED", "UNAVAILABLE"])
def test_non_pass_session_breaks_segment_and_does_not_contribute(status):
    result = calculate_cumulative_ad_line(
        metrics([
            ("2026-11-12", 3, "PASS"),
            ("2026-11-13", None, status),
            ("2026-11-16", 4, "PASS"),
        ]),
        ["2026-11-12", "2026-11-13", "2026-11-16"],
    )
    rows = result["summary"]
    assert rows["cumulative_ad"].iloc[0] == 3
    assert pd.isna(rows["cumulative_ad"].iloc[1])
    assert rows["analysis_status"].iloc[1] == status
    assert rows["cumulative_ad"].iloc[2] == 4
    assert rows["segment_id"].iloc[2] == 2
    assert result["analysis_status"] == status


def test_nullable_dataframe_difference_column_accepts_integer_valued_float():
    result = calculate_cumulative_ad_line(
        metrics([
            ("2026-11-12", 3, "PASS"),
            ("2026-11-13", None, "BLOCKED"),
            ("2026-11-16", 4, "PASS"),
        ]),
        ["2026-11-12", "2026-11-13", "2026-11-16"],
    )
    assert result["summary"]["cumulative_ad"].iloc[2] == 4


def test_expected_sessions_must_be_unique_and_chronological():
    source = metrics([("2026-11-12", 3, "PASS")])
    with pytest.raises(CumulativeADLineError, match="unique"):
        calculate_cumulative_ad_line(source, ["2026-11-12", "2026-11-12"])
    with pytest.raises(CumulativeADLineError, match="chronological"):
        calculate_cumulative_ad_line(
            source, ["2026-11-13", "2026-11-12"]
        )


def test_metrics_outside_verified_session_calendar_are_rejected():
    with pytest.raises(CumulativeADLineError, match="not in the verified"):
        calculate_cumulative_ad_line(
            metrics([("2026-11-14", 1, "PASS")]),
            ["2026-11-13"],
        )


def test_duplicate_metrics_dates_are_rejected():
    with pytest.raises(CumulativeADLineError, match="Duplicate"):
        calculate_cumulative_ad_line(
            metrics([
                ("2026-11-13", 1, "PASS"),
                ("2026-11-13", 2, "PASS"),
            ]),
            ["2026-11-13"],
        )


def test_invalid_pass_difference_is_rejected():
    with pytest.raises(CumulativeADLineError, match="requires an integer"):
        calculate_cumulative_ad_line(
            metrics([("2026-11-13", 1.5, "PASS")]),
            ["2026-11-13"],
        )


def test_unsupported_status_is_rejected():
    with pytest.raises(CumulativeADLineError, match="Unsupported"):
        calculate_cumulative_ad_line(
            metrics([("2026-11-13", 1, "UNKNOWN")]),
            ["2026-11-13"],
        )


def test_repeated_calculation_is_deterministic():
    source = metrics([
        ("2026-11-12", 3, "PASS"),
        ("2026-11-13", -1, "PASS"),
    ])
    sessions = ["2026-11-12", "2026-11-13"]
    first = calculate_cumulative_ad_line(source, sessions)["summary"]
    second = calculate_cumulative_ad_line(source, sessions)["summary"]
    pd.testing.assert_frame_equal(first, second)


def test_empty_expected_sessions_are_rejected():
    with pytest.raises(CumulativeADLineError, match="At least one"):
        calculate_cumulative_ad_line(
            metrics([("2026-11-13", 1, "PASS")]), []
        )
