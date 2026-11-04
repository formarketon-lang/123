import pandas as pd
import pytest

from core.stock_search import search_stock_universe


@pytest.fixture
def universe():
    return pd.DataFrame(
        {
            "Symbol": ["MARICO", "HINDUNILVR", "RELIANCE"],
            "Company": [
                "Marico Limited",
                "Hindustan Unilever Limited",
                "Reliance Industries Limited",
            ],
            "Series": ["EQ", "EQ", "EQ"],
        }
    )


def test_search_by_symbol(universe):
    result = search_stock_universe(universe, "marico")
    assert result["Symbol"].tolist() == ["MARICO"]


def test_search_by_company_name(universe):
    result = search_stock_universe(universe, "unilever")
    assert result["Symbol"].tolist() == ["HINDUNILVR"]


def test_search_is_case_insensitive(universe):
    result = search_stock_universe(universe, "RELIANCE")
    assert result["Symbol"].tolist() == ["RELIANCE"]


def test_empty_query_returns_limited_universe(universe):
    result = search_stock_universe(universe, limit=2)
    assert len(result) == 2


def test_invalid_universe_is_rejected():
    with pytest.raises(ValueError, match="missing required columns"):
        search_stock_universe(pd.DataFrame({"Ticker": ["ABC"]}))


def test_invalid_limit_is_rejected(universe):
    with pytest.raises(ValueError, match="at least 1"):
        search_stock_universe(universe, limit=0)
