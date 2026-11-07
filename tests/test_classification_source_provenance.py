
"""Tests for provenance, licensing and integrated taxonomy gates."""

import pandas as pd
import pytest

from scripts.run_industry_classification_audit import (
    build_industry_classification_audit,
    build_source_provenance,
)


def classification_data():
    return pd.DataFrame({
        "Symbol": ["MARICO", "HINDUNILVR"],
        "ISIN": ["INE196A01026", "INE030A01027"],
        "Sector": ["Consumer Products", "Consumer Products"],
        "Industry": ["Personal Products", "Household Products"],
        "Basic Industry": ["Personal Care", "Household Products"],
        "Macro Economic Sector Code": ["10", "10"],
        "Macro Economic Sector": [
            "Consumer Discretionary",
            "Consumer Discretionary",
        ],
        "Sector Code": ["1010", "1010"],
        "Industry Code": ["101001", "101002"],
        "Basic Industry Code": ["10100101", "10100201"],
    })


def official_taxonomy_data():
    return classification_data().drop(
        columns=["Symbol", "ISIN"]
    ).copy()


def nse_mii_data():
    return pd.DataFrame({
        "Symbol": ["MARICO", "HINDUNILVR"],
        "ISIN": ["INE196A01026", "INE030A01027"],
        "Series": ["EQ", "EQ"],
        "Source": [
            "NSE MII Security Master",
            "NSE MII Security Master",
        ],
    })


def test_provenance_records_file_hash_and_source(tmp_path):
    source_file = tmp_path / "classification.csv"
    source_file.write_text("Symbol,ISIN\nMARICO,INE196A01026")

    result = build_source_provenance(
        input_path=source_file,
        source_type="NSE_OFFICIAL",
        source_name="NSE Official Classification",
        source_reference="https://www.nseindia.com/",
        license_status="NOT_REQUIRED",
        effective_date="2026-11-07",
    )

    assert result["source_type"] == "NSE_OFFICIAL"
    assert result["source_name"] == "NSE Official Classification"
    assert result["effective_date"] == "2026-11-07"
    assert len(result["file_sha256"]) == 64
    assert result["file_size_bytes"] > 0
    assert result["source_type_is_operator_declared"] is True


def test_vendor_import_is_blocked_when_license_is_pending(tmp_path):
    source_file = tmp_path / "vendor.csv"
    source_file.write_text("Symbol,ISIN\nMARICO,INE196A01026")

    with pytest.raises(PermissionError, match="APPROVED"):
        build_source_provenance(
            input_path=source_file,
            source_type="THIRD_PARTY_VENDOR",
            source_name="Global Datafeeds",
            source_reference="Vendor API documentation",
            license_status="PENDING",
        )


def test_vendor_import_requires_license_reference(tmp_path):
    source_file = tmp_path / "vendor.csv"
    source_file.write_text("Symbol,ISIN\nMARICO,INE196A01026")

    with pytest.raises(ValueError, match="licence approval reference"):
        build_source_provenance(
            input_path=source_file,
            source_type="THIRD_PARTY_VENDOR",
            source_name="Global Datafeeds",
            source_reference="Vendor API documentation",
            license_status="APPROVED",
        )


def test_vendor_import_accepts_approved_license_reference(tmp_path):
    source_file = tmp_path / "vendor.csv"
    source_file.write_text("Symbol,ISIN\nMARICO,INE196A01026")

    result = build_source_provenance(
        input_path=source_file,
        source_type="THIRD_PARTY_VENDOR",
        source_name="Global Datafeeds",
        source_reference="Vendor API documentation",
        license_status="APPROVED",
        license_reference="Contract approval reference",
    )

    assert result["source_type"] == "THIRD_PARTY_VENDOR"
    assert result["license_status"] == "APPROVED"
    assert result["license_reference"] == "Contract approval reference"


def test_rejected_license_blocks_import(tmp_path):
    source_file = tmp_path / "source.csv"
    source_file.write_text("Symbol,ISIN\nMARICO,INE196A01026")

    with pytest.raises(PermissionError, match="rejected"):
        build_source_provenance(
            input_path=source_file,
            source_type="NSE_OFFICIAL",
            source_name="NSE",
            source_reference="Official source reference",
            license_status="REJECTED",
        )


def test_invalid_effective_date_is_rejected(tmp_path):
    source_file = tmp_path / "source.csv"
    source_file.write_text("Symbol,ISIN\nMARICO,INE196A01026")

    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        build_source_provenance(
            input_path=source_file,
            source_type="NSE_OFFICIAL",
            source_name="NSE",
            source_reference="Official source reference",
            license_status="NOT_REQUIRED",
            effective_date="07-11-2026",
        )


