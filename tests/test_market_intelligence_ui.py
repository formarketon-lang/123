
"""Tests for the isolated Market Intelligence UI shell."""

import ast
from pathlib import Path

import pytest
import streamlit as st

from ui.market_intelligence import render_market_intelligence_page


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
        "write": [],
        "divider": [],
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
    """The isolated page must render its main sections."""

    render_market_intelligence_page()

    calls = captured_streamlit_calls

    assert "Market Intelligence" in calls["header"]

    assert "Module Activation Status" in calls["subheader"]

    assert "Planned Analysis Areas" in calls["subheader"]

    assert calls["info"]
    assert calls["warning"]
    assert calls["divider"]


def test_market_intelligence_lists_all_planned_analysis_areas(
    captured_streamlit_calls,
):
    """All planned analysis areas must remain visible."""

    render_market_intelligence_page()

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


def test_market_intelligence_remains_pending_without_fake_signals(
    captured_streamlit_calls,
):
    """The shell must not imply that unbuilt analysis is active."""

    render_market_intelligence_page()

    warning_text = " ".join(
        str(value)
        for value in captured_streamlit_calls["warning"]
    )

    info_text = " ".join(
        str(value)
        for value in captured_streamlit_calls["info"]
    )

    assert "PENDING" in warning_text
    assert "কোনো Market Signal" in info_text


def test_market_intelligence_ui_has_no_core_or_data_imports():
    """The UI shell must not depend directly on Core or Data layers."""

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

    assert not any(
        module == "core"
        or module.startswith("core.")
        or module == "data"
        or module.startswith("data.")
        for module in imported_modules
    )
  
