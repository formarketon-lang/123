"""Tests for NSE Bhavcopy provenance and coverage audit."""

import hashlib

import pandas as pd
import pytest

from data.providers.nse_bhavcopy_provenance import (
    NSEBhavcopyProvenanceError,
    audit_nse_bhavcopy_provenance,
)


SOURCE_BYTES = b"nse-udiff-archive-test-content"
SOURCE_FILENAME = "CM_UDiFF_20261112.zip"


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


def make_bhavcopy():
    return pd.DataFrame({
        "Date": ["2026-11-12"] * 3,
        "Symbol": ["AAA", "BBB", "CCC"],
        "ISIN": [
            "INE000A01010",
            "INE000B01010",
            "INE000C01010",
        ],
        "Series": ["EQ"] * 3,
    })


def run_audit(
    bhavcopy=None,
    universe=None,
    source_bytes=SOURCE_BYTES,
    source_filename=SOURCE_FILENAME,
):
    return audit_nse_bhavcopy_provenance(
        bhavcopy=make_bhavcopy() if bhavcopy is None else bhavcopy,
        universe=make_universe() if universe is None else universe,
        source_bytes=source_bytes,
        source_filename=source_filename,
    )


def test_records_original_archive_sha256():
    result = run_audit()

    assert result["source_sha256"] == hashlib.sha256(
        SOURCE_BYTES
    ).hexdigest()


def test_records_archive_size_and_filename():
    result = run_audit()

    assert result["source_size_bytes"] == len(SOURCE_BYTES)
    assert result["source_filename"] == SOURCE_FILENAME
    assert result["source_format"] == "NSE_CM_UDIFF_ZIP"


def test_full_mii_coverage_is_reported():
    result = run_audit()

    assert result["observed_symbols"] == 3
    assert result["expected_symbols"] == 3
    assert result["missing_count"] == 0
    assert result["missing_symbols"] == []
    assert result["coverage_pct"] == 100.0
    assert result["coverage_status"] == "PASS"


def test_incomplete_coverage_is_review():
    bhavcopy = make_bhavcopy().iloc[:2].copy()

    result = run_audit(bhavcopy=bhavcopy)

    assert result["observed_symbols"] == 2
    assert result["expected_symbols"] == 3
    assert result["missing_symbols"] == ["CCC"]
    assert result["missing_count"] == 1
    assert result["coverage_status"] == "REVIEW"
    assert "MII_SYMBOL_COVERAGE_INCOMPLETE" in (
        result["audit_reasons"]
    )


def test_identity_mismatch_is_rejected():
    bhavcopy = make_bhavcopy()
    bhavcopy.loc[0, "ISIN"] = "INE999Z01010"

    with pytest.raises(ValueError, match="mismatch"):
        run_audit(bhavcopy=bhavcopy)


def test_unknown_symbol_is_rejected():
    bhavcopy = make_bhavcopy()
    bhavcopy.loc[0, "Symbol"] = "UNKNOWN"

    with pytest.raises(ValueError, match="absent from MII"):
        run_audit(bhavcopy=bhavcopy)


def test_empty_archive_bytes_are_rejected():
    with pytest.raises(
        NSEBhavcopyProvenanceError,
        match="archive bytes",
    ):
        run_audit(source_bytes=b"")


def test_non_bytes_archive_is_rejected():
    with pytest.raises(
        NSEBhavcopyProvenanceError,
        match="archive bytes",
    ):
        run_audit(source_bytes="not-bytes")


def test_invalid_archive_filename_is_rejected():
    with pytest.raises(
        NSEBhavcopyProvenanceError,
        match="filename",
    ):
        run_audit(source_filename="../bhavcopy.zip")


def test_non_zip_filename_is_rejected():
    with pytest.raises(
        NSEBhavcopyProvenanceError,
        match="filename",
    ):
        run_audit(source_filename="bhavcopy.csv")


def test_schema_mapping_remains_unverified():
    result = run_audit()

    assert result["schema_mapping_status"] == "UNVERIFIED"
    assert result["audit_status"] == "REVIEW"
    assert (
        "OFFICIAL_UDIFF_SCHEMA_MAPPING_UNVERIFIED"
        in result["audit_reasons"]
    )


def test_source_provenance_is_recorded():
    result = run_audit()

    assert result["source"] == "NSE"
    assert result["source_provenance_status"] == "PASS"
    assert result["observation_date"] == "2026-11-12"
    assert result["mii_snapshot_date"] == "2026-11-12"
    assert result["identity_status"] == "PASS"
  
