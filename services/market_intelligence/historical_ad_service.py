"""Service orchestration for historical NSE Advance / Decline analysis.

This layer composes the existing historical observation retriever with the
pure Chapter 02 core. It does not add a downloader, calendar provider or UI.
"""

from __future__ import annotations

from typing import Any, Iterable

from core.market_intelligence.historical_ad_analysis import (
    analyze_historical_advance_decline,
)
from services.market_intelligence.historical_observation_service import (
    retrieve_nse_historical_observations,
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
