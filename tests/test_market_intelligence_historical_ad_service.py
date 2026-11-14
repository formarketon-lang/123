"""Tests for the historical NSE A/D service orchestration."""

import pandas as pd
import pytest

import services.market_intelligence.historical_ad_service as service


def fake_history():
    return {
        "analysis_status": "PASS",
        "requested_dates": ["2026-11-12", "2026-11-13"],
        "date_count": 2,
        "summary": pd.DataFrame([
            {"observation_date": "2026-11-12", "status": "PASS", "source_sha256": "a" * 64},
            {"observation_date": "2026-11-13", "status": "PASS", "source_sha256": "b" * 64},
        ]),
        "per_date": [],
    }


def fake_analysis():
    return {
        "analysis_status": "PASS",
        "date_count": 2,
        "per_date_status": pd.DataFrame(),
        "coverage": pd.DataFrame(),
        "provenance": pd.DataFrame(),
    }


def test_service_reuses_existing_retriever_and_core(monkeypatch):
    calls = {}
    history = fake_history()
    analysis = fake_analysis()

    def retrieve(dates, *, session=None):
        calls["dates"] = dates
        calls["session"] = session
        return history

    def analyze(received, *, expected_sessions, initial_anchor):
        calls["history"] = received
        calls["expected_sessions"] = expected_sessions
        calls["initial_anchor"] = initial_anchor
        return analysis

    monkeypatch.setattr(service, "retrieve_nse_historical_observations", retrieve)
    monkeypatch.setattr(service, "analyze_historical_advance_decline", analyze)

    session = object()
    dates = ["2026-11-12", "2026-11-13"]
    result = service.analyze_nse_historical_advance_decline(
        dates,
        initial_anchor=25,
        session=session,
    )

    assert calls["dates"] == dates
    assert calls["expected_sessions"] == dates
    assert calls["history"] is history
    assert calls["initial_anchor"] == 25
    assert calls["session"] is session
    assert result["analysis_status"] == "PASS"
    assert result["retrieval_status"] == "PASS"
    assert result["retrieval_summary"] is history["summary"]
    assert result["requested_sessions"] == dates
    assert result["source_observation_count"] == 2


def test_service_preserves_unavailable_retrieval_status(monkeypatch):
    history = fake_history()
    history["analysis_status"] = "UNAVAILABLE"
    history["requested_dates"] = ["2026-11-12"]
    history["date_count"] = 1
    monkeypatch.setattr(
        service, "retrieve_nse_historical_observations",
        lambda dates, session=None: history,
    )
    monkeypatch.setattr(
        service, "analyze_historical_advance_decline",
        lambda *args, **kwargs: {**fake_analysis(), "analysis_status": "UNAVAILABLE"},
    )
    result = service.analyze_nse_historical_advance_decline(["2026-11-12"])
    assert result["analysis_status"] == "UNAVAILABLE"
    assert result["retrieval_status"] == "UNAVAILABLE"


