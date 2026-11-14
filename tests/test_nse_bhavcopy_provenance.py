
"""Tests for NSE Bhavcopy provenance and archive validation."""

import hashlib
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

import pandas as pd
import pytest

from data.providers.nse_bhavcopy_provenance import (
    NSEBhavcopyProvenanceError,
    _validate_bhavcopy_archive,
    audit_nse_bhavcopy_provenance,
)


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


def make_zip(files=None):
    if files is None:
        files = {"bhavcopy.csv": "Symbol\nAAA\n"}

    buffer = BytesIO()

    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)

    return buffer.getvalue()


SOURCE_BYTES = make_zip()


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


# Original regression tests restored

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
    result = run_audit(bhavcopy=make_bhavcopy().iloc[:2].copy())

    assert result["observed_symbols"] == 2
    assert result["expected_symbols"] == 3
    assert result["missing_symbols"] == ["CCC"]
    assert result["missing_count"] == 1
    assert result["coverage_status"] == "REVIEW"
    assert "MII_SYMBOL_COVERAGE_INCOMPLETE" in (
        result["audit_reasons"]
    )


def test_identity_mismatch_is_reported_in_provenance_review():
    bhavcopy = make_bhavcopy()
    bhavcopy.loc[0, "ISIN"] = "INE999Z01010"

    result = run_audit(bhavcopy=bhavcopy)

    assert result["identity_status"] == "REVIEW"
    assert result["isin_mismatch_symbols"] == ["AAA"]
    assert result["isin_mismatch_count"] == 1
    assert "BHAVCOPY_SYMBOL_ISIN_MISMATCH" in result["audit_reasons"]


def test_unknown_symbol_is_reported_in_provenance_review():
    bhavcopy = make_bhavcopy()
    bhavcopy.loc[0, "Symbol"] = "UNKNOWN"

    result = run_audit(bhavcopy=bhavcopy)

    assert result["identity_status"] == "REVIEW"
    assert result["unknown_symbols"] == ["UNKNOWN"]
    assert result["unknown_count"] == 1
    assert "BHAVCOPY_SYMBOLS_NOT_PRESENT_IN_DATED_MII" in (
        result["audit_reasons"]
    )


def test_empty_archive_bytes_are_rejected():
    with pytest.raises(NSEBhavcopyProvenanceError, match="archive bytes"):
        run_audit(source_bytes=b"")


def test_non_bytes_archive_is_rejected():
    with pytest.raises(NSEBhavcopyProvenanceError, match="archive bytes"):
        run_audit(source_bytes="not-bytes")


def test_invalid_archive_filename_is_rejected():
    with pytest.raises(NSEBhavcopyProvenanceError, match="filename"):
        run_audit(source_filename="../bhavcopy.zip")


def test_non_zip_filename_is_rejected():
    with pytest.raises(NSEBhavcopyProvenanceError, match="filename"):
        run_audit(source_filename="bhavcopy.csv")


def test_invalid_zip_bytes_are_rejected():
    with pytest.raises(NSEBhavcopyProvenanceError, match="Invalid"):
        run_audit(source_bytes=b"not-a-real-zip")


def test_schema_mapping_remains_unverified():
    result = run_audit()

    assert result["schema_mapping_status"] == "UNVERIFIED"
    assert result["audit_status"] == "REVIEW"
    assert "OFFICIAL_UDIFF_SCHEMA_REFERENCE_NOT_RECORDED" in (
        result["audit_reasons"]
    )
    assert "OFFICIAL_UDIFF_SCHEMA_CONTENT_REVIEW_PENDING" in (
        result["audit_reasons"]
    )


def test_hash_recording_does_not_claim_source_authenticity():
    result = run_audit()

    assert result["source_provenance_status"] == "HASH_RECORDED"
    assert result["source_authenticity_status"] == "UNVERIFIED"
    assert "OFFICIAL_NSE_HTTPS_ENDPOINT_NOT_VERIFIED" in (
        result["audit_reasons"]
    )


