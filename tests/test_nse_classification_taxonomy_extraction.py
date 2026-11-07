from scripts.run_nse_classification_taxonomy_extraction import (
    LEVELS,
    normalize_taxonomy_rows,
)


def test_normalizes_four_level_taxonomy():
    rows = [
        [
            "Macro Economic Indicator",
            "Sector",
            "Industry",
            "Basic Industry",
        ],
        [
            "Commodities",
            "Chemicals",
            "Chemicals & Petrochemicals",
            "Commodity Chemicals",
        ],
        [
            "",
            "",
            "",
            "Specialty Chemicals",
        ],
    ]

    result = normalize_taxonomy_rows(rows)

    assert len(result) == 2
    assert result[0]["Macro Economic Sector"] == "Commodities"
    assert result[1]["Macro Economic Sector"] == "Commodities"
    assert result[1]["Sector"] == "Chemicals"
    assert result[1]["Basic Industry"] == "Specialty Chemicals"


def test_does_not_create_record_without_basic_industry():
    rows = [
        ["Commodities", "Chemicals", "Chemicals & Petrochemicals", ""],
    ]

    result = normalize_taxonomy_rows(rows)

    assert result == []


def test_output_has_exact_four_levels():
    rows = [
        [
            "Commodities",
            "Chemicals",
            "Chemicals & Petrochemicals",
            "Commodity Chemicals",
        ],
    ]

    result = normalize_taxonomy_rows(rows)

    assert list(result[0].keys()) == LEVELS


def test_duplicate_taxonomy_rows_are_removed():
    row = [
        "Commodities",
        "Chemicals",
        "Chemicals & Petrochemicals",
        "Commodity Chemicals",
    ]

    result = normalize_taxonomy_rows([row, row])

    assert len(result) == 1
