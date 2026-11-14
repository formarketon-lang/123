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


def make_raw(include_unknown=False, include_mismatch=False):
    symbols = ["AAA", "BBB", "CCC"]
    if include_unknown:
        symbols.append("DCMFINSERV")
    if include_mismatch:
        symbols.append("BNAGROCHEM")
    count = len(symbols)
    isins = [
        f"INE000{chr(65 + i)}01010" for i in range(count)
    ]
    if include_mismatch:
        isins[-1] = "INE00HZ01011"

    return pd.DataFrame({
        "TradDt": ["2026-11-13"] * count,
        "Sgmt": ["CM"] * count,
        "Src": ["NSE"] * count,
        "FinInstrmTp": ["STK"] * count,
        "FinInstrmId": [str(i + 1) for i in range(count)],
        "SsnId": ["F1"] * count,
        "ISIN": isins,
        "TckrSymb": symbols,
        "SctySrs": ["EQ"] * count,
        "OpnPric": ["100"] * count,
        "HghPric": ["110"] * count,
        "LwPric": ["90"] * count,
        "ClsPric": (
            ["105", "95", "100"]
            + (["105"] if include_unknown else [])
            + (["105"] if include_mismatch else [])
        ),
        "PrvsClsgPric": ["100"] * count,
        "TtlTradgVol": ["1000"] * count,
    })


def make_universe(include_mismatch=False):
    symbols = ["AAA", "BBB", "CCC"]
    isins = [
        "INE000A01010",
        "INE000B01010",
        "INE000C01010",
    ]
    if include_mismatch:
        symbols.append("BNAGROCHEM")
        isins.append("INE00HZ01029")
    frame = pd.DataFrame({
        "Symbol": symbols,
        "Instrument ID": [str(i + 1) for i in range(len(symbols))],
        "ISIN": isins,
        "Series": ["EQ"] * len(symbols),
        "Exchange": ["NSE"] * len(symbols),
        "Source": ["NSE MII Security Master"] * len(symbols),
        "Universe As Of Date": ["2026-11-13"] * len(symbols),
        "Universe Verification Status": ["MII_DATED"] * len(symbols),
    })
    frame.attrs["source_provenance"] = {
        "source": "NSE",
        "source_url": "https://nsearchives.nseindia.com/content/cm/NSE_CM_security_13112026.csv.gz",
        "source_filename": "NSE_CM_security_13112026.csv.gz",
        "source_sha256": "a" * 64,
        "fetched_at_utc": FETCHED_AT,
        "snapshot_date": "2026-11-13",
        "published_at_utc": "2026-11-13T00:00:00Z",
        "point_in_time_status": "PASS",
        "verification_status": "MII_DATED",
    }
    return frame


def make_archive():
    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        archive.writestr(
            "bhavcopy.csv",
            make_raw().to_csv(index=False),
        )
    return buffer.getvalue()


def install_download(
    monkeypatch,
    include_unknown=False,
    include_mismatch=False,
):
    raw = make_raw(
        include_unknown=include_unknown,
        include_mismatch=include_mismatch,
    )
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
        lambda **kwargs: make_universe(
            include_mismatch=include_mismatch
        ),
    )


def test_production_service_uses_date_matched_mii_and_passes_schema_audit(
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
    assert result["audit"]["schema_mapping_status"] == "PASS"
    assert result["audit"]["raw_schema_status"] == "PASS"
    assert result["audit"]["audit_status"] == "PASS"
    assert result["analysis_status"] == "PASS"



def test_unknown_mii_publication_timestamp_keeps_point_in_time_review(monkeypatch):
    install_download(monkeypatch)
    universe = make_universe()
    universe.attrs["source_provenance"]["published_at_utc"] = None
    universe.attrs["source_provenance"]["point_in_time_status"] = "REVIEW"
    monkeypatch.setattr(service, "fetch_nse_equity_universe", lambda **kwargs: universe)

    result = service.analyze_nse_market_breadth_from_udiff(
        "2026-11-13",
        session=object(),
    )

    assert result["point_in_time_status"] == "REVIEW"
    assert result["analysis_status"] == "REVIEW"
    assert result["reconciliation"]["coverage_status"] == "PASS"



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


def test_symbol_isin_mismatch_is_excluded_and_keeps_review_status(
    monkeypatch,
):
    install_download(monkeypatch, include_mismatch=True)

    result = service.analyze_nse_market_breadth_from_udiff(
        "2026-11-13"
    )

    assert result["reconciliation"]["identity_status"] == "REVIEW"
    assert result["reconciliation"]["isin_mismatch_symbols"] == [
        "BNAGROCHEM"
    ]
    assert "BNAGROCHEM" not in (
        result["verified_observations"]["Symbol"].tolist()
    )
    assert result["unverified_observations"]["Symbol"].tolist() == [
        "BNAGROCHEM"
    ]
    assert result["analysis_status"] == "REVIEW"
