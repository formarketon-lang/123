
import pandas as pd
import pytest

from data.constituent_audit import build_constituent_audit


def _mii_source(rows):
    rows = rows.copy()
    rows["Source"] = "NSE MII Security Master"
    return rows


def test_matching_symbols_and_isins_pass():
    constituents = pd.DataFrame({
        "Symbol": ["MARICO", "HINDUNILVR"],
        "ISIN": ["INE196A01026", "INE030A01027"],
    })

    nse = _mii_source(pd.DataFrame({
        "Symbol": ["MARICO", "HINDUNILVR"],
        "ISIN": ["INE196A01026", "INE030A01027"],
        "Series": ["EQ", "EQ"],
    }))

    detail, summary = build_constituent_audit(
        constituents, nse
    )

    assert summary["status"] == "PASS"
    assert summary["nse_source_status"] == "PRIMARY_MII"
    assert summary["nse_eq_matched"] == 2
    assert summary["nse_eq_missing"] == 0
    assert summary["isin_mismatches"] == 0
    assert set(detail["Audit_Status"]) == {
        "SYMBOL_MATCH_ISIN_MATCH"
    }


def test_missing_nse_symbol_is_review():
    constituents = pd.DataFrame({
        "Symbol": ["MARICO", "NOTLISTED"],
        "ISIN": ["INE196A01026", "INE000X01000"],
    })

    nse = _mii_source(pd.DataFrame({
        "Symbol": ["MARICO"],
        "ISIN": ["INE196A01026"],
        "Series": ["EQ"],
    }))

    _, summary = build_constituent_audit(
        constituents, nse
    )

    assert summary["status"] == "REVIEW"
    assert summary["nse_eq_missing"] == 1
    assert summary["approved_for_sector_membership"] is False


def test_isin_mismatch_is_review():
    constituents = pd.DataFrame({
        "Symbol": ["MARICO"],
        "ISIN": ["INE000X01000"],
    })

    nse = _mii_source(pd.DataFrame({
        "Symbol": ["MARICO"],
        "ISIN": ["INE196A01026"],
        "Series": ["EQ"],
    }))

    detail, summary = build_constituent_audit(
        constituents, nse
    )

    assert summary["status"] == "REVIEW"
    assert summary["isin_mismatches"] == 1
    assert detail.loc[0, "Audit_Status"] == "ISIN_MISMATCH"


def test_non_eq_nse_row_does_not_match():
    constituents = pd.DataFrame({
        "Symbol": ["MARICO"],
        "ISIN": ["INE196A01026"],
    })

    nse = _mii_source(pd.DataFrame({
        "Symbol": ["MARICO"],
        "ISIN": ["INE196A01026"],
        "Series": ["BE"],
    }))

    _, summary = build_constituent_audit(
        constituents, nse
    )

    assert summary["nse_eq_matched"] == 0
    assert summary["status"] == "REVIEW"


def test_raw_constituent_duplicates_are_not_hidden():
    constituents = pd.DataFrame({
        "Symbol": ["MARICO", "MARICO"],
        "ISIN": ["INE196A01026", "INE196A01026"],
    })

    nse = _mii_source(pd.DataFrame({
        "Symbol": ["MARICO"],
        "ISIN": ["INE196A01026"],
        "Series": ["EQ"],
    }))

    detail, summary = build_constituent_audit(
        constituents, nse
    )

    assert len(detail) == 2
    assert summary["raw_constituent_rows"] == 2
    assert summary["constituent_rows_audited"] == 2
    assert summary["duplicate_constituent_symbol_rows"] == 2
    assert summary["status"] == "REVIEW"


def test_duplicate_nse_eq_symbol_is_ambiguous_and_review():
    constituents = pd.DataFrame({
        "Symbol": ["MARICO"],
        "ISIN": ["INE196A01026"],
    })

    nse = _mii_source(pd.DataFrame({
        "Symbol": ["MARICO", "MARICO"],
        "ISIN": ["INE196A01026", "INE196A01027"],
        "Series": ["EQ", "EQ"],
    }))

    detail, summary = build_constituent_audit(
        constituents, nse
    )

    assert summary["duplicate_nse_eq_symbol_rows"] == 2
    assert summary["status"] == "REVIEW"
    assert (
        detail.loc[0, "Audit_Status"]
        == "NSE_EQ_SYMBOL_AMBIGUOUS"
    )


def test_legacy_nse_fallback_never_passes():
    constituents = pd.DataFrame({
        "Symbol": ["MARICO"],
        "ISIN": ["INE196A01026"],
    })

    nse = pd.DataFrame({
        "Symbol": ["MARICO"],
        "ISIN": ["INE196A01026"],
        "Series": ["EQ"],
        "Source": ["NSE Official Equity Master"],
    })

    _, summary = build_constituent_audit(
        constituents, nse
    )

    assert summary["nse_source_status"] == "LEGACY_FALLBACK"
    assert summary["status"] == "REVIEW"
    assert summary["approved_for_sector_membership"] is False


def test_missing_constituent_isin_is_review():
    constituents = pd.DataFrame({
        "Symbol": ["MARICO"],
        "ISIN": [pd.NA],
    })

    nse = _mii_source(pd.DataFrame({
        "Symbol": ["MARICO"],
        "ISIN": ["INE196A01026"],
        "Series": ["EQ"],
    }))

    detail, summary = build_constituent_audit(
        constituents, nse
    )

    assert summary["constituent_rows_missing_isin"] == 1
    assert summary["constituent_isin_missing"] == 1
    assert summary["status"] == "REVIEW"
    assert (
        detail.loc[0, "Audit_Status"]
        == "CONSTITUENT_ISIN_MISSING"
    )


def test_unknown_source_never_passes():
    constituents = pd.DataFrame({
        "Symbol": ["MARICO"],
        "ISIN": ["INE196A01026"],
    })

    nse = pd.DataFrame({
        "Symbol": ["MARICO"],
        "ISIN": ["INE196A01026"],
        "Series": ["EQ"],
    })

    _, summary = build_constituent_audit(
        constituents, nse
    )

    assert summary["nse_source_status"] == "UNKNOWN_SOURCE"
    assert summary["status"] == "REVIEW"


@pytest.mark.parametrize(
    "constituents,nse",
    [
        (pd.DataFrame(), pd.DataFrame()),
        (
            pd.DataFrame({"Symbol": ["MARICO"]}),
            pd.DataFrame({
                "Symbol": ["MARICO"],
                "ISIN": ["X"],
                "Series": ["EQ"],
            }),
        ),
        (
            pd.DataFrame({
                "Symbol": ["MARICO"],
                "ISIN": ["X"],
            }),
            pd.DataFrame({
                "Symbol": ["MARICO"],
                "ISIN": ["X"],
            }),
        ),
    ],
)
def test_invalid_inputs_raise_clear_errors(
    constituents,
    nse,
):
    with pytest.raises(ValueError):
        build_constituent_audit(
            constituents, nse
        )
        
