"""Service orchestration for historical NSE Advance / Decline analysis.

This layer composes the existing historical observation retriever with the
pure Chapter 02 core. It does not add a downloader, calendar provider or UI.
"""

from __future__ import annotations

from typing import Any, Iterable

import pandas as pd

from core.market_intelligence.historical_ad_analysis import (
    analyze_historical_advance_decline,
)
from services.market_intelligence.historical_observation_service import (
    retrieve_nse_historical_observations,
)

from data.providers.nse_trading_calendar import (
    NSETradingCalendarError,
    discover_nse_cm_trading_sessions,
)


class HistoricalADServiceError(ValueError):
    """Raised when the historical A/D service request is invalid."""


def analyze_nse_historical_advance_decline(
    expected_sessions: Iterable[Any],
    *,
    initial_anchor: int = 0,
    session=None,
) -> dict:
    """Retrieve and analyze the caller-supplied verified NSE trading sessions.

    The session calendar is supplied by the caller. Each session is retrieved
    independently through the existing historical NSE observation service.
    Per-date failures remain represented in the result and are not replaced
    with Yahoo data or carried observations.
    """
    if isinstance(expected_sessions, (str, bytes)):
        raise HistoricalADServiceError(
            "Pass an iterable of verified NSE sessions, not one date string."
        )
    try:
        sessions = list(expected_sessions)
    except TypeError as exc:
        raise HistoricalADServiceError(
            "Verified NSE sessions must be iterable."
        ) from exc
    if not sessions:
        raise HistoricalADServiceError(
            "At least one verified NSE session is required."
        )

    history = retrieve_nse_historical_observations(
        sessions,
        session=session,
    )
    normalized_sessions = history.get("requested_dates")
    if not isinstance(normalized_sessions, list) or not normalized_sessions:
        raise HistoricalADServiceError(
            "Historical retriever did not return normalized requested dates."
        )

    analysis = analyze_historical_advance_decline(
        history,
        expected_sessions=normalized_sessions,
        initial_anchor=initial_anchor,
    )

    return {
        **analysis,
        "retrieval_status": history["analysis_status"],
        "retrieval_summary": history["summary"],
        "requested_sessions": history["requested_dates"],
        "source_observation_count": history["date_count"],
    }


def analyze_nse_historical_advance_decline_for_range(
    start_date,
    end_date,
    *,
    initial_anchor: int = 0,
    max_sessions: int = 180,
    session=None,
) -> dict:
    """Discover official NSE CM sessions and analyze the bounded date range.

    Regular sessions come from the official NSE CM holiday master. Weekend
    and holiday exceptions are included only when an official final UDiFF
    archive is successfully downloaded and validated.
    """
    if (
        not isinstance(max_sessions, int)
        or isinstance(max_sessions, bool)
        or max_sessions < 1
    ):
        raise HistoricalADServiceError(
            "max_sessions must be a positive integer."
        )

    try:
        calendar = discover_nse_cm_trading_sessions(
            start_date,
            end_date,
            session=session,
        )
    except NSETradingCalendarError as exc:
        return {
            "analysis_status": "UNAVAILABLE",
            "retrieval_status": "UNAVAILABLE",
            "calendar_status": "UNAVAILABLE",
            "calendar_provenance": {
                "calendar_status": "UNAVAILABLE",
                "error_type": type(exc).__name__,
                "error": str(exc),
            },
            "date_count": 0,
            "pass_count": 0,
            "review_count": 0,
            "blocked_count": 0,
            "unavailable_count": 0,
            "missing_count": 0,
            "per_date_status": pd.DataFrame(),
            "coverage": pd.DataFrame(),
            "provenance": pd.DataFrame(),
            "retrieval_summary": pd.DataFrame(),
        }
    if calendar["calendar_status"] != "PASS":
        return {
            "analysis_status": "UNAVAILABLE",
            "retrieval_status": "UNAVAILABLE",
            "calendar_status": calendar["calendar_status"],
            "calendar_provenance": calendar,
            "date_count": 0,
            "pass_count": 0,
            "review_count": 0,
            "blocked_count": 0,
            "unavailable_count": 0,
            "missing_count": 0,
            "per_date_status": pd.DataFrame(),
            "coverage": pd.DataFrame(),
            "provenance": pd.DataFrame(),
            "retrieval_summary": pd.DataFrame(),
        }

    if not calendar["session_dates"]:
        return {
            "analysis_status": "UNAVAILABLE",
            "retrieval_status": "UNAVAILABLE",
            "calendar_status": "PASS",
            "calendar_provenance": calendar,
            "date_count": 0,
            "pass_count": 0,
            "review_count": 0,
            "blocked_count": 0,
            "unavailable_count": 0,
            "missing_count": 0,
            "per_date_status": pd.DataFrame(),
            "coverage": pd.DataFrame(),
            "provenance": pd.DataFrame(),
            "retrieval_summary": pd.DataFrame(),
        }

    selected_sessions = calendar["session_dates"][-max_sessions:]
    result = analyze_nse_historical_advance_decline(
        selected_sessions,
        initial_anchor=initial_anchor,
        session=session,
    )
    return {
        **result,
        "calendar_status": calendar["calendar_status"],
        "calendar_provenance": calendar,
        "session_count": len(selected_sessions),
        "calendar_session_count": len(calendar["session_dates"]),
        "analyzed_session_dates": selected_sessions,
    }
