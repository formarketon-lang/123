
"""Tests for Market Intelligence breadth integration."""

import pandas as pd
import pytest

from services.market_intelligence.breadth_service import (
    analyze_nse_market_breadth,
)


def make_universe():
    return pd.DataFrame({
        "Symbol": ["AAA", "BBB", "CCC"],
        "ISIN": [
            "INE000A01010",
            "INE000B01010",
            "INE000C01010",
        ],
        "Series": ["EQ", "EQ", "EQ"],
        "Exchange": ["NSE", "NSE", "NSE"],
        "Source": ["NSE MII Security Master"] * 3,
        "Universe As Of Date": ["2025-01-02"] * 3,
        "Universe Verification Status": ["MII_DATED"] * 3,
    })


def make_stock_data():
    return pd.DataFrame({
        "Date": ["2025-01-02"] * 3,
        "Symbol": ["AAA", "BBB", "CCC"],
        "Previous Close": [100, 100, 100],
        "Current Close": [110, 90, 100],
        "Source": ["NSE"] * 3,
        "Exchange": ["NSE"] * 3,
        "Timeframe": ["1d"] * 3,
        "Fallback Reason": [""] * 3,
        "Validation Status": ["PASS"] * 3,
    })


def test_valid_nse_breadth_integration():
    result = analyze_nse_market_breadth(
        make_stock_data(),
        make_universe(),
        "2025-01-02",
    )

    assert result["advancing"] == 1
    assert result["declining"] == 1
    assert result["unchanged"] == 1
    assert result["coverage_pct"] == 100.0
    assert result["coverage_status"] == "PASS"
    assert result["analysis_status"] == "PASS"
    assert result["data_sources"] == ["NSE"]


def test_incomplete_coverage_returns_review():
    data = make_stock_data().iloc[:2].copy()

    result = analyze_nse_market_breadth(
        data,
        make_universe(),
        "2025-01-02",
    )

    assert result["coverage_pct"] < 100.0
    assert result["coverage_status"] == "REVIEW"
    assert result["analysis_status"] == "REVIEW"


def test_yahoo_fallback_provenance_is_preserved():
    data = make_stock_data()
    data.loc[0, "Source"] = "Yahoo"
    data.loc[0, "Fallback Reason"] = "NSE unavailable"

    result = analyze_nse_market_breadth(
        data,
        make_universe(),
        "2025-01-02",
    )

    assert result["data_sources"] == ["NSE", "YAHOO"]
    assert result["source_counts"]["YAHOO"] == 1
    assert result["yahoo_fallback_symbols"] == ["AAA"]


def test_yahoo_without_fallback_reason_is_rejected():
    data = make_stock_data()
    data.loc[0, "Source"] = "Yahoo"

    with pytest.raises(ValueError, match="fallback reason"):
        analyze_nse_market_breadth(
            data,
            make_universe(),
            "2025-01-02",
        )


def test_wrong_exchange_is_rejected():
    data = make_stock_data()
    data.loc[0, "Exchange"] = "BSE"

    with pytest.raises(ValueError, match="Only NSE"):
        analyze_nse_market_breadth(
            data,
            make_universe(),
            "2025-01-02",
        )


def test_failed_validation_is_rejected():
    data = make_stock_data()
    data.loc[0, "Validation Status"] = "FAIL"

    with pytest.raises(ValueError, match="did not PASS"):
        analyze_nse_market_breadth(
            data,
            make_universe(),
            "2025-01-02",
        )


def test_observation_date_mismatch_is_rejected():
    data = make_stock_data()
    data.loc[0, "Date"] = "2025-01-01"

    with pytest.raises(ValueError, match="match the requested date"):
        analyze_nse_market_breadth(
            data,
            make_universe(),
            "2025-01-02",
        )


def test_undated_universe_is_rejected():
    universe = make_universe()
    universe["Universe Verification Status"] = "LEGACY_UNDATED"

    with pytest.raises(ValueError, match="dated official NSE MII"):
        analyze_nse_market_breadth(
            make_stock_data(),
            universe,
            "2025-01-02",
        )


def test_duplicate_symbols_are_rejected():
    data = make_stock_data()
    data.loc[1, "Symbol"] = "AAA"

    with pytest.raises(ValueError, match="Duplicate"):
        analyze_nse_market_breadth(
            data,
            make_universe(),
            "2025-01-02",
        )
