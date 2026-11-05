
import pandas as pd
import pytest

from data import market_data_adapter as adapter
from data.providers.nse_index_downloader import INDEX_ALIASES


MAIN_INDEXES = {
    "^NSEI": "NIFTY 50",
    "^NSMIDCP": "NIFTY NEXT 50",
    "^CNX100": "NIFTY 100",
    "^CNX200": "NIFTY 200",
    "^CRSLDX": "NIFTY 500",
    "^CNXFMCG": "NIFTY FMCG",
}


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


def sample_index_data():
    return sample_data().drop(columns=["Volume"])


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


@pytest.mark.parametrize(
    "symbol,index_name",
    MAIN_INDEXES.items(),
)
def test_all_configured_indexes_use_nse_primary(
    monkeypatch,
    symbol,
    index_name,
):
    calls = []

    def fake_nse(name, start_date, end_date):
        calls.append(name)
        return sample_index_data()

    def fake_yahoo(**kwargs):
        raise AssertionError("Yahoo must not be called.")

    monkeypatch.setattr(
        adapter,
        "download_index_history",
        fake_nse,
    )
    monkeypatch.setattr(
        adapter,
        "fetch_yahoo_history",
        fake_yahoo,
    )

    result = adapter.fetch_market_history(
        symbol,
        "2026-10-01",
        "2026-10-02",
    )

    assert calls == [index_name]
    assert result["Source"].unique().tolist() == ["NSE"]
    assert result["Volume"].isna().all()
    assert result["Fallback Reason"].iloc[0] == ""


@pytest.mark.parametrize(
    "symbol,index_name",
    MAIN_INDEXES.items(),
)
def test_all_configured_indexes_fallback_to_yahoo(
    monkeypatch,
    symbol,
    index_name,
):
    def fake_nse(*args):
        raise RuntimeError("NSE index unavailable")

    monkeypatch.setattr(
        adapter,
        "download_index_history",
        fake_nse,
    )
    monkeypatch.setattr(
        adapter,
        "fetch_yahoo_history",
        lambda **kwargs: sample_data(),
    )

    result = adapter.fetch_market_history(
        symbol,
        "2026-10-01",
        "2026-10-02",
    )

    assert result["Source"].unique().tolist() == ["Yahoo"]
    assert "NSE index unavailable" in (
        result["Fallback Reason"].iloc[0]
    )


def test_downloader_accepts_all_configured_index_names():
    for index_name in MAIN_INDEXES.values():
        assert index_name in INDEX_ALIASES
        assert INDEX_ALIASES[index_name] == index_name


def test_yahoo_fallback_after_nse_equity_failure(monkeypatch):
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
        "^UNKNOWN",
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
