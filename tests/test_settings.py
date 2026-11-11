
"""Regression tests for verified benchmark mappings."""

from data.benchmark_mapping import (
    MAIN_BENCHMARKS,
    SECTOR_BENCHMARKS,
    get_main_benchmarks,
    get_sector_benchmark,
    get_available_sector_mappings,
)


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
  
