"""Regression tests for full NSE EQ classification coverage audit."""

import pandas as pd
import pytest

from data.providers.nse_eq_coverage_audit import (
    build_nse_eq_coverage_audit,
)


def classification_fixture():
    return pd.DataFrame({
        "Symbol": ["MARICO", "HINDUNILVR"],
        "ISIN": ["INE196A01026", "INE030A01027"],
    })


def nse_fixture():
    return pd.DataFrame({
        "Symbol": ["MARICO", "HINDUNILVR"],
        "ISIN": ["INE196A01026", "INE030A01027"],
        "Series": ["EQ", "EQ"],
        "Source": [
            "NSE MII Security Master",
            "NSE MII Security Master",
        ],
    })


def test_exact_full_universe_match_passes_identity_coverage():
    detail, classification_only, summary = (
        build_nse_eq_coverage_audit(
            classification_fixture(),
            nse_fixture(),
        )
    )

    assert summary["status"] == "PASS"
    assert summary["nse_source_status"] == "PRIMARY_MII"
    assert summary["nse_eq_input_rows"] == 2
    assert summary["exact_symbol_isin_matches"] == 2
    assert summary["nse_eq_coverage_pct"] == 100.0
    assert summary["full_universe_coverage_passed"] is True
    assert detail["Coverage_Status"].eq("MATCH").all()
    assert classification_only.empty


def test_missing_classification_symbol_is_reported():
    classification = classification_fixture().iloc[[0]].copy()

    detail, _, summary = build_nse_eq_coverage_audit(
        classification,
        nse_fixture(),
    )

    hind = detail.loc[
        detail["Symbol"].eq("HINDUNILVR")
    ].iloc[0]

    assert hind["Coverage_Status"] == "CLASSIFICATION_MISSING"
    assert summary["classification_missing_rows"] == 1
    assert summary["status"] == "REVIEW"
    assert summary["full_universe_coverage_passed"] is False


def test_isin_mismatch_is_reported():
    classification = classification_fixture()
    classification.loc[0, "ISIN"] = "INE999A01099"

    detail, _, summary = build_nse_eq_coverage_audit(
        classification,
        nse_fixture(),
    )

    marico = detail.loc[
        detail["Symbol"].eq("MARICO")
    ].iloc[0]

    assert marico["Coverage_Status"] == "ISIN_MISMATCH"
    assert summary["isin_mismatch_rows"] == 1
    assert summary["status"] == "REVIEW"


def test_duplicate_nse_symbol_is_ambiguous():
    nse = nse_fixture()
    duplicate = nse.iloc[[0]].copy()
    duplicate["ISIN"] = "INE999A01099"
    nse = pd.concat([nse, duplicate], ignore_index=True)

    detail, _, summary = build_nse_eq_coverage_audit(
        classification_fixture(),
        nse,
    )

    marico_rows = detail.loc[
        detail["Symbol"].eq("MARICO")
    ]

    assert len(marico_rows) == 2
    assert marico_rows["Coverage_Status"].eq(
        "NSE_IDENTITY_AMBIGUOUS"
    ).all()
    assert summary["nse_identity_ambiguous_rows"] == 2
    assert summary["status"] == "REVIEW"


def test_duplicate_classification_symbol_is_ambiguous():
    classification = classification_fixture()
    duplicate = classification.iloc[[0]].copy()
    duplicate["ISIN"] = "INE999A01099"
    classification = pd.concat(
        [classification, duplicate],
        ignore_index=True,
    )

    detail, _, summary = build_nse_eq_coverage_audit(
        classification,
        nse_fixture(),
    )

    marico = detail.loc[
        detail["Symbol"].eq("MARICO")
    ].iloc[0]

    assert marico["Coverage_Status"] == (
        "CLASSIFICATION_AMBIGUOUS"
    )
    assert summary["classification_ambiguous_rows"] == 1
    assert summary["status"] == "REVIEW"


