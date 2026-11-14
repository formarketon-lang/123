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
    monkeypatch.setattr(
        service, "analyze_historical_advance_decline",
        lambda *args, **kwargs: fake_analysis(),
    )
    service.analyze_nse_historical_advance_decline(dates)
    assert calls["dates"] == dates
