import pytest

from data.providers import nse_downloader
from data.providers import nse_index_downloader


class FakeResponse:

    def __init__(self, records):
        self.records = records

    def raise_for_status(self):
        pass

    def json(self):
        return {"data": self.records}


class FakeSession:

    def __init__(self, records):
        self.response = FakeResponse(records)

    def get(self, *args, **kwargs):
        return self.response


def equity_record(trading_date):
    return {
        "CH_TIMESTAMP": trading_date,
        "CH_OPENING_PRICE": 100,
        "CH_TRADE_HIGH_PRICE": 105,
        "CH_TRADE_LOW_PRICE": 99,
        "CH_CLOSING_PRICE": 104,
        "CH_TOT_TRADED_QTY": 1000,
    }


def index_record(trading_date):
    return {
        "EOD_TIMESTAMP": trading_date,
        "EOD_OPEN_INDEX_VAL": 25000,
        "EOD_HIGH_INDEX_VAL": 25100,
        "EOD_LOW_INDEX_VAL": 24900,
        "EOD_CLOSE_INDEX_VAL": 25050,
        "EOD_VOLUME": 1000,
    }


def test_equity_downloader_rejects_duplicate_dates(monkeypatch):

    records = [
        equity_record("2026-10-05"),
        equity_record("2026-10-05"),
    ]

    monkeypatch.setattr(
        nse_downloader,
        "create_nse_session",
        lambda: FakeSession(records),
    )

    with pytest.raises(
        ValueError,
        match="Duplicate dates found in NSE equity data",
    ):
        nse_downloader.download_equity_history(
            "MARICO",
            "2026-10-01",
            "2026-10-10",
        )


def test_equity_downloader_rejects_invalid_dates(monkeypatch):

    records = [
        equity_record("INVALID-DATE"),
    ]

    monkeypatch.setattr(
        nse_downloader,
        "create_nse_session",
        lambda: FakeSession(records),
    )

    with pytest.raises(
        ValueError,
        match="invalid or missing trading dates",
    ):
        nse_downloader.download_equity_history(
            "MARICO",
            "2026-10-01",
            "2026-10-10",
        )


def test_index_downloader_rejects_duplicate_dates(monkeypatch):

    records = [
        index_record("05-Oct-2026"),
        index_record("05-Oct-2026"),
    ]

    monkeypatch.setattr(
        nse_index_downloader,
        "create_nse_session",
        lambda: FakeSession(records),
    )

    with pytest.raises(
        ValueError,
        match="Duplicate dates found in NSE index data",
    ):
        nse_index_downloader.download_index_history(
            "NIFTY 50",
            "2026-10-01",
            "2026-10-10",
        )


def test_index_downloader_rejects_invalid_dates(monkeypatch):

    records = [
        index_record("INVALID-DATE"),
    ]

    monkeypatch.setattr(
        nse_index_downloader,
        "create_nse_session",
        lambda: FakeSession(records),
    )

    with pytest.raises(
        ValueError,
        match="invalid or missing trading dates",
    ):
        nse_index_downloader.download_index_history(
            "NIFTY 50",
            "2026-10-01",
            "2026-10-10",
        )