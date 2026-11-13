
from scripts.run_nse_classification_taxonomy_extraction import (
    LEVELS,
    extract_guidelines_table_rows,
    is_guidelines_header,
    normalize_taxonomy_rows,
)


GUIDELINES_HEADER = [
    "Macro Economic Indicator",
    "Sector",
    "Industry",
    "Basic Industry",
]


def test_recognizes_official_four_column_guidelines_header():
    assert is_guidelines_header(GUIDELINES_HEADER)


def test_extracts_four_column_guidelines_rows():
    rows = [
        GUIDELINES_HEADER,
        [
            "Commodities",
            "Chemicals",
            "Chemicals & Petrochemicals",
            "Commodity Chemicals",
        ],
        ["", "", "", "Specialty Chemicals"],
    ]

    result = extract_guidelines_table_rows(rows)

    assert len(result) == 2
    assert result[0][0] == "Commodities"
    assert result[1][3] == "Specialty Chemicals"


def test_normalizes_merged_hierarchy_cells():
    rows = [
        [
            "Commodities",
            "Chemicals",
            "Chemicals & Petrochemicals",
            "Commodity Chemicals",
        ],
        ["", "", "", "Specialty Chemicals"],
    ]

    result = normalize_taxonomy_rows(rows)

    assert len(result) == 2
    assert result[1]["Macro Economic Sector"] == "Commodities"
    assert result[1]["Sector"] == "Chemicals"
    assert result[1]["Industry"] == "Chemicals & Petrochemicals"
    assert result[1]["Basic Industry"] == "Specialty Chemicals"


def test_does_not_create_record_without_basic_industry():
    rows = [
        ["Commodities", "Chemicals", "Chemicals & Petrochemicals", ""]
    ]

    assert normalize_taxonomy_rows(rows) == []


def test_output_has_exact_four_levels():
    rows = [
        [
            "Commodities",
            "Chemicals",
            "Chemicals & Petrochemicals",
            "Commodity Chemicals",
        ]
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

    assert len(normalize_taxonomy_rows([row, row])) == 1


def test_rejects_nine_column_structure_header():
    structure_header = [
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

    assert not is_guidelines_header(structure_header)
    assert extract_guidelines_table_rows([structure_header]) == []


def test_rejects_unrecognized_table():
    rows = [
        ["Wrong", "Header", "Format", "Here"],
        ["A", "B", "C", "D"],
    ]

    assert extract_guidelines_table_rows(rows) == []
