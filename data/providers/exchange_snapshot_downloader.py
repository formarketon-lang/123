"""Verified official exchange snapshot downloader.

NSE downloads are restricted to the verified NSE archive hostname.
BSE remains disabled until TLP access authorization is verified.

Redirect targets are validated before requests are sent.
Original downloaded bytes and provenance metadata are retained.
GZIP files are fully decompressed and integrity-checked before storage.
"""

from __future__ import annotations

import gzip
import hashlib
import io
import json
import zlib

from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests


NSE_ALLOWED_HOSTS = {"nsearchives.nseindia.com"}

BSE_DOWNLOAD_ENABLED = False
BSE_DOCUMENTED_HOSTS = {"member.bseindia.com"}

ALLOWED_NSE_SUFFIXES = (".csv", ".csv.gz", ".gz")

REDIRECT_STATUS_CODES = {301, 302, 303, 307, 308}
MAX_REDIRECTS = 5

MAX_UNCOMPRESSED_BYTES = 256 * 1024 * 1024
GZIP_READ_CHUNK_BYTES = 64 * 1024


class SnapshotDownloadError(RuntimeError):
    """Raised when a snapshot fails source or integrity validation."""


def _validate_url(url: str, exchange: str) -> str:
    if not isinstance(url, str) or not url.strip():
        raise SnapshotDownloadError("Source URL is required.")

    try:
        parsed = urlparse(url.strip())

        if parsed.scheme.lower() != "https":
            raise SnapshotDownloadError("HTTPS source URL is required.")

        if not parsed.hostname:
            raise SnapshotDownloadError("Source URL has no hostname.")

        if parsed.username or parsed.password:
            raise SnapshotDownloadError(
                "Credentials in source URLs are not permitted."
            )

        if parsed.port not in (None, 443):
            raise SnapshotDownloadError("Unapproved source URL port.")

        if parsed.fragment:
            raise SnapshotDownloadError(
                "Source URL fragments are not permitted."
            )

        host = parsed.hostname.lower().rstrip(".")

    except ValueError as exc:
        raise SnapshotDownloadError("Malformed source URL.") from exc

    if exchange == "NSE":
        allowed = NSE_ALLOWED_HOSTS
    elif exchange == "BSE":
        if not BSE_DOWNLOAD_ENABLED:
            raise SnapshotDownloadError(
                "BSE download is disabled: TLP access "
                "authorization has not been verified."
            )
        allowed = BSE_DOCUMENTED_HOSTS
    else:
        raise SnapshotDownloadError(
            f"Unsupported exchange: {exchange}"
        )

    if host not in allowed:
        raise SnapshotDownloadError(
            f"Unapproved {exchange} source hostname: {host}"
        )

    return url.strip()


def _validate_filename(filename: str, exchange: str) -> str:
    if not isinstance(filename, str):
        raise SnapshotDownloadError("Filename must be text.")

    value = filename.strip()

    if (
        not value
        or value in {".", ".."}
        or "/" in value
        or "\\" in value
        or Path(value).name != value
        or any(ord(char) < 32 for char in value)
    ):
        raise SnapshotDownloadError("Unsafe snapshot filename.")

    if exchange == "NSE" and not value.lower().endswith(
        ALLOWED_NSE_SUFFIXES
    ):
        raise SnapshotDownloadError(
            "NSE snapshot must be a CSV or CSV.GZ file."
        )

    return value


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _validate_gzip_content(
    content: bytes,
    max_uncompressed_bytes: int | None = None,
) -> int:
    """Fully decompress and validate GZIP CRC, size and EOF."""

    if not isinstance(content, bytes) or content[:2] != b"\x1f\x8b":
        raise SnapshotDownloadError(
            "Expected gzip snapshot bytes were not received."
        )

    if max_uncompressed_bytes is None:
        max_uncompressed_bytes = MAX_UNCOMPRESSED_BYTES

    if (
        not isinstance(max_uncompressed_bytes, int)
        or isinstance(max_uncompressed_bytes, bool)
        or max_uncompressed_bytes <= 0
    ):
        raise SnapshotDownloadError(
            "Invalid GZIP uncompressed size limit."
        )

    total_size = 0

    try:
        with gzip.GzipFile(
            fileobj=io.BytesIO(content),
            mode="rb",
        ) as stream:

            while True:
                remaining = max_uncompressed_bytes - total_size

                # Read one extra byte when at the limit so oversized
                # streams are detected without unbounded decompression.
                read_size = min(
                    GZIP_READ_CHUNK_BYTES,
                    remaining + 1,
                )

                chunk = stream.read(read_size)

                if not chunk:
                    break

                total_size += len(chunk)

                if total_size > max_uncompressed_bytes:
                    raise SnapshotDownloadError(
                        "GZIP content exceeds the configured safety limit."
                    )

    except SnapshotDownloadError:
        raise
    except (OSError, EOFError, zlib.error) as exc:
        raise SnapshotDownloadError(
            f"GZIP integrity validation failed: {exc}"
        ) from exc

    if total_size == 0:
        raise SnapshotDownloadError(
            "GZIP content contains no uncompressed data."
        )

    return total_size


