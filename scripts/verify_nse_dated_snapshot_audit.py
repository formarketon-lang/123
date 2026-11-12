
"""Verify retained evidence from a dated NSE snapshot audit."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT_ROOT = ROOT / "reports" / "nse_dated_snapshot_audit"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_report(report_dir: Path, expected_date: date) -> dict:
    summary_path = report_dir / "summary.json"
    if not summary_path.is_file():
        raise ValueError("summary.json is missing.")

    summary = json.loads(summary_path.read_text(encoding="utf-8"))

    if summary.get("status") != "PASS":
        raise ValueError("Original NSE audit status is not PASS.")

    if summary.get("exchange") != "NSE":
        raise ValueError("Report exchange is not NSE.")

    if summary.get("archive_date") != expected_date.isoformat():
        raise ValueError("Archive date does not match requested date.")

    source_url = summary.get("source_url", "")
    parsed = urlparse(source_url)
    if parsed.scheme != "https" or parsed.hostname != "nsearchives.nseindia.com":
        raise ValueError("Unapproved NSE source URL.")

    raw_path = report_dir / summary["raw_snapshot"]
    normalized_path = report_dir / summary["normalized_file"]
    provenance_path = Path(str(raw_path) + ".provenance.json")

    for path in (raw_path, normalized_path, provenance_path):
        if not path.is_file():
            raise ValueError(f"Required evidence file is missing: {path.name}")

    actual_hash = sha256_file(raw_path)
    expected_hash = str(summary.get("raw_sha256", "")).lower()

    if len(expected_hash) != 64 or actual_hash != expected_hash:
        raise ValueError("Raw snapshot SHA-256 mismatch.")

    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))

    if provenance.get("exchange") != "NSE":
        raise ValueError("Provenance exchange mismatch.")

    if provenance.get("source_url") != source_url:
        raise ValueError("Provenance source URL mismatch.")

    if provenance.get("sha256", "").lower() != actual_hash:
        raise ValueError("Provenance SHA-256 mismatch.")

    if provenance.get("original_bytes_retained") is not True:
        raise ValueError("Original snapshot retention is not confirmed.")

    provenance_check = summary.get("provenance_check", {})
    if provenance_check.get("status") != "PASS":
        raise ValueError("Provenance validation was not PASS.")

    normalized = pd.read_csv(normalized_path, dtype="string")

    if normalized.empty:
        raise ValueError("Normalized NSE universe is empty.")

    required = {"Symbol", "ISIN", "Series", "Universe As Of Date"}
    missing = sorted(required.difference(normalized.columns))
    if missing:
        raise ValueError(f"Normalized fields missing: {missing}")

    if len(normalized) != int(summary.get("normalized_rows", -1)):
        raise ValueError("Normalized row count mismatch.")

    if normalized["Symbol"].nunique() != int(summary.get("unique_symbols", -1)):
        raise ValueError("Unique symbol count mismatch.")

    if normalized["ISIN"].nunique() != int(summary.get("unique_isins", -1)):
        raise ValueError("Unique ISIN count mismatch.")

    if not normalized["Series"].eq("EQ").all():
        raise ValueError("Non-EQ record found in normalized universe.")

    if not normalized["Universe As Of Date"].eq(expected_date.isoformat()).all():
        raise ValueError("Normalized universe date mismatch.")

    if summary.get("bse_status") != "REVIEW":
        raise ValueError("BSE must remain REVIEW.")

    if summary.get("sector_mapping_activated") is not False:
        raise ValueError("Sector Mapping must remain OFF.")

    if summary.get("independent_external_checksum_verified") is not False:
        raise ValueError("Independent checksum status changed unexpectedly.")

    return {
        "status": "PASS",
        "verification": "CH25_STEP_37",
        "archive_date": expected_date.isoformat(),
        "report_directory": report_dir.name,
        "raw_sha256": actual_hash,
        "normalized_rows": int(len(normalized)),
        "unique_symbols": int(normalized["Symbol"].nunique()),
        "unique_isins": int(normalized["ISIN"].nunique()),
        "bse_status": "REVIEW",
        "sector_mapping_activated": False,
        "independent_external_checksum_verified": False,
    }


def find_latest_report(report_root: Path, archive_date: date) -> Path:
    matches = sorted(
        path for path in report_root.glob(f"{archive_date.isoformat()}_*")
        if path.is_dir()
    )
    if not matches:
        raise FileNotFoundError(
            f"No audit report found for {archive_date.isoformat()}."
        )
    return matches[-1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--as-of-date", required=True)
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    args = parser.parse_args()

    try:
        archive_date = date.fromisoformat(args.as_of_date)
    except ValueError:
        parser.error("--as-of-date must use YYYY-MM-DD.")

    report_dir = find_latest_report(args.report_root, archive_date)
    result = verify_report(report_dir, archive_date)

    output_path = report_dir / "step37_verification.json"
    output_path.write_text(
        json.dumps(result, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(json.dumps(result, indent=2, ensure_ascii=False))
    print("CH25 STEP 37 EVIDENCE VERIFICATION: PASS")


if __name__ == "__main__":
    main()
