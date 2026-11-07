
"""Tests for the strict NSE industry classification provider."""

import pandas as pd
import pytest

from data.providers.nse_industry_classification import (
    load_industry_classification_file,
    normalize_industry_classification,
)


def sample_data():
    return pd.DataFrame({
        "Symbol": ["MARICO", "HINDUNILVR"],
        "ISIN": ["INE196A01026", "INE030A01027"],
        "Company Name": [
            "Marico Limited",
            "Hindustan Unilever Limited",
        ],
        "Macro Economic Sector": [
            "Consumer Goods",
            "Consumer Goods",
        ],
        "Sector": ["FMCG", "FMCG"],
        "Industry": [
            "Personal Care",
            "Household Products",
        ],
        "Basic Industry": [
            "Other Personal Products",
            "Household Products",
        ],
    })


def normalize(data=None, **kwargs):
    return normalize_industry_classification(
        data=data if data is not None else sample_data(),
        source_name="NSE Official Classification",
        source_reference="https://www.nseindia.com/",
        **kwargs,
    )


def test_valid_classification_is_normalized():
    result = normalize()

    assert len(result) == 2
    assert list(result["Symbol"]) == [
        "HINDUNILVR",
        "MARICO",
    ]
    assert result["Source"].eq(
        "NSE Official Classification"
    ).all()
    assert result["Source Reference"].notna().all()


def test_required_classification_columns_are_present():
    result = normalize()

    required = [
        "Symbol",
        "ISIN",
        "Macro Economic Sector",
        "Sector",
        "Industry",
        "Basic Industry",
    ]

    for column in required:
        assert column in result.columns
        assert result[column].notna().all()


def test_missing_required_column_is_rejected():
    data = sample_data().drop(columns=["Basic Industry"])

    with pytest.raises(ValueError, match="Basic Industry"):
        normalize(data)


def test_empty_dataframe_is_rejected():
    with pytest.raises(ValueError, match="empty"):
        normalize(pd.DataFrame())


def test_invalid_isin_is_rejected():
    data = sample_data()
    data.loc[0, "ISIN"] = "INVALID"

    with pytest.raises(ValueError, match="ISIN"):
        normalize(data)


def test_missing_sector_value_is_rejected():
    data = sample_data()
    data.loc[0, "Sector"] = None

    with pytest.raises(ValueError, match="missing"):
        normalize(data)


def test_duplicate_symbols_are_rejected():
    data = sample_data()
    data.loc[1, "Symbol"] = "MARICO"

    with pytest.raises(ValueError, match="Duplicate symbols"):
        normalize(data)


def test_duplicate_isins_are_rejected():
    data = sample_data()
    data.loc[1, "ISIN"] = data.loc[0, "ISIN"]

    with pytest.raises(ValueError, match="Duplicate ISIN"):
        normalize(data)


def test_empty_source_name_is_rejected():
    with pytest.raises(ValueError, match="source name"):
        normalize_industry_classification(
            sample_data(),
            "",
            "https://www.nseindia.com/",
        )


def test_empty_source_reference_is_rejected():
    with pytest.raises(ValueError, match="reference"):
        normalize_industry_classification(
            sample_data(),
            "NSE Official Classification",
            "",
        )


def test_original_dataframe_is_not_modified():
    data = sample_data()
    original = data.copy(deep=True)

    normalize(data)

    pd.testing.assert_frame_equal(data, original)


def test_csv_file_loading(tmp_path):
    path = tmp_path / "nse_classification.csv"
    sample_data().to_csv(path, index=False)

    result = load_industry_classification_file(
        file_path=path,
        source_name="NSE Official Classification",
        source_reference="https://www.nseindia.com/",
        as_of_date="2026-11-06",
    )

    assert len(result) == 2
    assert result["Symbol"].is_unique
    assert result["ISIN"].is_unique
    assert result["As Of Date"].eq("2026-11-06").all()


def test_missing_file_is_rejected(tmp_path):
    path = tmp_path / "missing.csv"

    with pytest.raises(FileNotFoundError):
        load_industry_classification_file(
            path,
            "NSE Official Classification",
            "https://www.nseindia.com/",
        )


def test_unsupported_file_format_is_rejected(tmp_path):
    path = tmp_path / "classification.txt"
    path.write_text("invalid format", encoding="utf-8")

    with pytest.raises(ValueError, match="CSV or XLSX"):
        load_industry_classification_file(
            path,
            "NSE Official Classification",
            "https://www.nseindia.com/",
        )
      
