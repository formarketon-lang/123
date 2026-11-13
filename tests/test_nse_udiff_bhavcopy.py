from io import BytesIO
from zipfile import ZipFile

import pandas as pd
import pytest

from data.providers.nse_udiff_bhavcopy import (
    NSEUdiFFError,
    normalize_nse_udiff_equity_bhavcopy,
    read_nse_udiff_bhavcopy,
)


COLUMN_MAP = {
    "Date": "TradeDate",
    "Symbol": "Ticker",
    "ISIN": "SecurityISIN",
    "Series": "SecuritySeries",
    "Previous Close": "PrevClose",
    "Current Close": "ClosePrice",
}

# Fixed test fixture only. Production callers must pass the real fetch time.
TEST_FETCHED_AT = "2026-11-13T17:00:00Z"


def sample_data():
    return pd.DataFrame({
        "TradeDate": [
            "2026-11-12",
            "2026-11-12",
            "2026-11-12",
        ],
        "Ticker": ["AAA", "BBB", "CCC"],
        "SecurityISIN": [
            "INE000A01010",
            "INE000B01010",
            "INE000C01010",
        ],
        "SecuritySeries": ["EQ", "EQ", "BE"],
        "PrevClose": ["100", "200", "50"],
        "ClosePrice": ["110", "190", "55"],
    })


def normalize(data=None, *, fetched_at_utc=TEST_FETCHED_AT):
    return normalize_nse_udiff_equity_bhavcopy(
        sample_data() if data is None else data,
        COLUMN_MAP,
        fetched_at_utc=fetched_at_utc,
    )


def make_zip(csv_data):
    buffer = BytesIO()

    with ZipFile(buffer, "w") as archive:
        archive.writestr(
            "bhavcopy.csv",
            csv_data.to_csv(index=False),
        )

    return buffer.getvalue()


def test_reads_one_csv_from_zip():
    result = read_nse_udiff_bhavcopy(
        make_zip(sample_data())
    )

    assert len(result) == 3
    assert "TradeDate" in result.columns


def test_rejects_empty_zip_content():
    with pytest.raises(NSEUdiFFError, match="empty"):
        read_nse_udiff_bhavcopy(b"")


def test_rejects_invalid_zip():
    with pytest.raises(NSEUdiFFError, match="Invalid"):
        read_nse_udiff_bhavcopy(b"not-a-zip")


def test_normalizes_eq_rows_to_breadth_format():
    result = normalize()

    assert result["Symbol"].tolist() == ["AAA", "BBB"]
    assert result["Source"].eq("NSE").all()
    assert result["Exchange"].eq("NSE").all()
    assert result["Timeframe"].eq("1d").all()
    assert result["Validation Status"].eq("PASS").all()
    assert result["Fallback Reason"].eq("").all()
    assert result["Fetched At UTC"].eq(TEST_FETCHED_AT).all()


def test_previous_and_current_close_are_normalized():
    result = normalize()

    assert result["Previous Close"].tolist() == [100, 200]
    assert result["Current Close"].tolist() == [110, 190]


def test_requires_fetch_timestamp():
    with pytest.raises(NSEUdiFFError, match="timestamp is required"):
        normalize_nse_udiff_equity_bhavcopy(
            sample_data(),
            COLUMN_MAP,
        )


def test_rejects_timezone_naive_fetch_timestamp():
    with pytest.raises(NSEUdiFFError, match="timezone-aware"):
        normalize(fetched_at_utc="2026-11-13T17:00:00")


def test_normalizes_fetch_timestamp_to_utc():
    result = normalize(
        fetched_at_utc="2026-11-13T22:30:00+05:30"
    )

    assert result["Fetched At UTC"].eq(
        "2026-11-13T17:00:00Z"
    ).all()


def test_rejects_invalid_fetch_timestamp():
    with pytest.raises(NSEUdiFFError, match="Invalid"):
        normalize(fetched_at_utc="not-a-timestamp")


def test_rejects_infinite_close_price():
    data = sample_data()
    data.loc[0, "ClosePrice"] = "inf"

    with pytest.raises(NSEUdiFFError, match="finite"):
        normalize(data)


def test_rejects_negative_infinite_previous_close():
    data = sample_data()
    data.loc[0, "PrevClose"] = "-inf"

    with pytest.raises(NSEUdiFFError, match="finite"):
        normalize(data)


def test_rejects_incomplete_verified_mapping():
    with pytest.raises(NSEUdiFFError, match="incomplete"):
        normalize_nse_udiff_equity_bhavcopy(
            sample_data(),
            {"Symbol": "Ticker"},
            fetched_at_utc=TEST_FETCHED_AT,
        )


def test_rejects_unmatched_raw_column():
    mapping = dict(COLUMN_MAP)
    mapping["Current Close"] = "UnknownClose"

    with pytest.raises(NSEUdiFFError, match="do not match"):
        normalize_nse_udiff_equity_bhavcopy(
            sample_data(),
            mapping,
            fetched_at_utc=TEST_FETCHED_AT,
        )


def test_rejects_invalid_isin():
    data = sample_data()
    data.loc[0, "SecurityISIN"] = "INVALID"

    with pytest.raises(NSEUdiFFError, match="invalid Indian ISIN"):
        normalize(data)


def test_rejects_duplicate_symbols():
    data = sample_data()
    data.loc[1, "Ticker"] = "AAA"

    with pytest.raises(NSEUdiFFError, match="Duplicate EQ symbols"):
        normalize(data)


def test_rejects_multiple_trade_dates():
    data = sample_data()
    data.loc[1, "TradeDate"] = "2026-11-11"

    with pytest.raises(NSEUdiFFError, match="exactly one"):
        normalize(data)


def test_rejects_zero_or_invalid_close():
    data = sample_data()
    data.loc[0, "ClosePrice"] = "0"

    with pytest.raises(NSEUdiFFError, match="greater than zero"):
        normalize(data)
