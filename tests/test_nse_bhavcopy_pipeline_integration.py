
"""End-to-end tests for the guarded NSE Bhavcopy pipeline."""

from io import BytesIO
from zipfile import ZipFile

import pandas as pd
import pytest

from data.providers.nse_udiff_bhavcopy import (
    normalize_nse_udiff_equity_bhavcopy,
    read_nse_udiff_bhavcopy,
)
from data.providers.nse_bhavcopy_mii_validation import (
    reconcile_bhavcopy_with_mii,
)
from data.providers.nse_bhavcopy_provenance import (
    audit_nse_bhavcopy_provenance,
)
from services.market_intelligence.breadth_service import (
    analyze_nse_market_breadth,
)


TEST_ONLY_COLUMN_MAP = {
    "Date": "TradeDate",
    "Symbol": "Ticker",
    "ISIN": "SecurityISIN",
    "Series": "SecuritySeries",
    "Previous Close": "PrevClose",
    "Current Close": "ClosePrice",
}


def make_raw_data():
    return pd.DataFrame({
        "TradeDate": ["2026-11-12"] * 3,
        "Ticker": ["AAA", "BBB", "CCC"],
        "SecurityISIN": [
            "INE000A01010",
            "INE000B01010",
            "INE000C01010",
        ],
        "SecuritySeries": ["EQ"] * 3,
        "PrevClose": ["100", "100", "100"],
        "ClosePrice": ["110", "90", "100"],
    })


def make_universe():
    return pd.DataFrame({
        "Symbol": ["AAA", "BBB", "CCC"],
        "ISIN": [
            "INE000A01010",
            "INE000B01010",
            "INE000C01010",
        ],
        "Series": ["EQ"] * 3,
        "Exchange": ["NSE"] * 3,
        "Source": ["NSE MII Security Master"] * 3,
        "Universe As Of Date": ["2026-11-12"] * 3,
        "Universe Verification Status": ["MII_DATED"] * 3,
    })


def make_archive(raw_data=None):
    buffer = BytesIO()

    with ZipFile(buffer, "w") as archive:
        archive.writestr(
            "bhavcopy.csv",
            (make_raw_data() if raw_data is None else raw_data).to_csv(
                index=False
            ),
        )

    return buffer.getvalue()


def run_pipeline(raw_data=None):
    archive_bytes = make_archive(raw_data)

    raw = read_nse_udiff_bhavcopy(archive_bytes)

    normalized = normalize_nse_udiff_equity_bhavcopy(
        raw,
        TEST_ONLY_COLUMN_MAP,
    )

    universe = make_universe()

    reconciliation = reconcile_bhavcopy_with_mii(
        normalized,
        universe,
    )

    audit = audit_nse_bhavcopy_provenance(
        bhavcopy=normalized,
        universe=universe,
        source_bytes=archive_bytes,
        source_filename="CM_UDiFF_20261112.zip",
    )

    breadth = analyze_nse_market_breadth(
        stock_data=normalized,
        verified_universe=universe,
        observation_date="2026-11-12",
    )

    return normalized, reconciliation, audit, breadth


def test_complete_bhavcopy_pipeline():
    normalized, reconciliation, audit, breadth = run_pipeline()

    assert normalized["Symbol"].tolist() == ["AAA", "BBB", "CCC"]
    assert reconciliation["identity_status"] == "PASS"
    assert reconciliation["coverage_status"] == "PASS"

    assert audit["source_provenance_status"] == "HASH_RECORDED"
    assert audit["source_authenticity_status"] == "UNVERIFIED"
    assert audit["schema_mapping_status"] == "UNVERIFIED"
    assert audit["audit_status"] == "REVIEW"

    assert breadth["advancing"] == 1
    assert breadth["declining"] == 1
    assert breadth["unchanged"] == 1
    assert breadth["coverage_pct"] == 100.0
    assert breadth["coverage_status"] == "PASS"


def test_incomplete_bhavcopy_coverage_stays_review():
    raw = make_raw_data().iloc[:2].copy()

    normalized, reconciliation, audit, breadth = run_pipeline(raw)

    assert reconciliation["missing_symbols"] == ["CCC"]
    assert reconciliation["coverage_status"] == "REVIEW"
    assert audit["coverage_status"] == "REVIEW"
    assert audit["audit_status"] == "REVIEW"
    assert breadth["coverage_status"] == "REVIEW"
    assert breadth["analysis_status"] == "REVIEW"


def test_symbol_isin_mismatch_blocks_pipeline():
    raw = make_raw_data()
    raw.loc[0, "SecurityISIN"] = "INE999Z01010"

    archive_bytes = make_archive(raw)
    parsed = read_nse_udiff_bhavcopy(archive_bytes)
    normalized = normalize_nse_udiff_equity_bhavcopy(
        parsed,
        TEST_ONLY_COLUMN_MAP,
    )

    with pytest.raises(ValueError, match="mismatch"):
        reconcile_bhavcopy_with_mii(
            normalized,
            make_universe(),
        )


def test_test_mapping_is_not_official_schema_approval():
    _, _, audit, _ = run_pipeline()

    assert audit["schema_mapping_status"] == "UNVERIFIED"
    assert audit["audit_status"] == "REVIEW"
      
