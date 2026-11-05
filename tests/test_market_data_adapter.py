
import pandas as pd
import pytest

from data import market_data_adapter as adapter


def sample_data():
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


def test_nse_equity_is_primary(monkeypatch):
    calls = []

    def fake_nse(*args):
        calls.append("NSE")
        return sample_data()

    def fake_yahoo(**kwargs):
        calls.append("Yahoo")
        raise AssertionError("Yahoo must not be called.")

    monkeypatch.setattr(
        adapter,
        "download_equity_history",
        fake_nse,
    )

    monkeypatch.setattr(
        adapter,
        "fetch_yahoo_history",
        fake_yahoo,
    )

    result = adapter.fetch_market_history(
        "MARICO",
        "2026-10-01",
        "2026-10-02",
    )

    assert calls == ["NSE"]
    assert result["Source"].unique().tolist() == ["NSE"]


def test_nse_index_is_primary(monkeypatch):
    index_data = sample_data().drop(columns=["Volume"])

    monkeypatch.setattr(
        adapter,
        "download_index_history",
        lambda *args: index_data,
    )

    def fake_yahoo(**kwargs):
        raise AssertionError("Yahoo must not be called.")

    monkeypatch.setattr(
        adapter,
        "fetch_yahoo_history",
        fake_yahoo,
    )

    result = adapter.fetch_market_history(
        "^NSEI",
        "2026-10-01",
        "2026-10-02",
    )

    assert result["Source"].unique().tolist() == ["NSE"]
    assert result["Volume"].isna().all()
    assert result["Close"].tolist() == [102, 103]


def test_yahoo_fallback_after_nse_failure(monkeypatch):
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
        lambda **kwargs: sample_data(),
    )

    result = adapter.fetch_market_history(
        "MARICO",
        "2026-10-01",
        "2026-10-02",
    )

    assert result["Source"].unique().tolist() == ["Yahoo"]

    assert "NSE unavailable" in (
        result["Fallback Reason"].iloc[0]
    )


def test_unmapped_index_uses_yahoo_with_reason(monkeypatch):
    monkeypatch.setattr(
        adapter,
        "fetch_yahoo_history",
        lambda **kwargs: sample_data(),
    )

    result = adapter.fetch_market_history(
        "^NSMIDCP",
        "2026-10-01",
        "2026-10-02",
    )

    assert result["Source"].unique().tolist() == ["Yahoo"]

    assert "No verified NSE index mapping" in (
        result["Fallback Reason"].iloc[0]
    )


def test_bse_is_rejected():
    with pytest.raises(ValueError, match="supports NSE only"):
        adapter.fetch_market_history(
            "500034",
            "2026-10-01",
            "2026-10-02",
            exchange="BSE",
        )


def test_both_sources_failure_is_reported(monkeypatch):
    monkeypatch.setattr(
        adapter,
        "download_equity_history",
        lambda *args: (_ for _ in ()).throw(
            RuntimeError("NSE failed")
        ),
    )

    monkeypatch.setattr(
        adapter,
        "fetch_yahoo_history",
        lambda **kwargs: (_ for _ in ()).throw(
            RuntimeError("Yahoo failed")
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
      