def test_duplicate_classification_isin_is_ambiguous():
    classification = classification_fixture()
    classification.loc[1, "ISIN"] = "INE196A01026"

    detail, _, summary = build_nse_eq_coverage_audit(
        classification,
        nse_fixture(),
    )

    assert detail["Coverage_Status"].eq(
        "CLASSIFICATION_AMBIGUOUS"
    ).all()
    assert summary["classification_ambiguous_rows"] == 2
    assert summary["status"] == "REVIEW"


def test_classification_symbol_not_in_nse_is_separately_reported():
    classification = classification_fixture()
    extra = pd.DataFrame({
        "Symbol": ["NOTLISTED"],
        "ISIN": ["INE111A01011"],
    })
    classification = pd.concat(
        [classification, extra],
        ignore_index=True,
    )

    detail, classification_only, summary = (
        build_nse_eq_coverage_audit(
            classification,
            nse_fixture(),
        )
    )

    assert len(detail) == 2
    assert len(classification_only) == 1
    assert classification_only.iloc[0]["Symbol"] == "NOTLISTED"
    assert classification_only.iloc[0]["Coverage_Status"] == (
        "CLASSIFICATION_SYMBOL_NOT_IN_NSE_EQ"
    )
    assert summary["classification_symbols_not_in_nse_eq"] == 1
    assert summary["status"] == "REVIEW"


def test_non_eq_rows_are_excluded_from_coverage_denominator():
    nse = nse_fixture()
    non_eq = pd.DataFrame({
        "Symbol": ["EXAMPLEBE"],
        "ISIN": ["INE222A01022"],
        "Series": ["BE"],
        "Source": ["NSE MII Security Master"],
    })
    nse = pd.concat([nse, non_eq], ignore_index=True)

    detail, _, summary = build_nse_eq_coverage_audit(
        classification_fixture(),
        nse,
    )

    assert len(detail) == 2
    assert summary["nse_eq_input_rows"] == 2
    assert summary["nse_eq_coverage_pct"] == 100.0


def test_legacy_source_cannot_pass_full_universe_coverage():
    nse = nse_fixture()
    nse["Source"] = "NSE Official Equity Master"

    _, _, summary = build_nse_eq_coverage_audit(
        classification_fixture(),
        nse,
    )

    assert summary["nse_source_status"] == "NOT_PRIMARY_MII"
    assert summary["status"] == "REVIEW"
    assert summary["full_universe_coverage_passed"] is False


def test_mapping_never_activates_even_when_coverage_passes():
    _, _, summary = build_nse_eq_coverage_audit(
        classification_fixture(),
        nse_fixture(),
    )

    assert summary["status"] == "PASS"
    assert summary["mapping_eligible"] is False
    assert summary["source_authenticity_verified"] is False
    assert summary["sector_mapping_activated"] is False


def test_empty_inputs_are_rejected():
    with pytest.raises(ValueError, match="empty"):
        build_nse_eq_coverage_audit(
            pd.DataFrame(),
            nse_fixture(),
        )

    with pytest.raises(ValueError, match="empty"):
        build_nse_eq_coverage_audit(
            classification_fixture(),
            pd.DataFrame(),
        )


def test_missing_required_columns_are_rejected():
    with pytest.raises(ValueError, match="Symbol and ISIN"):
        build_nse_eq_coverage_audit(
            classification_fixture().drop(columns=["ISIN"]),
            nse_fixture(),
        )

    with pytest.raises(ValueError, match="Symbol, ISIN and Series"):
        build_nse_eq_coverage_audit(
            classification_fixture(),
            nse_fixture().drop(columns=["Series"]),
        )


def test_blank_identity_values_are_rejected():
    classification = classification_fixture()
    classification.loc[0, "Symbol"] = " "

    with pytest.raises(ValueError, match="blank Symbol or ISIN"):
        build_nse_eq_coverage_audit(
            classification,
            nse_fixture(),
  )
