"""Historical daily Advance / Decline classification.

Reuses the established Market Breadth classifier. Missing observations are
reported separately and are never counted as unchanged.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from core.market_intelligence.breadth import analyze_market_breadth


class AdvanceDeclineClassificationError(ValueError):
    """Raised when historical A/D inputs violate the daily contract."""


def classify_historical_daily_advance_decline(history: dict[str, Any]) -> dict:
    """Classify each retrieved NSE session using verified observations only.

    The input is the result of retrieve_nse_historical_observations().
    REVIEW dates may expose counts for their verified subset, but remain
    REVIEW. UNAVAILABLE/BLOCKED dates never receive fabricated counts.
    """
    if not isinstance(history, dict):
        raise TypeError("history must be a historical observation result.")

    per_date = history.get("per_date")
    if not isinstance(per_date, list) or not per_date:
        raise AdvanceDeclineClassificationError(
            "Historical result must contain at least one per-date record."
        )

    rows = []
    seen_dates = set()

    for item in per_date:
        if not isinstance(item, dict):
            raise AdvanceDeclineClassificationError(
                "Every per-date record must be a mapping."
            )

        day = pd.to_datetime(item.get("observation_date"), errors="coerce")
        if pd.isna(day):
            raise AdvanceDeclineClassificationError(
                "Every per-date record requires a valid observation date."
            )
        day_key = pd.Timestamp(day).date().isoformat()
        if day_key in seen_dates:
            raise AdvanceDeclineClassificationError(
                "Duplicate observation dates are not allowed."
            )
        seen_dates.add(day_key)

        status = str(item.get("status") or "").strip().upper()
        if status not in {"PASS", "REVIEW", "BLOCKED", "UNAVAILABLE"}:
            raise AdvanceDeclineClassificationError(
                f"Unsupported observation status for {day_key}."
            )

        expected = item.get("expected_symbols")
        verified = item.get("verified_symbols")
        missing = item.get("missing_count")
        exceptions = item.get("identity_exception_count")

        if status == "UNAVAILABLE":
            rows.append({
                "observation_date": day_key,
                "advancing": None,
                "declining": None,
                "unchanged": None,
                "missing": None,
                "identity_exceptions": None,
                "verified_observations": None,
                "expected_universe": None,
                "coverage_pct": None,
                "analysis_status": "UNAVAILABLE",
                "reason": item.get("error") or "NSE_OBSERVATION_UNAVAILABLE",
            })
            continue

        if status == "BLOCKED":
            rows.append({
                "observation_date": day_key,
                "advancing": None,
                "declining": None,
                "unchanged": None,
                "missing": missing,
                "identity_exceptions": exceptions,
                "verified_observations": verified,
                "expected_universe": expected,
                "coverage_pct": item.get("coverage_pct"),
                "analysis_status": "BLOCKED",
                "reason": "SOURCE_OR_IDENTITY_VALIDATION_BLOCKED",
            })
            continue

        for label, value in (
            ("expected_symbols", expected),
            ("verified_symbols", verified),
            ("missing_count", missing),
            ("identity_exception_count", exceptions),
        ):
            if (
                not isinstance(value, int)
                or isinstance(value, bool)
                or value < 0
            ):
                raise AdvanceDeclineClassificationError(
                    f"{label} must be a non-negative integer for {day_key}."
                )

        if (
            expected < 1
            or verified > expected
            or missing > expected
            or verified + missing != expected
        ):
            raise AdvanceDeclineClassificationError(
                f"Universe counts are inconsistent for {day_key}."
            )

        observations = item.get("verified_observations")
        if not isinstance(observations, pd.DataFrame):
            raise AdvanceDeclineClassificationError(
                f"Verified observations must be a DataFrame for {day_key}."
            )
        if len(observations) != verified:
            raise AdvanceDeclineClassificationError(
                f"Verified observation count mismatch for {day_key}."
            )
        if "Date" not in observations.columns:
            raise AdvanceDeclineClassificationError(
                f"Verified observations require a Date column for {day_key}."
            )
        observed_dates = pd.to_datetime(
            observations["Date"],
            errors="coerce",
        )
        if observed_dates.isna().any() or not observed_dates.dt.normalize().eq(
            pd.Timestamp(day_key)
        ).all():
            raise AdvanceDeclineClassificationError(
                f"Verified observations contain a mismatched date for {day_key}."
            )

        if observations.empty:
            advancing = declining = unchanged = 0
        else:
            metrics = analyze_market_breadth(
                stock_data=observations,
                expected_universe_size=expected,
            )
            advancing = metrics["advancing"]
            declining = metrics["declining"]
            unchanged = metrics["unchanged"]

        if advancing + declining + unchanged != verified:
            raise AdvanceDeclineClassificationError(
                f"Daily classification does not reconcile for {day_key}."
            )

        coverage = float(item.get("coverage_pct")) if item.get("coverage_pct") is not None else None
        expected_coverage = (verified / expected) * 100.0
        if (
            coverage is None
            or not pd.notna(coverage)
            or not 0 <= coverage <= 100
            or abs(coverage - expected_coverage) > 1e-6
        ):
            raise AdvanceDeclineClassificationError(
                f"Coverage percentage is invalid or inconsistent for {day_key}."
            )

        final_status = (
            "PASS"
            if status == "PASS"
            and missing == 0
            and exceptions == 0
            and verified == expected
            and coverage == 100.0
            else "REVIEW"
        )

        rows.append({
            "observation_date": day_key,
            "advancing": advancing,
            "declining": declining,
            "unchanged": unchanged,
            "missing": missing,
            "identity_exceptions": exceptions,
            "verified_observations": verified,
            "expected_universe": expected,
            "coverage_pct": coverage,
            "analysis_status": final_status,
            "reason": None if final_status == "PASS" else "INCOMPLETE_OR_REVIEW_SOURCE_COVERAGE",
        })

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
