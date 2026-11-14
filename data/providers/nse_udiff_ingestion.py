"""Production retrieval and guarded ingestion for NSE CM UDiFF Bhavcopy."""

from __future__ import annotations

from datetime import date, datetime, timezone

import pandas as pd
import requests

from data.providers.nse_udiff_bhavcopy import (
    normalize_nse_udiff_equity_bhavcopy,
    read_nse_udiff_bhavcopy,
)
from data.providers.nse_bhavcopy_provenance import (
    audit_nse_bhavcopy_provenance,
)


NSE_CM_UDIFF_URL_TEMPLATE = (
    "https://nsearchives.nseindia.com/content/cm/"
    "BhavCopy_NSE_CM_0_0_0_{date}_F_0000.csv.zip"
)

NSE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/zip,application/octet-stream,*/*",
    "Referer": "https://www.nseindia.com/",
}


class NSEUdiFFIngestionError(RuntimeError):
    """Raised when official NSE UDiFF retrieval or ingestion fails."""


def fetch_nse_udiff_bhavcopy(
    as_of_date: date,
    column_map: dict[str, str],
    universe: pd.DataFrame,
    *,
    timeout: int = 30,
    session: requests.Session | None = None,
) -> dict:
    """Fetch one NSE CM UDiFF archive and run guarded normalization/audit.

    The caller must supply a reviewed raw-to-standard column map.
    No guessed/default mapping is provided. The audit deliberately
    remains REVIEW until official schema mapping and authenticity
    have been independently approved.
    """

    if not isinstance(as_of_date, date) or isinstance(as_of_date, datetime):
        raise TypeError("as_of_date must be a datetime.date value.")

    if not isinstance(column_map, dict) or not column_map:
        raise ValueError("A reviewed UDiFF column_map is required.")

    if (
        not isinstance(timeout, int)
        or isinstance(timeout, bool)
        or timeout < 1
    ):
        raise ValueError("timeout must be a positive integer.")

    date_token = as_of_date.strftime("%Y%m%d")
    source_filename = (
        f"BhavCopy_NSE_CM_0_0_0_{date_token}_F_0000.csv.zip"
    )
    source_url = NSE_CM_UDIFF_URL_TEMPLATE.format(date=date_token)

    client = session or requests.Session()

    try:
        client.headers.update(NSE_HEADERS)
        response = client.get(source_url, timeout=timeout)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise NSEUdiFFIngestionError(
            "NSE CM UDiFF archive retrieval failed: "
            f"{type(exc).__name__}: {exc}"
        ) from exc

    # Capture only after the complete HTTP response was received.
    fetched_at_utc = datetime.now(timezone.utc).isoformat().replace(
        "+00:00", "Z"
    )
    archive_bytes = response.content

    try:
        raw = read_nse_udiff_bhavcopy(archive_bytes)
        normalized = normalize_nse_udiff_equity_bhavcopy(
            raw,
            column_map,
            fetched_at_utc=fetched_at_utc,
        )
        audit = audit_nse_bhavcopy_provenance(
            bhavcopy=normalized,
            universe=universe,
            source_bytes=archive_bytes,
            source_filename=source_filename,
        )
    except Exception as exc:
        raise NSEUdiFFIngestionError(
            "NSE CM UDiFF archive was retrieved but failed "
            f"normalization or audit: {type(exc).__name__}: {exc}"
        ) from exc

    return {
        "source_url": source_url,
        "source_filename": source_filename,
        "fetched_at_utc": fetched_at_utc,
        "raw_data": raw,
        "normalized_data": normalized,
        "audit": audit,
        "ingestion_status": (
            "REVIEW"
            if audit["audit_status"] != "PASS"
            else "PASS"
        ),
    }
