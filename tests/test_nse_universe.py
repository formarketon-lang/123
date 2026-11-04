import pandas as pd
import pytest

from data.providers.nse_universe import (
    normalize_nse_equity_master,
    normalize_nse_mii_security_master,
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


def sample_mii():
    return pd.DataFrame({
        "FinInstrmId": ["1", "2", "3", "4", "5", "6", "7"],
        "TckrSymb": [
            "MARICO",
            "RELIANCE",
            "ABC$",
            "SUSPENDED",
            "DELETED",
            "BSEONLY$",
            "NSETEST01",
        ],
        "FinInstrmNm": [
            "MARICO LIMITED",
            "RELIANCE INDUSTRIES LTD",
            "ABC LIMITED",
            "SUSPENDED LTD",
            "DELETED LTD",
            "BSE EXCLUSIVE LTD",
            "TEST SECURITY",
        ],
        "SctySrs": ["EQ"] * 7,
        "ISIN": [
            "INE196A01026",
            "INE002A01018",
            "INE000A01000",
            "INE111A01011",
            "INE222A01022",
            "INE333A01033",
            "DUMMYSAN005",
        ],
        "ParVal": ["1"] * 7,
        "ListgDt": [
            "515376000",
            "0",
            "515376000",
            "515376000",
            "515376000",
            "515376000",
            "0",
        ],
        "DelFlg": ["N", "N", "N", "N", "Y", "N", "N"],
        "SctyStsNrmlMkt": ["6", "6", "6", "3", "6", "6", "6"],
        "ElgbltyNrmlMkt": ["1"] * 7,
        "PrtdToTrad": ["0", "0", "2", "1", "1", "2", "0"],
    })


def test_legacy_master_keeps_eq_series_only():
    result = normalize_nse_equity_master(sample_master())

    assert result["Symbol"].tolist() == [
        "HINDUNILVR",
        "MARICO",
    ]


def test_legacy_master_can_include_other_series():
    result = normalize_nse_equity_master(
        sample_master(),
        equity_series_only=False,
    )

    assert set(result["Series"]) == {"EQ", "BE"}


def test_legacy_master_rejects_missing_columns():
    with pytest.raises(ValueError, match="missing columns"):
        normalize_nse_equity_master(
            pd.DataFrame({"SYMBOL": ["MARICO"]})
        )


def test_legacy_master_rejects_empty_data():
    with pytest.raises(ValueError, match="empty or invalid"):
        normalize_nse_equity_master(pd.DataFrame())


def test_mii_keeps_normal_market_eligible_eq_including_prtd_zero():
    result = normalize_nse_mii_security_master(sample_mii())

    assert result["Symbol"].tolist() == [
        "MARICO",
        "RELIANCE",
    ]

    assert set(result["Permitted to Trade"]) == {"0"}
    assert result["Source"].eq(
        "NSE MII Security Master"
    ).all()


def test_mii_excludes_bse_exclusive_suspended_deleted_and_test():
    result = normalize_nse_mii_security_master(sample_mii())

    assert not result["Symbol"].str.endswith("$").any()
    assert "SUSPENDED" not in set(result["Symbol"])
    assert "DELETED" not in set(result["Symbol"])
    assert "NSETEST01" not in set(result["Symbol"])


def test_mii_listing_date_uses_1980_epoch():
    result = normalize_nse_mii_security_master(sample_mii())

    marico = result.loc[
        result["Symbol"] == "MARICO"
    ].iloc[0]

    reliance = result.loc[
        result["Symbol"] == "RELIANCE"
    ].iloc[0]

    assert marico["Listing Date"] == pd.Timestamp("1996-05-01")
    assert pd.isna(reliance["Listing Date"])


def test_mii_does_not_deduplicate_different_symbols_by_isin():
    data = sample_mii().iloc[:2].copy()

    data.loc[data.index[1], "TckrSymb"] = "MARICOOLD"
    data.loc[data.index[1], "ISIN"] = "INE196A01026"

    result = normalize_nse_mii_security_master(data)

    assert set(result["Symbol"]) == {
        "MARICO",
        "MARICOOLD",
    }


def test_mii_rejects_missing_required_columns():
    with pytest.raises(ValueError, match="missing columns"):
        normalize_nse_mii_security_master(
            pd.DataFrame({"TckrSymb": ["MARICO"]})
        )
        
