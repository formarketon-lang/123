
import gzip
import hashlib
import json

from datetime import date

import pandas as pd

import scripts.run_nse_dated_snapshot_audit as audit


def sample_mii_bytes():
    frame = pd.DataFrame({
        "FININSTRMID": ["1", "2"],
        "TCKRSYMB": ["MARICO", "HINDUNILVR"],
        "FININSTRMNM": [
            "Marico Limited",
            "Hindustan Unilever Limited",
        ],
        "SCTYSRS": ["EQ", "EQ"],
        "LISTGDT": ["0", "0"],
        "ISIN": ["INE196A01026", "INE030A01027"],
        "PARVAL": ["1", "1"],
        "ISSDCPTL": ["100", "200"],
        "DELFLG": ["N", "N"],
        "ELGBLTYNRMLMKT": ["1", "1"],
        "SCTYSTSNRMLMKT": ["1", "1"],
        "PRTDTOTRAD": ["1", "1"],
    })
    return gzip.compress(frame.to_csv(index=False).encode())


def fake_downloader(
    exchange,
    source_url,
    destination,
    *,
    session=None,
    timeout=45,
):
    content = sample_mii_bytes()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(content)

    record = {
        "exchange": exchange,
        "status": "DOWNLOADED",
        "source_url": source_url,
        "redirect_chain": [],
        "final_source_url": source_url,
        "filename": destination.name,
        "downloaded_at_utc": "2026-11-12T01:00:00+00:00",
        "size_bytes": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
        "original_bytes_retained": True,
        "redirects_validated": True,
        "gzip_integrity_validated": True,
    }

    provenance = destination.with_name(
        destination.name + ".provenance.json"
    )
    provenance.write_text(json.dumps(record), encoding="utf-8")
    return record


def test_nse_dated_snapshot_audit_passes(tmp_path, monkeypatch):
    monkeypatch.setattr(
        audit,
        "download_exchange_snapshot",
        fake_downloader,
    )

    result = audit.run_nse_dated_snapshot_audit(
        date(2026, 11, 11),
        tmp_path,
    )

    assert result["status"] == "PASS"
    assert result["archive_date"] == "2026-11-11"
    assert result["normalized_rows"] == 2
    assert result["bse_status"] == "REVIEW"
    assert result["sector_mapping_activated"] is False
    assert result["independent_external_checksum_verified"] is False


def test_archive_url_uses_requested_date():
    token = date(2026, 11, 11).strftime("%d%m%Y")
    url = audit.NSE_MII_SECURITY_URL_TEMPLATE.format(date=token)

    assert url.endswith(
        f"NSE_CM_security_{token}.csv.gz"
    )


def test_invalid_normalized_isin_is_rejected():
    frame = pd.DataFrame({
        "Symbol": ["AAA"],
        "Company": ["AAA Limited"],
        "Series": ["EQ"],
        "ISIN": ["INVALID"],
        "Delete Flag": ["N"],
        "Normal Market Eligibility": ["1"],
        "Normal Market Status": ["1"],
    })

    try:
        audit.validate_normalized_universe(frame)
    except ValueError as exc:
        assert "ISIN" in str(exc)
    else:
        raise AssertionError("Invalid ISIN was accepted.")


def test_non_eq_record_is_rejected():
    frame = pd.DataFrame({
        "Symbol": ["AAA"],
        "Company": ["AAA Limited"],
        "Series": ["BE"],
        "ISIN": ["INE123A01011"],
        "Delete Flag": ["N"],
        "Normal Market Eligibility": ["1"],
        "Normal Market Status": ["1"],
    })

    try:
        audit.validate_normalized_universe(frame)
    except ValueError as exc:
        assert "Non-EQ" in str(exc)
    else:
        raise AssertionError("Non-EQ record was accepted.")
  
