
"""Tests for the NSE industry classification reconciliation audit."""

import pandas as pd
import pytest

from scripts.run_industry_classification_audit import (
    build_industry_classification_audit,
)


def classification_data():
    return pd.DataFrame({
        "Symbol": ["MARICO", "HINDUNILVR"],
        "ISIN": ["INE196A01026", "INE030A01027"],
        "Sector": ["FMCG", "FMCG"],
        "Industry": ["Personal Care", "Household Products"],
        "Basic Industry": [
            "Other Personal Products",
            "Household Products",
        ],
    })


def nse_mii_data():
    return pd.DataFrame({
        "Symbol": ["MARICO", "HINDUNILVR"],
        "ISIN": ["INE196A01026", "INE030A01027"],
        "Series": ["EQ", "EQ"],
        "Source": [
            "NSE MII Security Master",
            "NSE MII Security Master",
        ],
    })


def test_exact_symbol_and_isin_match_is_approved():
    detail, summary = build_industry_classification_audit(
        classification_data(),
        nse_mii_data(),
    )

    assert summary["status"] == "PASS"
    assert summary["nse_eq_matched"] == 2
    assert summary["approved_rows"] == 2
    assert detail["Audit_Status"].eq("MATCH").all()
    assert detail["Approved"].all()
    assert summary["sector_mapping_activated"] is False


def test_isin_mismatch_is_not_approved():
    nse = nse_mii_data()
    nse.loc[0, "ISIN"] = "INE999A01099"

    detail, summary = build_industry_classification_audit(
        classification_data(),
        nse,
    )

    marico = detail.loc[detail["Symbol"].eq("MARICO")].iloc[0]

    assert marico["Audit_Status"] == "ISIN_MISMATCH"
    assert not marico["Approved"]
    assert summary["status"] == "REVIEW"
    assert summary["isin_mismatches"] == 1


def test_missing_nse_eq_symbol_is_not_approved():
    nse = nse_mii_data()
    nse = nse[nse["Symbol"] != "MARICO"]

    detail, summary = build_industry_classification_audit(
        classification_data(),
        nse,
    )

    marico = detail.loc[detail["Symbol"].eq("MARICO")].iloc[0]

    assert marico["Audit_Status"] == "NSE_EQ_SYMBOL_MISSING"
    assert not marico["Approved"]
    assert summary["nse_eq_missing"] == 1
    assert summary["status"] == "REVIEW"


def test_duplicate_nse_eq_symbol_is_ambiguous():
    nse = nse_mii_data()
    duplicate = nse.iloc[[0]].copy()
    duplicate["ISIN"] = "INE999A01099"

    nse = pd.concat([nse, duplicate], ignore_index=True)

    detail, summary = build_industry_classification_audit(
        classification_data(),
        nse,
    )

    marico = detail.loc[detail["Symbol"].eq("MARICO")].iloc[0]

    assert marico["Audit_Status"] == "NSE_EQ_SYMBOL_AMBIGUOUS"
    assert not marico["Approved"]
    assert summary["ambiguous_nse_symbols"] == 1
    assert summary["status"] == "REVIEW"


def test_legacy_source_never_approves_rows():
    nse = nse_mii_data()
    nse["Source"] = "NSE Official Equity Master"

    detail, summary = build_industry_classification_audit(
        classification_data(),
        nse,
    )

    assert summary["nse_source_status"] == "LEGACY_FALLBACK"
    assert summary["status"] == "REVIEW"
    assert summary["approved_rows"] == 0
    assert not detail["Approved"].any()


def test_non_eq_series_is_not_used_for_matching():
    nse = nse_mii_data()
    nse.loc[0, "Series"] = "BE"

    detail, summary = build_industry_classification_audit(
        classification_data(),
        nse,
    )

    marico = detail.loc[detail["Symbol"].eq("MARICO")].iloc[0]

    assert marico["Audit_Status"] == "NSE_EQ_SYMBOL_MISSING"
    assert not marico["Approved"]
    assert summary["status"] == "REVIEW"


def test_empty_classification_is_rejected():
    with pytest.raises(ValueError, match="empty"):
        build_industry_classification_audit(
            pd.DataFrame(),
            nse_mii_data(),
        )


def test_empty_nse_universe_is_rejected():
    with pytest.raises(ValueError, match="empty"):
        build_industry_classification_audit(
            classification_data(),
            pd.DataFrame(),
        )


def test_missing_classification_column_is_rejected():
    data = classification_data().drop(columns=["Basic Industry"])

    with pytest.raises(ValueError, match="Basic Industry"):
        build_industry_classification_audit(
            data,
            nse_mii_data(),
        )


def test_missing_nse_column_is_rejected():
    nse = nse_mii_data().drop(columns=["ISIN"])

    with pytest.raises(ValueError, match="Symbol, ISIN and Series"):
        build_industry_classification_audit(
            classification_data(),
            nse,
        )
      
