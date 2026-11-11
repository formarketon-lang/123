"""Tests for the Market Intelligence data contract."""

from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_FILE = (
    PROJECT_ROOT
    / "docs"
    / "architecture"
    / "market_intelligence_data_contract.md"
)


@pytest.fixture
def contract_text():
    assert CONTRACT_FILE.is_file(), (
        "Market Intelligence data contract is missing."
    )
    return CONTRACT_FILE.read_text(encoding="utf-8")


def test_contract_contains_all_main_sections(contract_text):
    required_sections = [
        "## 1. Purpose",
        "## 2. Existing Data Layer",
        "## 3. Source Priority",
        "## 4. Common Data Provenance Contract",
        "## 5. Analysis Data Requirements",
        "## 6. Validation Rules",
        "## 7. Data Status Contract",
        "## 8. Failure and Fallback Policy",
        "## 9. Proposed Service Boundaries",
        "## 10. Testing Requirements",
        "## 11. Activation Gate",
        "## 12. Non-Negotiable Rules",
    ]

    for section in required_sections:
        assert section in contract_text


def test_contract_preserves_source_priority(contract_text):
    assert "NSE official data sources" in contract_text
    assert "Yahoo Finance" in contract_text
    assert "BSE remains disabled" in contract_text
    assert "must not silently replace" in contract_text


def test_contract_defines_all_analysis_areas(contract_text):
    analysis_areas = [
        "Market Regime Analysis",
        "Market Breadth",
        "Advance / Decline Analysis",
        "Sector Strength",
        "Index Participation",
        "Market Trend Classification",
        "News and Events Context",
    ]

    for area in analysis_areas:
        assert area in contract_text


def test_contract_requires_data_provenance(contract_text):
    required_fields = [
        "Symbol or index identifier",
        "Exchange",
        "Observation date",
        "Data source",
        "Fetch timestamp in UTC",
        "Validation status",
        "Fallback reason",
        "benchmark or universe reference",
    ]

    for field in required_fields:
        assert field in contract_text


def test_contract_defines_explicit_data_statuses(contract_text):
    statuses = [
        "`PASS`",
        "`REVIEW`",
        "`BLOCKED`",
        "`UNAVAILABLE`",
        "`PENDING`",
    ]

    for status in statuses:
        assert status in contract_text


def test_contract_preserves_non_negotiable_restrictions(
    contract_text,
):
    restrictions = [
        "No fake market data.",
        "No fabricated market signals.",
        "No unsupported sector mappings.",
        "No F&O Scanner.",
        "BSE remains disabled",
        "Sector Mapping Expansion remains OFF.",
    ]

    for restriction in restrictions:
        assert restriction in contract_text


def test_contract_references_existing_data_modules():
    existing_modules = [
        "data/schema.py",
        "data/market_data_adapter.py",
        "data/benchmark_mapping.py",
        "data/universe.py",
        "data/constituent_audit.py",
    ]

    for module in existing_modules:
        assert (PROJECT_ROOT / module).is_file(), (
            f"Referenced module does not exist: {module}"
        )


def test_contract_requires_activation_gates(contract_text):
    required_gates = [
        "Data interfaces are implemented and verified.",
        "Core calculations are implemented and tested.",
        "Provenance and validation tests pass.",
        "Navigation integration tests pass.",
        "Existing application regression tests pass.",
        "GitHub Actions are successful.",
    ]

    for gate in required_gates:
        assert gate in contract_text
