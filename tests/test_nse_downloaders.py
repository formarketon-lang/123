
import pytest

from data.providers import nse_downloader
from data.providers import nse_index_downloader


class FakeResponse:

    def __init__(self, records=None, text="", content_type="text/csv"):
        self.records = records or []
        self.text = text
        self.headers = {"content-type": content_type}

    def raise_for_status(self):
        pass

    def json(self):
        return {"data": self.records}


class FakeSession:

    def __init__(self, response=None):
        self.response = response or FakeResponse()
        self.headers = {}
        self.calls = []

    def get(self, url, *args, **kwargs):
        self.calls.append((url, kwargs))
        return self.response


def equity_csv(dates):
    rows = [
        "Date,Symbol,Series,Open Price,High Price,Low Price,Close Price,Total Traded Quantity"
    ]

    for trading_date in dates:
        rows.append(
            f"{trading_date},MARICO,EQ,100,105,99,104,1000"
        )

    return "\n".join(rows)


def index_record(trading_date):
    return {
        "EOD_TIMESTAMP": trading_date,
        "EOD_OPEN_INDEX_VAL": 25000,
        "EOD_HIGH_INDEX_VAL": 25100,
        "EOD_LOW_INDEX_VAL": 24900,
        "EOD_CLOSE_INDEX_VAL": 25050,
    }


def test_chrome_impersonation_and_session_warmup(monkeypatch):

    created = {}

    def fake_session_factory(**kwargs):
        created["kwargs"] = kwargs
        created["session"] = FakeSession()
        return created["session"]

    monkeypatch.setattr(
        nse_downloader.requests,
        "Session",
        fake_session_factory,
    )

    session = nse_downloader.create_nse_session()

    assert created["kwargs"] == {
        "impersonate": "chrome"
    }

    assert session is created["session"]

    requested_urls = [
        call[0] for call in session.calls
    ]

    assert requested_urls == [
        nse_downloader.NSE_BOOTSTRAP_URL
    ]

    assert session.headers["Accept"] == (
        "application/json, text/plain, */*"
    )

    assert (
        session.headers["Referer"]
        == nse_downloader.NSE_BOOTSTRAP_URL
    )


def test_equity_downloader_rejects_duplicate_dates(monkeypatch):

    response = FakeResponse(
        text=equity_csv([
            "05-Oct-2026",
            "05-Oct-2026",
        ])
    )

    monkeypatch.setattr(
        nse_downloader,
        "create_nse_session",
        lambda: FakeSession(response),
    )

    with pytest.raises(
        ValueError,
        match="Duplicate dates in NSE equity response",
    ):
        nse_downloader.download_equity_history(
            "MARICO",
            "2026-10-01",
            "2026-10-10",
        )


def test_equity_downloader_rejects_invalid_dates(monkeypatch):

    response = FakeResponse(
        text=equity_csv(["INVALID-DATE"])
    )

    monkeypatch.setattr(
        nse_downloader,
        "create_nse_session",
        lambda: FakeSession(response),
    )

    with pytest.raises(
        ValueError,
        match="Invalid dates in NSE equity response",
    ):
        nse_downloader.download_equity_history(
            "MARICO",
            "2026-10-01",
            "2026-10-10",
        )


def test_index_downloader_rejects_duplicate_dates(monkeypatch):

    response = FakeResponse(
        records=[
            index_record("05-Oct-2026"),
            index_record("05-Oct-2026"),
        ],
        content_type="application/json",
    )

    monkeypatch.setattr(
        nse_index_downloader,
        "create_nse_session",
        lambda: FakeSession(response),
    )

    with pytest.raises(
        ValueError,
        match="Duplicate NSE index trading dates",
    ):
        nse_index_downloader.download_index_history(
            "NIFTY 50",
            "2026-10-01",
            "2026-10-10",
        )


def test_index_downloader_rejects_invalid_dates(monkeypatch):

    response = FakeResponse(
        records=[
            index_record("INVALID-DATE"),
        ],
        content_type="application/json",
    )

    monkeypatch.setattr(
        nse_index_downloader,
        "create_nse_session",
        lambda: FakeSession(response),
    )

    with pytest.raises(
        ValueError,
        match="Invalid NSE index trading dates",
    ):
        nse_index_downloader.download_index_history(
            "NIFTY 50",
            "2026-10-01",
            "2026-10-10",
        )


def test_equity_downloader_uses_current_api(monkeypatch):

    response = FakeResponse(
        text=equity_csv(["05-Oct-2026"])
    )

    session = FakeSession(response)

    monkeypatch.setattr(
        nse_downloader,
        "create_nse_session",
        lambda: session,
    )

    result = nse_downloader.download_equity_history(
        "MARICO",
        "2026-10-01",
        "2026-10-10",
    )

    assert len(result) == 1
    assert result.iloc[0]["Close"] == 104

    url, kwargs = session.calls[0]

    assert url == nse_downloader.NSE_EQUITY_HISTORY_URL
    assert kwargs["params"]["symbol"] == "MARICO"


def test_index_downloader_uses_current_api(monkeypatch):

    response = FakeResponse(
        records=[index_record("05-Oct-2026")],
        content_type="application/json",
    )

    session = FakeSession(response)

    monkeypatch.setattr(
        nse_index_downloader,
        "create_nse_session",
        lambda: session,
    )

    result = nse_index_downloader.download_index_history(
        "NIFTY 50",
        "2026-10-01",
        "2026-10-10",
    )

    assert len(result) == 1
    assert result.iloc[0]["Source"] == "NSE"
    assert result.iloc[0]["Close"] == 25050

    url, kwargs = session.calls[0]

    assert url == nse_index_downloader.NSE_INDEX_URL
    assert kwargs["params"]["indexType"] == "NIFTY 50"
