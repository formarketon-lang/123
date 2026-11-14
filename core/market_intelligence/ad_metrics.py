"""Historical daily A-D difference and A/D ratio metrics.

Consumes the output of classify_historical_daily_advance_decline. It does
not retrieve data or alter the upstream daily classification.
"""

from __future__ import annotations

from numbers import Integral
from typing import Any

import math
import pandas as pd


class AdvanceDeclineMetricsError(ValueError):
    """Raised when daily A/D counts cannot produce reliable metrics."""


_REQUIRED_COLUMNS = {
    "observation_date",
    "advancing",
    "declining",
    "unchanged",
    "verified_observations",
    "analysis_status",
}


def calculate_historical_ad_metrics(classification: dict[str, Any]) -> dict:
    """Calculate daily A-D difference and A/D ratio with explicit zero states.

    A/D ratio is undefined when declining == 0; it is returned as None with
    NO_DECLINERS or NO_ADVANCES_OR_DECLINES, never infinity or a capped value.
    A zero ratio is valid when advancing == 0 and declining > 0.
    REVIEW rows calculate metrics on their verified subset but retain REVIEW.
    BLOCKED and UNAVAILABLE rows never receive fabricated metrics.
    """
    if not isinstance(classification, dict):
        raise TypeError("classification must be a daily A/D classification result.")

    source = classification.get("summary")
    if not isinstance(source, pd.DataFrame) or source.empty:
        raise AdvanceDeclineMetricsError(
            "Classification summary must be a non-empty DataFrame."
        )
    missing_columns = _REQUIRED_COLUMNS.difference(source.columns)
    if missing_columns:
        raise AdvanceDeclineMetricsError(
            "Classification summary missing columns: "
            + ", ".join(sorted(missing_columns))
        )

    rows = []
    seen_dates = set()
    for _, item in source.iterrows():
        parsed = pd.to_datetime(item["observation_date"], errors="coerce")
        if pd.isna(parsed):
            raise AdvanceDeclineMetricsError("Every row requires a valid observation date.")
        day = pd.Timestamp(parsed).date().isoformat()
        if day in seen_dates:
            raise AdvanceDeclineMetricsError("Duplicate observation dates are not allowed.")
        seen_dates.add(day)

        status = str(item["analysis_status"]).strip().upper()
        if status not in {"PASS", "REVIEW", "BLOCKED", "UNAVAILABLE"}:
            raise AdvanceDeclineMetricsError(f"Unsupported analysis status for {day}.")

        base = {
            "observation_date": day,
            "advancing": None,
            "declining": None,
            "unchanged": None,
            "verified_observations": item["verified_observations"],
            "ad_difference": None,
            "ad_ratio": None,
            "ratio_status": "NOT_CALCULATED",
            "analysis_status": status,
        }
        if status in {"BLOCKED", "UNAVAILABLE"}:
            rows.append(base)
            continue

        counts = {}
        for field in ("advancing", "declining", "unchanged", "verified_observations"):
            value = item[field]
            if not isinstance(value, Integral) or isinstance(value, bool) or value < 0:
                raise AdvanceDeclineMetricsError(
                    f"{field} must be a non-negative integer for {day}."
                )
            counts[field] = int(value)

        if sum(counts[field] for field in ("advancing", "declining", "unchanged")) != counts["verified_observations"]:
            raise AdvanceDeclineMetricsError(
                f"Daily counts do not reconcile with verified observations for {day}."
            )

        advancing = counts["advancing"]
        declining = counts["declining"]
        difference = advancing - declining

        if declining > 0:
            ratio = advancing / declining
            if not math.isfinite(ratio):
                raise AdvanceDeclineMetricsError(f"Non-finite A/D ratio for {day}.")
            ratio_status = "NO_ADVANCERS" if advancing == 0 else "CALCULATED"
        else:
            ratio = None
            ratio_status = (
                "NO_ADVANCES_OR_DECLINES"
                if advancing == 0
                else "NO_DECLINERS"
            )

        base.update({
            "advancing": advancing,
            "declining": declining,
            "unchanged": counts["unchanged"],
            "ad_difference": difference,
            "ad_ratio": ratio,
            "ratio_status": ratio_status,
        })
        rows.append(base)

    rows.sort(key=lambda row: row["observation_date"])
    summary = pd.DataFrame(rows)
    statuses = summary["analysis_status"].tolist()
    if "BLOCKED" in statuses:
        overall = "BLOCKED"
    elif "UNAVAILABLE" in statuses:
        overall = "UNAVAILABLE"
    elif "REVIEW" in statuses:
        overall = "REVIEW"
    else:
        overall = "PASS"

    return {
        "analysis_status": overall,
        "date_count": len(summary),
        "pass_count": statuses.count("PASS"),
        "review_count": statuses.count("REVIEW"),
        "blocked_count": statuses.count("BLOCKED"),
        "unavailable_count": statuses.count("UNAVAILABLE"),
        "summary": summary,
    }
