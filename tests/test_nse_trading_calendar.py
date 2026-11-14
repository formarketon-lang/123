import hashlib
import json

import pytest

from data.providers import nse_trading_calendar as calendar


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self.content = json.dumps(payload).encode("utf-8")
        self.status_code = status_code
        self.url = calendar.NSE_CM_HOLIDAY_MASTER_URL

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return json.loads(self.content)


class FakeSession:
    def __init__(self, response):
        self.response = response

    def get(self, url, **kwargs):
        assert url == calendar.NSE_CM_HOLIDAY_MASTER_URL
        return self.response


def test_official_cm_holiday_master_hashes_raw_response():
    payload = {
        "CM": [
            {
                "tradingDate": "26-Jan-2026",
                "weekDay": "Monday",
                "description": "Republic Day",
            }
        ]
    }
    response = FakeResponse(payload)
    result = calendar.fetch_nse_cm_trading_holidays(
        session=FakeSession(response)
    )

    assert result["calendar_status"] == "PASS"
    assert result["source"] == "NSE"
    assert result["source_sha256"] == hashlib.sha256(
        response.content
    ).hexdigest()
    assert result["holidays"][0]["date"] == "2026-01-26"


def test_calendar_excludes_official_holiday_and_adds_archive_verified_weekend(
    monkeypatch,
):
    payload = {
        "CM": [
            {
                "tradingDate": "26-Jan-2026",
                "weekDay": "Monday",
                "description": "Republic Day",
            }
        ]
    }
    session = FakeSession(FakeResponse(payload))

    def fake_archive(day, *, session, timeout):
        if day.isoformat() == "2026-01-31":
            raise calendar.NSEUdiFFArchiveNotFoundError("No archive")
        return {
            "source_url": "https://nsearchives.nseindia.com/example.zip",
            "source_filename": "example.zip",
            "sha256": "a" * 64,
            "fetched_at_utc": "2026-02-02T00:00:00Z",
        }

    monkeypatch.setattr(
        calendar,
        "download_nse_cm_udiff_equity_bhavcopy",
        fake_archive,
    )
    result = calendar.discover_nse_cm_trading_sessions(
        "2026-01-30",
        "2026-02-02",
        session=session,
    )

    assert result["calendar_status"] == "PASS"
    assert result["session_dates"] == [
        "2026-01-30",
        "2026-02-01",
        "2026-02-02",
    ]
    assert result["special_sessions"][0]["date"] == "2026-02-01"
    assert "2026-01-31" not in result["session_dates"]


def test_calendar_does_not_guess_when_special_session_archive_request_fails(
    monkeypatch,
):
    payload = {"CM": []}
    session = FakeSession(FakeResponse(payload))

    def failed_archive(day, *, session, timeout):
        raise calendar.NSEUdiFFDownloadError("NSE 403")

    monkeypatch.setattr(
        calendar,
        "download_nse_cm_udiff_equity_bhavcopy",
        failed_archive,
    )
    result = calendar.discover_nse_cm_trading_sessions(
        "2026-01-31",
        "2026-02-01",
        session=session,
    )

    assert result["calendar_status"] == "UNAVAILABLE"
    assert result["session_dates"] == []
    assert len(result["source_errors"]) == 2


def test_calendar_rejects_reversed_or_oversized_ranges():
    with pytest.raises(ValueError, match="earlier"):
        calendar.discover_nse_cm_trading_sessions(
            "2026-02-02",
            "2026-01-30",
            session=FakeSession(FakeResponse({"CM": []})),
        )

    with pytest.raises(ValueError, match="cannot exceed"):
        calendar.discover_nse_cm_trading_sessions(
            "2025-01-01",
            "2026-02-01",
            session=FakeSession(FakeResponse({"CM": []})),
        )
