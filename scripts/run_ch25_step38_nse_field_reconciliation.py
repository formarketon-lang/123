
"""Reconcile dated NSE MII raw fields with normalized EQ universe."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.run_nse_universe_live_check import (
    compare_fields,
    prepare_raw_equity_scope,
)
from scripts.verify_nse_dated_snapshot_audit import (
    find_latest_report,
    verify_report,
)

REPORT_ROOT = ROOT / "reports" / "nse_dated_snapshot_audit"


def run_reconciliation(archive_date: date) -> dict:
    report_dir = find_latest_report(REPORT_ROOT, archive_date)

    # Re-verify Step 37 evidence before using its files.
    verified = verify_report(report_dir, archive_date)

    step37_path = report_dir / "step37_verification.json"
    if not step37_path.is_file():
        raise ValueError("Step 37 verification evidence is missing.")

    step37 = json.loads(step37_path.read_text(encoding="utf-8"))

    if step37.get("status") != "PASS":
        raise ValueError("Step 37 verification status is not PASS.")

    if step37.get("raw_sha256") != verified.get("raw_sha256"):
        raise ValueError("Step 37 snapshot hash does not match.")

    summary = json.loads(
        (report_dir / "summary.json").read_text(encoding="utf-8")
    )

    raw_path = report_dir / summary["raw_snapshot"]
    normalized_path = report_dir / summary["normalized_file"]

    if not raw_path.is_file() or not normalized_path.is_file():
        raise FileNotFoundError("Step 37 source evidence file is missing.")

    raw = pd.read_csv(
        raw_path,
        compression="gzip",
        dtype="string",
        low_memory=False,
    )
    normalized = pd.read_csv(
        normalized_path,
        dtype="string",
        low_memory=False,
    )

    raw_scope, scope_summary = prepare_raw_equity_scope(raw)

    field_results, total_mismatches, key_coverage = compare_fields(
        raw_scope,
        normalized,
    )

    scope_count = scope_summary["eligible_eq_scope_rows"]
    normalized_count = len(normalized)

    count_match = scope_count == normalized_count
    field_status = all(
        item.get("status") == "PASS"
        for item in field_results.values()
    )

    status = (
        "PASS"
        if (
            total_mismatches == 0
            and key_coverage["status"] == "PASS"
            and count_match
            and field_status
        )
        else "FAIL"
    )

    result = {
        "verification": "CH25_STEP_38",
        "status": status,
        "archive_date": archive_date.isoformat(),
        "report_directory": report_dir.name,
        "raw_sha256": verified["raw_sha256"],
        "raw_scope": scope_summary,
        "normalized_rows": normalized_count,
        "raw_normalized_count_match": count_match,
        "key_coverage": key_coverage,
        "field_mapping": field_results,
        "total_field_mismatches": total_mismatches,
        "bse_status": "REVIEW",
        "sector_mapping_activated": False,
        "independent_external_checksum_verified": False,
    }

    output_path = report_dir / "step38_raw_normalized_audit.json"
    output_path.write_text(
        json.dumps(result, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(json.dumps(result, indent=2, ensure_ascii=False))

    if status != "PASS":
        raise ValueError("CH25 Step 38 reconciliation failed.")

    print("CH25 STEP 38 RAW-TO-NORMALIZED RECONCILIATION: PASS")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--as-of-date", required=True)
    args = parser.parse_args()

    try:
        archive_date = date.fromisoformat(args.as_of_date)
    except ValueError:
        parser.error("--as-of-date must use YYYY-MM-DD.")

    run_reconciliation(archive_date)


if __name__ == "__main__":
    main()
