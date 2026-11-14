"""Integration tests for the Market Intelligence application navigation."""

import runpy
from pathlib import Path

import streamlit as st

import ui.data_alerts as data_alerts
import ui.market_intelligence as market_intelligence
import ui.relative_strength as relative_strength
import ui.settings as settings
import ui.stock_search as stock_search


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_market_intelligence_navigation_preserves_existing_pages(
    monkeypatch,
):
    rendered = []
    navigation = {}

    monkeypatch.setattr(st, "set_page_config", lambda **kwargs: None)
    monkeypatch.setattr(st, "title", lambda *args, **kwargs: None)
    monkeypatch.setattr(st, "caption", lambda *args, **kwargs: None)

    def fake_radio(label, options, index=0):
        navigation["label"] = label
        navigation["options"] = list(options)
        return "Market Intelligence"

    monkeypatch.setattr(st.sidebar, "radio", fake_radio)

    monkeypatch.setattr(
        data_alerts,
        "render_data_integrity_alerts",
        lambda: rendered.append("global_alerts"),
    )
    monkeypatch.setattr(
        market_intelligence,
        "render_market_intelligence_page",
        lambda: rendered.append("market_intelligence"),
    )
    monkeypatch.setattr(
        relative_strength,
        "render_relative_strength_page",
        lambda: rendered.append("relative_strength"),
    )
    monkeypatch.setattr(
        stock_search,
        "render_stock_search_page",
        lambda: rendered.append("stock_search"),
    )
    monkeypatch.setattr(
        settings,
        "render_settings_page",
        lambda: rendered.append("settings"),
    )

    runpy.run_path(str(PROJECT_ROOT / "app.py"))

    assert navigation["label"] == "Navigation"
    assert navigation["options"] == [
        "Relative Strength",
        "Stock Search",
        "Settings (Data)",
        "Market Intelligence",
    ]
    assert rendered == [
        "global_alerts",
        "market_intelligence",
    ]


def test_global_data_integrity_monitor_is_not_removed_from_navigation():
    source = (PROJECT_ROOT / "app.py").read_text(encoding="utf-8")

    assert "render_data_integrity_alerts()" in source
    assert '"Relative Strength"' in source
    assert '"Stock Search"' in source
    assert '"Settings (Data)"' in source
    assert '"Market Intelligence"' in source
