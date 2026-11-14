"""UI tests for the historical A/D analysis section."""

from datetime import date

import pandas as pd
import pytest
import streamlit as st

import ui.market_intelligence as market_ui


def fake_result():
    daily = pd.DataFrame([{
        "observation_date": "2026-11-12",
        "analysis_status": "PASS",
        "advancing": 1,
        "declining": 1,
        "unchanged": 1,
        "missing": 0,
        "identity_exceptions": 0,
        "verified_observations": 3,
        "expected_universe": 3,
        "coverage_pct": 100.0,
        "ad_difference": 0,
        "ad_ratio": 1.0,
        "ratio_status": "CALCULATED",
        "cumulative_ad": 10,
        "cumulative_segment_id": 1,
    }])
    return {
        "analysis_status": "PASS",
        "date_count": 1,
        "pass_count": 1,
        "review_count": 0,
        "blocked_count": 0,
        "unavailable_count": 0,
        "missing_count": 0,
        "per_date_status": daily,
        "coverage": daily[["observation_date", "coverage_pct", "analysis_status"]],
        "provenance": pd.DataFrame([{
            "observation_date": "2026-11-12",
            "source": "NSE_UDIFF",
            "source_sha256": "a" * 64,
        }]),
    }


def install_streamlit_stubs(monkeypatch, session_text):
    calls = {"errors": [], "dataframes": [], "charts": [], "messages": []}
    for name in [
        "header", "caption", "info", "subheader", "warning", "divider",
        "write", "success",
    ]:
        monkeypatch.setattr(st, name, lambda *args, **kwargs: None)
    monkeypatch.setattr(st, "error", lambda value, **kwargs: calls["errors"].append(value))
    monkeypatch.setattr(st, "dataframe", lambda value, **kwargs: calls["dataframes"].append(value))
    monkeypatch.setattr(st, "line_chart", lambda *args, **kwargs: calls["charts"].append((args, kwargs)))
    monkeypatch.setattr(
        st, "selectbox",
        lambda label, options, **kwargs: list(options)[0],
    )
    monkeypatch.setattr(st, "date_input", lambda label, value=None, **kwargs: value)
    monkeypatch.setattr(
        st, "text_input",
        lambda label, value="", **kwargs: session_text,
    )
    monkeypatch.setattr(st, "number_input", lambda *args, **kwargs: 10)
    monkeypatch.setattr(
        st, "button",
        lambda label, **kwargs: label == "Run Historical A/D Analysis",
    )
    return calls


def test_ui_calls_historical_service_and_renders_metrics_and_provenance(monkeypatch):
    calls = install_streamlit_stubs(monkeypatch, "2026-11-12")
    service_calls = {}

    def analyze(sessions, *, initial_anchor=0, session=None):
        service_calls["sessions"] = sessions
        service_calls["anchor"] = initial_anchor
        return fake_result()

    monkeypatch.setattr(
        market_ui, "analyze_nse_historical_advance_decline", analyze
    )
    market_ui.render_market_intelligence_page()

    assert service_calls["sessions"] == [date(2026, 11, 12)]
    assert service_calls["anchor"] == 10
    assert len(calls["dataframes"]) == 3
    assert len(calls["charts"]) == 1
    assert not calls["errors"]


def test_ui_requires_explicit_verified_session_dates(monkeypatch):
    calls = install_streamlit_stubs(monkeypatch, "")
    invoked = {"value": False}

    def analyze(*args, **kwargs):
        invoked["value"] = True
        return fake_result()

    monkeypatch.setattr(
        market_ui, "analyze_nse_historical_advance_decline", analyze
    )
    market_ui.render_market_intelligence_page()

    assert invoked["value"] is False
    assert any("কমপক্ষে একটি" in error for error in calls["errors"])


def test_ui_rejects_more_than_thirty_sessions_before_service_call(monkeypatch):
    session_text = ", ".join(
        f"2026-01-{day:02d}" for day in range(1, 32)
    )
    calls = install_streamlit_stubs(monkeypatch, session_text)
    invoked = {"value": False}

    def analyze(*args, **kwargs):
        invoked["value"] = True
        return fake_result()

    monkeypatch.setattr(
        market_ui, "analyze_nse_historical_advance_decline", analyze
    )
    market_ui.render_market_intelligence_page()

    assert invoked["value"] is False
    assert any("সর্বোচ্চ ৩০টি" in error for error in calls["errors"])


def test_ui_rejects_non_iso_date_before_service_call(monkeypatch):
    calls = install_streamlit_stubs(monkeypatch, "2026/11/12")
    invoked = {"value": False}

    def analyze(*args, **kwargs):
        invoked["value"] = True
        return fake_result()

    monkeypatch.setattr(
        market_ui, "analyze_nse_historical_advance_decline", analyze
    )
    market_ui.render_market_intelligence_page()

    assert invoked["value"] is False
    assert calls["errors"]
