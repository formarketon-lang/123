
import pandas as pd
import pytest

from data.providers.nse_bhavcopy_mii_validation import (
    NSEMIIReconciliationError,
    reconcile_bhavcopy_with_mii,
)


def make_universe():
    return pd.DataFrame({
        "Symbol": ["AAA", "BBB", "CCC"],
        "ISIN": ["INE000A01010", "INE000B01010", "INE000C01010"],
        "Series": ["EQ"] * 3,
        "Exchange": ["NSE"] * 3,
        "Source": ["NSE MII Security Master"] * 3,
        "Universe As Of Date": ["2026-11-12"] * 3,
        "Universe Verification Status": ["MII_DATED"] * 3,
    })


def make_bhavcopy():
    return pd.DataFrame({
        "Date": ["2026-11-12"] * 3,
        "Symbol": ["AAA", "BBB", "CCC"],
        "ISIN": ["INE000A01010", "INE000B01010", "INE000C01010"],
        "Series": ["EQ"] * 3,
    })


def test_exact_mii_identity_and_full_coverage_pass():
    result = reconcile_bhavcopy_with_mii(
        make_bhavcopy(), make_universe()
    )
    assert result["identity_status"] == "PASS"
    assert result["coverage_status"] == "PASS"
    assert result["coverage_pct"] == 100.0
    assert result["missing_symbols"] == []


def test_missing_bhavcopy_symbol_is_review_not_fake_data():
    data = make_bhavcopy().iloc[:2].copy()
    result = reconcile_bhavcopy_with_mii(data, make_universe())

    assert result["identity_status"] == "PASS"
    assert result["coverage_status"] == "REVIEW"
    assert result["missing_symbols"] == ["CCC"]


def test_unknown_symbol_is_rejected():
    data = make_bhavcopy()
    data.loc[0, "Symbol"] = "UNKNOWN"

    with pytest.raises(NSEMIIReconciliationError, match="absent from MII"):
        reconcile_bhavcopy_with_mii(data, make_universe())


def test_symbol_isin_mismatch_is_rejected():
    data = make_bhavcopy()
    data.loc[0, "ISIN"] = "INE999Z01010"

    with pytest.raises(NSEMIIReconciliationError, match="mismatch"):
        reconcile_bhavcopy_with_mii(data, make_universe())


def test_wrong_snapshot_date_is_rejected():
    universe = make_universe()
    universe["Universe As Of Date"] = "2026-11-11"

    with pytest.raises(NSEMIIReconciliationError, match="exactly match"):
        reconcile_bhavcopy_with_mii(make_bhavcopy(), universe)


def test_undated_mii_is_rejected():
    universe = make_universe()
    universe["Universe Verification Status"] = "LEGACY_UNDATED"

    with pytest.raises(NSEMIIReconciliationError, match="MII_DATED"):
        reconcile_bhavcopy_with_mii(make_bhavcopy(), universe)


def test_duplicate_symbol_is_rejected():
    data = pd.concat(
        [make_bhavcopy(), make_bhavcopy().iloc[[0]]],
        ignore_index=True,
    )

    with pytest.raises(NSEMIIReconciliationError, match="duplicate symbols"):
        reconcile_bhavcopy_with_mii(data, make_universe())


def test_duplicate_isin_in_universe_is_rejected():
    universe = make_universe()
    universe.loc[1, "ISIN"] = universe.loc[0, "ISIN"]

    with pytest.raises(NSEMIIReconciliationError, match="duplicate ISIN"):
        reconcile_bhavcopy_with_mii(make_bhavcopy(), universe)
