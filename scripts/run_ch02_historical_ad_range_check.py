"""Multi-month official NSE historical A/D range verification."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.market_intelligence.historical_ad_service import (
    analyze_nse_historical_advance_decline_for_range,
)



def _reconciliation_summary(result: dict) -> dict:
    """Return truthful aggregate reconciliation counts for the JSON report."""
    coverage = result.get("coverage")
    details = result.get("reconciliation_details")

    if isinstance(coverage, pd.DataFrame):
        missing_count = int(
            pd.to_numeric(
                coverage.get("missing", pd.Series(dtype="float64")),
                errors="coerce",
            ).fillna(0).sum()
        )
        identity_exception_count = int(
            pd.to_numeric(
                coverage.get(
                    "identity_exceptions", pd.Series(dtype="float64")
                ),
                errors="coerce",
            ).fillna(0).sum()
        )
        expected_observations = int(
            pd.to_numeric(
                coverage.get(
                    "expected_universe", pd.Series(dtype="float64")
                ),
                errors="coerce",
            ).fillna(0).sum()
        )
        verified_observations = int(
            pd.to_numeric(
                coverage.get(
                    "verified_observations", pd.Series(dtype="float64")
                ),
                errors="coerce",
            ).fillna(0).sum()
        )
    else:
        missing_count = 0
        identity_exception_count = 0
        expected_observations = 0
        verified_observations = 0

    if isinstance(details, pd.DataFrame) and "issue_type" in details.columns:
        issue_counts = {
            str(key): int(value)
            for key, value in details["issue_type"].value_counts().items()
        }
        detail_count = int(len(details))
    else:
        issue_counts = {}
        detail_count = 0

    return {
        "missing_count": missing_count,
        "identity_exception_count": identity_exception_count,
        "expected_member_observations": expected_observations,
        "verified_member_observations": verified_observations,
        "reconciliation_detail_count": detail_count,
        "reconciliation_issue_type_counts": issue_counts,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--calendar-days", type=int, default=120)
    parser.add_argument("--max-sessions", type=int, default=180)
    args = parser.parse_args()

    if not 30 <= args.calendar_days <= 370:
        raise SystemExit("--calendar-days must be between 30 and 370.")
    if not 10 <= args.max_sessions <= 180:
        raise SystemExit("--max-sessions must be between 10 and 180.")

    today = datetime.now(ZoneInfo("Asia/Kolkata")).date()
    end_date = today - timedelta(days=1)
    start_date = end_date - timedelta(days=args.calendar_days - 1)

    output = Path("artifacts/ch02_historical_ad_range")
    output.mkdir(parents=True, exist_ok=True)

    result = analyze_nse_historical_advance_decline_for_range(
        start_date,
        end_date,
        max_sessions=args.max_sessions,
        initial_anchor=0,
    )

    calendar = result.get("calendar_provenance", {})
    reconciliation_summary = _reconciliation_summary(result)
    report = {
        "project": "TLP-MIM-001",
        "chapter": "02",
        "verification": "MULTI_MONTH_HISTORICAL_NSE_AD_RANGE",
        "generated_at_utc": datetime.now(ZoneInfo("UTC")).isoformat(),
        "requested_range": {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "calendar_days": args.calendar_days,
            "max_sessions": args.max_sessions,
        },
        "calendar_status": result.get("calendar_status"),
        "calendar_provenance": calendar,
        "calendar_session_count": result.get("calendar_session_count", 0),
        "analyzed_session_count": result.get("session_count", 0),
        "analyzed_session_dates": result.get("analyzed_session_dates", []),
        "analysis_status": result.get("analysis_status", "UNAVAILABLE"),
        "retrieval_status": result.get("retrieval_status", "UNAVAILABLE"),
        "pass_count": result.get("pass_count", 0),
        "review_count": result.get("review_count", 0),
        "blocked_count": result.get("blocked_count", 0),
        "unavailable_count": result.get("unavailable_count", 0),
        **reconciliation_summary,
        "note": (
            "A range evidence run. REVIEW is retained and is not promoted "
            "to PASS. This workflow validates the requested range and "
            "does not imply complete-universe coverage on REVIEW dates."
        ),
    }

    (output / "range_verification.json").write_text(
        json.dumps(report, indent=2, default=str),
        encoding="utf-8",
    )

    for key, filename in (
        ("per_date_status", "historical_ad_daily_metrics.csv"),
        ("coverage", "historical_ad_coverage.csv"),
        ("provenance", "historical_ad_provenance.csv"),
        ("retrieval_summary", "nse_retrieval_summary.csv"),
        ("reconciliation_details", "historical_ad_reconciliation_details.csv"),
    ):
        frame = result.get(key)
        if isinstance(frame, pd.DataFrame):
            frame.to_csv(output / filename, index=False)

    print(json.dumps(report, indent=2, default=str))

    if result.get("calendar_status") != "PASS":
        raise SystemExit("UNAVAILABLE: official NSE calendar could not be verified.")
    if result.get("analysis_status") in {"BLOCKED", "UNAVAILABLE"}:
        raise SystemExit(
            f"{result.get('analysis_status')}: historical range did not complete."
        )
    if result.get("analysis_status") == "REVIEW":
        print("REVIEW: range retrieved; incomplete dates remain REVIEW.")
    else:
        print("PASS: all analyzed dates passed available validation gates.")


if __name__ == "__main__":
    main()
