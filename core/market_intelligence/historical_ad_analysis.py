"""Pure orchestration for historical NSE Advance / Decline analysis.

No network, provider, or Streamlit imports are permitted in this module.
It composes the established daily classifier and the Chapter 02 metric
calculators, while retaining per-date coverage and source provenance.
"""

from __future__ import annotations

from typing import Any, Iterable

import pandas as pd

from core.market_intelligence.advance_decline import (
    classify_historical_daily_advance_decline,
)
from core.market_intelligence.ad_metrics import calculate_historical_ad_metrics
from core.market_intelligence.cumulative_ad_line import calculate_cumulative_ad_line


class HistoricalADAnalysisError(ValueError):
    """Raised when historical A/D orchestration inputs are inconsistent."""


_PROVENANCE_FIELDS = (
    "source",
    "source_url",
    "source_filename",
    "source_sha256",
    "fetched_at_utc",
    "mii_snapshot_date",
)


def _date_key(value: Any) -> str:
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        raise HistoricalADAnalysisError("Every source record requires a valid observation date.")
    return pd.Timestamp(parsed).date().isoformat()


def analyze_historical_advance_decline(
    history: dict[str, Any],
    expected_sessions: Iterable[Any],
    initial_anchor: int = 0,
) -> dict:
    """Return daily A/D metrics, cumulative line, coverage and provenance.

    expected_sessions must be the caller's verified NSE trading-session
    calendar. Missing expected dates are represented explicitly and break
    the cumulative segment; no calendar or market data is fetched here.
    """
    if not isinstance(history, dict):
        raise TypeError("history must be a historical NSE observation result.")

    per_date = history.get("per_date")
    if not isinstance(per_date, list) or not per_date:
        raise HistoricalADAnalysisError("history must contain per-date source records.")

    provenance_by_date = {}
    for item in per_date:
        if not isinstance(item, dict):
            raise HistoricalADAnalysisError("Every source record must be a mapping.")
        day = _date_key(item.get("observation_date"))
        if day in provenance_by_date:
            raise HistoricalADAnalysisError("Duplicate source observation dates are not allowed.")
        provenance_by_date[day] = {
            "observation_date": day,
            **{field: item.get(field) for field in _PROVENANCE_FIELDS},
            "mii_snapshot_date": item.get("mii_snapshot_date"),
            "source_status": str(item.get("status") or "").strip().upper(),
            "expected_symbols": item.get("expected_symbols"),
            "verified_symbols": item.get("verified_symbols"),
            "missing_count": item.get("missing_count"),
            "identity_exception_count": item.get("identity_exception_count"),
            "coverage_pct": item.get("coverage_pct"),
            "error_type": item.get("error_type"),
            "error": item.get("error"),
        }

    daily = classify_historical_daily_advance_decline(history)
    metrics = calculate_historical_ad_metrics(daily)
    cumulative = calculate_cumulative_ad_line(
        metrics,
        expected_sessions=expected_sessions,
        initial_anchor=initial_anchor,
    )

    daily_by_date = {
        row["observation_date"]: row
        for row in daily["summary"].to_dict(orient="records")
    }
    metric_by_date = {
        row["observation_date"]: row
        for row in metrics["summary"].to_dict(orient="records")
    }
    cumulative_rows = cumulative["summary"].to_dict(orient="records")

    combined = []
    for line in cumulative_rows:
        day = line["observation_date"]
        daily_row = daily_by_date.get(day, {})
        metric_row = metric_by_date.get(day, {})
        source_row = provenance_by_date.get(day, {})
        combined.append({
            "observation_date": day,
            "analysis_status": line["analysis_status"],
            "advancing": daily_row.get("advancing"),
            "declining": daily_row.get("declining"),
            "unchanged": daily_row.get("unchanged"),
            "missing": daily_row.get("missing"),
            "identity_exceptions": daily_row.get("identity_exceptions"),
            "verified_observations": daily_row.get("verified_observations"),
            "expected_universe": daily_row.get("expected_universe"),
            "coverage_pct": daily_row.get("coverage_pct"),
            "ad_difference": metric_row.get("ad_difference"),
            "ad_ratio": metric_row.get("ad_ratio"),
            "ratio_status": metric_row.get("ratio_status", "NOT_CALCULATED"),
            "cumulative_ad": line["cumulative_ad"],
            "cumulative_segment_id": line["segment_id"],
            **{field: source_row.get(field) for field in _PROVENANCE_FIELDS},
            "mii_snapshot_date": source_row.get("mii_snapshot_date"),
            "source_status": source_row.get("source_status"),
            "reason": daily_row.get("reason") or source_row.get("error"),
        })

    per_date_status = pd.DataFrame(combined)
    statuses = per_date_status["analysis_status"].tolist()
    if "BLOCKED" in statuses:
        overall = "BLOCKED"
    elif "UNAVAILABLE" in statuses:
        overall = "UNAVAILABLE"
    elif "REVIEW" in statuses or "MISSING" in statuses:
        overall = "REVIEW"
    else:
        overall = "PASS"

    provenance = pd.DataFrame([
        provenance_by_date.get(
            row["observation_date"],
            {
                "observation_date": row["observation_date"],
                **{field: None for field in _PROVENANCE_FIELDS},
                "mii_snapshot_date": None,
                "source_status": "MISSING",
                "expected_symbols": None,
                "verified_symbols": None,
                "missing_count": None,
                "identity_exception_count": None,
                "coverage_pct": None,
                "error_type": None,
                "error": None,
            },
        )
        for row in cumulative_rows
    ])

    return {
        "analysis_status": overall,
        "date_count": len(per_date_status),
        "pass_count": statuses.count("PASS"),
        "review_count": statuses.count("REVIEW"),
        "blocked_count": statuses.count("BLOCKED"),
        "unavailable_count": statuses.count("UNAVAILABLE"),
        "missing_count": statuses.count("MISSING"),
        "daily_classification": daily,
        "daily_metrics": metrics,
        "cumulative_line": cumulative,
        "per_date_status": per_date_status,
        "coverage": per_date_status[[
            "observation_date",
            "expected_universe",
            "verified_observations",
            "missing",
            "identity_exceptions",
            "coverage_pct",
            "analysis_status",
        ]].copy(),
        "provenance": provenance,
    }
