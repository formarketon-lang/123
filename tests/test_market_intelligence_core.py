
"""Tests for the Market Intelligence Core Engine."""

import pandas as pd
import pytest

from core.market_intelligence import (
    analyze_market_breadth,
    analyze_market_regime,
)


def make_index_data(closes):
    dates = pd.date_range("2025-01-01", periods=len(closes))

    return pd.DataFrame({
        "Date": dates,
        "Close": closes,
        "Source": "NSE",
        "Validation Status": "PASS",
        "Fallback Reason": "",
    })


def test_regime_requires_sufficient_observations():
    data = make_index_data([100, 101, 102])

    with pytest.raises(ValueError, match="observations"):
        analyze_market_regime(
            data,
            short_window=2,
            long_window=3,
        )


def test_regime_rejects_invalid_window_order():
    data = make_index_data([100, 101, 102, 103])

    with pytest.raises(ValueError, match="Windows"):
        analyze_market_regime(
            data,
            short_window=3,
            long_window=2,
        )


def test_regime_returns_review_without_provenance():
    data = pd.DataFrame({
        "Date": pd.date_range("2025-01-01", periods=4),
        "Close": [100, 101, 102, 103],
    })

    result = analyze_market_regime(
        data,
        short_window=2,
        long_window=3,
    )

    assert result["regime"] in {
        "BULLISH", "BEARISH", "NEUTRAL"
    }
    assert result["analysis_status"] == "REVIEW"
    assert result["source"] == "UNKNOWN"


def test_regime_preserves_valid_nse_provenance():
    data = make_index_data(list(range(100, 111)))

    result = analyze_market_regime(
        data,
        short_window=2,
        long_window=3,
    )

    assert result["regime"] == "BULLISH"
    assert result["analysis_status"] == "PASS"
    assert result["source"] == "NSE"
    assert result["validation_status"] == "PASS"


def test_breadth_counts_all_three_categories():
    data = pd.DataFrame({
        "Symbol": ["AAA", "BBB", "CCC", "DDD"],
        "Previous Close": [100, 100, 100, 100],
        "Current Close": [110, 90, 100, 105],
    })

    result = analyze_market_breadth(
        data,
        expected_universe_size=4,
    )

    assert result["advancing"] == 2
    assert result["declining"] == 1
    assert result["unchanged"] == 1
    assert result["net_advances"] == 1
    assert result["coverage_pct"] == 100.0
    assert result["coverage_status"] == "PASS"


def test_partial_breadth_coverage_is_review():
    data = pd.DataFrame({
        "Symbol": ["AAA", "BBB"],
        "Previous Close": [100, 100],
        "Current Close": [110, 90],
    })

    result = analyze_market_breadth(
        data,
        expected_universe_size=4,
    )

    assert result["observed_stocks"] == 2
    assert result["coverage_pct"] == 50.0
    assert result["coverage_status"] == "REVIEW"


def test_breadth_without_expected_universe_is_review():
    data = pd.DataFrame({
        "Symbol": ["AAA", "BBB"],
        "Previous Close": [100, 100],
        "Current Close": [110, 90],
    })

    result = analyze_market_breadth(data)

    assert result["coverage_pct"] is None
    assert result["coverage_status"] == "REVIEW"


def test_breadth_rejects_duplicate_symbols():
    data = pd.DataFrame({
        "Symbol": ["AAA", "AAA"],
        "Previous Close": [100, 100],
        "Current Close": [110, 90],
    })

    with pytest.raises(ValueError, match="Duplicate"):
        analyze_market_breadth(data)


def test_breadth_rejects_missing_prices():
    data = pd.DataFrame({
        "Symbol": ["AAA"],
        "Previous Close": [100],
        "Current Close": [None],
    })

    with pytest.raises(ValueError, match="Invalid values"):
        analyze_market_breadth(data)
        
