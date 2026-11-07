"""Tests for exact official classification taxonomy validation."""

import pandas as pd
import pytest

from data.providers.classification_taxonomy_validator import (
    HIERARCHY_COLUMNS,
    validate_classification_taxonomy,
)


def taxonomy_data():
    return pd.DataFrame({
        "Macro Economic Sector Code": ["10", "10"],
        "Macro Economic Sector": ["Consumer Discretionary", "Consumer Discretionary"],
        "Sector Code": ["1010", "1010"],
        "Sector": ["Consumer Products", "Consumer Products"],
        "Industry Code": ["101001", "101002"],
        "Industry": ["Personal Products", "Household Products"],
        "Basic Industry Code": ["10100101", "10100201"],
        "Basic Industry": ["Personal Care", "Household Products"],
    })


def classification_data():
    return taxonomy_data().copy()


def test_exact_official_hierarchy_passes():
    detail, summary = validate_classification_taxonomy(
        classification_data(),
        taxonomy_data(),
    )

    assert summary["status"] == "PASS"
    assert summary["taxonomy_matched_rows"] == 2
    assert summary["unknown_hierarchy_rows"] == 0
    assert detail["Taxonomy_Validated"].all()
    assert summary["sector_mapping_activated"] is False


def test_unknown_basic_industry_is_flagged():
    company = classification_data()
    company.loc[0, "Basic Industry"] = "Unverified Industry"

    detail, summary = validate_classification_taxonomy(
        company,
        taxonomy_data(),
    )

    assert summary["status"] == "REVIEW"
    assert summary["unknown_hierarchy_rows"] == 1
    assert detail.loc[0, "Taxonomy_Status"] == (
        "NOT_IN_OFFICIAL_TAXONOMY"
    )
    assert not detail.loc[0, "Taxonomy_Validated"]


def test_wrong_parent_sector_path_is_rejected():
    company = classification_data()
    company.loc[0, "Sector Code"] = "9999"

    detail, summary = validate_classification_taxonomy(
        company,
        taxonomy_data(),
    )

    assert summary["status"] == "REVIEW"
    assert detail.loc[0, "Taxonomy_Status"] == (
        "NOT_IN_OFFICIAL_TAXONOMY"
    )


def test_missing_hierarchy_value_is_flagged():
    company = classification_data()
    company.loc[0, "Industry"] = " "

    detail, summary = validate_classification_taxonomy(
        company,
        taxonomy_data(),
    )

    assert summary["status"] == "REVIEW"
    assert summary["missing_hierarchy_rows"] == 1
    assert detail.loc[0, "Taxonomy_Status"] == (
        "MISSING_HIERARCHY_FIELD"
    )


def test_case_and_outer_spaces_are_normalized():
    company = classification_data()
    company.loc[0, "Sector"] = "  CONSUMER PRODUCTS  "

    detail, summary = validate_classification_taxonomy(
        company,
        taxonomy_data(),
    )

    assert summary["status"] == "PASS"
    assert detail["Taxonomy_Validated"].all()


def test_duplicate_official_taxonomy_path_is_rejected():
    taxonomy = taxonomy_data()
    taxonomy = pd.concat(
        [taxonomy, taxonomy.iloc[[0]]],
        ignore_index=True,
    )

    with pytest.raises(ValueError, match="duplicate"):
        validate_classification_taxonomy(
            classification_data(),
            taxonomy,
        )


def test_missing_official_taxonomy_value_is_rejected():
    taxonomy = taxonomy_data()
    taxonomy.loc[0, "Basic Industry Code"] = None

    with pytest.raises(ValueError, match="missing"):
        validate_classification_taxonomy(
            classification_data(),
            taxonomy,
        )


def test_missing_required_column_is_rejected():
    taxonomy = taxonomy_data().drop(
        columns=["Basic Industry Code"]
    )

    with pytest.raises(ValueError, match="Basic Industry Code"):
        validate_classification_taxonomy(
            classification_data(),
            taxonomy,
        )


def test_empty_classification_is_rejected():
    with pytest.raises(ValueError, match="empty"):
        validate_classification_taxonomy(
            pd.DataFrame(),
            taxonomy_data(),
        )


def test_empty_official_taxonomy_is_rejected():
    with pytest.raises(ValueError, match="empty"):
        validate_classification_taxonomy(
            classification_data(),
            pd.DataFrame(),
        )


def test_taxonomy_validator_does_not_activate_sector_mapping():
    detail, summary = validate_classification_taxonomy(
        classification_data(),
        taxonomy_data(),
    )

    assert summary["sector_mapping_activated"] is False
    assert "Taxonomy_Validated" in detail.columns
    assert "Approved" not in detail.columns
