"""Extract the official four-level NSE Indices taxonomy from its PDF."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import fitz

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SOURCE_PDF = (
    ROOT / "data/raw/nse/industry_classification_sources/"
    "nse_industry_classification_structure.pdf"
)
OUTPUT_DIR = ROOT / "data/raw/nse/industry_classification_sources"
REPORT_DIR = ROOT / "reports/industry_classification"

LEVELS = [
    "Macro Economic Sector",
    "Sector",
    "Industry",
    "Basic Industry",
]

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
    return re.sub(r"[^a-z]", "", clean(value).lower())


HEADER_ALIASES = {
    "macroeconomicindicator": "Macro Economic Sector",
    "macroeconomicsector": "Macro Economic Sector",
    "sector": "Sector",
    "industry": "Industry",
    "basicindustry": "Basic Industry",
}


def normalize_taxonomy_rows(rows):
    """Normalize table rows and forward-fill merged hierarchy cells."""
    output = []
    current = {level: "" for level in LEVELS}

    for raw_row in rows:
        row = [clean(value) for value in raw_row]

        if not row or not any(row):
            continue

        mapped_headers = [
            HEADER_ALIASES.get(header_key(value))
            for value in row
        ]

        if all(
            level in mapped_headers
            for level in LEVELS
        ):
            continue

        if len(row) < 4:
            row += [""] * (4 - len(row))

        row = row[:4]

        # Skip repeated table headings.
        if any(
            header_key(value) in HEADER_ALIASES
            for value in row
        ):
            continue

        for index, level in enumerate(LEVELS):
            value = row[index]

            if value:
                current[level] = value

                # A new parent invalidates old child values.
                for child in LEVELS[index + 1:]:
                    current[child] = ""

        if not current["Basic Industry"]:
            continue

        if not all(current.values()):
            continue

        record = dict(current)

        if record not in output:
            output.append(record)

    return output


def extract_pdf_tables(pdf_path):
    """Extract tables from all pages using PyMuPDF."""
    if not pdf_path.is_file():
        raise FileNotFoundError(
            f"Official Structure PDF not found: {pdf_path}"
        )

    rows = []

    with fitz.open(pdf_path) as document:
        for page_number, page in enumerate(document, start=1):
            finder = page.find_tables()

            for table in finder.tables:
                extracted = table.extract()

                if extracted:
                    rows.extend(extracted)

    if not rows:
        raise ValueError(
            "No tables were extracted from the official PDF. "
            "Manual review is required; no taxonomy was fabricated."
        )

    return normalize_taxonomy_rows(rows)


def run_extraction():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    records = extract_pdf_tables(SOURCE_PDF)

    if not records:
        raise RuntimeError(
            "PDF extraction produced zero valid taxonomy records."
        )

    import pandas as pd

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

    taxonomy_path = OUTPUT_DIR / "nse_official_taxonomy.csv"
    frame.to_csv(
        taxonomy_path,
        index=False,
        encoding="utf-8-sig",
    )

    report = {
        "source_file": str(SOURCE_PDF.relative_to(ROOT)),
        "records_extracted": len(frame),
        "unique_counts": counts,
        "expected_count_check": count_check,
        "taxonomy_status": (
            "PASS"
            if all(item["match"] for item in count_check.values())
            else "REVIEW"
        ),
        "company_mapping_status": "PENDING",
        "sector_mapping_enabled": False,
        "output_file": str(taxonomy_path.relative_to(ROOT)),
    }

    report_path = (
        REPORT_DIR / "nse_official_taxonomy_extraction.json"
    )

    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(json.dumps(report, indent=2, ensure_ascii=False))

    if report["taxonomy_status"] != "PASS":
        raise RuntimeError(
            "Taxonomy extraction completed but count verification "
            "requires review. Company mapping remains disabled."
        )

    return report


if __name__ == "__main__":
    run_extraction()