def test_source_and_mii_dates_are_recorded():
    result = run_audit()

    assert result["source"] == "NSE"
    assert result["observation_date"] == "2026-11-12"
    assert result["mii_snapshot_date"] == "2026-11-12"
    assert result["identity_status"] == "PASS"


# New archive validation tests

def test_valid_archive_has_exactly_one_csv():
    _validate_bhavcopy_archive(make_zip())


def test_rejects_archive_without_csv():
    with pytest.raises(NSEBhavcopyProvenanceError):
        _validate_bhavcopy_archive(
            make_zip({"readme.txt": "not a bhavcopy"})
        )


def test_rejects_multiple_csv_files():
    with pytest.raises(NSEBhavcopyProvenanceError):
        _validate_bhavcopy_archive(
            make_zip({
                "first.csv": "A\n1\n",
                "second.csv": "B\n2\n",
            })
        )


def test_rejects_empty_csv():
    with pytest.raises(NSEBhavcopyProvenanceError):
        _validate_bhavcopy_archive(
            make_zip({"bhavcopy.csv": ""})
        )


def test_rejects_unsafe_archive_path():
    with pytest.raises(NSEBhavcopyProvenanceError):
        _validate_bhavcopy_archive(
            make_zip({"../bhavcopy.csv": "A\n1\n"})
        )


def test_rejects_windows_style_archive_path():
    with pytest.raises(NSEBhavcopyProvenanceError):
        _validate_bhavcopy_archive(
            make_zip({"folder\\bhavcopy.csv": "A\n1\n"})
        )


def test_rejects_invalid_zip_directly():
    with pytest.raises(NSEBhavcopyProvenanceError):
        _validate_bhavcopy_archive(b"not-a-zip")


def test_rejects_empty_bytes_directly():
    with pytest.raises(NSEBhavcopyProvenanceError):
        _validate_bhavcopy_archive(b"")


def test_archive_structure_is_reported():
    result = run_audit()

    assert result["archive_structure_status"] == "PASS"
    assert result["source_authenticity_status"] == "UNVERIFIED"
    assert result["audit_status"] == "REVIEW"


def test_official_endpoint_and_schema_reference_are_recorded():
    from data.providers.nse_bhavcopy_provenance import (
        NSE_UDIFF_SCHEMA_REFERENCE_URL,
    )

    result = audit_nse_bhavcopy_provenance(
        bhavcopy=make_bhavcopy(),
        universe=make_universe(),
        source_bytes=SOURCE_BYTES,
        source_filename=SOURCE_FILENAME,
        source_url=(
            "https://nsearchives.nseindia.com/content/cm/"
            "BhavCopy_NSE_CM_0_0_0_20261112_F_0000.csv.zip"
        ),
        schema_reference_url=NSE_UDIFF_SCHEMA_REFERENCE_URL,
    )

    assert result["source_authenticity_status"] == (
        "OFFICIAL_NSE_HTTPS_HOST"
    )
    assert result["schema_mapping_status"] == (
        "REVIEW_REFERENCE_RECORDED"
    )
    assert result["audit_status"] == "REVIEW"
    assert "OFFICIAL_UDIFF_SCHEMA_CONTENT_REVIEW_PENDING" in (
        result["audit_reasons"]
    )


def test_official_schema_evidence_can_pass_when_verified():
    from data.providers.nse_bhavcopy_provenance import (
        NSE_UDIFF_SCHEMA_REFERENCE_URL,
    )

    result = audit_nse_bhavcopy_provenance(
        bhavcopy=make_bhavcopy(),
        universe=make_universe(),
        source_bytes=SOURCE_BYTES,
        source_filename=SOURCE_FILENAME,
        source_url=(
            "https://nsearchives.nseindia.com/content/cm/"
            "BhavCopy_NSE_CM_0_0_0_20261112_F_0000.csv.zip"
        ),
        schema_reference_url=NSE_UDIFF_SCHEMA_REFERENCE_URL,
        schema_mapping_verified=True,
    )

    assert result["schema_mapping_status"] == "PASS"
    assert result["audit_status"] == "PASS"
    assert result["audit_reasons"] == []
