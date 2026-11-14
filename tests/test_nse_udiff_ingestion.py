"""Tests for production NSE CM UDiFF retrieval and guarded ingestion."""

from datetime import date
from io import BytesIO
from zipfile import ZipFile

import pandas as pd
import pytest
import requests

from data.providers.nse_udiff_ingestion import (
    NSEUdiFFIngestionError,
    fetch_nse_udiff_bhavcopy,
)


COLUMN_MAP = {
    "Date": "TradDt",
    "Symbol": "TckrSymb",
    "ISIN": "ISIN",
    "Series": "SctySrs",
    "Previous Close": "PrvsClsgPric",
    "Current Close": "ClsPric",
}


def make_archive():
    raw = pd.DataFrame({
        "TradDt": ["2026-11-12", "2026-11-12"],
        "TckrSymb": ["AAA", "BBB"],
        "ISIN": ["INE000A01010", "INE000B01010"],
        "SctySrs": ["EQ", "EQ"],
        "PrvsClsgPric": ["100", "200"],
        "ClsPric": ["110", "190"],
    })
    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        archive.writestr("bhavcopy.csv", raw.to_csv(index=False))
    return buffer.getvalue()


def make_universe():
    return pd.DataFrame({
        "Symbol": ["AAA", "BBB"],
        "ISIN": ["INE000A01010", "INE000B01010"],
        "Series": ["EQ", "EQ"],
        "Exchange": ["NSE", "NSE"],
        "Source": ["NSE MII Security Master"] * 2,
        "Universe As Of Date": ["2026-11-12"] * 2,
        "Universe Verification Status": ["MII_DATED"] * 2,
    })


class FakeResponse:
    def __init__(self, content, error=None):
        self.content = content
        self.error = error

    def raise_for_status(self):
        if self.error:
            raise self.error


class FakeSession:
    def __init__(self, response):
        self.response = response
        self.headers = {}
        self.requested_url = None
        self.requested_timeout = None

    def get(self, url, timeout):
        self.requested_url = url
        self.requested_timeout = timeout
        return self.response


def test_fetches_official_archive_and_captures_real_fetch_time():
    session = FakeSession(FakeResponse(make_archive()))

    result = fetch_nse_udiff_bhavcopy(
        date(2026, 11, 12),
        COLUMN_MAP,
        make_universe(),
        session=session,
    )

    assert session.requested_url == (
        "https://nsearchives.nseindia.com/content/cm/"
        "BhavCopy_NSE_CM_0_0_0_20261112_F_0000.csv.zip"
    )
    assert session.requested_timeout == 30
    assert result["source_filename"] == (
        "BhavCopy_NSE_CM_0_0_0_20261112_F_0000.csv.zip"
    )
    fetched = pd.Timestamp(result["fetched_at_utc"])
    assert fetched.tzinfo is not None
    assert fetched.tz_convert("UTC").isoformat().endswith("+00:00")
    assert result["normalized_data"]["Fetched At UTC"].eq(
        result["fetched_at_utc"]
    ).all()
    assert result["audit"]["source_sha256"]
    assert result["audit"]["source_authenticity_status"] == "UNVERIFIED"
    assert result["audit"]["schema_mapping_status"] == "UNVERIFIED"
    assert result["ingestion_status"] == "REVIEW"


def test_requires_explicit_column_map():
    with pytest.raises(ValueError, match="column_map"):
        fetch_nse_udiff_bhavcopy(
            date(2026, 11, 12),
            {},
            make_universe(),
            session=FakeSession(FakeResponse(make_archive())),
        )


def test_rejects_invalid_as_of_date():
    with pytest.raises(TypeError, match="datetime.date"):
        fetch_nse_udiff_bhavcopy(
            "2026-11-12",
            COLUMN_MAP,
            make_universe(),
            session=FakeSession(FakeResponse(make_archive())),
        )


def test_retrieval_failure_is_reported_without_fallback():
    session = FakeSession(
        FakeResponse(b"", requests.HTTPError("403 Forbidden"))
    )
    with pytest.raises(NSEUdiFFIngestionError, match="retrieval failed"):
        fetch_nse_udiff_bhavcopy(
            date(2026, 11, 12),
            COLUMN_MAP,
            make_universe(),
            session=session,
        )


def test_corrupt_archive_is_rejected_after_retrieval():
    with pytest.raises(NSEUdiFFIngestionError, match="normalization or audit"):
        fetch_nse_udiff_bhavcopy(
            date(2026, 11, 12),
            COLUMN_MAP,
            make_universe(),
            session=FakeSession(FakeResponse(b"not-a-zip")),
        )


def test_mii_date_mismatch_does_not_pass():
    universe = make_universe()
    universe["Universe As Of Date"] = "2026-11-11"

    with pytest.raises(NSEUdiFFIngestionError, match="normalization or audit"):
        fetch_nse_udiff_bhavcopy(
            date(2026, 11, 12),
            COLUMN_MAP,
            universe,
            session=FakeSession(FakeResponse(make_archive())),
        )
