"""Extract the official four-level NSE taxonomy from the Structure PDF."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pymupdf
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SOURCE_PDF = (
    ROOT
    / "data/raw/nse/industry_classification_sources/"
    "nse_industry_classification_structure.pdf"
)

OUTPUT_DIR = (
    ROOT / "data/raw/nse/industry_classification_sources"
)
REPORT_DIR = ROOT / "reports/industry_classification"

LEVELS = [
    "Macro Economic Sector",
    "Sector",
    "Industry",
    "Basic Industry",
]

# Official NSE Structure PDF columns:
# 0 MES_Code
# 1 Macro Economic Sector
# 2 Sect_Code
# 3 Sector
# 4 Ind_Code
# 5 Industry
# 6 Basic_Ind_Code
# 7 Basic Industry
# 8 Definition

STRUCTURE_COLUMN_INDEXES = (1, 3, 5, 7)

EXPECTED_COUNTS = {
    "Macro Economic Sector": 12,
    "Sector": 22,
    "Industry": 59,
    "Basic Industry": 197,
}


def clean(value):
    if value is None:
        return ""

    return " ".join(str(value).replace("\n", " ").split())


def header_key(value):
    return "".join(
        character
        for character in clean(value).lower()
        if character.isalnum()
    )


def is_structure_header(row):
    if not row or len(row) < 8:
        return False

    return (
        header_key(row[1]) == "macroeconomicsector"
        and header_key(row[3]) == "sector"
        and header_key(row[5]) == "industry"
        and header_key(row[7]) == "basicindustry"
    )


def extract_structure_table_rows(rows):
    """Read only the four hierarchy columns from NSE's 9-column table."""

    header_index = None

    for index, row in enumerate(rows):
        if is_structure_header(row):
            header_index = index
            break

    if header_index is None:
        return []

    extracted = []

    for row in rows[header_index + 1:]:
        if not row or len(row) < 8:
            continue

        if is_structure_header(row):
            continue

        hierarchy = [
            clean(row[index])
            for index in STRUCTURE_COLUMN_INDEXES
        ]

        if any(hierarchy):
            extracted.append(hierarchy)

    return extracted


def normalize_taxonomy_rows(rows):
    """Forward-fill merged hierarchy cells without inventing values."""

    output = []
    current = {level: "" for level in LEVELS}

    for raw_row in rows:
        row = [clean(value) for value in raw_row]

        if not row or not any(row):
            continue

        if len(row) < 4:
            row += [""] * (4 - len(row))

        row = row[:4]

        for index, level in enumerate(LEVELS):
            value = row[index]

            if value:
                current[level] = value

                for child in LEVELS[index + 1:]:
                    current[child] = ""

        if not all(current.values()):
            continue

        record = dict(current)

        if record not in output:
            output.append(record)

    return output


def extract_pdf_tables(pdf_path):
    """Extract the 9-column official NSE Structure PDF."""

    if not pdf_path.is_file():
        raise FileNotFoundError(
            f"Official Structure PDF not found: {pdf_path}"
        )

    hierarchy_rows = []
    header_tables_found = 0

    with pymupdf.open(pdf_path) as document:
        for page in document:
            finder = page.find_tables()

            for table in finder.tables:
                extracted = table.extract()

                if not extracted:
                    continue

                page_rows = extract_structure_table_rows(
                    extracted
                )

                if page_rows:
                    header_tables_found += 1
                    hierarchy_rows.extend(page_rows)

    if header_tables_found == 0:
        raise ValueError(
            "Could not identify the official 9-column NSE "
            "Structure table. Extraction stopped safely."
        )

    if not hierarchy_rows:
        raise ValueError(
            "No hierarchy rows were extracted. "
            "No taxonomy was fabricated."
        )

    return normalize_taxonomy_rows(hierarchy_rows)


def run_extraction():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    records = extract_pdf_tables(SOURCE_PDF)

    if not records:
        raise RuntimeError(
            "PDF extraction produced zero valid taxonomy records."
        )

    frame = pd.DataFrame(records, columns=LEVELS)

    counts = {
        level: int(frame[level].nunique())
        for level in LEVELS
    }

    count_check = {
        level: {
            "expected": expected,
            "actual": counts[level],
            "match": counts[level] == expected,
        }
        for level, expected in EXPECTED_COUNTS.items()
    }

    taxonomy_path = (
        OUTPUT_DIR / "nse_official_taxonomy.csv"
    )

    frame.to_csv(
        taxonomy_path,
        index=False,
        encoding="utf-8-sig",
    )

    all_counts_match = all(
        item["match"]
        for item in count_check.values()
    )

    report = {
        "source_file": str(SOURCE_PDF.relative_to(ROOT)),
        "source_type": "OFFICIAL_NSE_STRUCTURE_PDF",
        "records_extracted": len(frame),
        "unique_counts": counts,
        "expected_count_check": count_check,
        "taxonomy_status": (
            "PASS" if all_counts_match else "REVIEW"
        ),
        "company_mapping_status": "PENDING",
        "sector_mapping_enabled": False,
        "output_file": str(taxonomy_path.relative_to(ROOT)),
    }

    report_path = (
        REPORT_DIR
        / "nse_official_taxonomy_extraction.json"
    )

    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(json.dumps(report, indent=2, ensure_ascii=False))

    if not all_counts_match:
        raise RuntimeError(
            "NSE taxonomy count verification failed. "
            "Company mapping remains disabled."
        )

    return report


if __name__ == "__main__":
    run_extraction()