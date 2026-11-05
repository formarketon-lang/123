
import pandas as pd

from scripts.run_sector_constituents_audit import build_constituent_audit


def test_matching_symbols_and_isins_pass():
    constituents = pd.DataFrame({
        "Symbol": ["MARICO", "HINDUNILVR"],
        "ISIN": ["INE196A01026", "INE030A01027"],
    })

    nse = pd.DataFrame({
        "Symbol": ["MARICO", "HINDUNILVR"],
        "ISIN": ["INE196A01026", "INE030A01027"],
        "Series": ["EQ", "EQ"],
    })

    detail, summary = build_constituent_audit(constituents, nse)

    assert summary["status"] == "PASS"
    assert summary["nse_eq_matched"] == 2
    assert summary["nse_eq_missing"] == 0
    assert summary["isin_mismatches"] == 0
    assert set(detail["Audit_Status"]) == {"SYMBOL_MATCH_ISIN_MATCH"}


def test_missing_nse_symbol_is_review():
    constituents = pd.DataFrame({
        "Symbol": ["MARICO", "NOTLISTED"],
        "ISIN": ["INE196A01026", "INE000X01000"],
    })

    nse = pd.DataFrame({
        "Symbol": ["MARICO"],
        "ISIN": ["INE196A01026"],
        "Series": ["EQ"],
    })

    _, summary = build_constituent_audit(constituents, nse)

    assert summary["status"] == "REVIEW"
    assert summary["nse_eq_missing"] == 1
    assert summary["approved_for_sector_membership"] is False


def test_isin_mismatch_is_review():
    constituents = pd.DataFrame({
        "Symbol": ["MARICO"],
        "ISIN": ["INE000X01000"],
    })

    nse = pd.DataFrame({
        "Symbol": ["MARICO"],
        "ISIN": ["INE196A01026"],
        "Series": ["EQ"],
    })

    detail, summary = build_constituent_audit(constituents, nse)

    assert summary["status"] == "REVIEW"
    assert summary["isin_mismatches"] == 1
    assert detail.loc[0, "Audit_Status"] == "ISIN_MISMATCH"


def test_non_eq_nse_row_does_not_match():
    constituents = pd.DataFrame({
        "Symbol": ["MARICO"],
        "ISIN": ["INE196A01026"],
    })

    nse = pd.DataFrame({
        "Symbol": ["MARICO"],
        "ISIN": ["INE196A01026"],
        "Series": ["BE"],
    })

    _, summary = build_constituent_audit(constituents, nse)

    assert summary["nse_eq_matched"] == 0
    assert summary["status"] == "REVIEW"
  
