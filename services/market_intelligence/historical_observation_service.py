"""Historical NSE observation retrieval using the accepted single-date service.

This module orchestrates one independently validated NSE CM/EQ Bhavcopy
per requested trade date. It does not invent historical MII membership,
reuse a current universe, or merge data across dates.
"""

from __future__ import annotations

from datetime import date
from typing import Iterable

import pandas as pd

from data.providers.nse_udiff_downloader import NSEUdiFFDownloadError
from services.market_intelligence.bhavcopy_service import (
    NSEBhavcopyServiceError,
    analyze_nse_market_breadth_from_udiff,
)


class NSEHistoricalObservationError(ValueError):
    """Raised when a historical retrieval request is malformed."""


def _normalize_observation_dates(values: Iterable[date | str]) -> list[date]:
    """Validate, de-duplicate-check and chronologically order trade dates."""

    if isinstance(values, (str, bytes)):
        raise NSEHistoricalObservationError(
            "Pass an iterable of dates, not one date string."
        )

    try:
        raw_dates = list(values)
    except TypeError as exc:
        raise NSEHistoricalObservationError(
            "Observation dates must be an iterable of date values."
        ) from exc

    if not raw_dates:
        raise NSEHistoricalObservationError(
            "At least one historical observation date is required."
        )

    parsed: list[date] = []
    for value in raw_dates:
        try:
            timestamp = pd.Timestamp(value)
        except (TypeError, ValueError, OverflowError) as exc:
            raise NSEHistoricalObservationError(
                f"Invalid observation date: {value!r}"
            ) from exc

        if pd.isna(timestamp):
            raise NSEHistoricalObservationError(
                f"Invalid observation date: {value!r}"
            )
        parsed.append(timestamp.date())

    if len(set(parsed)) != len(parsed):
        raise NSEHistoricalObservationError(
            "Duplicate observation dates are not allowed."
        )

    return sorted(parsed)


def retrieve_nse_historical_observations(
    observation_dates: Iterable[date | str],
    *,
    session=None,
) -> dict:
    """Retrieve independently verified NSE observations for each date.

    Each date is passed to the existing production single-date service.
    A failed date is retained as UNAVAILABLE and does not prevent later
    requested dates from being attempted. No date's universe or prices
    are carried forward/backward to another date.

    The returned per-date result retains source URL, archive filename,
    SHA-256, actual fetch timestamp, dated MII snapshot date, identity
    reconciliation and verified/unverified observations.
    """

    dates = _normalize_observation_dates(observation_dates)
    results: list[dict] = []
    verified_frames: list[pd.DataFrame] = []

    for observation_date in dates:
        date_key = observation_date.isoformat()
        try:
            result = analyze_nse_market_breadth_from_udiff(
                observation_date,
                session=session,
            )
        except (
            NSEBhavcopyServiceError,
            NSEUdiFFDownloadError,
            RuntimeError,
        ) as exc:
            results.append({
                "observation_date": date_key,
                "status": "UNAVAILABLE",
                "error_type": type(exc).__name__,
                "error": str(exc),
                "source": None,
                "source_url": None,
                "source_filename": None,
                "source_sha256": None,
                "fetched_at_utc": None,
                "mii_snapshot_date": None,
                "expected_symbols": None,
                "verified_symbols": 0,
                "missing_count": None,
                "identity_exception_count": None,
                "coverage_pct": None,
                "verified_observations": pd.DataFrame(),
                "unverified_observations": pd.DataFrame(),
                "result": None,
            })
            continue

        reconciliation = result["reconciliation"]
        verified = result["verified_observations"].copy()
        unverified = result["unverified_observations"].copy()

        if not verified.empty:
            verified_frames.append(verified)

        results.append({
            "observation_date": date_key,
            "status": result["analysis_status"],
            "error_type": None,
            "error": None,
            "source": result["source"],
            "source_url": result["source_url"],
            "source_filename": result["source_filename"],
            "source_sha256": result["source_sha256"],
            "fetched_at_utc": result["fetched_at_utc"],
            "mii_snapshot_date": reconciliation["mii_snapshot_date"],
            "expected_symbols": reconciliation["expected_symbols"],
            "verified_symbols": reconciliation["observed_symbols"],
            "missing_count": reconciliation["missing_count"],
            "identity_exception_count": len(
                reconciliation["identity_exceptions"]
            ),
            "coverage_pct": reconciliation["coverage_pct"],
            "verified_observations": verified,
            "unverified_observations": unverified,
            "result": result,
        })

    statuses = [item["status"] for item in results]
    if any(status == "BLOCKED" for status in statuses):
        overall_status = "BLOCKED"
    elif any(status == "UNAVAILABLE" for status in statuses):
        overall_status = "UNAVAILABLE"
    elif any(status == "REVIEW" for status in statuses):
        overall_status = "REVIEW"
    else:
        overall_status = "PASS"

    observations = (
        pd.concat(verified_frames, ignore_index=True)
        if verified_frames
        else pd.DataFrame()
    )

    if not observations.empty:
        observations = observations.sort_values(
            ["Date", "Symbol"]
        ).reset_index(drop=True)

    summary = pd.DataFrame([
        {
            key: item[key]
            for key in (
                "observation_date",
                "status",
                "source",
                "source_url",
                "source_filename",
                "source_sha256",
                "fetched_at_utc",
                "mii_snapshot_date",
                "expected_symbols",
                "verified_symbols",
                "missing_count",
                "identity_exception_count",
                "coverage_pct",
                "error_type",
                "error",
            )
        }
        for item in results
    ])

    return {
        "analysis_status": overall_status,
        "requested_dates": [value.isoformat() for value in dates],
        "date_count": len(dates),
        "pass_count": statuses.count("PASS"),
        "review_count": statuses.count("REVIEW"),
        "unavailable_count": statuses.count("UNAVAILABLE"),
        "blocked_count": statuses.count("BLOCKED"),
        "per_date": results,
        "summary": summary,
        "verified_observations": observations,
    }