def test_vendor_rows_never_become_nse_official_approved_rows():
    detail, summary = build_industry_classification_audit(
        classification_data(),
        nse_mii_data(),
        classification_source_type="THIRD_PARTY_VENDOR",
        license_status="APPROVED",
        official_taxonomy=official_taxonomy_data(),
    )

    assert summary["status"] == "PASS"
    assert summary["nse_eq_matched"] == 2
    assert summary["approved_rows"] == 0
    assert summary["source_authorized_for_nse_mapping"] is False
    assert summary["mapping_eligible"] is False
    assert not detail["Approved"].any()
    assert summary["sector_mapping_activated"] is False


def test_vendor_rows_are_blocked_when_license_is_pending():
    with pytest.raises(PermissionError, match="not licensed"):
        build_industry_classification_audit(
            classification_data(),
            nse_mii_data(),
            classification_source_type="THIRD_PARTY_VENDOR",
            license_status="PENDING",
        )


def test_bse_source_cannot_be_approved_as_nse_mapping():
    detail, summary = build_industry_classification_audit(
        classification_data(),
        nse_mii_data(),
        classification_source_type="BSE_OFFICIAL",
        license_status="NOT_REQUIRED",
        official_taxonomy=official_taxonomy_data(),
    )

    assert summary["status"] == "PASS"
    assert summary["approved_rows"] == 0
    assert summary["source_authorized_for_nse_mapping"] is False
    assert not detail["Approved"].any()


def test_nse_official_source_passes_all_three_gates():
    detail, summary = build_industry_classification_audit(
        classification_data(),
        nse_mii_data(),
        classification_source_type="NSE_OFFICIAL",
        license_status="NOT_REQUIRED",
        official_taxonomy=official_taxonomy_data(),
    )

    assert summary["status"] == "PASS"
    assert summary["taxonomy_status"] == "PASS"
    assert summary["nse_eq_matched"] == 2
    assert summary["taxonomy_matched_rows"] == 2
    assert summary["approved_rows"] == 2
    assert summary["source_authorized_for_nse_mapping"] is True
    assert summary["mapping_eligible"] is True
    assert detail["Approved"].all()
    assert summary["sector_mapping_activated"] is False


def test_missing_taxonomy_reference_blocks_all_approvals():
    detail, summary = build_industry_classification_audit(
        classification_data(),
        nse_mii_data(),
        classification_source_type="NSE_OFFICIAL",
        license_status="NOT_REQUIRED",
    )

    assert summary["status"] == "PASS"
    assert summary["taxonomy_status"] == "REVIEW"
    assert summary["approved_rows"] == 0
    assert summary["mapping_eligible"] is False
    assert not detail["Approved"].any()


def test_unknown_taxonomy_path_blocks_mapping():
    taxonomy = official_taxonomy_data()
    taxonomy.loc[0, "Basic Industry"] = "Unverified Industry"

    detail, summary = build_industry_classification_audit(
        classification_data(),
        nse_mii_data(),
        classification_source_type="NSE_OFFICIAL",
        license_status="NOT_REQUIRED",
        official_taxonomy=taxonomy,
    )

    marico = detail.loc[detail["Symbol"].eq("MARICO")].iloc[0]

    assert summary["status"] == "PASS"
    assert summary["taxonomy_status"] == "REVIEW"
    assert summary["approved_rows"] == 1
    assert summary["mapping_eligible"] is False
    assert marico["Taxonomy_Status"] == "NOT_IN_OFFICIAL_TAXONOMY"
    assert not marico["Approved"]


def test_wrong_sector_parent_blocks_mapping():
    taxonomy = official_taxonomy_data()
    taxonomy.loc[0, "Sector Code"] = "9999"

    detail, summary = build_industry_classification_audit(
        classification_data(),
        nse_mii_data(),
        classification_source_type="NSE_OFFICIAL",
        license_status="NOT_REQUIRED",
        official_taxonomy=taxonomy,
    )

    marico = detail.loc[detail["Symbol"].eq("MARICO")].iloc[0]

    assert summary["taxonomy_status"] == "REVIEW"
    assert summary["mapping_eligible"] is False
    assert marico["Taxonomy_Status"] == "NOT_IN_OFFICIAL_TAXONOMY"
    assert not marico["Approved"]


def test_file_hash_changes_when_file_content_changes(tmp_path):
    source_file = tmp_path / "source.csv"
    source_file.write_text("first version")

    first = build_source_provenance(
        input_path=source_file,
        source_type="NSE_OFFICIAL",
        source_name="NSE",
        source_reference="Official reference",
        license_status="NOT_REQUIRED",
    )

    source_file.write_text("second version")

    second = build_source_provenance(
        input_path=source_file,
        source_type="NSE_OFFICIAL",
        source_name="NSE",
        source_reference="Official reference",
        license_status="NOT_REQUIRED",
    )

    assert first["file_sha256"] != second["file_sha256"]
