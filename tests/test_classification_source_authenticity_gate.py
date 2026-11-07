"""Regression tests for the independent source-authenticity gate.

All fixtures are synthetic. They are not official NSE evidence.
"""

import pandas as pd

from data.providers.classification_taxonomy_validator import (
    validate_classification_taxonomy,
)
from scripts.run_industry_classification_audit import (
    build_industry_classification_audit,
    build_source_provenance,
)


def classification_fixture():
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


def synthetic_nse_mii_fixture():
    return pd.DataFrame({
        "Symbol": ["MARICO"],
        "ISIN": ["INE196A01026"],
        "Series": ["EQ"],
        "Source": ["NSE MII Security Master"],
    })


def test_operator_declared_nse_official_label_cannot_authorize_mapping():
    detail, summary = build_industry_classification_audit(
        classification=classification_fixture(),
        nse_universe=synthetic_nse_mii_fixture(),
        classification_source_type="NSE_OFFICIAL",
        license_status="NOT_REQUIRED",
        official_taxonomy=taxonomy_fixture(),
    )

    assert summary["status"] == "PASS"
    assert summary["nse_source_status"] == "PRIMARY_MII"
    assert summary["taxonomy_status"] == "PASS"

    assert summary["source_authenticity_status"] == "UNVERIFIED"
    assert summary["source_authenticity_verified"] is False
    assert summary["source_authorized_for_nse_mapping"] is False

    assert summary["approved_rows"] == 0
    assert summary["mapping_eligible"] is False
    assert summary["sector_mapping_activated"] is False

    assert detail.loc[0, "Audit_Status"] == "MATCH"
    assert detail.loc[0, "Taxonomy_Validated"] == True
    assert detail.loc[0, "Source_Authenticity_Status"] == "UNVERIFIED"
    assert detail.loc[0, "Source_Authenticity_Verified"] == False
    assert detail.loc[0, "Approved"] == False


def test_source_provenance_records_authenticity_as_unverified(tmp_path):
    source_file = tmp_path / "classification.csv"
    source_file.write_text(
        "Symbol,ISIN\nMARICO,INE196A01026\n",
        encoding="utf-8",
    )

    provenance = build_source_provenance(
        input_path=source_file,
        source_type="NSE_OFFICIAL",
        source_name="Operator supplied label",
        source_reference="https://example.invalid/source",
        license_status="NOT_REQUIRED",
    )

    assert provenance["source_type"] == "NSE_OFFICIAL"
    assert provenance["source_type_is_operator_declared"] is True
    assert provenance["source_authenticity_status"] == "UNVERIFIED"
    assert provenance["source_authenticity_verified"] is False
    assert provenance["source_authorized_for_nse_mapping"] is False
  
