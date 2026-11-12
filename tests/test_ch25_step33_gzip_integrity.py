
import gzip
import zlib

import pytest

from data.providers.exchange_snapshot_downloader import (
    SnapshotDownloadError,
    download_exchange_snapshot,
)


SOURCE_URL = (
    "https://nsearchives.nseindia.com/"
    "content/cm/snapshot.csv.gz"
)


class FakeResponse:
    def __init__(self, content):
        self.status_code = 200
        self.url = SOURCE_URL
        self.content = content
        self.headers = {
            "content-type": "application/gzip"
        }
        self.history = []

    def raise_for_status(self):
        return None


class FakeSession:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.response


def make_gzip(data):
    return gzip.compress(data)


def test_accepts_valid_gzip_and_records_uncompressed_size(
    tmp_path,
):
    original = b"SYMBOL,SERIES\nRELIANCE,EQ\n"
    compressed = make_gzip(original)

    session = FakeSession(FakeResponse(compressed))
    destination = tmp_path / "snapshot.csv.gz"

    result = download_exchange_snapshot(
        "NSE",
        SOURCE_URL,
        destination,
        session=session,
    )

    assert destination.read_bytes() == compressed
    assert result["status"] == "DOWNLOADED"
    assert result["original_bytes_retained"] is True
    assert result["gzip_integrity_validated"] is True
    assert result["uncompressed_size_bytes"] == len(original)
    assert result["size_bytes"] == len(compressed)


def test_rejects_corrupted_gzip_crc(tmp_path):
    compressed = bytearray(
        make_gzip(b"SYMBOL,SERIES\nRELIANCE,EQ\n")
    )

    compressed[-8] ^= 0xFF

    session = FakeSession(
        FakeResponse(bytes(compressed))
    )

    with pytest.raises(
        SnapshotDownloadError,
        match="GZIP integrity validation failed",
    ):
        download_exchange_snapshot(
            "NSE",
            SOURCE_URL,
            tmp_path / "snapshot.csv.gz",
            session=session,
        )

    assert not (tmp_path / "snapshot.csv.gz").exists()


def test_rejects_truncated_gzip(tmp_path):
    compressed = make_gzip(
        b"SYMBOL,SERIES\nRELIANCE,EQ\n"
    )

    truncated = compressed[:-5]

    session = FakeSession(
        FakeResponse(truncated)
    )

    with pytest.raises(
        SnapshotDownloadError,
        match="GZIP integrity validation failed",
    ):
        download_exchange_snapshot(
            "NSE",
            SOURCE_URL,
            tmp_path / "snapshot.csv.gz",
            session=session,
        )

    assert not (tmp_path / "snapshot.csv.gz").exists()


def test_rejects_empty_gzip_payload(tmp_path):
    compressed = make_gzip(b"")

    session = FakeSession(
        FakeResponse(compressed)
    )

    with pytest.raises(
        SnapshotDownloadError,
        match="contains no uncompressed data",
    ):
        download_exchange_snapshot(
            "NSE",
            SOURCE_URL,
            tmp_path / "snapshot.csv.gz",
            session=session,
        )


def test_rejects_gzip_decompression_bomb_size(tmp_path):
    from data.providers import exchange_snapshot_downloader

    compressed = make_gzip(b"A" * 1024)

    monkeypatch_limit = 100
    original_limit = (
        exchange_snapshot_downloader.MAX_UNCOMPRESSED_BYTES
    )

    exchange_snapshot_downloader.MAX_UNCOMPRESSED_BYTES = (
        monkeypatch_limit
    )

    try:
        session = FakeSession(
            FakeResponse(compressed)
        )

        with pytest.raises(
            SnapshotDownloadError,
            match="exceeds the configured safety limit",
        ):
            download_exchange_snapshot(
                "NSE",
                SOURCE_URL,
                tmp_path / "snapshot.csv.gz",
                session=session,
            )

        assert not (
            tmp_path / "snapshot.csv.gz"
        ).exists()

    finally:
        exchange_snapshot_downloader.MAX_UNCOMPRESSED_BYTES = (
            original_limit
        )


def test_rejects_non_gzip_content(tmp_path):
    session = FakeSession(
        FakeResponse(b"NOT-GZIP-DATA")
    )

    with pytest.raises(
        SnapshotDownloadError,
        match="Expected gzip snapshot bytes",
    ):
        download_exchange_snapshot(
            "NSE",
            SOURCE_URL,
            tmp_path / "snapshot.csv.gz",
            session=session,
        )
      
