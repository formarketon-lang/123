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
      
from unittest.mock import patch


def test_validates_and_returns_yahoo_ohlcv_data():
    fake_data = pd.DataFrame(
        {
            "Open": [100.0, 105.0],
            "High": [103.0, 108.0],
            "Low": [99.0, 104.0],
            "Close": [102.0, 107.0],
            "Volume": [1000, 1200],
        },
        index=pd.to_datetime(["2026-10-05", "2026-10-06"]),
    )

    with patch("data.yahoo_adapter.yf.download", return_value=fake_data):
        result = fetch_yahoo_history(
            "HINDUNILVR",
            "2026-10-01",
            "2026-10-10",
        )

    assert list(result.columns) == [
        "Date", "Open", "High", "Low", "Close", "Volume"
    ]
    assert len(result) == 2
    assert result["Close"].tolist() == [102.0, 107.0]
    

def test_raises_error_when_yahoo_returns_no_data():
    with patch("data.yahoo_adapter.yf.download", return_value=pd.DataFrame()):
        with pytest.raises(ValueError, match="No Yahoo Finance data"):
            fetch_yahoo_history(
                "HINDUNILVR",
                "2026-10-01",
                "2026-10-10",
            )
            
