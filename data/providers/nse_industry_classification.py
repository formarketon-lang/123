
"""NSE Indices company-level industry classification provider.

This module accepts an official company-level CSV/XLSX file.
It does not infer, fabricate, or assign sector classifications.

The resulting records must still be reconciled against the NSE MII
EQ universe before they can be approved for TradeLab Pro.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


REQUIRED_COLUMNS = {
    "Symbol",
    "ISIN",
    "Macro Economic Sector",
    "Sector",
    "Industry",
    "Basic Industry",
}

COLUMN_ALIASES = {
    "symbol": "Symbol",
    "trading symbol": "Symbol",
    "nse symbol": "Symbol",
    "isin": "ISIN",
    "isin code": "ISIN",
    "isin number": "ISIN",
    "company": "Company",
    "company name": "Company",
    "name of company": "Company",
    "macro economic sector": "Macro Economic Sector",
    "macro-economic sector": "Macro Economic Sector",
    "macroeconomic sector": "Macro Economic Sector",
    "mes": "Macro Economic Sector",
    "mes code": "Macro Economic Sector Code",
    "mes_code": "Macro Economic Sector Code",
    "sector": "Sector",
    "sector name": "Sector",
    "sect code": "Sector Code",
    "sect_code": "Sector Code",
    "industry": "Industry",
    "industry name": "Industry",
    "ind code": "Industry Code",
    "ind_code": "Industry Code",
    "basic industry": "Basic Industry",
    "basic_industry": "Basic Industry",
    "basic ind code": "Basic Industry Code",
    "basic_ind_code": "Basic Industry Code",
}

OUTPUT_COLUMNS = [
    "Symbol",
    "Company",
    "ISIN",
    "Macro Economic Sector Code",
    "Macro Economic Sector",
    "Sector Code",
    "Sector",
    "Industry Code",
    "Industry",
    "Basic Industry Code",
    "Basic Industry",
    "Source",
    "Source Reference",
    "As Of Date",
]


def _clean_header(value: object) -> str:
    """Normalize an input column name."""
    return " ".join(
        str(value)
        .replace("\ufeff", "")
        .strip()
        .lower()
        .replace("_", " ")
        .split()
    )


def _clean_text(series: pd.Series) -> pd.Series:
    """Normalize text values without inventing missing data."""
    result = series.astype("string").str.strip()
    return result.mask(result.eq(""))


def _validate_isin(series: pd.Series) -> pd.Series:
    """Return a mask for syntactically valid Indian ISIN values."""
    return series.str.fullmatch(
        r"IN[A-Z0-9]{10}",
        na=False,
    )


def normalize_industry_classification(
    data: pd.DataFrame,
    source_name: str,
    source_reference: str,
    as_of_date: str | None = None,
) -> pd.DataFrame:
    """Validate and normalize official company-level classification.

    Required source fields:
    Symbol, ISIN, Macro Economic Sector, Sector, Industry,
    Basic Industry.

    Optional fields:
    Company and official classification codes.

    Duplicate symbols or ISINs are rejected. No arbitrary row is
    selected when the source contains ambiguous records.
    """

    if not isinstance(data, pd.DataFrame) or data.empty:
        raise ValueError(
            "Industry classification data is empty or invalid."
        )

    if not isinstance(source_name, str) or not source_name.strip():
        raise ValueError(
            "A non-empty official source name is required."
        )

    if (
        not isinstance(source_reference, str)
        or not source_reference.strip()
    ):
        raise ValueError(
            "A source URL or document reference is required."
        )

    frame = data.copy()

    normalized_headers = []
    for column in frame.columns:
        cleaned = _clean_header(column)
        normalized_headers.append(
            COLUMN_ALIASES.get(cleaned, str(column).strip())
        )

    frame.columns = normalized_headers

    if frame.columns.duplicated().any():
        duplicates = sorted(
            set(
                frame.columns[
                    frame.columns.duplicated(keep=False)
                ].tolist()
            )
        )
        raise ValueError(
            "Duplicate columns after normalization: "
            + ", ".join(duplicates)
        )

    missing = sorted(REQUIRED_COLUMNS.difference(frame.columns))

    if missing:
        raise ValueError(
            "Official classification file is missing required "
            "columns: "
            + ", ".join(missing)
        )

    for column in OUTPUT_COLUMNS:
        if column not in frame.columns:
            frame[column] = pd.NA

    text_columns = [
        "Symbol",
        "Company",
        "ISIN",
        "Macro Economic Sector Code",
        "Macro Economic Sector",
        "Sector Code",
        "Sector",
        "Industry Code",
        "Industry",
        "Basic Industry Code",
        "Basic Industry",
    ]

    for column in text_columns:
        frame[column] = _clean_text(frame[column])

    for column in [
        "Symbol",
        "ISIN",
        "Macro Economic Sector Code",
        "Sector Code",
        "Industry Code",
        "Basic Industry Code",
    ]:
        frame[column] = frame[column].str.upper()

    missing_values = {}

    for column in [
        "Symbol",
        "ISIN",
        "Macro Economic Sector",
        "Sector",
        "Industry",
        "Basic Industry",
    ]:
        missing_values[column] = int(
            frame[column].isna().sum()
        )

    invalid_isin = ~_validate_isin(frame["ISIN"])

    if invalid_isin.any():
        examples = (
            frame.loc[invalid_isin, "Symbol"]
            .head(10)
            .fillna("<missing symbol>")
            .tolist()
        )
        raise ValueError(
            "Invalid or missing Indian ISIN values found. "
            "Affected symbols: "
            + ", ".join(examples)
        )

    if any(missing_values.values()):
        details = [
            f"{name}={count}"
            for name, count in missing_values.items()
            if count
        ]
        raise ValueError(
            "Required classification values are missing: "
            + ", ".join(details)
        )

    if frame["Symbol"].duplicated(keep=False).any():
        duplicates = sorted(
            frame.loc[
                frame["Symbol"].duplicated(keep=False),
                "Symbol",
            ].dropna().unique().tolist()
        )
        raise ValueError(
            "Duplicate symbols make classification ambiguous: "
            + ", ".join(duplicates[:20])
        )

    if frame["ISIN"].duplicated(keep=False).any():
        duplicates = sorted(
            frame.loc[
                frame["ISIN"].duplicated(keep=False),
                "ISIN",
            ].dropna().unique().tolist()
        )
        raise ValueError(
            "Duplicate ISIN values make classification ambiguous: "
            + ", ".join(duplicates[:20])
        )

    frame["Source"] = source_name.strip()
    frame["Source Reference"] = source_reference.strip()
    frame["As Of Date"] = (
        str(as_of_date).strip()
        if as_of_date is not None
        else pd.NA
    )

    frame = frame[OUTPUT_COLUMNS].copy()

    return (
        frame.sort_values("Symbol")
        .reset_index(drop=True)
    )


def load_industry_classification_file(
    file_path: str | Path,
    source_name: str,
    source_reference: str,
    as_of_date: str | None = None,
) -> pd.DataFrame:
    """Load and validate an official CSV or XLSX classification file."""

    path = Path(file_path)

    if not path.exists() or not path.is_file():
        raise FileNotFoundError(
            f"Industry classification file not found: {path}"
        )

    suffix = path.suffix.lower()

    if suffix == ".csv":
        raw = pd.read_csv(
            path,
            dtype="string",
            encoding="utf-8-sig",
            low_memory=False,
        )

    elif suffix == ".xlsx":
        raw = pd.read_excel(
            path,
            dtype="string",
            engine="openpyxl",
        )

    else:
        raise ValueError(
            "Unsupported file format. Use CSV or XLSX only."
        )

    return normalize_industry_classification(
        data=raw,
        source_name=source_name,
        source_reference=source_reference,
        as_of_date=as_of_date,
)
  
