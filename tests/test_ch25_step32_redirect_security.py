
from types import SimpleNamespace

import pytest

from data.providers.exchange_snapshot_downloader import (
    SnapshotDownloadError,
    download_exchange_snapshot,
)


BASE_URL = (
    "https://nsearchives.nseindia.com/"
    "content/cm/snapshot.csv"
)


class FakeResponse:
    def __init__(
        self,
        status_code=200,
        url=BASE_URL,
        content=b"SYMBOL,SERIES\nRELIANCE,EQ\n",
        headers=None,
    ):
        self.status_code = status_code
        self.url = url
        self.content = content
        self.headers = headers or {
            "content-type": "text/csv"
        }
        self.history = []

    def raise_for_status(self):
        return None


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))

        if not self.responses:
            raise AssertionError(
                "Unexpected additional HTTP request"
            )

        return self.responses.pop(0)


def test_redirect_is_disabled_in_http_client(tmp_path):
    session = FakeSession([FakeResponse()])

    download_exchange_snapshot(
        "NSE",
        BASE_URL,
        tmp_path / "snapshot.csv",
        session=session,
    )

    assert len(session.calls) == 1
    assert session.calls[0][1]["allow_redirects"] is False


def test_rejects_external_redirect_before_request(tmp_path):
    redirect = FakeResponse(
        status_code=302,
        url=BASE_URL,
        headers={
            "Location": "https://evil.example/steal.csv"
        },
    )

    session = FakeSession([redirect])

    with pytest.raises(
        SnapshotDownloadError,
        match="Unapproved NSE source hostname",
    ):
        download_exchange_snapshot(
            "NSE",
            BASE_URL,
            tmp_path / "snapshot.csv",
            session=session,
        )

    # Only the original approved URL was requested.
    assert len(session.calls) == 1
    assert session.calls[0][0] == BASE_URL
    assert not (tmp_path / "snapshot.csv").exists()


def test_accepts_valid_relative_redirect(tmp_path):
    redirect = FakeResponse(
        status_code=302,
        url=BASE_URL,
        headers={"Location": "final.csv"},
    )

    final_url = (
        "https://nsearchives.nseindia.com/"
        "content/cm/final.csv"
    )

    final_response = FakeResponse(
        status_code=200,
        url=final_url,
    )

    session = FakeSession([redirect, final_response])

    result = download_exchange_snapshot(
        "NSE",
        BASE_URL,
        tmp_path / "snapshot.csv",
        session=session,
    )

    assert len(session.calls) == 2
    assert session.calls[0][0] == BASE_URL
    assert session.calls[1][0] == final_url
    assert all(
        call[1]["allow_redirects"] is False
        for call in session.calls
    )
    assert result["redirect_chain"] == [final_url]
    assert result["final_source_url"] == final_url


def test_rejects_redirect_loop(tmp_path):
    redirect = FakeResponse(
        status_code=302,
        url=BASE_URL,
        headers={"Location": BASE_URL},
    )

    session = FakeSession([redirect])

    with pytest.raises(
        SnapshotDownloadError,
        match="Redirect loop",
    ):
        download_exchange_snapshot(
            "NSE",
            BASE_URL,
            tmp_path / "snapshot.csv",
            session=session,
        )

    assert len(session.calls) == 1


def test_rejects_redirect_without_location(tmp_path):
    redirect = FakeResponse(
        status_code=302,
        url=BASE_URL,
        headers={},
    )

    session = FakeSession([redirect])

    with pytest.raises(
        SnapshotDownloadError,
        match="no Location header",
    ):
        download_exchange_snapshot(
            "NSE",
            BASE_URL,
            tmp_path / "snapshot.csv",
            session=session,
        )

    assert len(session.calls) == 1


def test_rejects_too_many_redirects(tmp_path):
    responses = []

    current_url = BASE_URL

    for number in range(6):
        next_url = (
            "https://nsearchives.nseindia.com/"
            f"content/cm/redirect-{number}.csv"
        )

        responses.append(
            FakeResponse(
                status_code=302,
                url=current_url,
                headers={"Location": next_url},
            )
        )
        current_url = next_url

    session = FakeSession(responses)

    with pytest.raises(
        SnapshotDownloadError,
        match="Maximum redirect limit",
    ):
        download_exchange_snapshot(
            "NSE",
            BASE_URL,
            tmp_path / "snapshot.csv",
            session=session,
        )

    assert len(session.calls) == 6
    assert not (tmp_path / "snapshot.csv").exists()


def test_rejects_http_downgrade_redirect(tmp_path):
    redirect = FakeResponse(
        status_code=302,
        url=BASE_URL,
        headers={
            "Location": "http://nsearchives.nseindia.com/file.csv"
        },
    )

    session = FakeSession([redirect])

    with pytest.raises(
        SnapshotDownloadError,
        match="HTTPS source URL is required",
    ):
        download_exchange_snapshot(
            "NSE",
            BASE_URL,
            tmp_path / "snapshot.csv",
            session=session,
        )

    assert len(session.calls) == 1
      
