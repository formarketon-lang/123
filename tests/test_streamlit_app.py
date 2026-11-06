
"""TradeLab Pro - Streamlit UI smoke tests.

Checks that the main application and its three navigation
pages render without uncaught Streamlit exceptions.
External market-data calls are mocked for deterministic tests.
"""

from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_FILE = PROJECT_ROOT / "app.py"


def fake_nse_universe():
    """Small verified NSE EQ universe for UI-only tests."""
    return pd.DataFrame({
        "Symbol": ["MARICO", "RELIANCE"],
        "Company": ["Marico Limited", "Reliance Industries Limited"],
        "ISIN": ["INE196A01026", "INE002A01018"],
        "Series": ["EQ", "EQ"],
        "Listing Date": ["1996-04-01", "1995-11-29"],
        "Face Value": [1, 10],
        "Exchange": ["NSE", "NSE"],
        "Source": ["TEST_FIXTURE", "TEST_FIXTURE"],
    })


@pytest.fixture
def mock_market_data(monkeypatch):
    """Prevent external market-data requests during UI smoke tests."""

    import ui.relative_strength as relative_strength
    import ui.stock_search as stock_search

    monkeypatch.setattr(
        relative_strength,
        "get_cached_nse_universe",
        fake_nse_universe,
    )

    monkeypatch.setattr(
        relative_strength,
        "get_cached_amfi_market_cap",
        lambda: pd.DataFrame(),
    )

    monkeypatch.setattr(
        stock_search,
        "load_nse_universe",
        fake_nse_universe,
    )


def run_app():
    """Start the application through Streamlit AppTest."""
    return AppTest.from_file(
        str(APP_FILE),
        default_timeout=30,
    ).run()


def assert_no_app_exception(app_test):
    """Fail with readable details if Streamlit raises an exception."""
    if app_test.exception:
        messages = [
            str(item.message)
            for item in app_test.exception
        ]
        pytest.fail(
            "Streamlit application raised an exception: "
            + " | ".join(messages)
        )


def test_app_starts_on_relative_strength(mock_market_data):
    """Default application page must be Relative Strength."""

    app_test = run_app()

    assert_no_app_exception(app_test)

    assert app_test.title
    assert app_test.title[0].value == "TradeLab Pro"

    assert app_test.radio
    assert app_test.radio[0].value == "Relative Strength"

    visible_text = " ".join(
        item.value
        for item in app_test.header
    )

    assert "Relative Strength Scanner" in visible_text


def test_settings_data_page_renders(mock_market_data):
    """Settings page must render verified configuration controls."""

    app_test = run_app()

    assert_no_app_exception(app_test)

    app_test.radio[0].set_value("Settings (Data)").run()

    assert_no_app_exception(app_test)

    headers = " ".join(
        item.value
        for item in app_test.header
    )

    assert "Settings (Data)" in headers

    visible_text = " ".join(
        item.value
        for item in app_test.success
    )

    assert "NSE Primary" in visible_text


def test_stock_search_page_renders(mock_market_data):
    """Stock Search must render using the mocked NSE universe."""

    app_test = run_app()

    assert_no_app_exception(app_test)

    app_test.radio[0].set_value("Stock Search").run()

    assert_no_app_exception(app_test)

    headers = " ".join(
        item.value
        for item in app_test.header
    )

    assert "Stock Search" in headers

    assert app_test.metric

    assert app_test.text_input


def test_relative_strength_shows_multiple_benchmark_control(
    mock_market_data,
):
    """Relative Strength must expose the multi-benchmark selector."""

    app_test = run_app()

    assert_no_app_exception(app_test)

    multiselect_labels = [
        item.label
        for item in app_test.multiselect
    ]

    assert "Select one or more Main Benchmarks" in (
        multiselect_labels
    )

    assert "Select Stocks from NSE Universe" in (
        multiselect_labels
)
  
