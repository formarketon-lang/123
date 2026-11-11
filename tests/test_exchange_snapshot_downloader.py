from types import SimpleNamespace

import pytest

from data.providers.exchange_snapshot_downloader import (
    SnapshotDownloadError,
    download_exchange_snapshot,
)


NSE_URL = (
    "https://nsearchives.nseindia.com/"
    "content/cm/NSE_CM_security_20261111.csv.gz"
)


class FakeSession:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.response


def make_response(
    content=b"SYMBOL,SERIES\nRELIANCE,EQ\n",
    url=NSE_URL,
    headers=None,
    history=None,
):
    return SimpleNamespace(
        content=content,
        url=url,
        headers=headers or {"content-type": "text/csv"},
        history=history or [],
        raise_for_status=lambda: None,
    )


def test_downloads_nse_snapshot_and_writes_provenance(tmp_path):
    response = make_response()
    session = FakeSession(response)
    destination = tmp_path / "nse_snapshot.csv"

    result = download_exchange_snapshot(
        "NSE",
        NSE_URL,
        destination,
        session=session,
    )

    assert destination.read_bytes() == response.content
    assert result["exchange"] == "NSE"
    assert result["status"] == "DOWNLOADED"
    assert result["original_bytes_retained"] is True
    assert result["redirects_validated"] is True
    assert result["final_source_url"] == NSE_URL
    assert result["size_bytes"] == len(response.content)
    assert len(result["sha256"]) == 64
    assert result["sector_mapping_activated"] is False

    metadata_path = destination.with_name(
        destination.name + ".provenance.json"
    )
    assert metadata_path.exists()


@pytest.mark.parametrize(
    "url",
    [
        "http://nsearchives.nseindia.com/file.csv",
        "https://evil.example/file.csv",
        "https://user@nsearchives.nseindia.com/file.csv",
        "https://nsearchives.nseindia.com:8443/file.csv",
        "https://nsearchives.nseindia.com/file.csv#fragment",
    ],
)
def test_rejects_unapproved_nse_urls(tmp_path, url):
    session = FakeSession(make_response())

    with pytest.raises(SnapshotDownloadError):
        download_exchange_snapshot(
            "NSE",
            url,
            tmp_path / "snapshot.csv",
            session=session,
        )

    assert session.calls == []


def test_rejects_unsupported_exchange(tmp_path):
    with pytest.raises(
        SnapshotDownloadError,
        match="Unsupported exchange",
    ):
        download_exchange_snapshot(
            "BOTH",
            NSE_URL,
            tmp_path / "snapshot.csv",
        )


def test_bse_download_remains_disabled(tmp_path):
    with pytest.raises(
        SnapshotDownloadError,
        match="BSE download is disabled",
    ):
        download_exchange_snapshot(
            "BSE",
            "https://member.bseindia.com/file.csv",
            tmp_path / "bse_snapshot.csv",
        )


def test_rejects_html_response(tmp_path):
    response = make_response(
        content=b"<html><body>Access denied</body></html>",
        headers={"content-type": "text/html"},
    )

    with pytest.raises(
        SnapshotDownloadError,
        match="HTML instead of a snapshot",
    ):
        download_exchange_snapshot(
            "NSE",
            NSE_URL,
            tmp_path / "snapshot.csv",
            session=FakeSession(response),
        )


def test_rejects_empty_response(tmp_path):
    response = make_response(content=b"")

    with pytest.raises(
        SnapshotDownloadError,
        match="empty",
    ):
        download_exchange_snapshot(
            "NSE",
            NSE_URL,
            tmp_path / "snapshot.csv",
            session=FakeSession(response),
        )


def test_rejects_gzip_without_gzip_signature(tmp_path):
    response = make_response(
        content=b"not-a-gzip-file",
    )

    with pytest.raises(
        SnapshotDownloadError,
        match="gzip snapshot bytes",
    ):
        download_exchange_snapshot(
            "NSE",
            NSE_URL,
            tmp_path / "snapshot.csv.gz",
            session=FakeSession(response),
        )


def test_refuses_to_overwrite_existing_snapshot(tmp_path):
    destination = tmp_path / "snapshot.csv"
    destination.write_bytes(b"existing-data")

    session = FakeSession(make_response())

    with pytest.raises(
        SnapshotDownloadError,
        match="Refusing to overwrite",
    ):
        download_exchange_snapshot(
            "NSE",
            NSE_URL,
            destination,
            session=session,
        )

    assert destination.read_bytes() == b"existing-data"
    assert session.calls == []


def test_rejects_unapproved_redirect_url(tmp_path):
    response = make_response(
        url="https://evil.example/final.csv",
        history=[
            SimpleNamespace(
                url="https://evil.example/redirect.csv"
            )
        ],
    )

    destination = tmp_path / "snapshot.csv"

    with pytest.raises(
        SnapshotDownloadError,
        match="Unapproved NSE source hostname",
    ):
        download_exchange_snapshot(
            "NSE",
            NSE_URL,
            destination,
            session=FakeSession(response),
        )

    assert not destination.exists()


def test_records_valid_redirect_chain(tmp_path):
    redirect_url = (
        "https://nsearchives.nseindia.com/"
        "content/cm/redirect.csv"
    )
    final_url = (
        "https://nsearchives.nseindia.com/"
        "content/cm/final.csv"
    )
    response = make_response(
        url=final_url,
        history=[SimpleNamespace(url=redirect_url)],
    )

    result = download_exchange_snapshot(
        "NSE",
        NSE_URL,
        tmp_path / "snapshot.csv",
        session=FakeSession(response),
    )

    assert result["redirect_chain"] == [redirect_url]
    assert result["final_source_url"] == final_url


def test_rejects_invalid_timeout(tmp_path):
    with pytest.raises(
        SnapshotDownloadError,
        match="positive integer",
    ):
        download_exchange_snapshot(
            "NSE",
            NSE_URL,
            tmp_path / "snapshot.csv",
            timeout=0,
        )


def test_rejects_unsafe_filename(tmp_path):
    destination = tmp_path / "bad\nname.csv"

    with pytest.raises(
        SnapshotDownloadError,
        match="Unsafe snapshot filename",
    ):
        download_exchange_snapshot(
            "NSE",
            NSE_URL,
            destination,
            session=FakeSession(make_response()),
        )


def test_rejects_non_csv_nse_filename(tmp_path):
    with pytest.raises(
        SnapshotDownloadError,
        match="CSV or CSV.GZ",
    ):
        download_exchange_snapshot(
            "NSE",
            NSE_URL,
            tmp_path / "snapshot.json",
            session=FakeSession(make_response()),
  )
      
