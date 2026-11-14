
"""Tests for Market Intelligence regime integration."""

import pandas as pd
import pytest

from services.market_intelligence.regime_service import (
    analyze_index_market_regime,
)


def make_index_data():
    return pd.DataFrame({
        "Date": pd.date_range("2025-01-01", periods=202),
        "Close": range(100, 302),
        "Source": ["NSE"] * 202,
        "Validation Status": ["PASS"] * 202,
        "Fallback Reason": [""] * 202,
        "Fetched At UTC": ["2025-08-01T00:00:00Z"] * 202,
    })


def test_regime_service_integrates_validated_index(monkeypatch):
    def fake_fetch(**kwargs):
        assert kwargs["symbol"] == "^NSEI"
        return make_index_data()

    monkeypatch.setattr(
        "services.market_intelligence.regime_service.fetch_index_history",
        fake_fetch,
    )

    result = analyze_index_market_regime(
        "^NSEI", "2025-01-01", "2025-08-01"
    )

    assert result["index_symbol"] == "^NSEI"
    assert result["index_name"] == "NIFTY 50"
    assert result["regime"] == "BULLISH"
    assert result["analysis_status"] == "PASS"
    assert result["source"] == "NSE"
    assert result["fetched_at_utc"] == "2025-08-01T00:00:00Z"


def test_regime_service_blocks_unknown_index():
    with pytest.raises(ValueError, match="unverified"):
        analyze_index_market_regime(
            "^UNKNOWN", "2025-01-01", "2025-08-01"
        )


def test_regime_service_preserves_yahoo_fallback(monkeypatch):
    data = make_index_data()
    data["Source"] = "Yahoo"
    data["Fallback Reason"] = "NSE source unavailable"

    monkeypatch.setattr(
        "services.market_intelligence.regime_service.fetch_index_history",
        lambda **kwargs: data,
    )

    result = analyze_index_market_regime(
        "^NSEI", "2025-01-01", "2025-08-01"
    )

    assert result["source"] == "Yahoo"
    assert result["fallback_reason"] == "NSE source unavailable"
    assert result["analysis_status"] == "PASS"


def test_regime_service_rejects_invalid_windows(monkeypatch):
    monkeypatch.setattr(
        "services.market_intelligence.regime_service.fetch_index_history",
        lambda **kwargs: make_index_data(),
    )

    with pytest.raises(ValueError, match="Windows"):
        analyze_index_market_regime(
            "^NSEI",
            "2025-01-01",
            "2025-08-01",
            short_window=200,
            long_window=50,
        )
      
