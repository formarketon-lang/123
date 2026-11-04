import gzip
from datetime import date

import pandas as pd
import pytest

from data.providers.nse_universe import (
    NSE_EQUITY_MASTER_URL,
    NSE_MII_SECURITY_URL_TEMPLATE,
    fetch_nse_equity_universe,
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
        "IssdCptl": [
            "100", "200", "300", "400",
            "500", "600", "700",
        ],
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


class FakeResponse:
    def __init__(self, content=b"", status_code=200):
        self.content = content
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(
                f"HTTP error: {self.status_code}"
            )


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.headers = {}
        self.urls = []

    def get(self, url, timeout):
        self.urls.append(url)

        if not self.responses:
            raise AssertionError(
                f"Unexpected request: {url}"
            )

        return self.responses.pop(0)


def gzip_csv(data):
    csv_bytes = data.to_csv(index=False).encode("utf-8")
    return gzip.compress(csv_bytes)


# ---------------------------------------------------------
# LEGACY NSE EQUITY MASTER TESTS
# ---------------------------------------------------------

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


# ---------------------------------------------------------
# NSE MII SECURITY MASTER TESTS
# ---------------------------------------------------------

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


def test_mii_maps_all_raw_fields_to_normalized_columns():
    result = normalize_nse_mii_security_master(sample_mii())

    marico = result.loc[
        result["Symbol"] == "MARICO"
    ].iloc[0]

    # Raw FinInstrmId -> Instrument ID
    assert marico["Instrument ID"] == "1"

    # Raw TckrSymb -> Symbol
    assert marico["Symbol"] == "MARICO"

    # Raw FinInstrmNm -> Company
    assert marico["Company"] == "MARICO LIMITED"

    # Raw SctySrs -> Series
    assert marico["Series"] == "EQ"

    # Raw ListgDt -> Listing Date
    assert marico["Listing Date"] == pd.Timestamp(
        "1996-05-01"
    )

    # Raw ISIN -> ISIN
    assert marico["ISIN"] == "INE196A01026"

    # Raw ParVal -> Face Value
    assert marico["Face Value"] == 1

    # Raw IssdCptl -> Issued Capital
    assert marico["Issued Capital"] == 100

    # Raw DelFlg -> Delete Flag
    assert marico["Delete Flag"] == "N"

    # Raw ElgbltyNrmlMkt -> Normal Market Eligibility
    assert marico["Normal Market Eligibility"] == "1"

    # Raw SctyStsNrmlMkt -> Normal Market Status
    assert marico["Normal Market Status"] == "6"

    # Raw PrtdToTrad -> Permitted to Trade
    assert marico["Permitted to Trade"] == "0"

    # Provider-generated fields
    assert marico["Exchange"] == "NSE"
    assert marico["Source"] == "NSE MII Security Master"


def test_mii_numeric_fields_are_converted_correctly():
    result = normalize_nse_mii_security_master(sample_mii())

    assert pd.api.types.is_numeric_dtype(
        result["Face Value"]
    )

    assert pd.api.types.is_numeric_dtype(
        result["Issued Capital"]
    )

    marico = result.loc[
        result["Symbol"] == "MARICO"
    ].iloc[0]

    assert marico["Face Value"] == 1
    assert marico["Issued Capital"] == 100


def test_mii_missing_optional_fields_does_not_break_normalization():
    data = sample_mii().drop(
        columns=[
            "FinInstrmId",
            "ListgDt",
            "ParVal",
            "IssdCptl",
            "PrtdToTrad",
        ]
    )

    result = normalize_nse_mii_security_master(data)

    assert result["Symbol"].tolist() == [
        "MARICO",
        "RELIANCE",
    ]

    assert "Instrument ID" not in result.columns
    assert "Listing Date" not in result.columns
    assert "Face Value" not in result.columns
    assert "Issued Capital" not in result.columns
    assert "Permitted to Trade" not in result.columns


def test_mii_listing_date_uses_1980_epoch():
    result = normalize_nse_mii_security_master(sample_mii())

    marico = result.loc[
        result["Symbol"] == "MARICO"
    ].iloc[0]

    reliance = result.loc[
        result["Symbol"] == "RELIANCE"
    ].iloc[0]

    assert marico["Listing Date"] == pd.Timestamp(
        "1996-05-01"
    )

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


# ---------------------------------------------------------
# NSE DATA FETCHER TESTS
# ---------------------------------------------------------

def test_fetcher_uses_mii_as_primary_source():
    report_date = date(2026, 11, 4)

    mii_url = NSE_MII_SECURITY_URL_TEMPLATE.format(
        date="04112026"
    )

    session = FakeSession([
        FakeResponse(),
        FakeResponse(gzip_csv(sample_mii())),
    ])

    result = fetch_nse_equity_universe(
        session=session,
        as_of_date=report_date,
        lookback_days=0,
    )

    assert result["Symbol"].tolist() == [
        "MARICO",
        "RELIANCE",
    ]

    assert result["Source"].eq(
        "NSE MII Security Master"
    ).all()

    assert mii_url in session.urls
    assert NSE_EQUITY_MASTER_URL not in session.urls


def test_fetcher_tries_previous_date_when_latest_mii_is_missing():
    report_date = date(2026, 11, 4)

    today_url = NSE_MII_SECURITY_URL_TEMPLATE.format(
        date="04112026"
    )

    previous_url = NSE_MII_SECURITY_URL_TEMPLATE.format(
        date="03112026"
    )

    session = FakeSession([
        FakeResponse(),
        FakeResponse(status_code=404),
        FakeResponse(gzip_csv(sample_mii())),
    ])

    result = fetch_nse_equity_universe(
        session=session,
        as_of_date=report_date,
        lookback_days=1,
    )

    assert "MARICO" in set(result["Symbol"])
    assert today_url in session.urls
    assert previous_url in session.urls

    assert result["Source"].eq(
        "NSE MII Security Master"
    ).all()


def test_fetcher_falls_back_to_legacy_master_when_mii_fails():
    legacy_csv = sample_master().to_csv(
        index=False
    ).encode("utf-8")

    session = FakeSession([
        FakeResponse(),
        FakeResponse(status_code=404),
        FakeResponse(legacy_csv),
    ])

    result = fetch_nse_equity_universe(
        session=session,
        as_of_date=date(2026, 11, 4),
        lookback_days=0,
    )

    assert result["Symbol"].tolist() == [
        "HINDUNILVR",
        "MARICO",
    ]

    assert result["Source"].eq(
        "NSE Official Equity Master"
    ).all()

    assert session.urls[-1] == NSE_EQUITY_MASTER_URL
        

