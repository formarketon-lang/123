
import pandas as pd
import pytest

from data import market_data_adapter as adapter


def sample_equity_data():
    return pd.DataFrame({
        "Date": pd.to_datetime([
            "2026-10-01",
            "2026-10-02",
        ]),
        "Open": [100, 101],
        "High": [103, 104],
        "Low": [99, 100],
        "Close": [102, 103],
        "Volume": [1000, 1200],
    })


def sample_index_data():
    return sample_equity_data().drop(columns=["Volume"])


def test_nse_equity_passes_common_schema(monkeypatch):
    monkeypatch.setattr(
        adapter,
        "download_equity_history",
        lambda *args: sample_equity_data(),
    )

    result = adapter.fetch_market_history(
        "MARICO",
        "2026-10-01",
        "2026-10-02",
    )

    assert result["Symbol"].eq("MARICO").all()
    assert result["Source"].eq("NSE").all()
    assert result["Exchange"].eq("NSE").all()
    assert result["Timeframe"].eq("1d").all()
    assert result["Fallback Reason"].eq("").all()
    assert result["Volume"].notna().all()


def test_nse_index_without_volume_passes_schema(monkeypatch):
    monkeypatch.setattr(
        adapter,
        "download_index_history",
        lambda *args: sample_index_data(),
    )

    result = adapter.fetch_market_history(
        "^NSEI",
        "2026-10-01",
        "2026-10-02",
    )

    assert result["Symbol"].eq("^NSEI").all()
    assert result["Source"].eq("NSE").all()
    assert result["Exchange"].eq("NSE").all()
    assert result["Volume"].isna().all()


def test_index_with_partially_missing_volume_is_rejected():
    data = sample_equity_data()
    data.loc[0, "Volume"] = None

    with pytest.raises(
        ValueError,
        match="fully available or absent",
    ):
        adapter._validate_nse_data(
            data,
            "^NSEI",
            is_index=True,
        )


def test_yahoo_fallback_uses_common_schema(monkeypatch):
    monkeypatch.setattr(
        adapter,
        "download_equity_history",
        lambda *args: (_ for _ in ()).throw(
            RuntimeError("NSE deliberately unavailable")
        ),
    )

    monkeypatch.setattr(
        adapter,
        "fetch_yahoo_history",
        lambda **kwargs: sample_equity_data(),
    )

    result = adapter.fetch_market_history(
        "MARICO",
        "2026-10-01",
        "2026-10-02",
    )

    assert result["Symbol"].eq("MARICO").all()
    assert result["Source"].eq("Yahoo").all()
    assert result["Exchange"].eq("NSE").all()
    assert result["Timeframe"].eq("1d").all()
    assert "NSE deliberately unavailable" in (
        result["Fallback Reason"].iloc[0]
    )
    assert result["Volume"].notna().all()


def test_invalid_nse_data_triggers_yahoo_fallback(monkeypatch):
    invalid_data = sample_equity_data()
    invalid_data.loc[0, "High"] = 50

    monkeypatch.setattr(
        adapter,
        "download_equity_history",
        lambda *args: invalid_data,
    )

    monkeypatch.setattr(
        adapter,
        "fetch_yahoo_history",
        lambda **kwargs: sample_equity_data(),
    )

    result = adapter.fetch_market_history(
        "MARICO",
        "2026-10-01",
        "2026-10-02",
    )

    assert result["Source"].eq("Yahoo").all()
    assert "Inconsistent OHLC" in (
        result["Fallback Reason"].iloc[0]
    )


def test_both_sources_failure_raises_clear_error(monkeypatch):
    monkeypatch.setattr(
        adapter,
        "download_equity_history",
        lambda *args: (_ for _ in ()).throw(
            RuntimeError("NSE unavailable")
        ),
    )

    monkeypatch.setattr(
        adapter,
        "fetch_yahoo_history",
        lambda **kwargs: (_ for _ in ()).throw(
            RuntimeError("Yahoo deliberately unavailable")
        ),
    )

    with pytest.raises(
        adapter.MarketDataUnavailableError,
        match="NSE Primary failed",
    ):
        adapter.fetch_market_history(
            "MARICO",
            "2026-10-01",
            "2026-10-02",
        )


def test_bse_remains_disabled():
    with pytest.raises(ValueError, match="supports NSE only"):
        adapter.fetch_market_history(
            "500034",
            "2026-10-01",
            "2026-10-02",
            exchange="BSE",
        )
      
