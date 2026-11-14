"""Live official NSE calendar-backed historical A/D smoke verification."""

from __future__ import annotations

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


def main() -> None:
    today = datetime.now(ZoneInfo("Asia/Kolkata")).date()
    end_date = today - timedelta(days=1)
    start_date = end_date - timedelta(days=29)

    output = Path("artifacts/ch02_historical_ad_live")
    output.mkdir(parents=True, exist_ok=True)

    result = analyze_nse_historical_advance_decline_for_range(
        start_date,
        end_date,
        max_sessions=10,
        initial_anchor=0,
    )
    calendar = result.get("calendar_provenance", {})

    report = {
        "project": "TLP-MIM-001",
        "chapter": "02",
        "verification": "OFFICIAL_NSE_CALENDAR_BACKED_HISTORICAL_AD_SMOKE_TEST",
        "generated_at_utc": datetime.now(ZoneInfo("UTC")).isoformat(),
        "requested_range": {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "calendar_days": 30,
            "max_sessions": 10,
        },
        "calendar_status": result.get("calendar_status", "UNAVAILABLE"),
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
        "missing_count": result.get("missing_count", 0),
        "note": (
            "Calendar comes from the official NSE CM holiday master. "
            "Weekend/holiday exceptions require a validated official UDiFF "
            "archive. REVIEW is preserved and never promoted to PASS."
        ),
    }

    (output / "live_verification.json").write_text(
        json.dumps(report, indent=2, default=str),
        encoding="utf-8",
    )

    for key, filename in (
        ("per_date_status", "historical_ad_daily_metrics.csv"),
        ("coverage", "historical_ad_coverage.csv"),
        ("provenance", "historical_ad_provenance.csv"),
        ("retrieval_summary", "nse_retrieval_summary.csv"),
    ):
        frame = result.get(key)
        if isinstance(frame, pd.DataFrame):
            frame.to_csv(output / filename, index=False)

    print(json.dumps(report, indent=2, default=str))

    if result.get("calendar_status") != "PASS":
        raise SystemExit("UNAVAILABLE: official NSE calendar could not be verified.")
    if result.get("analysis_status") in {"BLOCKED", "UNAVAILABLE"}:
        raise SystemExit(
            f"{result.get('analysis_status')}: NSE historical A/D smoke test failed."
        )
    if result.get("analysis_status") == "REVIEW":
        print("REVIEW: official NSE data is incomplete; no full-universe PASS claim.")
    else:
        print("PASS: all analyzed sessions passed available validation gates.")


if __name__ == "__main__":
    main()
