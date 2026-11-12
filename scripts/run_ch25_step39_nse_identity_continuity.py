"""Compare two verified NSE snapshots for Symbol and ISIN continuity."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.verify_nse_dated_snapshot_audit import (
    find_latest_report,
    verify_report,
)

SNAPSHOT_ROOT = ROOT / "reports" / "nse_dated_snapshot_audit"
OUTPUT_ROOT = ROOT / "reports" / "nse_identity_continuity"

REQUIRED = ["Symbol", "Series", "ISIN"]


def prepare_identity(frame: pd.DataFrame, label: str) -> pd.DataFrame:
    missing = sorted(set(REQUIRED) - set(frame.columns))
    if missing:
        raise ValueError(f"{label} missing identity columns: {missing}")

    result = frame[REQUIRED].copy()

    for column in REQUIRED:
        result[column] = (
            result[column].astype("string").str.strip().str.upper()
        )

    if result.isna().any().any() or result.eq("").any().any():
        raise ValueError(f"{label} contains blank identity values.")

    if not result["Series"].eq("EQ").all():
        raise ValueError(f"{label} contains non-EQ records.")

    for column in ["Symbol", "ISIN"]:
        if result[column].duplicated().any():
            raise ValueError(f"{label} contains duplicate {column} values.")

    if not result["ISIN"].str.fullmatch(
        r"IN[A-Z0-9]{10}", na=False
    ).all():
        raise ValueError(f"{label} contains invalid ISIN values.")

    return result.reset_index(drop=True)


def build_identity_ledger(
    previous: pd.DataFrame,
    current: pd.DataFrame,
) -> dict:
    old = prepare_identity(previous, "Previous snapshot")
    new = prepare_identity(current, "Current snapshot")

    old_by_isin = old.set_index("ISIN").to_dict("index")
    new_by_isin = new.set_index("ISIN").to_dict("index")
    old_by_symbol = old.set_index("Symbol").to_dict("index")
    new_by_symbol = new.set_index("Symbol").to_dict("index")

    events = []
    unchanged = 0
    paired_new_isins = set()

    for isin, old_item in old_by_isin.items():
        new_item = new_by_isin.get(isin)

        if new_item is not None:
            symbol_changed = old_item["Symbol"] != new_item["Symbol"]
            series_changed = old_item["Series"] != new_item["Series"]

            if symbol_changed or series_changed:
                events.append({
                    "event_type": "SAME_ISIN_IDENTITY_CHANGE",
                    "previous_symbol": old_item["Symbol"],
                    "current_symbol": new_item["Symbol"],
                    "previous_isin": isin,
                    "current_isin": isin,
                    "previous_series": old_item["Series"],
                    "current_series": new_item["Series"],
                    "symbol_changed": symbol_changed,
                    "series_changed": series_changed,
                })
            else:
                unchanged += 1
            continue

        same_symbol = new_by_symbol.get(old_item["Symbol"])

        if same_symbol is not None:
            paired_new_isins.add(same_symbol["ISIN"])
            events.append({
                "event_type": "ISIN_CHANGED_SAME_SYMBOL",
                "symbol": old_item["Symbol"],
                "previous_isin": isin,
                "current_isin": same_symbol["ISIN"],
                "previous_series": old_item["Series"],
                "current_series": same_symbol["Series"],
            })
        else:
            events.append({
                "event_type": "REMOVED_SECURITY",
                "symbol": old_item["Symbol"],
                "previous_isin": isin,
                "current_isin": None,
                "previous_series": old_item["Series"],
                "current_series": None,
            })

    for isin, new_item in new_by_isin.items():
        if isin in old_by_isin or isin in paired_new_isins:
            continue

        if new_item["Symbol"] not in old_by_symbol:
            events.append({
                "event_type": "ADDED_SECURITY",
                "symbol": new_item["Symbol"],
                "previous_isin": None,
                "current_isin": isin,
                "previous_series": None,
                "current_series": new_item["Series"],
            })

    events.sort(
        key=lambda item: (
            item["event_type"],
            str(item.get("symbol", item.get("current_symbol", ""))),
        )
    )

    return {
        "status": "PASS",
        "previous_rows": len(old),
        "current_rows": len(new),
        "unchanged_identity_count": unchanged,
        "change_event_count": len(events),
        "review_required": bool(events),
        "events": events,
        "interpretation": (
            "Changes are recorded for review; no corporate action "
            "or legal cause is inferred."
        ),
    }


def load_verified_snapshot(archive_date: date) -> tuple[pd.DataFrame, dict]:
    report_dir = find_latest_report(SNAPSHOT_ROOT, archive_date)
    verification = verify_report(report_dir, archive_date)

    evidence_path = report_dir / "step37_verification.json"
    if not evidence_path.is_file():
        raise ValueError("Step 37 verification evidence is missing.")

    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))

    if (
        evidence.get("status") != "PASS"
        or evidence.get("raw_sha256") != verification.get("raw_sha256")
    ):
        raise ValueError("Step 37 evidence does not match verified snapshot.")

    summary = json.loads(
        (report_dir / "summary.json").read_text(encoding="utf-8")
    )

    frame = pd.read_csv(
        report_dir / summary["normalized_file"],
        dtype="string",
        low_memory=False,
    )

    return frame, verification


def run_identity_continuity(
    previous_date: date,
    current_date: date,
) -> dict:
    if previous_date >= current_date:
        raise ValueError("Previous date must be earlier than current date.")

    previous, previous_verification = load_verified_snapshot(previous_date)
    current, current_verification = load_verified_snapshot(current_date)

    ledger = build_identity_ledger(previous, current)

    report = {
        "verification": "CH25_STEP_39",
        "status": ledger["status"],
        "previous_archive_date": previous_date.isoformat(),
        "current_archive_date": current_date.isoformat(),
        "previous_raw_sha256": previous_verification["raw_sha256"],
        "current_raw_sha256": current_verification["raw_sha256"],
        "identity_ledger": ledger,
        "bse_status": "REVIEW",
        "sector_mapping_activated": False,
        "independent_external_checksum_verified": False,
    }

    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output = OUTPUT_ROOT / (
        f"{previous_date.isoformat()}_to_{current_date.isoformat()}_"
        f"{timestamp}.json"
    )
    output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(json.dumps(report, indent=2, ensure_ascii=False))
    print("CH25 STEP 39 IDENTITY CONTINUITY: PASS")

    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--previous-date", required=True)
    parser.add_argument("--current-date", required=True)
    args = parser.parse_args()

    try:
        previous_date = date.fromisoformat(args.previous_date)
        current_date = date.fromisoformat(args.current_date)
    except ValueError:
        parser.error("Dates must use YYYY-MM-DD format.")

    run_identity_continuity(previous_date, current_date)


if __name__ == "__main__":
    main()
  
