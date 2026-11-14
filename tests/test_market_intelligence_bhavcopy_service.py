"""Tests for the guarded production NSE UDiFF breadth service."""

from io import BytesIO
from zipfile import ZipFile

import pandas as pd
import pytest

from data.providers.nse_udiff_downloader import (
    normalize_nse_cm_udiff_equity,
)
from services.market_intelligence import bhavcopy_service as service


FETCHED_AT = "2026-11-14T01:00:00Z"


def make_raw(include_unknown=False):
    symbols = ["AAA", "BBB", "CCC"]
    if include_unknown:
        symbols.append("DCMFINSERV")
    count = len(symbols)

    return pd.DataFrame({
        "TradDt": ["2026-11-13"] * count,
        "Sgmt": ["CM"] * count,
        "Src": ["NSE"] * count,
        "FinInstrmTp": ["STK"] * count,
        "ISIN": [
            f"INE000{chr(65 + i)}01010" for i in range(count)
        ],
        "TckrSymb": symbols,
        "SctySrs": ["EQ"] * count,
        "OpnPric": ["100"] * count,
        "HghPric": ["110"] * count,
        "LwPric": ["90"] * count,
        "ClsPric": ["105", "95", "100"] + (
            ["105"] if include_unknown else []
        ),
        "PrvsClsgPric": ["100"] * count,
        "TtlTradgVol": ["1000"] * count,
    })


def make_universe():
    return pd.DataFrame({
        "Symbol": ["AAA", "BBB", "CCC"],
        "ISIN": [
            "INE000A01010",
            "INE000B01010",
            "INE000C01010",
        ],
        "Series": ["EQ"] * 3,
        "Exchange": ["NSE"] * 3,
        "Source": ["NSE MII Security Master"] * 3,
        "Universe As Of Date": ["2026-11-13"] * 3,
        "Universe Verification Status": ["MII_DATED"] * 3,
    })


def make_archive():
    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        archive.writestr("bhavcopy.csv", "Symbol\nAAA\n")
    return buffer.getvalue()


def install_download(monkeypatch, include_unknown=False):
    raw = make_raw(include_unknown=include_unknown)
    normalized = normalize_nse_cm_udiff_equity(
        raw,
        trade_date="2026-11-13",
        fetched_at_utc=FETCHED_AT,
    )
    archive = make_archive()
    downloaded = {
        "raw_bytes": archive,
        "raw_data": raw,
        "normalized": normalized,
        "source": "NSE",
        "exchange": "NSE",
        "source_url": (
            "https://nsearchives.nseindia.com/content/cm/"
            "BhavCopy_NSE_CM_0_0_0_20261113_F_0000.csv.zip"
        ),
        "source_filename": (
            "BhavCopy_NSE_CM_0_0_0_20261113_F_0000.csv.zip"
        ),
        "fetched_at_utc": FETCHED_AT,
        "observation_date": "2026-11-13",
        "sha256": "a" * 64,
    }
    monkeypatch.setattr(
        service,
        "download_nse_cm_udiff_equity_bhavcopy",
        lambda *args, **kwargs: downloaded,
    )
    monkeypatch.setattr(
        service,
        "fetch_nse_equity_universe",
        lambda **kwargs: make_universe(),
    )


def test_production_service_uses_date_matched_mii_and_reports_review(
    monkeypatch,
):
    install_download(monkeypatch)

    result = service.analyze_nse_market_breadth_from_udiff(
        "2026-11-13"
    )

    assert result["source"] == "NSE"
    assert result["observation_date"] == "2026-11-13"
    assert result["reconciliation"]["identity_status"] == "PASS"
    assert result["reconciliation"]["coverage_status"] == "PASS"
    assert result["breadth"]["analysis_status"] == "PASS"
    assert result["audit"]["audit_status"] == "REVIEW"
    assert result["analysis_status"] == "REVIEW"


def test_unknown_udiff_symbol_is_excluded_and_keeps_review_status(
    monkeypatch,
):
    install_download(monkeypatch, include_unknown=True)

    result = service.analyze_nse_market_breadth_from_udiff(
        "2026-11-13"
    )

    assert result["reconciliation"]["identity_status"] == "REVIEW"
    assert result["reconciliation"]["unknown_symbols"] == [
        "DCMFINSERV"
    ]
    assert "DCMFINSERV" not in (
        result["verified_observations"]["Symbol"].tolist()
    )
    assert result["unverified_observations"]["Symbol"].tolist() == [
        "DCMFINSERV"
    ]
    assert result["breadth"]["analysis_status"] == "PASS"
    assert result["analysis_status"] == "REVIEW"


def test_service_rejects_legacy_undated_universe(monkeypatch):
    install_download(monkeypatch)
    universe = make_universe()
    universe["Universe Verification Status"] = "LEGACY_UNDATED"
    monkeypatch.setattr(
        service,
        "fetch_nse_equity_universe",
        lambda **kwargs: universe,
    )

    with pytest.raises(
        service.NSEBhavcopyServiceError,
        match="MII_DATED",
    ):
        service.analyze_nse_market_breadth_from_udiff(
            "2026-11-13"
        )


def test_service_rejects_wrong_mii_snapshot_date(monkeypatch):
    install_download(monkeypatch)
    universe = make_universe()
    universe["Universe As Of Date"] = "2026-11-12"
    monkeypatch.setattr(
        service,
        "fetch_nse_equity_universe",
        lambda **kwargs: universe,
    )

    with pytest.raises(
        service.NSEBhavcopyServiceError,
        match="must match",
    ):
        service.analyze_nse_market_breadth_from_udiff(
            "2026-11-13"
        )