import gzip
import zlib

import pytest

from data.providers.exchange_snapshot_downloader import (
    SnapshotDownloadError,
    download_exchange_snapshot,
)


SOURCE_URL = (
    "https://nsearchives.nseindia.com/"
    "content/cm/snapshot.csv.gz"
)


class FakeResponse:
    def __init__(self, content):
        self.status_code = 200
        self.url = SOURCE_URL
        self.content = content
        self.headers = {
            "content-type": "application/gzip"
        }
        self.history = []

    def raise_for_status(self):
        return None


class FakeSession:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.response


def make_gzip(data):
    return gzip.compress(data)


def test_accepts_valid_gzip_and_records_uncompressed_size(
    tmp_path,
):
    original = b"SYMBOL,SERIES\nRELIANCE,EQ\n"
    compressed = make_gzip(original)

    session = FakeSession(FakeResponse(compressed))
    destination = tmp_path / "snapshot.csv.gz"

    result = download_exchange_snapshot(
        "NSE",
        SOURCE_URL,
        destination,
        session=session,
    )

    assert destination.read_bytes() == compressed
    assert result["status"] == "DOWNLOADED"
    assert result["original_bytes_retained"] is True
    assert result["gzip_integrity_validated"] is True
    assert result["uncompressed_size_bytes"] == len(original)
    assert result["size_bytes"] == len(compressed)


def test_rejects_corrupted_gzip_crc(tmp_path):
    compressed = bytearray(
        make_gzip(b"SYMBOL,SERIES\nRELIANCE,EQ\n")
    )

    compressed[-8] ^= 0xFF

    session = FakeSession(
        FakeResponse(bytes(compressed))
    )

    with pytest.raises(
        SnapshotDownloadError,
        match="GZIP integrity validation failed",
    ):
        download_exchange_snapshot(
            "NSE",
            SOURCE_URL,
            tmp_path / "snapshot.csv.gz",
            session=session,
        )

    assert not (tmp_path / "snapshot.csv.gz").exists()


def test_rejects_truncated_gzip(tmp_path):
    compressed = make_gzip(
        b"SYMBOL,SERIES\nRELIANCE,EQ\n"
    )

    truncated = compressed[:-5]

    session = FakeSession(
        FakeResponse(truncated)
    )

    with pytest.raises(
        SnapshotDownloadError,
        match="GZIP integrity validation failed",
    ):
        download_exchange_snapshot(
            "NSE",
            SOURCE_URL,
            tmp_path / "snapshot.csv.gz",
            session=session,
        )

    assert not (tmp_path / "snapshot.csv.gz").exists()


def test_rejects_empty_gzip_payload(tmp_path):
    compressed = make_gzip(b"")

    session = FakeSession(
        FakeResponse(compressed)
    )

    with pytest.raises(
        SnapshotDownloadError,
        match="contains no uncompressed data",
    ):
        download_exchange_snapshot(
            "NSE",
            SOURCE_URL,
            tmp_path / "snapshot.csv.gz",
            session=session,
        )


def test_rejects_gzip_decompression_bomb_size(tmp_path):
    from data.providers import exchange_snapshot_downloader

    compressed = make_gzip(b"A" * 1024)

    monkeypatch_limit = 100
    original_limit = (
        exchange_snapshot_downloader.MAX_UNCOMPRESSED_BYTES
    )

    exchange_snapshot_downloader.MAX_UNCOMPRESSED_BYTES = (
        monkeypatch_limit
    )

    try:
        session = FakeSession(
            FakeResponse(compressed)
        )

        with pytest.raises(
            SnapshotDownloadError,
            match="exceeds the configured safety limit",
        ):
            download_exchange_snapshot(
                "NSE",
                SOURCE_URL,
                tmp_path / "snapshot.csv.gz",
                session=session,
            )

        assert not (
            tmp_path / "snapshot.csv.gz"
        ).exists()

    finally:
        exchange_snapshot_downloader.MAX_UNCOMPRESSED_BYTES = (
            original_limit
        )


def test_rejects_non_gzip_content(tmp_path):
    session = FakeSession(
        FakeResponse(b"NOT-GZIP-DATA")
    )

    with pytest.raises(
        SnapshotDownloadError,
        match="Expected gzip snapshot bytes",
    ):
        download_exchange_snapshot(
            "NSE",
            SOURCE_URL,
            tmp_path / "snapshot.csv.gz",
            session=session,
        )
      
