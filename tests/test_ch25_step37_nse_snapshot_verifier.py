
import gzip
import hashlib
import json

from datetime import date

import pandas as pd
import pytest

from scripts.verify_nse_dated_snapshot_audit import verify_report


def make_report(tmp_path):
    report = tmp_path / "2026-11-11_test"
    report.mkdir()

    raw = report / "NSE_CM_security_11112026.csv.gz"
    raw.write_bytes(gzip.compress(b"test,nse,snapshot\n"))

    raw_hash = hashlib.sha256(raw.read_bytes()).hexdigest()

    normalized = pd.DataFrame({
        "Symbol": ["MARICO", "HINDUNILVR"],
        "ISIN": ["INE196A01026", "INE030A01027"],
        "Series": ["EQ", "EQ"],
        "Universe As Of Date": ["2026-11-11", "2026-11-11"],
    })
    normalized.to_csv(report / "nse_normalized_universe.csv", index=False)

    source_url = (
        "https://nsearchives.nseindia.com/content/cm/"
        "NSE_CM_security_11112026.csv.gz"
    )

    provenance = {
        "exchange": "NSE",
        "source_url": source_url,
        "sha256": raw_hash,
        "original_bytes_retained": True,
    }
    (report / (raw.name + ".provenance.json")).write_text(
        json.dumps(provenance),
        encoding="utf-8",
    )

    summary = {
        "status": "PASS",
        "exchange": "NSE",
        "archive_date": "2026-11-11",
        "source_url": source_url,
        "raw_snapshot": raw.name,
        "raw_sha256": raw_hash,
        "normalized_file": "nse_normalized_universe.csv",
        "normalized_rows": 2,
        "unique_symbols": 2,
        "unique_isins": 2,
        "provenance_check": {"status": "PASS"},
        "bse_status": "REVIEW",
        "sector_mapping_activated": False,
        "independent_external_checksum_verified": False,
    }
    (report / "summary.json").write_text(
        json.dumps(summary),
        encoding="utf-8",
    )
    return report


def test_valid_nse_snapshot_evidence_passes(tmp_path):
    report = make_report(tmp_path)

    result = verify_report(report, date(2026, 11, 11))

    assert result["status"] == "PASS"
    assert result["normalized_rows"] == 2
    assert result["sector_mapping_activated"] is False


def test_wrong_archive_date_is_rejected(tmp_path):
    report = make_report(tmp_path)

    with pytest.raises(ValueError, match="Archive date"):
        verify_report(report, date(2026, 11, 12))


def test_modified_raw_snapshot_is_rejected(tmp_path):
    report = make_report(tmp_path)
    raw = report / "NSE_CM_security_11112026.csv.gz"
    raw.write_bytes(b"modified")

    with pytest.raises(ValueError, match="SHA-256"):
        verify_report(report, date(2026, 11, 11))


def test_sector_mapping_must_remain_off(tmp_path):
    report = make_report(tmp_path)
    path = report / "summary.json"
    summary = json.loads(path.read_text(encoding="utf-8"))
    summary["sector_mapping_activated"] = True
    path.write_text(json.dumps(summary), encoding="utf-8")

    with pytest.raises(ValueError, match="Sector Mapping"):
        verify_report(report, date(2026, 11, 11))
