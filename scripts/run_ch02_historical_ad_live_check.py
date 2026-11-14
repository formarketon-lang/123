"""Live Chapter 02 historical NSE A/D verification.

Checks the most recent available official NSE CM/EQ session in a bounded
lookback window. A source REVIEW remains REVIEW; it is never promoted to PASS.
"""

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
    analyze_nse_historical_advance_decline,
)


def main() -> None:
    output = Path("artifacts/ch02_historical_ad_live")
    output.mkdir(parents=True, exist_ok=True)

    today = datetime.now(ZoneInfo("Asia/Kolkata")).date()
    attempts = []
    selected = None
    result = None

    # Weekdays are only candidate dates. The official NSE source response
    # determines availability; this script does not assume weekday=trading day.
    for offset in range(1, 11):
        candidate = today - timedelta(days=offset)
        if candidate.weekday() >= 5:
            continue
        try:
            candidate_result = analyze_nse_historical_advance_decline(
                [candidate],
                initial_anchor=0,
            )
        except Exception as exc:
            attempts.append({
                "candidate_date": candidate.isoformat(),
                "status": "ERROR",
                "error_type": type(exc).__name__,
                "error": str(exc),
            })
            continue

        status = candidate_result.get("analysis_status", "UNAVAILABLE")
        attempts.append({
            "candidate_date": candidate.isoformat(),
            "status": status,
            "retrieval_status": candidate_result.get("retrieval_status"),
        })
        if status != "UNAVAILABLE":
            selected = candidate
            result = candidate_result
            break

    report = {
        "project": "TLP-MIM-001",
        "chapter": "02",
        "verification": "HISTORICAL_NSE_AD_LIVE_SMOKE_TEST",
        "generated_at_utc": datetime.now(ZoneInfo("UTC")).isoformat(),
        "candidate_attempts": attempts,
        "selected_observation_date": selected.isoformat() if selected else None,
        "analysis_status": result.get("analysis_status") if result else "UNAVAILABLE",
        "retrieval_status": result.get("retrieval_status") if result else "UNAVAILABLE",
        "date_count": result.get("date_count", 0) if result else 0,
        "pass_count": result.get("pass_count", 0) if result else 0,
        "review_count": result.get("review_count", 0) if result else 0,
        "blocked_count": result.get("blocked_count", 0) if result else 0,
        "unavailable_count": result.get("unavailable_count", 0) if result else 0,
        "missing_count": result.get("missing_count", 0) if result else 0,
        "note": (
            "A one-session live smoke test only; not a multi-month historical "
            "range validation. REVIEW is retained as REVIEW."
        ),
    }
    (output / "live_verification.json").write_text(
        json.dumps(report, indent=2, default=str),
        encoding="utf-8",
    )

    if result is not None:
        result["per_date_status"].to_csv(
            output / "historical_ad_daily_metrics.csv", index=False
        )
        result["coverage"].to_csv(
            output / "historical_ad_coverage.csv", index=False
        )
        result["provenance"].to_csv(
            output / "historical_ad_provenance.csv", index=False
        )
        result["retrieval_summary"].to_csv(
            output / "nse_retrieval_summary.csv", index=False
        )

    print(json.dumps(report, indent=2, default=str))
    if result is None:
        raise SystemExit(
            "UNAVAILABLE: no usable official NSE historical observation "
            "was retrieved in the bounded lookback window."
        )
    if result["analysis_status"] == "BLOCKED":
        raise SystemExit("BLOCKED: contradictory NSE source/identity evidence.")
    # REVIEW is an auditable outcome, not a false CI success claim. The report
    # explicitly records it and the workflow artifact preserves all evidence.
    if result["analysis_status"] == "REVIEW":
        print("REVIEW: live data is incomplete; no verified full-universe claim.")
    else:
        print("PASS: selected live NSE observation passed available gates.")


if __name__ == "__main__":
    main()
