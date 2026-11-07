
"""Tests for taxonomy source provenance."""

import hashlib

import pytest

from scripts.run_industry_classification_audit import (
    build_taxonomy_provenance,
)


def test_taxonomy_provenance_records_hash_and_reference(tmp_path):
    path = tmp_path / "official_taxonomy.csv"
    content = b"Sector Code,Sector\n1010,Consumer"
    path.write_bytes(content)

    result = build_taxonomy_provenance(
        input_path=path,
        source_reference="https://www.niftyindices.com/resources/industry-classification",
    )

    assert result["file_name"] == "official_taxonomy.csv"
    assert result["file_sha256"] == hashlib.sha256(content).hexdigest()
    assert result["file_size_bytes"] == len(content)
    assert result["source_reference"].startswith("https://")
    assert result["source_reference_is_operator_declared"] is True
    assert "does not prove" in result["note"]


def test_taxonomy_provenance_requires_source_reference(tmp_path):
    path = tmp_path / "taxonomy.csv"
    path.write_text("Sector Code,Sector\n1010,Consumer")

    with pytest.raises(ValueError, match="source reference is required"):
        build_taxonomy_provenance(
            input_path=path,
            source_reference="",
        )


def test_taxonomy_provenance_rejects_missing_file(tmp_path):
    path = tmp_path / "missing.csv"

    with pytest.raises(FileNotFoundError):
        build_taxonomy_provenance(
            input_path=path,
            source_reference="Official source reference",
        )


def test_taxonomy_provenance_rejects_unsupported_format(tmp_path):
    path = tmp_path / "taxonomy.txt"
    path.write_text("not csv")

    with pytest.raises(ValueError, match="CSV"):
        build_taxonomy_provenance(
            input_path=path,
            source_reference="Official source reference",
        )


def test_taxonomy_provenance_rejects_empty_file(tmp_path):
    path = tmp_path / "taxonomy.csv"
    path.write_bytes(b"")

    with pytest.raises(ValueError, match="empty"):
        build_taxonomy_provenance(
            input_path=path,
            source_reference="Official source reference",
        )


def test_taxonomy_hash_changes_when_content_changes(tmp_path):
    path = tmp_path / "taxonomy.csv"
    path.write_text("Sector Code,Sector\n1010,Consumer")

    first = build_taxonomy_provenance(
        path,
        "Official source reference",
    )

    path.write_text("Sector Code,Sector\n2020,Financial")

    second = build_taxonomy_provenance(
        path,
        "Official source reference",
    )

    assert first["file_sha256"] != second["file_sha256"]
  
