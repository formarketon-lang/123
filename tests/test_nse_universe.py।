
import pandas as pd
import pytest

from data.providers.nse_universe import (
    normalize_nse_equity_master,
)


def sample_master():
    return pd.DataFrame({
        "SYMBOL": ["MARICO", "HINDUNILVR", "ABC"],
        "NAME OF COMPANY": [
            "Marico Limited",
            "Hindustan Unilever Limited",
            "ABC Limited",
        ],
        " SERIES ": ["EQ", "EQ", "BE"],
        "DATE OF LISTING": [
            "01-01-1990",
            "01-01-1956",
            "01-01-2000",
        ],
        "ISIN NUMBER": [
            "INE196A01026",
            "INE030A01027",
            "INE000A01000",
        ],
        "FACE VALUE": ["1", "1", "10"],
    })


def test_normalize_nse_master_keeps_eq_series_only():
    result = normalize_nse_equity_master(sample_master())

    assert result["Symbol"].tolist() == [
        "HINDUNILVR",
        "MARICO",
    ]

    assert result["Exchange"].tolist() == ["NSE", "NSE"]

    assert result["Source"].eq(
        "NSE Official Equity Master"
    ).all()


def test_normalize_nse_master_can_include_other_series():
    result = normalize_nse_equity_master(
        sample_master(),
        equity_series_only=False,
    )

    assert set(result["Series"]) == {"EQ", "BE"}


def test_normalize_nse_master_rejects_missing_columns():
    with pytest.raises(ValueError, match="missing columns"):
        normalize_nse_equity_master(
            pd.DataFrame({"SYMBOL": ["MARICO"]})
        )


def test_normalize_nse_master_rejects_empty_data():
    with pytest.raises(ValueError, match="empty or invalid"):
        normalize_nse_equity_master(pd.DataFrame())
