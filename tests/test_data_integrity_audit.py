import pandas as pd

from scripts.run_data_integrity_audit import (
    compare_sources,
    load_and_normalize,
)


def sample_data():
    nse = pd.DataFrame({
        "Date": ["2026-10-28", "2026-10-29"],
        "Open": [100, 102],
        "High": [105, 107],
        "Low": [99, 101],
        "Close": [104, 106],
        "Volume": [1000, 1200],
    })

    yahoo = pd.DataFrame({
        "Date": ["2026-10-28", "2026-10-29"],
        "Open": [100, 102],
        "High": [105, 107],
        "Low": [99, 101],
        "Close": [104, 106],
        "Volume": [1000, 1200],
    })

    nse["Date"] = pd.to_datetime(nse["Date"])
    yahoo["Date"] = pd.to_datetime(yahoo["Date"])

    return nse, yahoo


def test_matching_data():
    nse, yahoo = sample_data()

    summary, detail = compare_sources(
        nse,
        yahoo,
        "MARICO",
    )

    assert summary["status"] == "MATCH"
    assert summary["common_sessions"] == 2
    assert summary["ohlc_mismatch_sessions"] == 0


def test_close_price_mismatch():
    nse, yahoo = sample_data()
    yahoo.loc[1, "Close"] = 110

    summary, detail = compare_sources(
        nse,
        yahoo,
        "MARICO",
    )

    assert summary["status"] == "REVIEW"
    assert summary["ohlc_mismatch_sessions"] == 1


def test_missing_session_detection():
    nse, yahoo = sample_data()
    yahoo = yahoo.iloc[:1].copy()

    summary, detail = compare_sources(
        nse,
        yahoo,
        "MARICO",
    )

    assert summary["common_sessions"] == 1
    assert summary["nse_only_sessions"] == 1


def test_normalize_csv(tmp_path):
    file_path = tmp_path / "sample.csv"

    pd.DataFrame({
        "CH_TIMESTAMP": ["2026-10-29"],
        "CH_OPENING_PRICE": [100],
        "CH_TRADE_HIGH_PRICE": [105],
        "CH_TRADE_LOW_PRICE": [99],
        "CH_CLOSING_PRICE": [104],
        "CH_TOT_TRADED_QTY": [1000],
    }).to_csv(file_path, index=False)

    result = load_and_normalize(file_path)

    assert list(result.columns) == [
        "Date", "Open", "High", "Low", "Close", "Volume"
    ]
    assert len(result) == 1
  
