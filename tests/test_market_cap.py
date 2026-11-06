import pandas as pd
import pytest

from data.market_cap import (
    enrich_nse_universe_with_amfi,
    filter_by_market_cap,
    normalize_amfi_market_cap,
)


def sample_amfi_data():
    return pd.DataFrame({
        "ISIN": [
            "INE002A01018",
            "INE030A01027",
            "INE009A01021",
        ],
        "NSE Symbol": [
            "RELIANCE",
            "HINDUNILVR",
            "INFY",
        ],
        "Average of All Exchanges (Rs. Cr.)": [
            "100000",
            "50000",
            "40000",
        ],
        "Categorization as per SEBI Circular dated Oct 6, 2017": [
            "Large Cap",
            "Mid Cap",
            "Small Cap",
        ],
    })


def sample_nse_universe():
    return pd.DataFrame({
        "Symbol": [
            "RELIANCE",
            "HINDUNILVR",
            "INFY",
            "UNKNOWN",
        ],
        "ISIN": [
            "INE002A01018",
            "INE030A01027",
            "INE009A01021",
            "INE999A01099",
        ],
        "Series": ["EQ", "EQ", "EQ", "EQ"],
    })


def test_normalize_amfi_market_cap():
    result = normalize_amfi_market_cap(sample_amfi_data())

    assert len(result) == 3
    assert result.loc[0, "Market Cap Category"] == "LARGE CAP"
    assert result.loc[0, "AMFI NSE Symbol"] == "RELIANCE"


def test_normalize_rejects_duplicate_isin():
    data = sample_amfi_data()
    data.loc[1, "ISIN"] = data.loc[0, "ISIN"]

    with pytest.raises(ValueError, match="Duplicate ISIN"):
        normalize_amfi_market_cap(data)


def test_normalize_allows_duplicate_symbol_with_different_isin():
    data = sample_amfi_data()

    data.loc[1, "NSE Symbol"] = "RELIANCE"
    data.loc[1, "ISIN"] = "INE030A01027"

    result = normalize_amfi_market_cap(data)

    assert len(result) == 3
    assert result["AMFI NSE Symbol"].tolist().count("RELIANCE") == 2
    assert result["ISIN"].nunique() == 3


def test_enrichment_requires_both_isin_and_symbol():
    amfi = normalize_amfi_market_cap(sample_amfi_data())
    universe = sample_nse_universe()

    universe.loc[0, "Symbol"] = "WRONG_SYMBOL"

    result = enrich_nse_universe_with_amfi(universe, amfi)

    row = result[result["ISIN"] == "INE002A01018"].iloc[0]

    assert row["Market Cap Match Status"] == "ISIN_SYMBOL_MISMATCH"
    assert pd.isna(row["Market Cap Category"])


def test_enrichment_matches_verified_nse_eq_rows():
    amfi = normalize_amfi_market_cap(sample_amfi_data())
    universe = sample_nse_universe()

    result = enrich_nse_universe_with_amfi(universe, amfi)

    row = result[result["Symbol"] == "RELIANCE"].iloc[0]

    assert row["Market Cap Match Status"] == "MATCHED"
    assert row["Market Cap Category"] == "LARGE CAP"


def test_duplicate_symbol_does_not_cross_match_categories():
    data = sample_amfi_data()

    data.loc[1, "NSE Symbol"] = "RELIANCE"

    amfi = normalize_amfi_market_cap(data)

    universe = pd.DataFrame({
        "Symbol": ["RELIANCE", "RELIANCE"],
        "ISIN": ["INE002A01018", "INE030A01027"],
        "Series": ["EQ", "EQ"],
    })

    result = enrich_nse_universe_with_amfi(universe, amfi)

    large = result[result["ISIN"] == "INE002A01018"].iloc[0]
    mid = result[result["ISIN"] == "INE030A01027"].iloc[0]

    assert large["Market Cap Match Status"] == "MATCHED"
    assert large["Market Cap Category"] == "LARGE CAP"

    assert mid["Market Cap Match Status"] == "MATCHED"
    assert mid["Market Cap Category"] == "MID CAP"


def test_unmatched_symbol_has_no_approved_category():
    amfi = normalize_amfi_market_cap(sample_amfi_data())
    universe = sample_nse_universe()

    result = enrich_nse_universe_with_amfi(universe, amfi)

    row = result[result["Symbol"] == "UNKNOWN"].iloc[0]

    assert row["Market Cap Match Status"] == "NO_AMFI_MATCH"
    assert pd.isna(row["Market Cap Category"])


def test_filter_returns_only_matched_large_caps():
    amfi = normalize_amfi_market_cap(sample_amfi_data())
    universe = sample_nse_universe()
    enriched = enrich_nse_universe_with_amfi(universe, amfi)

    result = filter_by_market_cap(enriched, "Large Cap")

    assert result["Symbol"].tolist() == ["RELIANCE"]


def test_filter_rejects_unavailable_classification():
    with pytest.raises(ValueError, match="not been integrated"):
        filter_by_market_cap(
            sample_nse_universe(),
            "Large Cap",
    )
    
