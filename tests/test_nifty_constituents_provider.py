
import pandas as pd
import pytest

from data.providers.nifty_constituents import (
    fetch_sector_constituents,
    normalize_sector_constituents,
)


def test_normalize_fmcg_constituents():
    raw = pd.DataFrame({
        "Company Name": [
            "Marico Limited",
            "Hindustan Unilever Limited",
        ],
        "Industry": [
            "Fast Moving Consumer Goods",
            "Fast Moving Consumer Goods",
        ],
        "Symbol": ["MARICO", "HINDUNILVR"],
        "Series": ["EQ", "EQ"],
        "ISIN Code": [
            "INE196A01026",
            "INE030A01027",
        ],
    })

    result = normalize_sector_constituents(raw, "FMCG")

    assert set(result["Symbol"]) == {
        "MARICO",
        "HINDUNILVR",
    }
    assert result["Sector"].eq("FMCG").all()
    assert result["Exchange"].eq("NSE").all()
    assert result["Source"].notna().all()


def test_missing_symbol_column_is_rejected():
    raw = pd.DataFrame({
        "Company Name": ["Example Ltd"],
    })

    with pytest.raises(ValueError, match="Symbol"):
        normalize_sector_constituents(raw, "FMCG")


def test_empty_data_is_rejected():
    with pytest.raises(ValueError):
        normalize_sector_constituents(
            pd.DataFrame(),
            "FMCG",
        )


def test_unsupported_sector_is_rejected():
    with pytest.raises(ValueError, match="No official"):
        fetch_sector_constituents("BANK")
