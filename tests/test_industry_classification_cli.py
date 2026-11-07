"""End-to-end CLI integration tests for industry classification audit."""

import json

import pandas as pd
import pytest

import scripts.run_industry_classification_audit as audit


def classification_fixture():
    """Synthetic test data only; not an official NSE classification."""
    return pd.DataFrame({
        "Symbol": ["MARICO"],
        "ISIN": ["INE196A01026"],
        "Macro Economic Sector Code": ["10"],
        "Macro Economic Sector": ["Consumer Discretionary"],
        "Sector Code": ["1010"],
        "Sector": ["Consumer Products"],
        "Industry Code": ["101001"],
        "Industry": ["Personal Products"],
        "Basic Industry Code": ["10100101"],
        "Basic Industry": ["Personal Care"],
    })


def taxonomy_fixture():
    """Synthetic taxonomy test fixture."""
    return pd.DataFrame({
        "Macro Economic Sector Code": ["10"],
        "Macro Economic Sector": ["Consumer Discretionary"],
        "Sector Code": ["1010"],
        "Sector": ["Consumer Products"],
        "Industry Code": ["101001"],
        "Industry": ["Personal Products"],
        "Basic Industry Code": ["10100101"],
        "Basic Industry": ["Personal Care"],
    })


def nse_mii_fixture():
    """Synthetic NSE MII-shaped fixture; not live NSE evidence."""
    return pd.DataFrame({
        "Symbol": ["MARICO"],
        "ISIN": ["INE196A01026"],
        "Series": ["EQ"],
        "Source": ["NSE MII Security Master"],
    })


def write_input_files(tmp_path):
    classification_path = tmp_path / "classification.csv"
    taxonomy_path = tmp_path / "taxonomy.csv"

    classification_fixture().to_csv(
        classification_path,
        index=False,
    )
    taxonomy_fixture().to_csv(
        taxonomy_path,
        index=False,
    )

    return classification_path, taxonomy_path


def test_cli_requires_taxonomy_source_reference(
    tmp_path,
    monkeypatch,
):
    classification_path, taxonomy_path = write_input_files(
        tmp_path
    )

    monkeypatch.setattr(
        "sys.argv",
        [
            "run_industry_classification_audit.py",
            "--input", str(classification_path),
            "--source-type", "NSE_OFFICIAL",
            "--source-name", "Test source",
            "--source-reference", "Test classification reference",
            "--license-status", "NOT_REQUIRED",
            "--taxonomy-input", str(taxonomy_path),
        ],
    )

    with pytest.raises(SystemExit) as exc:
        audit.main()

    assert exc.value.code == 2


def test_cli_rejects_taxonomy_reference_without_input(
    tmp_path,
    monkeypatch,
):
    classification_path, _ = write_input_files(tmp_path)

    monkeypatch.setattr(
        "sys.argv",
        [
            "run_industry_classification_audit.py",
            "--input", str(classification_path),
            "--source-type", "NSE_OFFICIAL",
            "--source-name", "Test source",
            "--source-reference", "Test classification reference",
            "--license-status", "NOT_REQUIRED",
            "--taxonomy-source-reference", "Test taxonomy reference",
        ],
    )

    with pytest.raises(SystemExit) as exc:
        audit.main()

    assert exc.value.code == 2


def test_cli_end_to_end_creates_reports_and_blocks_vendor_mapping(
    tmp_path,
    monkeypatch,
):
    classification_path, taxonomy_path = write_input_files(
        tmp_path
    )

    report_dir = tmp_path / "reports"

    monkeypatch.setattr(audit, "REPORT_DIR", report_dir)
    monkeypatch.setattr(
        audit,
        "fetch_nse_equity_universe",
        nse_mii_fixture,
    )

    monkeypatch.setattr(
        "sys.argv",
        [
            "run_industry_classification_audit.py",
            "--input", str(classification_path),
            "--source-type", "THIRD_PARTY_VENDOR",
            "--source-name", "Synthetic test vendor",
            "--source-reference", "Test classification reference",
            "--license-status", "APPROVED",
            "--license-reference", "TEST-LICENSE-REFERENCE",
            "--taxonomy-input", str(taxonomy_path),
            "--taxonomy-source-reference", "Test taxonomy reference",
        ],
    )

    with pytest.raises(SystemExit) as exc:
        audit.main()

    assert exc.value.code != 0

    detail_path = (
        report_dir / "nse_industry_classification_audit.csv"
    )
    summary_path = (
        report_dir / "nse_industry_classification_summary.json"
    )
    provenance_path = (
        report_dir / "classification_source_provenance.json"
    )

    assert detail_path.is_file()
    assert summary_path.is_file()
    assert provenance_path.is_file()

    summary = json.loads(
        summary_path.read_text(encoding="utf-8")
    )

    provenance = json.loads(
        provenance_path.read_text(encoding="utf-8")
    )

    assert summary["status"] == "PASS"
    assert summary["taxonomy_status"] == "PASS"
    assert summary["nse_eq_matched"] == 1

    assert summary["source_authorized_for_nse_mapping"] is False
    assert summary["approved_rows"] == 0
    assert summary["mapping_eligible"] is False
    assert summary["sector_mapping_activated"] is False

    assert provenance["classification_source"]["source_type"] == (
        "THIRD_PARTY_VENDOR"
    )
    assert provenance["taxonomy_source"]["source_reference"] == (
        "Test taxonomy reference"
    )


def test_cli_without_taxonomy_keeps_mapping_blocked(
    tmp_path,
    monkeypatch,
):
    classification_path, _ = write_input_files(tmp_path)

    report_dir = tmp_path / "reports"

    monkeypatch.setattr(audit, "REPORT_DIR", report_dir)
    monkeypatch.setattr(
        audit,
        "fetch_nse_equity_universe",
        nse_mii_fixture,
    )

    monkeypatch.setattr(
        "sys.argv",
        [
            "run_industry_classification_audit.py",
            "--input", str(classification_path),
            "--source-type", "NSE_OFFICIAL",
            "--source-name", "Synthetic test source",
            "--source-reference", "Test classification reference",
            "--license-status", "NOT_REQUIRED",
        ],
    )

    with pytest.raises(SystemExit) as exc:
        audit.main()

    assert exc.value.code != 0

    summary_path = (
        report_dir / "nse_industry_classification_summary.json"
    )

    assert summary_path.is_file()

    summary = json.loads(
        summary_path.read_text(encoding="utf-8")
    )

    assert summary["status"] == "PASS"
    assert summary["taxonomy_status"] == "REVIEW"
    assert summary["approved_rows"] == 0
    assert summary["mapping_eligible"] is False
    assert summary["sector_mapping_activated"] is False