def _request_without_unsafe_redirects(
    client,
    initial_url: str,
    exchange: str,
    timeout: int,
):
    """Follow redirects manually, validating every target first."""

    current_url = initial_url
    visited = {current_url}
    redirect_chain = []

    for redirect_number in range(MAX_REDIRECTS + 1):
        try:
            response = client.get(
                current_url,
                timeout=timeout,
                allow_redirects=False,
            )
        except requests.RequestException as exc:
            raise SnapshotDownloadError(
                f"{exchange} snapshot download failed: "
                f"{type(exc).__name__}: {exc}"
            ) from exc

        status_code = getattr(response, "status_code", 200)

        if status_code not in REDIRECT_STATUS_CODES:
            try:
                response.raise_for_status()
            except requests.RequestException as exc:
                raise SnapshotDownloadError(
                    f"{exchange} snapshot HTTP error: {exc}"
                ) from exc

            for previous in getattr(response, "history", []):
                previous_url = _validate_url(previous.url, exchange)

                if previous_url not in redirect_chain:
                    redirect_chain.append(previous_url)

            final_url = _validate_url(response.url, exchange)

            return response, redirect_chain, final_url

        if redirect_number >= MAX_REDIRECTS:
            raise SnapshotDownloadError(
                "Maximum redirect limit exceeded."
            )

        location = response.headers.get("Location")

        if not location:
            raise SnapshotDownloadError(
                "Redirect response has no Location header."
            )

        next_url = urljoin(current_url, location)
        next_url = _validate_url(next_url, exchange)

        if next_url in visited:
            raise SnapshotDownloadError("Redirect loop detected.")

        visited.add(next_url)
        redirect_chain.append(next_url)
        current_url = next_url

    raise SnapshotDownloadError("Maximum redirect limit exceeded.")


def download_exchange_snapshot(
    exchange: str,
    source_url: str,
    destination: str | Path,
    *,
    session: requests.Session | None = None,
    timeout: int = 45,
) -> dict:
    """Download an authorized snapshot with integrity validation."""

    exchange = str(exchange).strip().upper()

    initial_url = _validate_url(source_url, exchange)

    target = Path(destination)
    filename = _validate_filename(target.name, exchange)

    if (
        not isinstance(timeout, int)
        or isinstance(timeout, bool)
        or timeout <= 0
    ):
        raise SnapshotDownloadError(
            "Timeout must be a positive integer."
        )

    if target.exists():
        raise SnapshotDownloadError(
            f"Refusing to overwrite existing snapshot: {target}"
        )

    client = session or requests.Session()

    response, redirect_chain, final_url = (
        _request_without_unsafe_redirects(
            client,
            initial_url,
            exchange,
            timeout,
        )
    )

    content = response.content

    if not content:
        raise SnapshotDownloadError(
            "Downloaded snapshot is empty."
        )

    content_type = response.headers.get(
        "content-type", ""
    ).lower()

    if (
        "text/html" in content_type
        or content.lstrip().lower().startswith(
            (b"<!doctype html", b"<html")
        )
    ):
        raise SnapshotDownloadError(
            "Exchange returned HTML instead of a snapshot file."
        )

    gzip_integrity_validated = False
    uncompressed_size_bytes = None

    if filename.lower().endswith(".gz"):
        uncompressed_size_bytes = _validate_gzip_content(content)
        gzip_integrity_validated = True

    target.parent.mkdir(parents=True, exist_ok=True)

    try:
        with target.open("xb") as handle:
            handle.write(content)
    except OSError as exc:
        raise SnapshotDownloadError(
            f"Unable to retain original snapshot: {exc}"
        ) from exc

    metadata = {
        "exchange": exchange,
        "status": "DOWNLOADED",
        "source_url": initial_url,
        "redirect_chain": redirect_chain,
        "final_source_url": final_url,
        "filename": filename,
        "downloaded_at_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "size_bytes": len(content),
        "sha256": _sha256(content),
        "original_bytes_retained": True,
        "redirects_validated": True,
        "sector_mapping_activated": False,
    }

    if filename.lower().endswith(".gz"):
        metadata["gzip_integrity_validated"] = (
            gzip_integrity_validated
        )
        metadata["uncompressed_size_bytes"] = (
            uncompressed_size_bytes
        )

    metadata_path = target.with_name(
        target.name + ".provenance.json"
    )

    try:
        with metadata_path.open(
            "x", encoding="utf-8"
        ) as handle:
            json.dump(
                metadata,
                handle,
                indent=2,
                ensure_ascii=False,
            )
    except OSError as exc:
        metadata["status"] = "PROVENANCE_WRITE_FAILED"
        raise SnapshotDownloadError(
            "Snapshot retained, but provenance metadata failed: "
            f"{exc}"
        ) from exc

    return metadata
        
