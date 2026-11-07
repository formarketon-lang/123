from scripts.run_nse_classification_taxonomy_extraction import (
    LEVELS,
    extract_structure_table_rows,
    normalize_taxonomy_rows,
)


STRUCTURE_HEADER = [
    "MES_Code",
    "Macro Economic Sector",
    "Sect_Code",
    "Sector",
    "Ind_Code",
    "Industry",
    "Basic_Ind_Code",
    "Basic Industry",
    "Definition",
]


def test_extracts_correct_columns_from_nine_column_structure():
    rows = [
        STRUCTURE_HEADER,
        [
            "IN01",
            "Commodities",
            "IN0101",
            "Chemicals",
            "IN010101",
            "Chemicals & Petrochemicals",
            "IN010101001",
            "Commodity Chemicals",
            "Manufacturers of chemicals",
        ],
        [
            "",
            "",
            "",
            "",
            "",
            "",
            "IN010101002",
            "Specialty Chemicals",
            "Manufacturers of specialty chemicals",
        ],
    ]

    result = extract_structure_table_rows(rows)

    assert len(result) == 2

    assert result[0] == [
        "Commodities",
        "Chemicals",
        "Chemicals & Petrochemicals",
        "Commodity Chemicals",
    ]

    assert result[1] == [
        "",
        "",
        "",
        "Specialty Chemicals",
    ]


def test_normalizes_four_level_taxonomy():
    rows = [
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
        [
            "Commodities",
            "Chemicals",
            "Chemicals & Petrochemicals",
            "",
        ],
    ]

    assert normalize_taxonomy_rows(rows) == []


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


def test_rejects_unrecognized_structure_table():
    rows = [
        ["Wrong", "Header", "Format"],
        ["A", "B", "C"],
    ]

    assert extract_structure_table_rows(rows) == []