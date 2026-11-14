"""Tests for accurate Chapter 02 range reconciliation summaries."""

import pandas as pd

from scripts.run_ch02_historical_ad_range_check import (
    _reconciliation_summary,
)


def test_reconciliation_summary_uses_coverage_totals_not_missing_top_level():
    result = {
        "missing_count": 0,
        "coverage": pd.DataFrame(
            {
                "missing": [11, 10],
                "identity_exceptions": [1, 2],
                "expected_universe": [2390, 2392],
                "verified_observations": [2379, 2382],
            }
        ),
        "reconciliation_details": pd.DataFrame(
            {
                "issue_type": [
                    "MISSING_EXPECTED_MEMBER",
                    "IDENTITY_EXCEPTION",
                    "IDENTITY_EXCEPTION_NOT_VERIFIED",
                ]
            }
        ),
    }

    summary = _reconciliation_summary(result)

    assert summary["missing_count"] == 21
    assert summary["identity_exception_count"] == 3
    assert summary["expected_member_observations"] == 4782
    assert summary["verified_member_observations"] == 4761
    assert summary["reconciliation_detail_count"] == 3
    assert summary["reconciliation_issue_type_counts"] == {
        "MISSING_EXPECTED_MEMBER": 1,
        "IDENTITY_EXCEPTION": 1,
        "IDENTITY_EXCEPTION_NOT_VERIFIED": 1,
    }


def test_reconciliation_summary_handles_missing_evidence_frames():
    summary = _reconciliation_summary({})

    assert summary["missing_count"] == 0
    assert summary["identity_exception_count"] == 0
    assert summary["expected_member_observations"] == 0
    assert summary["verified_member_observations"] == 0
    assert summary["reconciliation_detail_count"] == 0
    assert summary["reconciliation_issue_type_counts"] == {}
