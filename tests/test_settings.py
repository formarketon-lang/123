
"""Regression tests for benchmark mappings and shared data settings."""

from data.benchmark_mapping import (
    MAIN_BENCHMARKS,
    SECTOR_BENCHMARKS,
    get_main_benchmarks,
    get_sector_benchmark,
    get_available_sector_mappings,
)
from ui import settings


# ---------------------------------------------------------
# Benchmark Mapping Tests
# ---------------------------------------------------------


def test_all_configured_main_benchmarks_are_available():
    result = get_main_benchmarks()

    assert result == MAIN_BENCHMARKS
    assert len(result) == 5


def test_main_benchmark_mapping_returns_independent_copy():
    result = get_main_benchmarks()
    result["Fake Index"] = "^FAKE"

    assert "Fake Index" not in get_main_benchmarks()


def test_only_verified_fmcg_sector_is_available():
    result = get_available_sector_mappings()

    assert result == {"FMCG": "^CNXFMCG"}
    assert result == SECTOR_BENCHMARKS


def test_sector_mapping_returns_independent_copy():
    result = get_available_sector_mappings()
    result["Unverified Sector"] = "^FAKE"

    assert (
        "Unverified Sector"
        not in get_available_sector_mappings()
    )


def test_verified_sector_benchmark_is_returned():
    assert get_sector_benchmark("FMCG") == "^CNXFMCG"


def test_unverified_sector_has_no_benchmark():
    assert get_sector_benchmark("Banking") is None
    assert get_sector_benchmark("IT") is None


def test_invalid_sector_input_is_rejected():
    assert get_sector_benchmark(None) is None
    assert get_sector_benchmark(123) is None


# ---------------------------------------------------------
# Shared Settings Test Helper
# ---------------------------------------------------------


def initialize_with_state(monkeypatch, initial_state):
    state = dict(initial_state)

    monkeypatch.setattr(
        settings.st,
        "session_state",
        state,
    )

    settings._initialize_settings()
    return state


# ---------------------------------------------------------
# Settings Regression Tests
# ---------------------------------------------------------


def test_default_settings_use_nse_primary_yahoo_secondary(
    monkeypatch,
):
    state = initialize_with_state(monkeypatch, {})

    assert (
        state["data_source"]
        == "NSE Primary + Yahoo Secondary"
    )
    assert state["settings_exchange"] == "NSE"
    assert state["settings_benchmark"] == "Nifty 50"
    assert state["settings_main_benchmarks"] == ["Nifty 50"]
    assert state["settings_sector"] == "All Sectors"
    assert state["settings_market_cap"] == "All Market Caps"


def test_legacy_yahoo_source_is_migrated(monkeypatch):
    state = initialize_with_state(
        monkeypatch,
        {"data_source": "Yahoo Finance"},
    )

    assert state["data_source"] == settings.ACTIVE_DATA_SOURCE


def test_invalid_saved_benchmark_recovers_to_default(
    monkeypatch,
):
    state = initialize_with_state(
        monkeypatch,
        {
            "settings_main_benchmarks": ["Unknown Index"],
            "settings_benchmark": "Unknown Index",
        },
    )

    assert state["settings_main_benchmarks"] == ["Nifty 50"]
    assert state["settings_benchmark"] == "Nifty 50"


def test_valid_saved_benchmarks_are_preserved(monkeypatch):
    state = initialize_with_state(
        monkeypatch,
        {
            "settings_main_benchmarks": [
                "Nifty 50",
                "Nifty 500",
                "Unknown Index",
            ],
        },
    )

    assert state["settings_main_benchmarks"] == [
        "Nifty 50",
        "Nifty 500",
    ]
    assert state["settings_benchmark"] == "Nifty 50"


def test_legacy_single_benchmark_is_used_when_multi_selection_missing(
    monkeypatch,
):
    state = initialize_with_state(
        monkeypatch,
        {
            "settings_benchmark": "Nifty 500",
        },
    )

    assert state["settings_main_benchmarks"] == ["Nifty 500"]
    assert state["settings_benchmark"] == "Nifty 500"


def test_unverified_sector_recovers_to_all_sectors(
    monkeypatch,
):
    state = initialize_with_state(
        monkeypatch,
        {"settings_sector": "Unverified Sector"},
    )

    assert state["settings_sector"] == "All Sectors"


def test_invalid_exchange_and_market_cap_recover_safely(
    monkeypatch,
):
    state = initialize_with_state(
        monkeypatch,
        {
            "settings_exchange": "Unknown Exchange",
            "settings_market_cap": "Unknown Category",
        },
    )

    assert state["settings_exchange"] == "NSE"
    assert (
        state["settings_market_cap"]
        == "All Market Caps"
    )
    
