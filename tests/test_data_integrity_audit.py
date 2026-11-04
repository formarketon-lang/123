
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

    summary, detail = compare_sources(nse, yahoo, "MARICO")

    assert summary["status"] == "MATCH"
    assert summary["common_sessions"] == 2
    assert summary["ohlc_mismatch_sessions"] == 0
    assert summary["ohlc_missing_sessions"] == 0


def test_close_price_mismatch():
    nse, yahoo = sample_data()
    yahoo.loc[1, "Close"] = 110

    summary, detail = compare_sources(nse, yahoo, "MARICO")

    assert summary["status"] == "REVIEW"
    assert summary["ohlc_mismatch_sessions"] == 1


def test_missing_session_detection():
    nse, yahoo = sample_data()
    yahoo = yahoo.iloc[:1].copy()

    summary, detail = compare_sources(nse, yahoo, "MARICO")

    assert summary["common_sessions"] == 1
    assert summary["nse_only_sessions"] == 1
    assert summary["status"] == "REVIEW"


def test_common_session_missing_ohlc_value():
    nse, yahoo = sample_data()
    yahoo.loc[0, "High"] = float("nan")

    summary, detail = compare_sources(nse, yahoo, "MARICO")

    row = detail[
        detail["Date"] == pd.Timestamp("2026-10-28")
    ].iloc[0]

    assert summary["status"] == "REVIEW"
    assert summary["ohlc_missing_sessions"] == 1
    assert row["OHLC_Missing"]
    assert row["Session_Classification"] == "OHLC_DATA_MISSING"


def test_special_session_volume_mismatch_is_not_hidden():
    nse, yahoo = sample_data()

    special_date = pd.Timestamp("2026-02-01")

    nse.loc[0, "Date"] = special_date
    yahoo.loc[0, "Date"] = special_date

    yahoo.loc[0, "Volume"] = 9999

    summary, detail = compare_sources(nse, yahoo, "MARICO")

    row = detail[
        detail["Date"] == special_date
    ].iloc[0]

    assert summary["status"] == "REVIEW"
    assert summary["volume_mismatch_sessions"] == 1
    assert row["Session_Classification"] == "VOLUME_DIFFERENCE"


def test_verified_regular_session_missing_from_yahoo():
    verified_dates = [
        "2025-10-30",
        "2026-01-01",
    ]

    for date in verified_dates:
        nse, yahoo = sample_data()

        nse = nse.iloc[:1].copy()
        nse.loc[nse.index[0], "Date"] = pd.Timestamp(date)

        yahoo = yahoo.iloc[:0].copy()

        summary, detail = compare_sources(
            nse, yahoo, "NIFTY 50"
        )

        row = detail.iloc[0]

        assert summary["status"] == "REVIEW"
        assert summary["nse_only_sessions"] == 1
        assert summary["known_regular_session_yahoo_missing"] == 1

        assert (
            row["Session_Classification"]
            == "NSE_REGULAR_SESSION_YAHOO_MISSING"
        )


def test_verified_calendar_exceptions_are_accepted():
    nse, yahoo = sample_data()

    special_row = nse.iloc[[0]].copy()
    special_row["Date"] = pd.Timestamp("2026-02-01")

    holiday_row = yahoo.iloc[[0]].copy()
    holiday_row["Date"] = pd.Timestamp("2026-01-15")

    nse = pd.concat(
        [nse, special_row],
        ignore_index=True,
    )

    yahoo = pd.concat(
        [yahoo, holiday_row],
        ignore_index=True,
    )

    summary, detail = compare_sources(
        nse, yahoo, "MARICO"
    )

    assert summary["nse_only_sessions"] == 1
    assert summary["yahoo_only_sessions"] == 1

    assert summary["known_special_session_yahoo_missing"] == 1
    assert summary["known_nse_holiday_yahoo_records"] == 1

    assert summary["expected_exception_sessions"] == 2

    assert summary["status"] == "PASS_WITH_EXPECTED_EXCEPTIONS"


def test_unknown_yahoo_only_date_remains_review():
    nse, yahoo = sample_data()

    extra_row = yahoo.iloc[[0]].copy()
    extra_row["Date"] = pd.Timestamp("2026-03-17")

    yahoo = pd.concat(
        [yahoo, extra_row],
        ignore_index=True,
    )

    summary, detail = compare_sources(
        nse, yahoo, "MARICO"
    )

    assert summary["unverified_yahoo_only_sessions"] == 1
    assert summary["status"] == "REVIEW"


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


def test_normalize_nse_security_archive_format(tmp_path):
    file_path = tmp_path / "marico_nse.csv"

    pd.DataFrame({
        "Symbol  ": ["MARICO"],
        "Series  ": ["EQ"],
        "Date  ": ["29-Oct-2026"],
        "Prev Close  ": ["769.65"],
        "Open Price  ": ["769.00"],
        "High Price  ": ["804.75"],
        "Low Price  ": ["764.70"],
        "Close Price  ": ["802.90"],
        "Total Traded Quantity  ": ["33,93,736"],
    }).to_csv(file_path, index=False)

    result = load_and_normalize(file_path)

    assert list(result.columns) == [
        "Date", "Open", "High", "Low", "Close", "Volume"
    ]

    assert len(result) == 1
    assert result.loc[0, "Date"] == pd.Timestamp("2026-10-29")
    assert result.loc[0, "Open"] == 769.00
    assert result.loc[0, "High"] == 804.75
    assert result.loc[0, "Low"] == 764.70
    assert result.loc[0, "Close"] == 802.90
    assert result.loc[0, "Volume"] == 3393736
    
