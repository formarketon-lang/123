"""Cumulative A-D Line from verified daily A-D metrics.

A verified NSE trading-session calendar is mandatory. Any missing or
non-PASS session breaks the cumulative segment; later PASS sessions start
a new segment from the configured initial anchor.
"""

from __future__ import annotations

from numbers import Integral, Real
import math
from typing import Any, Iterable

import pandas as pd


class CumulativeADLineError(ValueError):
    """Raised when cumulative A-D inputs are incomplete or inconsistent."""


_REQUIRED_COLUMNS = {"observation_date", "ad_difference", "analysis_status"}


def _session_date(value: Any) -> str:
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        raise CumulativeADLineError("Every expected session must have a valid date.")
    return pd.Timestamp(parsed).date().isoformat()


def calculate_cumulative_ad_line(
    metrics: dict[str, Any],
    expected_sessions: Iterable[Any],
    initial_anchor: int = 0,
) -> dict:
    """Build a deterministic cumulative A-D series over verified NSE sessions.

    Only PASS sessions contribute to the cumulative line. REVIEW, BLOCKED,
    UNAVAILABLE or missing expected sessions emit a null cumulative value and
    break the segment. The next PASS session starts a new segment at
    initial_anchor + that day's A-D difference. No implicit calendar inference.
    """
    if not isinstance(metrics, dict):
        raise TypeError("metrics must be the daily A-D metrics result.")
    if not isinstance(initial_anchor, Integral) or isinstance(initial_anchor, bool):
        raise CumulativeADLineError("initial_anchor must be an integer.")

    if isinstance(expected_sessions, (str, bytes)):
        raise CumulativeADLineError("expected_sessions must be a sequence of verified sessions.")
    try:
        sessions = [_session_date(value) for value in expected_sessions]
    except TypeError as exc:
        raise CumulativeADLineError("expected_sessions must be iterable.") from exc
    if not sessions:
        raise CumulativeADLineError("At least one verified expected session is required.")
    if len(set(sessions)) != len(sessions):
        raise CumulativeADLineError("Expected session dates must be unique.")
    if sessions != sorted(sessions):
        raise CumulativeADLineError("Expected session dates must be chronological.")

    source = metrics.get("summary")
    if not isinstance(source, pd.DataFrame) or source.empty:
        raise CumulativeADLineError("Metrics summary must be a non-empty DataFrame.")
    missing_columns = _REQUIRED_COLUMNS.difference(source.columns)
    if missing_columns:
        raise CumulativeADLineError(
            "Metrics summary missing columns: " + ", ".join(sorted(missing_columns))
        )

    by_date = {}
    for _, item in source.iterrows():
        day = _session_date(item["observation_date"])
        if day in by_date:
            raise CumulativeADLineError("Duplicate metrics dates are not allowed.")
        if day not in set(sessions):
            raise CumulativeADLineError(
                f"Metrics date {day} is not in the verified expected-session calendar."
            )
        by_date[day] = item

    output = []
    running = int(initial_anchor)
    segment_id = 0
    segment_active = False

    for day in sessions:
        item = by_date.get(day)
        if item is None:
            output.append({
                "observation_date": day,
                "ad_difference": None,
                "cumulative_ad": None,
                "segment_id": None,
                "analysis_status": "MISSING",
            })
            segment_active = False
            continue

        status = str(item["analysis_status"]).strip().upper()
        if status not in {"PASS", "REVIEW", "BLOCKED", "UNAVAILABLE"}:
            raise CumulativeADLineError(f"Unsupported analysis status for {day}.")

        if status != "PASS":
            output.append({
                "observation_date": day,
                "ad_difference": None,
                "cumulative_ad": None,
                "segment_id": None,
                "analysis_status": status,
            })
            segment_active = False
            continue

        difference = item["ad_difference"]
        if (
            isinstance(difference, bool)
            or not isinstance(difference, Real)
            or not math.isfinite(float(difference))
            or not float(difference).is_integer()
        ):
            raise CumulativeADLineError(
                f"PASS session requires an integer A-D difference for {day}."
            )
        if not segment_active:
            segment_id += 1
            running = int(initial_anchor)
            segment_active = True
        running += int(difference)
        output.append({
            "observation_date": day,
            "ad_difference": int(difference),
            "cumulative_ad": running,
            "segment_id": segment_id,
            "analysis_status": "PASS",
        })

    summary = pd.DataFrame(output)
    statuses = summary["analysis_status"].tolist()
    overall = (
        "BLOCKED" if "BLOCKED" in statuses
        else "UNAVAILABLE" if "UNAVAILABLE" in statuses
        else "REVIEW" if "REVIEW" in statuses
        else "REVIEW" if "MISSING" in statuses
        else "PASS"
    )
    return {
        "analysis_status": overall,
        "date_count": len(summary),
        "pass_count": statuses.count("PASS"),
        "review_count": statuses.count("REVIEW"),
        "blocked_count": statuses.count("BLOCKED"),
        "unavailable_count": statuses.count("UNAVAILABLE"),
        "missing_count": statuses.count("MISSING"),
        "segment_count": segment_id,
        "initial_anchor": int(initial_anchor),
        "reset_policy": "RESET_AFTER_NON_PASS_OR_MISSING_SESSION",
        "summary": summary,
    }
