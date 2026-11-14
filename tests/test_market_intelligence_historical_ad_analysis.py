"""Tests for the pure historical A/D analysis orchestration module."""

import ast
from pathlib import Path

import pandas as pd
import pytest

from core.market_intelligence.historical_ad_analysis import (
    HistoricalADAnalysisError,
    analyze_historical_advance_decline,
)


def observations(day="2026-11-12"):
    return pd.DataFrame([
        (day, "AAA", "INE000A01010", 100, 110),
        (day, "BBB", "INE000B01010", 100, 90),
        (day, "CCC", "INE000C01010", 100, 100),
    ], columns=[
        "Date", "Symbol", "ISIN", "Previous Close", "Current Close",
    ])


def record(day="2026-11-12", status="PASS", frame=None,
           expected=3, verified=3, missing=0, exceptions=0,
           coverage=100.0):
    if frame is None:
        frame = observations(day)
    return {
        "observation_date": day,
        "status": status,
        "error_type": None,
        "error": None,
        "source": "NSE_UDIFF",
        "source_url": "https://example.invalid/nse-archive",
        "source_filename": f"CM_{day}.zip",
        "source_sha256": "a" * 64,
        "fetched_at_utc": "2026-11-14T04:00:00Z",
        "mii_snapshot_date": day,
        "expected_symbols": expected,
        "verified_symbols": verified,
        "missing_count": missing,
        "identity_exception_count": exceptions,
        "coverage_pct": coverage,
        "verified_observations": frame,
    }


def test_core_analysis_returns_daily_metrics_coverage_and_cumulative_line():
    history = {"per_date": [
        record("2026-11-12"),
        record("2026-11-13", frame=observations("2026-11-13")),
    ]}
    result = analyze_historical_advance_decline(
        history,
        ["2026-11-12", "2026-11-13"],
    )
    assert result["analysis_status"] == "PASS"
    assert result["date_count"] == 2
    assert result["daily_metrics"]["summary"]["ad_difference"].tolist() == [0, 0]
    assert result["per_date_status"]["coverage_pct"].tolist() == [100.0, 100.0]
    assert result["cumulative_line"]["summary"]["cumulative_ad"].tolist() == [0, 0]
    assert list(result["coverage"].columns) == [
        "observation_date", "expected_universe", "verified_observations",
        "missing", "identity_exceptions", "coverage_pct", "analysis_status",
    ]


def test_source_provenance_is_retained_per_observation_date():
    result = analyze_historical_advance_decline(
        {"per_date": [record()]},
        ["2026-11-12"],
    )
    row = result["provenance"].iloc[0]
    assert row["source"] == "NSE_UDIFF"
    assert row["source_filename"] == "CM_2026-11-12.zip"
    assert row["source_sha256"] == "a" * 64
    assert row["mii_snapshot_date"] == "2026-11-12"
    assert row["fetched_at_utc"] == "2026-11-14T04:00:00Z"


def test_expected_session_missing_from_history_is_explicit_and_breaks_line():
    history = {"per_date": [
        record("2026-11-12"),
        record("2026-11-16", frame=observations("2026-11-16")),
    ]}
    result = analyze_historical_advance_decline(
        history,
        ["2026-11-12", "2026-11-13", "2026-11-16"],
    )
    rows = result["per_date_status"]
    assert rows["analysis_status"].tolist() == ["PASS", "MISSING", "PASS"]
    assert pd.isna(rows["cumulative_ad"].iloc[1])
    assert rows["cumulative_ad"].iloc[2] == 0
    assert rows["cumulative_segment_id"].iloc[2] == 2
    assert result["analysis_status"] == "REVIEW"


def test_review_date_keeps_review_and_verified_subset_coverage():
    partial = observations().iloc[:2].copy()
    result = analyze_historical_advance_decline(
        {"per_date": [record(
            status="REVIEW",
            frame=partial,
            expected=3,
            verified=2,
            missing=1,
            coverage=66.6666667,
        )]},
        ["2026-11-12"],
    )
    row = result["per_date_status"].iloc[0]
    assert row["analysis_status"] == "REVIEW"
    assert row["verified_observations"] == 2
    assert row["missing"] == 1
    assert pd.isna(row["cumulative_ad"])


def test_unavailable_date_has_no_fabricated_daily_metrics():
    unavailable = {
        "observation_date": "2026-11-12",
        "status": "UNAVAILABLE",
        "error_type": "ArchiveUnavailable",
        "error": "NSE archive unavailable",
        "source": None,
        "source_url": None,
        "source_filename": None,
        "source_sha256": None,
        "fetched_at_utc": None,
        "mii_snapshot_date": None,
        "expected_symbols": None,
        "verified_symbols": 0,
        "missing_count": None,
        "identity_exception_count": None,
        "coverage_pct": None,
        "verified_observations": pd.DataFrame(),
    }
    result = analyze_historical_advance_decline(
        {"per_date": [unavailable]},
        ["2026-11-12"],
    )
    row = result["per_date_status"].iloc[0]
    assert result["analysis_status"] == "UNAVAILABLE"
    assert pd.isna(row["advancing"])
    assert pd.isna(row["ad_difference"])
    assert pd.isna(row["cumulative_ad"])


def test_blocked_date_remains_blocked_in_core_status():
    blocked = {
        "observation_date": "2026-11-12",
        "status": "BLOCKED",
        "error_type": None,
        "error": "Identity conflict",
        "source": "NSE_UDIFF",
        "source_url": None,
        "source_filename": None,
        "source_sha256": None,
        "fetched_at_utc": None,
        "mii_snapshot_date": "2026-11-12",
        "expected_symbols": 3,
        "verified_symbols": 2,
        "missing_count": 0,
        "identity_exception_count": 1,
        "coverage_pct": 66.7,
        "verified_observations": pd.DataFrame(),
    }
    result = analyze_historical_advance_decline(
        {"per_date": [blocked]},
        ["2026-11-12"],
    )
    assert result["analysis_status"] == "BLOCKED"
    assert result["blocked_count"] == 1
    assert pd.isna(result["per_date_status"].iloc[0]["ad_difference"])


def test_duplicate_source_dates_are_rejected():
    with pytest.raises(HistoricalADAnalysisError, match="Duplicate"):
        analyze_historical_advance_decline(
            {"per_date": [record(), record()]},
            ["2026-11-12"],
        )


def test_metrics_dates_outside_expected_calendar_are_rejected():
    with pytest.raises(ValueError, match="not in the verified"):
        analyze_historical_advance_decline(
            {"per_date": [record()]},
            ["2026-11-13"],
        )


def test_wrong_date_observation_rows_are_rejected_by_daily_classifier():
    wrong_date = observations("2026-11-11")
    with pytest.raises(ValueError, match="mismatched date"):
        analyze_historical_advance_decline(
            {"per_date": [record(frame=wrong_date)]},
            ["2026-11-12"],
        )


def test_core_module_has_no_network_or_streamlit_imports():
    path = Path("core/market_intelligence/historical_ad_analysis.py")
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert "streamlit" not in imported
    assert "requests" not in imported
    assert "yfinance" not in imported


def test_initial_anchor_flows_into_cumulative_line():
    result = analyze_historical_advance_decline(
        {"per_date": [record()]},
        ["2026-11-12"],
        initial_anchor=50,
    )
    assert result["cumulative_line"]["summary"].iloc[0]["cumulative_ad"] == 50


def test_core_rejects_missing_per_date_records():
    with pytest.raises(HistoricalADAnalysisError, match="per-date"):
        analyze_historical_advance_decline({}, ["2026-11-12"])
