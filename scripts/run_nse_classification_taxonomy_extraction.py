
"""Extract the official four-level NSE taxonomy from the Guidelines PDF."""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pymupdf

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SOURCE_PDF = (
    ROOT
    / "data/raw/nse/industry_classification_sources/"
    "nse_industry_classification_guidelines.pdf"
)

SOURCE_URL = (
    "https://niftyindices.com/docs/default-source/"
    "default-document-library/nse-indices_industry-classification-guideline-2023-07.pdf"
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
    return "".join(
        char for char in clean(value).lower() if char.isalnum()
    )


def is_guidelines_header(row):
    if not row or len(row) != 4:
        return False

    first = header_key(row[0])
    return (
        first in {"macroeconomicindicator", "macroeconomicsector"}
        and header_key(row[1]) == "sector"
        and header_key(row[2]) == "industry"
        and header_key(row[3]) == "basicindustry"
    )


def extract_guidelines_table_rows(rows):
    """Extract only the four hierarchy columns from Guidelines tables."""
    extracted = []
    header_found = False

    for row in rows:
        if not row or len(row) != 4:
            continue

        if is_guidelines_header(row):
            header_found = True
            continue

        if not header_found:
            continue

        values = [clean(value) for value in row]

        if any(values):
            extracted.append(values)

    return extracted


def normalize_taxonomy_rows(rows):
    """Forward-fill merged hierarchy cells and remove duplicate paths."""
    output = []
    seen = set()
    current = {level: "" for level in LEVELS}

    for raw_row in rows:
        row = [clean(value) for value in raw_row]

        if len(row) != 4 or not any(row):
            continue

        for index, level in enumerate(LEVELS):
            value = row[index]

            if value:
                current[level] = value
                for child in LEVELS[index + 1:]:
                    current[child] = ""

        if not all(current.values()):
            continue

        record = dict(current)
        key = tuple(record[level] for level in LEVELS)

        if key not in seen:
            seen.add(key)
            output.append(record)

    return output


def extract_pdf_tables(pdf_path):
    """Read the four-column table from the official Guidelines PDF."""
    if not pdf_path.is_file():
        raise FileNotFoundError(
            f"Official NSE Guidelines PDF not found: {pdf_path}"
        )

    if not pdf_path.read_bytes().startswith(b"%PDF"):
        raise ValueError("Guidelines source is not a valid PDF.")

    hierarchy_rows = []
    tables_found = 0

    with pymupdf.open(pdf_path) as document:
        for page in document:
            finder = page.find_tables()

            for table in finder.tables:
                rows = table.extract() or []
                page_rows = extract_guidelines_table_rows(rows)

                if page_rows:
                    tables_found += 1
                    hierarchy_rows.extend(page_rows)

    if tables_found == 0:
        raise ValueError(
            "Four-column NSE Guidelines taxonomy table not found. "
            "Structure PDF or an unrecognized table cannot be substituted."
        )

    records = normalize_taxonomy_rows(hierarchy_rows)

    if not records:
        raise ValueError(
            "No valid four-level taxonomy records extracted."
        )

    return records


def run_extraction():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    records = extract_pdf_tables(SOURCE_PDF)
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

    all_counts_match = all(
        item["match"] for item in count_check.values()
    )

    source_bytes = SOURCE_PDF.read_bytes()
    source_sha256 = hashlib.sha256(source_bytes).hexdigest()

    taxonomy_path = OUTPUT_DIR / "nse_official_taxonomy.csv"
    frame.to_csv(taxonomy_path, index=False, encoding="utf-8-sig")

    report = {
        "source_file": str(SOURCE_PDF.relative_to(ROOT)),
        "source_type": "OFFICIAL_NSE_INDUSTRY_CLASSIFICATION_GUIDELINES_PDF",
        "source_version": "July 2023",
        "source_url": SOURCE_URL,
        "source_size_bytes": len(source_bytes),
        "source_sha256": source_sha256,
        "extraction_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "table_format": "FOUR_COLUMN_GUIDELINES_TAXONOMY",
        "records_extracted": len(frame),
        "unique_counts": counts,
        "expected_count_check": count_check,
        "taxonomy_status": "PASS" if all_counts_match else "REVIEW",
        "company_mapping_status": "PENDING",
        "sector_mapping_enabled": False,
        "output_file": str(taxonomy_path.relative_to(ROOT)),
        "checksum_note": (
            "SHA-256 calculated locally from downloaded source bytes; "
            "not an independently published NSE checksum."
        ),
    }

    report_path = (
        REPORT_DIR / "nse_official_taxonomy_extraction.json"
    )
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(json.dumps(report, indent=2, ensure_ascii=False))

    if not all_counts_match:
        raise RuntimeError(
            "Official NSE taxonomy counts do not match expected values. "
            "Company mapping and sector mapping remain disabled."
        )

    return report


if __name__ == "__main__":
    run_extraction()
