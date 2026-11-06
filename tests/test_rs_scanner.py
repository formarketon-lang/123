"""Integration tests for the Relative Strength Scanner."""

from datetime import date

import pandas as pd
import pytest

import core.rs_scanner as scanner
from ui.rs_results import build_ranked_results


def sample_universe():
    return pd.DataFrame({
        "Symbol": ["RELIANCE", "MIDSTOCK", "SMALLSTOCK"],
        "ISIN": [
            "INE002A01018",
            "INE111A01011",
            "INE222A01022",
        ],
        "Series": ["EQ", "EQ", "EQ"],
    })


def sample_market_cap_universe():
    universe = sample_universe().copy()
    universe["Market Cap Category"] = [
        "LARGE CAP",
        "MID CAP",
        "SMALL CAP",
    ]
    universe["Market Cap Match Status"] = "MATCHED"
    return universe


def sample_prices(start=100, end=110):
    return pd.DataFrame({
        "Date": [
            pd.Timestamp("2026-01-01"),
            pd.Timestamp("2026-01-02"),
        ],
        "Close": [start, end],
    })


def configure_scanner(monkeypatch):
    """Replace external data sources with deterministic test data."""
    monkeypatch.setattr(
        scanner,
        "get_sector_symbols",
        lambda sector, universe=None: [
            "RELIANCE",
            "MIDSTOCK",
            "SMALLSTOCK",
        ],
    )

    monkeypatch.setattr(
        scanner,
        "validate_sector_membership",
        lambda sector, symbols, universe=None: (
            True,
            "Official sector membership audit passed.",
        ),
    )

    monkeypatch.setattr(
        scanner,
        "get_sector_benchmark",
        lambda sector: "^CNXFMCG",
    )

    price_data = {
        "^NSEI": sample_prices(100, 105),
        "^NSMIDCP": sample_prices(100, 108),
        "^CNXFMCG": sample_prices(100, 106),
        "RELIANCE": sample_prices(100, 120),
        "MIDSTOCK": sample_prices(100, 115),
        "SMALLSTOCK": sample_prices(100, 112),
    }

    requested_symbols = []

    def fake_market_data(symbol, start_date, end_date, exchange):
        requested_symbols.append(symbol)
        if symbol not in price_data:
            raise AssertionError(
                f"Unexpected market-data request: {symbol}"
            )
        return price_data[symbol].copy()

    monkeypatch.setattr(
        scanner,
        "get_market_data",
        fake_market_data,
    )

    return requested_symbols


def run_test_scanner(
    universe,
    market_cap_universe,
    market_cap_filter,
    manual_symbols="",
    benchmark_names=None,
):
    return scanner.execute_scanner(
        sector="FMCG",
        manual_symbols=manual_symbols,
        exchange="NSE",
        benchmark_name="Nifty 50",
        benchmark_names=benchmark_names,
        sector_benchmark_symbol="^CNXFMCG",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 2),
        custom_windows=[],
        selected_symbols=[],
        universe=universe,
        market_cap_filter=market_cap_filter,
        market_cap_universe=market_cap_universe,
    )


def test_large_cap_scan_excludes_mid_and_small_caps(monkeypatch):
    requested = configure_scanner(monkeypatch)

    result = run_test_scanner(
        universe=sample_universe(),
        market_cap_universe=sample_market_cap_universe(),
        market_cap_filter="Large Cap",
    )

    assert result["symbols"] == ["RELIANCE"]
    assert "RELIANCE" in requested
    assert "MIDSTOCK" not in requested
    assert "SMALLSTOCK" not in requested
    assert result["market_cap_filter"] == "Large Cap"
    assert result["market_cap_verified_count"] == 1
    assert result["main_results"]
    assert result["sector_results"]


def test_manual_symbol_outside_selected_category_is_rejected(
    monkeypatch,
):
    configure_scanner(monkeypatch)

    with pytest.raises(ValueError, match="MIDSTOCK"):
        run_test_scanner(
            universe=sample_universe(),
            market_cap_universe=sample_market_cap_universe(),
            market_cap_filter="Large Cap",
            manual_symbols="MIDSTOCK",
        )


def test_fmcg_sector_scan_intersects_selected_market_cap(
    monkeypatch,
):
    requested = configure_scanner(monkeypatch)

    result = run_test_scanner(
        universe=sample_universe(),
        market_cap_universe=sample_market_cap_universe(),
        market_cap_filter="Mid Cap",
    )

    assert result["symbols"] == ["MIDSTOCK"]
    assert "MIDSTOCK" in requested
    assert "RELIANCE" not in requested
    assert "SMALLSTOCK" not in requested
    assert result["market_cap_filter"] == "Mid Cap"
    assert result["market_cap_verified_count"] == 1
    assert result["sector_comparison_available"] is True


