"""Tests for the Market Intelligence UI and service-layer boundary."""

import ast
from datetime import date
from pathlib import Path

import pandas as pd
import pytest
import streamlit as st

import ui.market_intelligence as market_intelligence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
UI_FILE = PROJECT_ROOT / "ui" / "market_intelligence.py"


@pytest.fixture
def captured_streamlit_calls(monkeypatch):
    """Capture Streamlit rendering calls without launching the app."""

    calls = {
        "header": [],
        "caption": [],
        "info": [],
        "subheader": [],
        "warning": [],
        "success": [],
        "error": [],
        "write": [],
        "divider": [],
        "date_input": [],
        "selectbox": [],
        "button": [],
        "dataframe": [],
    }

    for method_name in calls:

        def capture(*args, _name=method_name, **kwargs):
            value = args[0] if args else kwargs
            calls[_name].append(value)

        monkeypatch.setattr(st, method_name, capture)

    return calls


def test_market_intelligence_page_renders_without_error(
    captured_streamlit_calls,
):
    market_intelligence.render_market_intelligence_page()

    calls = captured_streamlit_calls

    assert "Market Intelligence" in calls["header"]
    assert "Module Activation Status" in calls["subheader"]
    assert "Live NSE Market Breadth" in calls["subheader"]
    assert calls["info"]
    assert calls["warning"]
    assert calls["date_input"]
    assert calls["selectbox"]
    assert calls["button"]


def test_market_intelligence_lists_all_planned_analysis_areas(
    captured_streamlit_calls,
):
    market_intelligence.render_market_intelligence_page()

    displayed_items = captured_streamlit_calls["write"]

    expected_items = [
        "• Market Regime Analysis",
        "• Market Breadth",
        "• Advance / Decline Analysis",
        "• Sector Strength",
        "• Index Participation",
        "• Market Trend Classification",
        "• News and Events Context",
    ]

    for item in expected_items:
        assert item in displayed_items


def test_market_intelligence_reports_review_without_claiming_pass(
    captured_streamlit_calls,
):
    market_intelligence.render_market_intelligence_page()

    warning_text = " ".join(
        str(value)
        for value in captured_streamlit_calls["warning"]
    )

    assert "REVIEW" in warning_text
    assert not captured_streamlit_calls["success"]


def test_market_intelligence_calls_service_and_displays_review(
    monkeypatch,
    captured_streamlit_calls,
):
    service_calls = []

    result = {
        "analysis_status": "REVIEW",
        "source": "NSE",
        "source_sha256": "a" * 64,
        "fetched_at_utc": "2026-11-14T01:00:00Z",
        "observation_date": "2026-11-13",
        "reconciliation": {
            "coverage_pct": 99.2,
            "observed_symbols": 2740,
            "expected_symbols": 2762,
            "identity_status": "REVIEW",
            "coverage_status": "REVIEW",
            "identity_exceptions": [
                {
                    "symbol": "BNAGROCHEM",
                    "reason": "SYMBOL_ISIN_MISMATCH",
                }
            ],
            "missing_symbols": ["MISSING1", "MISSING2"],
        },
        "breadth": {
            "advancing": 1200,
            "declining": 1100,
            "unchanged": 440,
            "coverage_status": "REVIEW",
        },
        "audit": {
            "schema_mapping_status": "PASS",
            "audit_status": "REVIEW",
            "audit_reasons": ["MII_SYMBOL_COVERAGE_INCOMPLETE"],
        },
    }

    monkeypatch.setattr(
        st,
        "date_input",
        lambda *args, **kwargs: date(2026, 11, 13),
    )
    monkeypatch.setattr(
        st,
        "button",
        lambda label, *args, **kwargs: (
            label == "Run NSE Market Breadth"
        ),
    )
    monkeypatch.setattr(
        market_intelligence,
        "analyze_nse_market_breadth_from_udiff",
        lambda selected_date: (
            service_calls.append(selected_date) or result
        ),
    )

    market_intelligence.render_market_intelligence_page()

    assert service_calls == [date(2026, 11, 13)]
    warning_text = " ".join(
        str(value)
        for value in captured_streamlit_calls["warning"]
    )
    assert "REVIEW" in warning_text
    assert "Advancing: 1200" in captured_streamlit_calls["write"]
    assert "Declining: 1100" in captured_streamlit_calls["write"]
    assert captured_streamlit_calls["dataframe"]
    assert "MISSING1, MISSING2" in captured_streamlit_calls["write"]


def test_market_intelligence_handles_service_failure(
    monkeypatch,
    captured_streamlit_calls,
):
    monkeypatch.setattr(
        st,
        "date_input",
        lambda *args, **kwargs: date(2026, 11, 13),
    )
    monkeypatch.setattr(
        st,
        "button",
        lambda label, *args, **kwargs: (
            label == "Run NSE Market Breadth"
        ),
    )

    def fail_service(_):
        raise RuntimeError("NSE source unavailable")

    monkeypatch.setattr(
        market_intelligence,
        "analyze_nse_market_breadth_from_udiff",
        fail_service,
    )

    market_intelligence.render_market_intelligence_page()

    assert captured_streamlit_calls["error"]
    assert not captured_streamlit_calls["success"]


def test_market_intelligence_ui_imports_service_not_core_or_data():
    source = UI_FILE.read_text(encoding="utf-8")
    syntax_tree = ast.parse(source)

    imported_modules = []

    for node in ast.walk(syntax_tree):
        if isinstance(node, ast.Import):
            imported_modules.extend(
                alias.name for alias in node.names
            )

        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported_modules.append(node.module)

    assert "streamlit" in imported_modules
    assert (
        "services.market_intelligence.bhavcopy_service"
        in imported_modules
    )
    assert (
        "services.market_intelligence.regime_service"
        in imported_modules
    )

    assert not any(
        module == "core"
        or module.startswith("core.")
        or module == "data"
        or module.startswith("data.")
        for module in imported_modules
    )


def test_market_intelligence_calls_regime_service_and_displays_pass(
    monkeypatch,
    captured_streamlit_calls,
):
    service_calls = []

    monkeypatch.setattr(
        st,
        "selectbox",
        lambda *args, **kwargs: "^NSEI",
    )
    monkeypatch.setattr(
        st,
        "date_input",
        lambda *args, **kwargs: date(2026, 11, 13),
    )
    monkeypatch.setattr(
        st,
        "button",
        lambda label, *args, **kwargs: (
            label == "Run NSE Market Regime"
        ),
    )
    monkeypatch.setattr(
        market_intelligence,
        "analyze_index_market_regime",
        lambda symbol, start, end: (
            service_calls.append((symbol, start, end))
            or {
                "analysis_status": "PASS",
                "index_name": "NIFTY 50",
                "regime": "BULLISH",
                "close": 25000.0,
                "short_sma": 24900.0,
                "long_sma": 24800.0,
                "source": "NSE",
                "fetched_at_utc": "2026-11-13T10:00:00Z",
                "fallback_reason": "",
            }
        ),
    )

    market_intelligence.render_market_intelligence_page()

    assert service_calls == [
        (
            "^NSEI",
            date(2026, 11, 13),
            date(2026, 11, 13),
        )
    ]
    assert any(
        "NIFTY 50 Regime: BULLISH" in str(value)
        for value in captured_streamlit_calls["success"]
    )
    assert "Close: 25000.00" in captured_streamlit_calls["write"]
