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


def make_verified_universe(snapshot_date="2025-01-02"):
    return pd.DataFrame({
        "Symbol": ["AAA", "BBB", "CCC", "DDD"],
        "ISIN": [
            "INE000A01010",
            "INE000B01010",
            "INE000C01010",
            "INE000D01010",
        ],
        "Series": ["EQ"] * 4,
        "Exchange": ["NSE"] * 4,
        "Source": ["NSE MII Security Master"] * 4,
        "Universe As Of Date": [snapshot_date] * 4,
        "Universe Verification Status": ["MII_DATED"] * 4,
    })


def make_breadth_data():
    return pd.DataFrame({
        "Symbol": ["AAA", "BBB", "CCC", "DDD"],
        "Previous Close": [100, 100, 100, 100],
        "Current Close": [110, 90, 100, 105],
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


def test_breadth_passes_with_exact_membership_and_same_date():
    result = analyze_market_breadth(
        make_breadth_data(),
        verified_universe=make_verified_universe(),
        observation_date="2025-01-02",
    )

    assert result["advancing"] == 2
    assert result["declining"] == 1
    assert result["unchanged"] == 1
    assert result["net_advances"] == 1
    assert result["coverage_pct"] == 100.0
    assert result["universe_verified"] is True
    assert result["membership_complete"] is True
    assert result["universe_snapshot_status"] == "PASS"
    assert result["universe_snapshot_reason"] == (
        "UNIVERSE_SNAPSHOT_DATE_ALIGNED"
    )
    assert result["coverage_status"] == "PASS"


def test_count_match_without_verified_universe_is_review():
    result = analyze_market_breadth(
        make_breadth_data(),
        expected_universe_size=4,
    )

    assert result["observed_stocks"] == 4
    assert result["coverage_pct"] == 100.0
    assert result["universe_verified"] is False
    assert result["coverage_status"] == "REVIEW"


def test_partial_verified_universe_coverage_is_review():
    data = make_breadth_data().iloc[:2].copy()

    result = analyze_market_breadth(
        data,
        verified_universe=make_verified_universe(),
        observation_date="2025-01-02",
    )

    assert result["observed_stocks"] == 2
    assert result["coverage_pct"] == 50.0
    assert result["membership_complete"] is False
    assert result["coverage_status"] == "REVIEW"


def test_unexpected_symbol_is_rejected():
    data = make_breadth_data()
    data.loc[0, "Symbol"] = "UNKNOWN"

    with pytest.raises(ValueError, match="not in verified NSE universe"):
        analyze_market_breadth(
            data,
            verified_universe=make_verified_universe(),
            observation_date="2025-01-02",
        )


def test_non_mii_universe_is_rejected():
    universe = make_verified_universe()
    universe["Source"] = "NSE Official Equity Master"

    with pytest.raises(ValueError, match="official NSE MII"):
        analyze_market_breadth(
            make_breadth_data(),
            verified_universe=universe,
            observation_date="2025-01-02",
        )


def test_non_eq_universe_is_rejected():
    universe = make_verified_universe()
    universe.loc[0, "Series"] = "BE"

    with pytest.raises(ValueError, match="NSE EQ"):
        analyze_market_breadth(
            make_breadth_data(),
            verified_universe=universe,
            observation_date="2025-01-02",
        )


def test_invalid_isin_in_universe_is_rejected():
    universe = make_verified_universe()
    universe.loc[0, "ISIN"] = "INVALID"

    with pytest.raises(ValueError, match="invalid ISIN"):
        analyze_market_breadth(
            make_breadth_data(),
            verified_universe=universe,
            observation_date="2025-01-02",
        )


def test_duplicate_universe_symbol_is_rejected():
    universe = make_verified_universe()
    universe.loc[1, "Symbol"] = "AAA"

    with pytest.raises(ValueError, match="duplicate symbols"):
        analyze_market_breadth(
            make_breadth_data(),
            verified_universe=universe,
            observation_date="2025-01-02",
        )


def test_duplicate_breadth_symbols_are_rejected():
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


def test_missing_snapshot_date_is_review():
    universe = make_verified_universe().drop(
        columns=["Universe As Of Date"]
    )

    result = analyze_market_breadth(
        make_breadth_data(),
        verified_universe=universe,
        observation_date="2025-01-02",
    )

    assert result["membership_complete"] is True
    assert result["universe_snapshot_status"] == "REVIEW"
    assert result["universe_snapshot_reason"] == (
        "UNIVERSE_SNAPSHOT_DATE_MISSING"
    )
    assert result["coverage_status"] == "REVIEW"


def test_missing_observation_date_is_review():
    result = analyze_market_breadth(
        make_breadth_data(),
        verified_universe=make_verified_universe(),
    )

    assert result["membership_complete"] is True
    assert result["universe_snapshot_status"] == "REVIEW"
    assert result["universe_snapshot_reason"] == (
        "OBSERVATION_DATE_MISSING"
    )
    assert result["coverage_status"] == "REVIEW"


def test_future_snapshot_is_rejected():
    universe = make_verified_universe(
        snapshot_date="2025-01-03"
    )

    with pytest.raises(ValueError, match="Future NSE universe snapshot"):
        analyze_market_breadth(
            make_breadth_data(),
            verified_universe=universe,
            observation_date="2025-01-02",
        )


def test_older_snapshot_is_review_not_pass():
    universe = make_verified_universe(
        snapshot_date="2025-01-01"
    )

    result = analyze_market_breadth(
        make_breadth_data(),
        verified_universe=universe,
        observation_date="2025-01-02",
    )

    assert result["membership_complete"] is True
    assert result["universe_snapshot_status"] == "REVIEW"
    assert result["universe_snapshot_reason"] == (
        "UNIVERSE_SNAPSHOT_DATE_NOT_ALIGNED"
    )
    assert result["coverage_status"] == "REVIEW"


def test_inconsistent_snapshot_dates_are_review():
    universe = make_verified_universe()
    universe.loc[0, "Universe As Of Date"] = "2025-01-01"

    result = analyze_market_breadth(
        make_breadth_data(),
        verified_universe=universe,
        observation_date="2025-01-02",
    )

    assert result["universe_snapshot_status"] == "REVIEW"
    assert result["universe_snapshot_reason"] == (
        "UNIVERSE_SNAPSHOT_DATE_INCONSISTENT"
    )
    assert result["coverage_status"] == "REVIEW"


def test_invalid_observation_date_is_review():
    result = analyze_market_breadth(
        make_breadth_data(),
        verified_universe=make_verified_universe(),
        observation_date="not-a-date",
    )

    assert result["universe_snapshot_status"] == "REVIEW"
    assert result["universe_snapshot_reason"] == (
        "OBSERVATION_DATE_INVALID"
    )
    assert result["coverage_status"] == "REVIEW"
