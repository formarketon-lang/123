
from datetime import date

import pandas as pd
import pytest

from core import rs_scanner


def _price_data(closes):
    dates = pd.to_datetime([
        "2026-10-01",
        "2026-10-02",
        "2026-10-05",
    ])

    return pd.DataFrame({
        "Date": dates,
        "Open": closes,
        "High": [price + 1 for price in closes],
        "Low": [price - 1 for price in closes],
        "Close": closes,
        "Volume": [100000, 110000, 120000],
    })


def _universe():
    return pd.DataFrame({
        "Symbol": ["HINDUNILVR", "MARICO"],
        "ISIN": ["INE030A01027", "INE196A01026"],
        "Series": ["EQ", "EQ"],
    })


def _run_scanner(monkeypatch, symbol, fail_symbol=None):
    market_data = {
        "^NSEI": _price_data([100, 102, 104]),
        "^CNXFMCG": _price_data([100, 103, 106]),
        "HINDUNILVR": _price_data([100, 105, 110]),
        "MARICO": _price_data([100, 108, 112]),
    }

    calls = []

    def fake_get_market_data(
        requested_symbol,
        start_date,
        end_date,
        exchange,
    ):
        calls.append(requested_symbol)

        if requested_symbol == fail_symbol:
            raise RuntimeError("Simulated data fetch failure")

        return market_data[requested_symbol]

    def fake_validate_sector_membership(
        sector,
        symbols,
        universe=None,
    ):
        requested = {
            str(item).strip().upper()
            for item in symbols
        }

        if str(sector).strip().upper() != "FMCG":
            return False, "No verified sector membership."

        unverified = sorted(requested - {"HINDUNILVR"})

        if unverified:
            return False, (
                "Sector membership is not verified for: "
                + ", ".join(unverified)
            )

        return True, "All selected stocks passed membership audit."

    monkeypatch.setattr(
        rs_scanner,
        "get_market_data",
        fake_get_market_data,
    )

    monkeypatch.setattr(
        rs_scanner,
        "validate_sector_membership",
        fake_validate_sector_membership,
    )

    result = rs_scanner.execute_scanner(
        sector="FMCG",
        manual_symbols=symbol,
        exchange="NSE",
        benchmark_name="Nifty 50",
        sector_benchmark_symbol="^CNXFMCG",
        start_date=date(2026, 10, 1),
        end_date=date(2026, 10, 5),
        custom_windows=[],
        universe=_universe(),
    )

    return result, calls


# --------------------------------------------------
# Existing NSE Integration Tests
# --------------------------------------------------

def test_verified_stock_gets_main_and_sector_comparisons(
    monkeypatch,
):
    result, calls = _run_scanner(
        monkeypatch,
        "HINDUNILVR",
    )

    assert len(result["main_results"]) == 1
    assert len(result["sector_results"]) == 1

    assert result["main_results"][0]["Stock"] == "HINDUNILVR"
    assert result["sector_results"][0]["Stock"] == "HINDUNILVR"

    assert result["sector_comparison_available"] is True

    assert "^NSEI" in calls
    assert "^CNXFMCG" in calls


def test_unverified_stock_keeps_main_but_blocks_sector(
    monkeypatch,
):
    result, calls = _run_scanner(
        monkeypatch,
        "MARICO",
    )

    assert len(result["main_results"]) == 1
    assert result["main_results"][0]["Stock"] == "MARICO"

    assert result["sector_results"] == []
    assert result["sector_comparison_available"] is False

    assert "MARICO" in result["sector_comparison_reason"]

    assert "^NSEI" in calls
    assert "^CNXFMCG" not in calls


def test_sector_data_failure_does_not_block_main_results(
    monkeypatch,
):
    result, calls = _run_scanner(
        monkeypatch,
        "HINDUNILVR",
        fail_symbol="^CNXFMCG",
    )

    assert len(result["main_results"]) == 1
    assert result["sector_results"] == []

    assert result["sector_comparison_available"] is False

    assert "could not be fetched" in (
        result["sector_comparison_reason"]
    )

    assert "^NSEI" in calls
    assert "^CNXFMCG" in calls

    assert any(
        error["Stock"] == "SECTOR INDEX"
        for error in result["errors"]
    )


# --------------------------------------------------
# New BSE Fail-Closed Security Tests
# --------------------------------------------------

def test_bse_manual_symbol_is_rejected_before_market_data(
    monkeypatch,
):
    calls = []

    def unexpected_market_data(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError(
            "BSE symbol must never reach market-data provider."
        )

    monkeypatch.setattr(
        rs_scanner,
        "get_market_data",
        unexpected_market_data,
    )

    with pytest.raises(
        ValueError,
        match="BSE Scanner বন্ধ রাখা হয়েছে",
    ):
        rs_scanner.execute_scanner(
            sector="FMCG",
            manual_symbols="500034",
            exchange="BSE",
            benchmark_name="Nifty 50",
            sector_benchmark_symbol="^CNXFMCG",
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 5),
            custom_windows=[],
            universe=_universe(),
        )

    assert calls == []


def test_bse_manual_symbol_is_rejected_by_symbol_resolver():
    with pytest.raises(
        ValueError,
        match="BSE Scanner বন্ধ রাখা হয়েছে",
    ):
        rs_scanner.resolve_symbols(
            sector="FMCG",
            manual_symbols="500034",
            exchange="BSE",
            universe=_universe(),
        )
