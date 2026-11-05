
import pandas as pd
import pytest

from ui.rs_results import build_ranked_results


def test_main_ranking_is_descending_by_excess_return():
    data = [
        {"Stock": "AAA", "Window": "1M", "Excess Return (%)": 5.0},
        {"Stock": "BBB", "Window": "1M", "Excess Return (%)": 12.0},
        {"Stock": "CCC", "Window": "1M", "Excess Return (%)": -2.0},
    ]

    result = build_ranked_results(
        data, ["1M"], "Excess Return (%)"
    )

    assert result["Stock"].tolist() == ["BBB", "AAA", "CCC"]
    assert result["Rank"].tolist() == [1, 2, 3]


def test_each_window_has_independent_ranking():
    data = [
        {"Stock": "AAA", "Window": "1M", "Excess Return (%)": 5},
        {"Stock": "BBB", "Window": "1M", "Excess Return (%)": 10},
        {"Stock": "AAA", "Window": "3M", "Excess Return (%)": 20},
        {"Stock": "BBB", "Window": "3M", "Excess Return (%)": 15},
    ]

    result = build_ranked_results(
        data, ["1M", "3M"], "Excess Return (%)"
    )

    one_month = result[result["Window"] == "1M"]
    three_month = result[result["Window"] == "3M"]

    assert one_month["Rank"].tolist() == [1, 2]
    assert one_month["Stock"].tolist() == ["BBB", "AAA"]

    assert three_month["Rank"].tolist() == [1, 2]
    assert three_month["Stock"].tolist() == ["AAA", "BBB"]


def test_ranking_drops_non_numeric_returns():
    data = [
        {"Stock": "AAA", "Window": "1M", "Excess Return (%)": 5},
        {"Stock": "BBB", "Window": "1M", "Excess Return (%)": "bad"},
    ]

    result = build_ranked_results(
        data, ["1M"], "Excess Return (%)"
    )

    assert result["Stock"].tolist() == ["AAA"]
    assert result["Rank"].tolist() == [1]


def test_ranking_rejects_missing_sort_column():
    data = [
        {"Stock": "AAA", "Window": "1M"},
    ]

    with pytest.raises(ValueError):
        build_ranked_results(
            data, ["1M"], "Excess Return (%)"
        )


def test_empty_ranking_returns_empty_dataframe():
    result = build_ranked_results(
        [], ["1M"], "Excess Return (%)"
    )

    assert isinstance(result, pd.DataFrame)
    assert result.empty


def test_sector_ranking_uses_sector_excess_return():
    data = [
        {
            "Stock": "AAA",
            "Window": "1M",
            "Sector Excess Return (%)": 3,
        },
        {
            "Stock": "BBB",
            "Window": "1M",
            "Sector Excess Return (%)": 8,
        },
    ]

    result = build_ranked_results(
        data, ["1M"], "Sector Excess Return (%)"
    )

    assert result["Stock"].tolist() == ["BBB", "AAA"]
    assert result["Rank"].tolist() == [1, 2]


def test_ranked_csv_preserves_rank_and_order():
    data = [
        {"Stock": "AAA", "Window": "1M", "Excess Return (%)": 5},
        {"Stock": "BBB", "Window": "1M", "Excess Return (%)": 10},
    ]

    ranked = build_ranked_results(
        data, ["1M"], "Excess Return (%)"
    )

    csv_text = ranked.to_csv(index=False)
    restored = pd.read_csv(pd.io.common.StringIO(csv_text))

    assert "Rank" in restored.columns
    assert restored["Rank"].tolist() == [1, 2]
    assert restored["Stock"].tolist() == ["BBB", "AAA"]
  
