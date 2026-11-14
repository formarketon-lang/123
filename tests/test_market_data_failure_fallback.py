
import pandas as pd
import pytest

from data import market_data_adapter as adapter


def sample_equity_data():
    data = pd.DataFrame({
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
    data.attrs["fetched_at_utc"] = "2026-11-11T05:00:00Z"
    return data


def sample_index_data():
    return sample_equity_data().drop(columns=["Volume"])


def test_nse_success_does_not_call_yahoo(monkeypatch):
    monkeypatch.setattr(
        adapter,
        "download_equity_history",
        lambda *args: sample_equity_data(),
    )

    def unexpected_yahoo_call(**kwargs):
        raise AssertionError("Yahoo must not be called")

    monkeypatch.setattr(
        adapter,
        "fetch_yahoo_history",
        unexpected_yahoo_call,
    )

    result = adapter.fetch_market_history(
        "MARICO",
        "2026-10-01",
        "2026-10-02",
    )

    assert result["Source"].eq("NSE").all()
    assert result["Validation Status"].eq("PASS").all()
    assert result["Fallback Reason"].eq("").all()


def test_empty_nse_response_uses_yahoo_fallback(monkeypatch):
    monkeypatch.setattr(
        adapter,
        "download_equity_history",
        lambda *args: pd.DataFrame(),
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
    assert result["Validation Status"].eq("PASS").all()
    assert "empty or invalid" in result["Fallback Reason"].iloc[0]


def test_invalid_nse_ohlc_uses_yahoo_fallback(monkeypatch):
    invalid = sample_equity_data()
    invalid.loc[0, "High"] = 50

    monkeypatch.setattr(
        adapter,
        "download_equity_history",
        lambda *args: invalid,
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
    assert "Inconsistent OHLC" in result["Fallback Reason"].iloc[0]


def test_yahoo_fallback_preserves_provenance(monkeypatch):
    monkeypatch.setattr(
        adapter,
        "download_equity_history",
        lambda *args: (_ for _ in ()).throw(
            RuntimeError("NSE connection failed")
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

    assert result["Source"].eq("Yahoo").all()
    assert result["Exchange"].eq("NSE").all()
    assert result["Validation Status"].eq("PASS").all()
    assert result["Fetched At UTC"].notna().all()
    assert result["Observation Start"].eq("2026-10-01").all()
    assert result["Observation End"].eq("2026-10-02").all()
    assert "NSE connection failed" in result["Fallback Reason"].iloc[0]


def test_both_sources_failure_reports_both_errors(monkeypatch):
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
            RuntimeError("Yahoo unavailable")
        ),
    )

    with pytest.raises(adapter.MarketDataUnavailableError) as error:
        adapter.fetch_market_history(
            "MARICO",
            "2026-10-01",
            "2026-10-02",
        )

    message = str(error.value)

    assert "NSE unavailable" in message
    assert "Yahoo unavailable" in message
    assert "NSE Primary failed" in message
    assert "Yahoo Secondary failed" in message


def test_invalid_yahoo_response_is_not_accepted(monkeypatch):
    invalid = sample_equity_data()
    invalid.loc[0, "High"] = 50

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
        lambda **kwargs: invalid,
    )

    with pytest.raises(adapter.MarketDataUnavailableError) as error:
        adapter.fetch_market_history(
            "MARICO",
            "2026-10-01",
            "2026-10-02",
        )

    assert "Yahoo Secondary failed" in str(error.value)
    assert "Inconsistent OHLC" in str(error.value)


def test_nse_index_without_volume_keeps_valid_provenance(monkeypatch):
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

    assert result["Source"].eq("NSE").all()
    assert result["Volume"].isna().all()
    assert result["Validation Status"].eq("PASS").all()
    assert result["Symbol"].eq("^NSEI").all()


def test_unsupported_nse_interval_uses_yahoo(monkeypatch):
    monkeypatch.setattr(
        adapter,
        "fetch_yahoo_history",
        lambda **kwargs: sample_equity_data(),
    )

    def unexpected_nse_call(*args):
        raise AssertionError("NSE must not be called for this interval")

    monkeypatch.setattr(
        adapter,
        "download_equity_history",
        unexpected_nse_call,
    )

    result = adapter.fetch_market_history(
        "MARICO",
        "2026-10-01",
        "2026-10-02",
        interval="5m",
    )

    assert result["Source"].eq("Yahoo").all()
    assert result["Timeframe"].eq("5m").all()
    assert "does not support interval 5m" in result["Fallback Reason"].iloc[0]


def test_bse_rejection_does_not_call_yahoo(monkeypatch):
    def unexpected_yahoo_call(**kwargs):
        raise AssertionError("BSE must be rejected before Yahoo")

    monkeypatch.setattr(
        adapter,
        "fetch_yahoo_history",
        unexpected_yahoo_call,
    )

    with pytest.raises(ValueError, match="supports NSE only"):
        adapter.fetch_market_history(
            "500034",
            "2026-10-01",
            "2026-10-02",
            exchange="BSE",
    )
      



def test_nse_response_without_fetch_timestamp_uses_yahoo_fallback(monkeypatch):
    nse_data = sample_equity_data()
    nse_data.attrs.pop("fetched_at_utc", None)

    monkeypatch.setattr(
        adapter,
        "download_equity_history",
        lambda *args: nse_data,
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
    assert "explicit fetched_at_utc" in result["Fallback Reason"].iloc[0]
