"""Tests for production NSE CM UDiFF cash-equity ingestion."""

from io import BytesIO
from zipfile import ZipFile

import pandas as pd
import pytest

from data.providers import nse_udiff_downloader as downloader


def make_raw():
    return pd.DataFrame({
        "TradDt": ["2026-11-13"] * 3,
        "BizDt": ["2026-11-13"] * 3,
        "Sgmt": ["CM"] * 3,
        "Src": ["NSE"] * 3,
        "FinInstrmTp": ["STK"] * 3,
        "FinInstrmId": ["1", "2", "3"],
        "ISIN": [
            "INE000A01010",
            "INE000B01010",
            "INE000C01010",
        ],
        "TckrSymb": ["AAA", "BBB", "CCC"],
        "SctySrs": ["EQ"] * 3,
        "OpnPric": ["101", "99", "100"],
        "HghPric": ["111", "101", "100"],
        "LwPric": ["100", "90", "100"],
        "ClsPric": ["110", "90", "100"],
        "PrvsClsgPric": ["100", "100", "100"],
        "TtlTradgVol": ["1000", "2000", "0"],
    })


def make_zip(data=None):
    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        archive.writestr(
            "BhavCopy.csv",
            (make_raw() if data is None else data).to_csv(index=False),
        )
    return buffer.getvalue()


class FakeResponse:
    def __init__(self, content, url=None):
        self.content = content
        self.url = url or (
            "https://nsearchives.nseindia.com/content/cm/"
            "BhavCopy_NSE_CM_0_0_0_20261113_F_0000.csv.zip"
        )

    def raise_for_status(self):
        return None


class FakeSession:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.response


def test_normalizes_official_nse_cm_udiff_iso_tags():
    result = downloader.normalize_nse_cm_udiff_equity(
        make_raw(),
        trade_date="2026-11-13",
        fetched_at_utc="2026-11-14T01:00:00Z",
    )

    assert result["Symbol"].tolist() == ["AAA", "BBB", "CCC"]
    assert result["ISIN"].tolist() == [
        "INE000A01010",
        "INE000B01010",
        "INE000C01010",
    ]
    assert result["Previous Close"].tolist() == [100, 100, 100]
    assert result["Current Close"].tolist() == [110, 90, 100]
    assert result["Open"].tolist() == [101, 99, 100]
    assert result["High"].tolist() == [111, 101, 100]
    assert result["Low"].tolist() == [100, 90, 100]
    assert result["Volume"].tolist() == [1000, 2000, 0]
    assert result["Source"].eq("NSE").all()
    assert result["Exchange"].eq("NSE").all()
    assert result["Fetched At UTC"].eq("2026-11-14T01:00:00Z").all()


def test_excludes_non_cm_non_nse_non_stock_and_non_eq_rows():
    raw = make_raw()
    raw.loc[0, "Sgmt"] = "FO"
    raw.loc[1, "FinInstrmTp"] = "FUT"
    raw.loc[2, "SctySrs"] = "BE"

    with pytest.raises(downloader.NSEUdiFFDownloadError, match="no NSE CM STK EQ rows"):
        downloader.normalize_nse_cm_udiff_equity(
            raw,
            trade_date="2026-11-13",
            fetched_at_utc="2026-11-14T01:00:00Z",
        )


def test_rejects_trade_date_mismatch():
    with pytest.raises(downloader.NSEUdiFFDownloadError, match="does not match requested date"):
        downloader.normalize_nse_cm_udiff_equity(
            make_raw(),
            trade_date="2026-11-12",
            fetched_at_utc="2026-11-14T01:00:00Z",
        )


def test_rejects_missing_official_iso_tag():
    raw = make_raw().drop(columns=["PrvsClsgPric"])

    with pytest.raises(downloader.NSEUdiFFDownloadError, match="missing required ISO tags"):
        downloader.normalize_nse_cm_udiff_equity(
            raw,
            trade_date="2026-11-13",
            fetched_at_utc="2026-11-14T01:00:00Z",
        )


def test_rejects_bad_ohlc_relationship():
    raw = make_raw()
    raw.loc[0, "HghPric"] = "99"

    with pytest.raises(downloader.NSEUdiFFDownloadError, match="inconsistent OHLC"):
        downloader.normalize_nse_cm_udiff_equity(
            raw,
            trade_date="2026-11-13",
            fetched_at_utc="2026-11-14T01:00:00Z",
        )


def test_download_uses_official_archive_and_records_fetch_timestamp():
    session = FakeSession(FakeResponse(make_zip()))

    result = downloader.download_nse_cm_udiff_equity_bhavcopy(
        "2026-11-13",
        session=session,
    )

    assert len(session.calls) == 1
    url, kwargs = session.calls[0]
    assert url == downloader.NSE_UDIFF_BHAVCOPY_URL_TEMPLATE.format(
        yyyymmdd="20261113"
    )
    assert kwargs["timeout"] == 60
    assert result["source"] == "NSE"
    assert result["source_filename"] == (
        "BhavCopy_NSE_CM_0_0_0_20261113_F_0000.csv.zip"
    )
    assert len(result["sha256"]) == 64
    assert result["normalized"]["Fetched At UTC"].nunique() == 1
    assert pd.Timestamp(
        result["fetched_at_utc"]
    ).tzinfo is not None


def test_download_rejects_non_official_redirect_host():
    session = FakeSession(
        FakeResponse(
            make_zip(),
            url="https://example.com/fake.zip",
        )
    )

    with pytest.raises(downloader.NSEUdiFFDownloadError, match="official NSE archive host"):
        downloader.download_nse_cm_udiff_equity_bhavcopy(
            "2026-11-13",
            session=session,
        )


def test_download_rejects_non_zip_response():
    session = FakeSession(
        FakeResponse(b"not-a-zip")
    )

    with pytest.raises(downloader.NSEUdiFFDownloadError, match="did not return a ZIP"):
        downloader.download_nse_cm_udiff_equity_bhavcopy(
            "2026-11-13",
            session=session,
        )


def test_previous_close_outside_current_candle_is_valid():
    raw = make_raw()
    raw.loc[0, "PrvsClsgPric"] = "120"
    raw.loc[0, "HghPric"] = "111"

    result = downloader.normalize_nse_cm_udiff_equity(
        raw,
        trade_date="2026-11-13",
        fetched_at_utc="2026-11-14T01:00:00Z",
    )

    assert result.loc[0, "Previous Close"] == 120
    assert result.loc[0, "High"] == 111
