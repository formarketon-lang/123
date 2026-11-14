"""Official NSE CM trading calendar with archive-verified special sessions.

Regular sessions follow NSE's published equities schedule (Monday-Friday,
excluding the official CM holiday master). Weekend/holiday exceptions are
included only when the official NSE UDiFF final archive exists and validates.
"""

from __future__ import annotations

import hashlib
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlparse

import pandas as pd

from data.providers.nse_downloader import create_nse_session
from data.providers.nse_udiff_downloader import (
    NSEUdiFFArchiveNotFoundError,
    NSEUdiFFDownloadError,
    download_nse_cm_udiff_equity_bhavcopy,
)


NSE_CM_HOLIDAY_MASTER_URL = (
    "https://www.nseindia.com/api/holiday-master?type=trading"
)
NSE_OFFICIAL_DOMAINS = {"nseindia.com", "nseindia.in"}


class NSETradingCalendarError(RuntimeError):
    """Raised when official NSE calendar evidence cannot be verified."""


def _as_date(value: date | str) -> date:
    parsed = pd.Timestamp(value)
    if pd.isna(parsed):
        raise ValueError("A valid calendar date is required.")
    return parsed.date()


def fetch_nse_cm_trading_holidays(*, session=None, timeout: int = 30) -> dict:
    """Fetch the official NSE holiday master and preserve response provenance."""
    client = session or create_nse_session()
    response = None
    try:
        response = client.get(
            NSE_CM_HOLIDAY_MASTER_URL,
            headers={
                "Accept": "application/json, text/plain, */*",
                "Referer": "https://www.nseindia.com/resources/exchange-communication-holidays",
            },
            timeout=timeout,
        )
        fetched_at_utc = (
            datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        )
        response.raise_for_status()
    except Exception as exc:
        raise NSETradingCalendarError(
            f"Official NSE CM holiday master request failed: {type(exc).__name__}: {exc}"
        ) from exc

    final_url = getattr(response, "url", None) or NSE_CM_HOLIDAY_MASTER_URL
    parsed_url = urlparse(final_url)
    hostname = (parsed_url.hostname or "").lower()
    if (
        parsed_url.scheme != "https"
        or not (
            any(
                hostname == domain or hostname.endswith("." + domain)
                for domain in NSE_OFFICIAL_DOMAINS
            )
        )
    ):
        raise NSETradingCalendarError(
            "NSE holiday master response did not originate from the official NSE domain: "
            f"{final_url!r}"
        )

    raw_bytes = getattr(response, "content", b"")
    if not isinstance(raw_bytes, bytes) or not raw_bytes:
        raise NSETradingCalendarError("NSE holiday master response is empty.")

    try:
        payload = response.json()
    except Exception as exc:
        raise NSETradingCalendarError(
            "NSE holiday master response is not valid JSON."
        ) from exc

    rows = payload.get("CM") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        raise NSETradingCalendarError(
            "NSE holiday master does not contain the CM segment list."
        )

    holidays = []
    for row in rows:
        if not isinstance(row, dict):
            raise NSETradingCalendarError("NSE CM holiday entry is malformed.")
        raw_date = row.get("tradingDate")
        try:
            holiday_date = datetime.strptime(raw_date, "%d-%b-%Y").date()
        except (TypeError, ValueError) as exc:
            raise NSETradingCalendarError(
                f"Invalid NSE CM holiday date: {raw_date!r}"
            ) from exc
        holidays.append({
            "date": holiday_date.isoformat(),
            "weekday": row.get("weekDay"),
            "description": row.get("description"),
        })

    dates = [item["date"] for item in holidays]
    if len(dates) != len(set(dates)):
        raise NSETradingCalendarError("NSE CM holiday master contains duplicate dates.")

    return {
        "source": "NSE",
        "source_url": final_url,
        "source_sha256": hashlib.sha256(raw_bytes).hexdigest(),
        "source_size_bytes": len(raw_bytes),
        "fetched_at_utc": fetched_at_utc,
        "holidays": holidays,
        "calendar_status": "PASS",
    }


def discover_nse_cm_trading_sessions(
    start_date: date | str,
    end_date: date | str,
    *,
    session=None,
    timeout: int = 60,
    max_calendar_days: int = 370,
) -> dict:
    """Build a bounded NSE CM session calendar from official holiday evidence.

    Weekday sessions are Monday-Friday excluding the NSE CM holiday master.
    Every weekend or holiday exception is checked against the official final
    UDiFF archive. HTTP 404 means no archive/session; any other source failure
    makes the calendar UNAVAILABLE rather than silently assuming a closure.
    """
    start = _as_date(start_date)
    end = _as_date(end_date)
    if end < start:
        raise ValueError("end_date must not be earlier than start_date.")
    if (end - start).days + 1 > max_calendar_days:
        raise ValueError(
            f"Calendar range cannot exceed {max_calendar_days} calendar days."
        )

    client = session or create_nse_session()
    holiday_evidence = fetch_nse_cm_trading_holidays(
        session=client,
        timeout=timeout,
    )
    holiday_by_date = {
        item["date"]: item for item in holiday_evidence["holidays"]
    }

    all_dates = [
        start + timedelta(days=offset)
        for offset in range((end - start).days + 1)
    ]
    regular_sessions = [
        day for day in all_dates
        if day.weekday() < 5 and day.isoformat() not in holiday_by_date
    ]

    exception_candidates = [
        day for day in all_dates
        if day.weekday() >= 5 or day.isoformat() in holiday_by_date
    ]

    special_sessions = []
    exception_checks = []
    errors = []

    for candidate in exception_candidates:
        try:
            archive = download_nse_cm_udiff_equity_bhavcopy(
                candidate,
                session=client,
                timeout=timeout,
            )
        except NSEUdiFFArchiveNotFoundError:
            exception_checks.append({
                "date": candidate.isoformat(),
                "status": "NO_OFFICIAL_ARCHIVE",
            })
            continue
        except NSEUdiFFDownloadError as exc:
            errors.append({
                "date": candidate.isoformat(),
                "error_type": type(exc).__name__,
                "error": str(exc),
            })
            exception_checks.append({
                "date": candidate.isoformat(),
                "status": "SOURCE_UNAVAILABLE",
            })
            continue

        special_sessions.append({
            "date": candidate.isoformat(),
            "source_url": archive["source_url"],
            "source_filename": archive["source_filename"],
            "source_sha256": archive["sha256"],
            "fetched_at_utc": archive["fetched_at_utc"],
        })
        exception_checks.append({
            "date": candidate.isoformat(),
            "status": "OFFICIAL_ARCHIVE_VERIFIED",
        })

    session_dates = sorted({
        day.isoformat() for day in regular_sessions
    }.union(item["date"] for item in special_sessions))

    status = "UNAVAILABLE" if errors else "PASS"
    return {
        "calendar_status": status,
        "source": "NSE",
        "source_url": holiday_evidence["source_url"],
        "source_sha256": holiday_evidence["source_sha256"],
        "fetched_at_utc": holiday_evidence["fetched_at_utc"],
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "holiday_count": sum(
            start <= datetime.strptime(day, "%Y-%m-%d").date() <= end
            for day in holiday_by_date
        ),
        "regular_session_count": len(regular_sessions),
        "special_sessions": special_sessions,
        "exception_checks": exception_checks,
        "source_errors": errors,
        "session_dates": session_dates,
    }
