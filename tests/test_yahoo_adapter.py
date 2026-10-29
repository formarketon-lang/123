import pandas as pd
import pytest

from data.yahoo_adapter import fetch_yahoo_history


def test_rejects_empty_symbol():
    with pytest.raises(ValueError, match="Stock symbol"):
        fetch_yahoo_history(
            "",
            "2026-10-01",
            "2026-10-10",
        )


def test_rejects_invalid_exchange():
    with pytest.raises(ValueError, match="Exchange"):
        fetch_yahoo_history(
            "HINDUNILVR",
            "2026-10-01",
            "2026-10-10",
            exchange="Both",
        )


def test_rejects_invalid_interval():
    with pytest.raises(ValueError, match="interval"):
        fetch_yahoo_history(
            "HINDUNILVR",
            "2026-10-01",
            "2026-10-10",
            interval="2h",
        )


def test_rejects_reversed_dates():
    with pytest.raises(ValueError, match="Start date"):
        fetch_yahoo_history(
            "HINDUNILVR",
            "2026-10-10",
            "2026-10-01",
        )
      
