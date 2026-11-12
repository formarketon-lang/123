
import hashlib
import json

from scripts.run_exchange_universe_reconciliation import (
    load_snapshot_provenance,
)


SOURCE = "https://nsearchives.nseindia.com/files/snapshot.csv"


def make_snapshot(tmp_path, content=b"SYMBOL,ISIN\nAAA,INE123A01011\n"):
    snapshot = tmp_path / "snapshot.csv"
    snapshot.write_bytes(content)

    provenance = tmp_path / "snapshot.csv.provenance.json"
    record = {
        "exchange": "NSE",
        "source_url": SOURCE,
        "redirect_chain": [],
        "final_source_url": SOURCE,
        "filename": snapshot.name,
        "downloaded_at_utc": "2026-11-12T01:00:00+00:00",
        "size_bytes": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
        "original_bytes_retained": True,
        "redirects_validated": True,
    }
    provenance.write_text(json.dumps(record), encoding="utf-8")
    return snapshot, provenance, record


def test_valid_provenance_matches_retained_snapshot(tmp_path):
    snapshot, provenance, _ = make_snapshot(tmp_path)

    metadata, result = load_snapshot_provenance(
        snapshot, provenance, "NSE", "2026-11-11"
    )

    assert result["status"] == "PASS"
    assert metadata["exchange"] == "NSE"
    assert result["sha256_matches_retained_bytes"] is True
    assert result["independent_external_checksum"] is False


def test_missing_provenance_returns_review(tmp_path):
    snapshot, _, _ = make_snapshot(tmp_path)

    metadata, result = load_snapshot_provenance(
        snapshot, None, "NSE", "2026-11-11"
    )

    assert metadata == {}
    assert result["status"] == "REVIEW"


def test_wrong_filename_returns_review(tmp_path):
    snapshot, provenance, record = make_snapshot(tmp_path)
    record["filename"] = "different.csv"
    provenance.write_text(json.dumps(record), encoding="utf-8")

    _, result = load_snapshot_provenance(
        snapshot, provenance, "NSE", "2026-11-11"
    )

    assert result["status"] == "REVIEW"
    assert "filename" in result["reason"]


def test_changed_snapshot_bytes_return_review(tmp_path):
    snapshot, provenance, _ = make_snapshot(tmp_path)
    snapshot.write_bytes(b"changed bytes")

    _, result = load_snapshot_provenance(
        snapshot, provenance, "NSE", "2026-11-11"
    )

    assert result["status"] == "REVIEW"
    assert "SHA-256" in result["reason"]


def test_unapproved_final_url_returns_review(tmp_path):
    snapshot, provenance, record = make_snapshot(tmp_path)
    record["final_source_url"] = "https://example.com/snapshot.csv"
    provenance.write_text(json.dumps(record), encoding="utf-8")

    _, result = load_snapshot_provenance(
        snapshot, provenance, "NSE", "2026-11-11"
    )

    assert result["status"] == "REVIEW"
    assert "URL" in result["reason"]


def test_unapproved_redirect_url_returns_review(tmp_path):
    snapshot, provenance, record = make_snapshot(tmp_path)
    record["redirect_chain"] = [
        "https://nseindia.com.evil.example/snapshot.csv"
    ]
    provenance.write_text(json.dumps(record), encoding="utf-8")

    _, result = load_snapshot_provenance(
        snapshot, provenance, "NSE", "2026-11-11"
    )

    assert result["status"] == "REVIEW"


def test_wrong_exchange_returns_review(tmp_path):
    snapshot, provenance, _ = make_snapshot(tmp_path)

    _, result = load_snapshot_provenance(
        snapshot, provenance, "BSE", "2026-11-11"
    )

    assert result["status"] == "REVIEW"


def test_unvalidated_redirects_return_review(tmp_path):
    snapshot, provenance, record = make_snapshot(tmp_path)
    record["redirects_validated"] = False
    provenance.write_text(json.dumps(record), encoding="utf-8")

    _, result = load_snapshot_provenance(
        snapshot, provenance, "NSE", "2026-11-11"
    )

    assert result["status"] == "REVIEW"
