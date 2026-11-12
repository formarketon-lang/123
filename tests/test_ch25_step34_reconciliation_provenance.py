
import hashlib
import json

from scripts.run_exchange_universe_reconciliation import (
    load_snapshot_provenance,
)


SOURCE = "https://nsearchives.nseindia.com/files/snapshot.csv"
REDIRECT_TARGET = (
    "https://nsearchives.nseindia.com/files/final_snapshot.csv"
)


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


def save_record(provenance, record):
    provenance.write_text(json.dumps(record), encoding="utf-8")


def verify(snapshot, provenance, exchange="NSE"):
    return load_snapshot_provenance(
        snapshot,
        provenance,
        exchange,
        "2026-11-11",
    )


def test_valid_provenance_matches_retained_snapshot(tmp_path):
    snapshot, provenance, _ = make_snapshot(tmp_path)

    metadata, result = verify(snapshot, provenance)

    assert result["status"] == "PASS"
    assert metadata["exchange"] == "NSE"
    assert result["sha256_matches_retained_bytes"] is True
    assert result["size_bytes_verified"] is True
    assert result["independent_external_checksum"] is False


def test_valid_single_redirect_is_accepted(tmp_path):
    snapshot, provenance, record = make_snapshot(tmp_path)
    record["redirect_chain"] = [REDIRECT_TARGET]
    record["final_source_url"] = REDIRECT_TARGET
    save_record(provenance, record)

    _, result = verify(snapshot, provenance)

    assert result["status"] == "PASS"
    assert result["redirect_chain_checked"] is True


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
    save_record(provenance, record)

    _, result = verify(snapshot, provenance)

    assert result["status"] == "REVIEW"
    assert "filename" in result["reason"]


def test_changed_snapshot_bytes_return_review(tmp_path):
    snapshot, provenance, _ = make_snapshot(tmp_path)
    snapshot.write_bytes(b"changed bytes")

    _, result = verify(snapshot, provenance)

    assert result["status"] == "REVIEW"
    assert "SHA-256" in result["reason"]


def test_wrong_size_returns_review(tmp_path):
    snapshot, provenance, record = make_snapshot(tmp_path)
    record["size_bytes"] += 1
    save_record(provenance, record)

    _, result = verify(snapshot, provenance)

    assert result["status"] == "REVIEW"
    assert "size" in result["reason"]


def test_invalid_sha256_returns_review(tmp_path):
    snapshot, provenance, record = make_snapshot(tmp_path)
    record["sha256"] = "not-a-valid-hash"
    save_record(provenance, record)

    _, result = verify(snapshot, provenance)

    assert result["status"] == "REVIEW"
    assert "SHA-256" in result["reason"]


def test_unapproved_final_url_returns_review(tmp_path):
    snapshot, provenance, record = make_snapshot(tmp_path)
    record["final_source_url"] = "https://example.com/snapshot.csv"
    save_record(provenance, record)

    _, result = verify(snapshot, provenance)

    assert result["status"] == "REVIEW"
    assert "URL" in result["reason"]


def test_unapproved_redirect_url_returns_review(tmp_path):
    snapshot, provenance, record = make_snapshot(tmp_path)
    bad_url = "https://nseindia.com.evil.example/snapshot.csv"
    record["redirect_chain"] = [bad_url]
    record["final_source_url"] = bad_url
    save_record(provenance, record)

    _, result = verify(snapshot, provenance)

    assert result["status"] == "REVIEW"


def test_nse_subdomain_not_on_exact_allowlist_returns_review(tmp_path):
    snapshot, provenance, record = make_snapshot(tmp_path)
    record["source_url"] = "https://other.nseindia.com/snapshot.csv"
    record["final_source_url"] = record["source_url"]
    save_record(provenance, record)

    _, result = verify(snapshot, provenance)

    assert result["status"] == "REVIEW"


def test_redirect_final_url_must_match_last_target(tmp_path):
    snapshot, provenance, record = make_snapshot(tmp_path)
    record["redirect_chain"] = [REDIRECT_TARGET]
    record["final_source_url"] = (
        "https://nsearchives.nseindia.com/files/other_snapshot.csv"
    )
    save_record(provenance, record)

    _, result = verify(snapshot, provenance)

    assert result["status"] == "REVIEW"
    assert "last redirect target" in result["reason"]


def test_redirect_loop_returns_review(tmp_path):
    snapshot, provenance, record = make_snapshot(tmp_path)
    record["redirect_chain"] = [SOURCE]
    record["final_source_url"] = SOURCE
    save_record(provenance, record)

    _, result = verify(snapshot, provenance)

    assert result["status"] == "REVIEW"
    assert "repeated URL or loop" in result["reason"]


def test_too_many_redirects_return_review(tmp_path):
    snapshot, provenance, record = make_snapshot(tmp_path)
    record["redirect_chain"] = [
        f"https://nsearchives.nseindia.com/files/redirect_{i}.csv"
        for i in range(6)
    ]
    record["final_source_url"] = record["redirect_chain"][-1]
    save_record(provenance, record)

    _, result = verify(snapshot, provenance)

    assert result["status"] == "REVIEW"
    assert "maximum" in result["reason"]


def test_wrong_exchange_returns_review(tmp_path):
    snapshot, provenance, _ = make_snapshot(tmp_path)

    _, result = verify(snapshot, provenance, exchange="BSE")

    assert result["status"] == "REVIEW"
    assert "exchange" in result["reason"]


def test_unvalidated_redirects_return_review(tmp_path):
    snapshot, provenance, record = make_snapshot(tmp_path)
    record["redirects_validated"] = False
    save_record(provenance, record)

    _, result = verify(snapshot, provenance)

    assert result["status"] == "REVIEW"
    assert "Redirect validation" in result["reason"]


def test_missing_snapshot_returns_review(tmp_path):
    snapshot, provenance, _ = make_snapshot(tmp_path)
    snapshot.unlink()

    _, result = verify(snapshot, provenance)

    assert result["status"] == "REVIEW"
    assert "does not exist" in result["reason"]


def test_non_list_redirect_chain_returns_review(tmp_path):
    snapshot, provenance, record = make_snapshot(tmp_path)
    record["redirect_chain"] = "not-a-list"
    save_record(provenance, record)

    _, result = verify(snapshot, provenance)

    assert result["status"] == "REVIEW"
    assert "Redirect chain" in result["reason"]
  