def test_service_propagates_retrieval_failures(monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("retrieval contract failure")
    monkeypatch.setattr(service, "retrieve_nse_historical_observations", fail)
    with pytest.raises(RuntimeError, match="retrieval contract failure"):
        service.analyze_nse_historical_advance_decline(["2026-11-12"])


def test_service_rejects_single_date_string():
    with pytest.raises(service.HistoricalADServiceError, match="not one date string"):
        service.analyze_nse_historical_advance_decline("2026-11-12")


@pytest.mark.parametrize("value", [None, 123])
def test_service_rejects_non_iterable_sessions(value):
    with pytest.raises(service.HistoricalADServiceError, match="iterable"):
        service.analyze_nse_historical_advance_decline(value)


def test_service_rejects_empty_session_list():
    with pytest.raises(service.HistoricalADServiceError, match="At least one"):
        service.analyze_nse_historical_advance_decline([])


def test_service_does_not_call_retriever_for_invalid_request(monkeypatch):
    called = {"value": False}
    def retrieve(*args, **kwargs):
        called["value"] = True
        return fake_history()
    monkeypatch.setattr(service, "retrieve_nse_historical_observations", retrieve)
    with pytest.raises(service.HistoricalADServiceError):
        service.analyze_nse_historical_advance_decline("")
    assert called["value"] is False


def test_service_preserves_caller_session_order_input_before_retriever(monkeypatch):
    calls = {}
    dates = ["2026-11-13", "2026-11-12"]
    def retrieve(received, session=None):
        calls["dates"] = received
        return fake_history()
    monkeypatch.setattr(service, "retrieve_nse_historical_observations", retrieve)
    def analyze(received, *, expected_sessions, initial_anchor):
        calls["core_sessions"] = expected_sessions
        return fake_analysis()
    monkeypatch.setattr(
        service, "analyze_historical_advance_decline", analyze,
    )
    service.analyze_nse_historical_advance_decline(dates)
    assert calls["dates"] == dates
    assert calls["core_sessions"] == ["2026-11-12", "2026-11-13"]


def test_range_service_uses_official_calendar_sessions(monkeypatch):
    calendar = {
        "calendar_status": "PASS",
        "source": "NSE",
        "source_sha256": "c" * 64,
        "session_dates": ["2026-11-12", "2026-11-13"],
        "special_sessions": [],
    }
    calls = {}
    monkeypatch.setattr(
        service,
        "discover_nse_cm_trading_sessions",
        lambda start, end, session=None: calendar,
    )

    def analyze(dates, *, initial_anchor, session=None):
        calls["dates"] = dates
        calls["initial_anchor"] = initial_anchor
        calls["session"] = session
        return {
            "analysis_status": "REVIEW",
            "retrieval_status": "REVIEW",
            "date_count": 2,
            "per_date_status": pd.DataFrame(),
            "coverage": pd.DataFrame(),
            "provenance": pd.DataFrame(),
            "retrieval_summary": pd.DataFrame(),
        }

    monkeypatch.setattr(
        service,
        "analyze_nse_historical_advance_decline",
        analyze,
    )
    session = object()
    result = service.analyze_nse_historical_advance_decline_for_range(
        "2026-11-12",
        "2026-11-13",
        initial_anchor=10,
        session=session,
    )

    assert calls["dates"] == calendar["session_dates"]
    assert calls["initial_anchor"] == 10
    assert calls["session"] is session
    assert result["calendar_status"] == "PASS"
    assert result["calendar_provenance"] is calendar
    assert result["session_count"] == 2
    assert result["analysis_status"] == "REVIEW"


def test_range_service_does_not_guess_sessions_when_calendar_unavailable(
    monkeypatch,
):
    calendar = {
        "calendar_status": "UNAVAILABLE",
        "source_errors": [{"date": "2026-11-08", "error": "NSE 403"}],
        "session_dates": [],
    }
    monkeypatch.setattr(
        service,
        "discover_nse_cm_trading_sessions",
        lambda *args, **kwargs: calendar,
    )

    def unexpected_analysis(*args, **kwargs):
        raise AssertionError("Analysis must not run without verified calendar.")

    monkeypatch.setattr(
        service,
        "analyze_nse_historical_advance_decline",
        unexpected_analysis,
    )
    result = service.analyze_nse_historical_advance_decline_for_range(
        "2026-11-01",
        "2026-11-14",
    )

    assert result["analysis_status"] == "UNAVAILABLE"
    assert result["calendar_status"] == "UNAVAILABLE"
    assert result["date_count"] == 0


def test_range_service_default_covers_all_83_verified_sessions(monkeypatch):
    sessions = pd.bdate_range("2026-07-17", periods=83).strftime("%Y-%m-%d").tolist()
    calendar = {
        "calendar_status": "PASS",
        "source": "NSE",
        "source_sha256": "d" * 64,
        "session_dates": sessions,
        "special_sessions": [],
    }
    calls = {}
    monkeypatch.setattr(
        service,
        "discover_nse_cm_trading_sessions",
        lambda *args, **kwargs: calendar,
    )

    def analyze(dates, *, initial_anchor, session=None):
        calls["dates"] = dates
        return {
            "analysis_status": "REVIEW",
            "retrieval_status": "REVIEW",
            "date_count": len(dates),
            "per_date_status": pd.DataFrame(),
            "coverage": pd.DataFrame(),
            "provenance": pd.DataFrame(),
            "retrieval_summary": pd.DataFrame(),
        }

    monkeypatch.setattr(service, "analyze_nse_historical_advance_decline", analyze)
    result = service.analyze_nse_historical_advance_decline_for_range(
        "2026-07-17",
        "2026-11-13",
    )

    assert result["calendar_session_count"] == 83
    assert result["session_count"] == 83
    assert calls["dates"] == sessions