def test_scanner_fails_closed_when_amfi_data_is_missing(
    monkeypatch,
):
    requested = configure_scanner(monkeypatch)

    with pytest.raises(
        ValueError,
        match="Verified AMFI Market Cap data is required",
    ):
        run_test_scanner(
            universe=sample_universe(),
            market_cap_universe=None,
            market_cap_filter="Large Cap",
        )

    assert requested == []


def test_multiple_benchmarks_create_independent_results(
    monkeypatch,
):
    configure_scanner(monkeypatch)

    result = run_test_scanner(
        universe=sample_universe(),
        market_cap_universe=sample_market_cap_universe(),
        market_cap_filter="All Market Caps",
        benchmark_names=["Nifty 50", "Nifty Next 50"],
    )

    assert result["benchmark_names"] == [
        "Nifty 50",
        "Nifty Next 50",
    ]

    assert result["benchmark_name"] == "Nifty 50"

    result_benchmarks = {
        row["Benchmark"]
        for row in result["main_results"]
    }

    assert result_benchmarks == {
        "Nifty 50",
        "Nifty Next 50",
    }

    assert any(
        row["Benchmark"] == "Nifty 50"
        for row in result["main_results"]
    )
    assert any(
        row["Benchmark"] == "Nifty Next 50"
        for row in result["main_results"]
    )


def test_stock_data_is_fetched_once_for_multiple_benchmarks(
    monkeypatch,
):
    requested = configure_scanner(monkeypatch)

    run_test_scanner(
        universe=sample_universe(),
        market_cap_universe=sample_market_cap_universe(),
        market_cap_filter="All Market Caps",
        benchmark_names=["Nifty 50", "Nifty Next 50"],
    )

    # The stock's historical data must be reused across benchmarks.
    assert requested.count("RELIANCE") == 1
    assert requested.count("MIDSTOCK") == 1
    assert requested.count("SMALLSTOCK") == 1

    # Both Main Benchmark datasets are independently requested.
    assert requested.count("^NSEI") == 1
    assert requested.count("^NSMIDCP") == 1


def test_invalid_benchmark_selection_is_rejected(monkeypatch):
    configure_scanner(monkeypatch)

    with pytest.raises(ValueError, match="Invalid Main Benchmark"):
        run_test_scanner(
            universe=sample_universe(),
            market_cap_universe=sample_market_cap_universe(),
            market_cap_filter="All Market Caps",
            benchmark_names=["Nifty 50", "Unverified Index"],
        )


def test_main_benchmark_ranking_is_separate_by_benchmark():
    rows = [
        {
            "Benchmark": "Nifty 50",
            "Stock": "AAA",
            "Window": "1M",
            "Excess Return (%)": 5.0,
        },
        {
            "Benchmark": "Nifty 50",
            "Stock": "BBB",
            "Window": "1M",
            "Excess Return (%)": 2.0,
        },
        {
            "Benchmark": "Nifty Next 50",
            "Stock": "BBB",
            "Window": "1M",
            "Excess Return (%)": 8.0,
        },
        {
            "Benchmark": "Nifty Next 50",
            "Stock": "AAA",
            "Window": "1M",
            "Excess Return (%)": 1.0,
        },
    ]

    ranked = build_ranked_results(
        rows,
        ["1M"],
        "Excess Return (%)",
    )

    nifty50 = ranked[
        ranked["Benchmark"] == "Nifty 50"
    ].reset_index(drop=True)

    next50 = ranked[
        ranked["Benchmark"] == "Nifty Next 50"
    ].reset_index(drop=True)

    assert nifty50["Stock"].tolist() == ["AAA", "BBB"]
    assert nifty50["Rank"].tolist() == [1, 2]

    assert next50["Stock"].tolist() == ["BBB", "AAA"]
    assert next50["Rank"].tolist() == [1, 2]


def test_empty_benchmark_selection_is_rejected(monkeypatch):
    configure_scanner(monkeypatch)

    with pytest.raises(ValueError, match="কমপক্ষে একটি"):
        run_test_scanner(
            universe=sample_universe(),
            market_cap_universe=sample_market_cap_universe(),
            market_cap_filter="All Market Caps",
            benchmark_names=[],
    )
    
