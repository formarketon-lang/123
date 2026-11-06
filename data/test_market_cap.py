"""
TradeLab Pro - AMFI Market Capitalization Classification

Source:
AMFI official half-yearly average market capitalization list.

This is NOT live daily market capitalization.
A category is approved only when both NSE Symbol and ISIN
match the verified NSE EQ universe.
"""

from io import BytesIO

import pandas as pd
import requests


AMFI_SOURCE_URL = (
    "https://portal.amfiindia.com/spages/"
    "AverageMarketCapitalization30Jun2026.xlsx"
)

AMFI_PERIOD = "2026-01-01 to 2026-06-30"

AMFI_SOURCE_NAME = "AMFI Half-Yearly Classification"

VALID_CATEGORIES = {
    "LARGE CAP",
    "MID CAP",
    "SMALL CAP",
}


def _token(value):
    """Normalize a column label for reliable header matching."""
    return "".join(
        character
        for character in str(value).strip().lower()
        if character.isalnum()
    )


def _find_column(columns, required_token):
    """Find a source column by its normalized header."""
    for column in columns:
        if _token(column) == required_token:
            return column

    raise ValueError(
        f"AMFI source is missing required column: {required_token}"
    )


def _find_header_row(raw):
    """Find the AMFI table header even when title rows come first."""
    for index in range(len(raw)):
        values = {
            _token(value)
            for value in raw.iloc[index].dropna().tolist()
        }

        has_isin = "isin" in values
        has_nse_symbol = "nsesymbol" in values
        has_category = any(
            value.startswith("categorization")
            for value in values
        )

        if has_isin and has_nse_symbol and has_category:
            return index

    raise ValueError(
        "AMFI Excel header row could not be identified. "
        "Source format may have changed."
    )


def fetch_amfi_market_cap():
    """
    Download and normalize the official AMFI Excel file.

    Raises an exception instead of returning unverified data.
    """
    response = requests.get(
        AMFI_SOURCE_URL,
        timeout=30,
        headers={
            "User-Agent": "TradeLab-Pro/1.0",
        },
    )
    response.raise_for_status()

    if not response.content:
        raise ValueError("AMFI returned an empty Excel file.")

    raw = pd.read_excel(
        BytesIO(response.content),
        header=None,
        dtype=object,
        engine="openpyxl",
    )

    header_row = _find_header_row(raw)

    headers = [
        str(value).strip()
        for value in raw.iloc[header_row].tolist()
    ]

    data = raw.iloc[header_row + 1:].copy()
    data.columns = headers

    return normalize_amfi_market_cap(data)


def normalize_amfi_market_cap(data):
    """
    Normalize AMFI rows.

    Required:
    ISIN, NSE Symbol, and SEBI category.

    Average market cap is retained when the source provides it.
    """
    if not isinstance(data, pd.DataFrame):
        raise TypeError("AMFI data must be a pandas DataFrame.")

    if data.empty:
        raise ValueError("AMFI market-cap data is empty.")

    isin_col = _find_column(data.columns, "isin")
    symbol_col = _find_column(data.columns, "nsesymbol")

    category_col = None
    for column in data.columns:
        if _token(column).startswith("categorization"):
            category_col = column
            break

    if category_col is None:
        raise ValueError(
            "AMFI SEBI categorization column is missing."
        )

    average_col = None
    for column in data.columns:
        token = _token(column)
        if token.startswith("averageofallexchanges"):
            average_col = column
            break

    result = pd.DataFrame({
        "ISIN": data[isin_col].astype("string").str.strip().str.upper(),
        "AMFI NSE Symbol": (
            data[symbol_col]
            .astype("string")
            .str.strip()
            .str.upper()
        ),
        "Market Cap Category": (
            data[category_col]
            .astype("string")
            .str.strip()
            .str.upper()
        ),
    })

    if average_col is not None:
        result["AMFI Average Market Cap (₹ Cr)"] = pd.to_numeric(
            data[average_col]
            .astype("string")
            .str.replace(",", "", regex=False)
            .str.strip(),
            errors="coerce",
        )

    # Ignore companies without an NSE listing in this AMFI row.
    result = result[
        result["ISIN"].notna()
        & result["AMFI NSE Symbol"].notna()
        & result["AMFI NSE Symbol"].ne("")
        & result["ISIN"].ne("")
    ].copy()

    invalid_categories = sorted(
        set(result["Market Cap Category"].dropna())
        - VALID_CATEGORIES
    )

    if invalid_categories:
        raise ValueError(
            "Unknown AMFI market-cap categories: "
            + ", ".join(invalid_categories)
        )

    if result["Market Cap Category"].isna().any():
        raise ValueError(
            "AMFI category is missing for one or more NSE listings."
        )

    if result["ISIN"].duplicated().any():
        duplicates = sorted(
            result.loc[
                result["ISIN"].duplicated(keep=False),
                "ISIN",
            ].unique().tolist()
        )
        raise ValueError(
            "Duplicate ISIN values in AMFI data: "
            + ", ".join(duplicates[:20])
        )

    if result["AMFI NSE Symbol"].duplicated().any():
        duplicates = sorted(
            result.loc[
                result["AMFI NSE Symbol"].duplicated(keep=False),
                "AMFI NSE Symbol",
            ].unique().tolist()
        )
        raise ValueError(
            "Duplicate NSE symbols in AMFI data: "
            + ", ".join(duplicates[:20])
        )

    return result.reset_index(drop=True)


def enrich_nse_universe_with_amfi(universe, amfi_data):
    """
    Add AMFI classification to the official NSE EQ universe.

    A category is accepted only if both ISIN and NSE Symbol match.
    Mismatches remain visible but receive no approved category.
    """
    if not isinstance(universe, pd.DataFrame) or universe.empty:
        raise ValueError("Verified NSE universe is empty.")

    required = {"Symbol", "ISIN", "Series"}
    missing = required.difference(universe.columns)

    if missing:
        raise ValueError(
            "NSE universe missing columns: "
            + ", ".join(sorted(missing))
        )

    if not isinstance(amfi_data, pd.DataFrame) or amfi_data.empty:
        raise ValueError("Normalized AMFI data is empty.")

    amfi_required = {
        "ISIN",
        "AMFI NSE Symbol",
        "Market Cap Category",
    }
    amfi_missing = amfi_required.difference(amfi_data.columns)

    if amfi_missing:
        raise ValueError(
            "AMFI data missing columns: "
            + ", ".join(sorted(amfi_missing))
        )

    result = universe.copy()

    result["Symbol"] = (
        result["Symbol"].astype("string").str.strip().str.upper()
    )
    result["ISIN"] = (
        result["ISIN"].astype("string").str.strip().str.upper()
    )
    result["Series"] = (
        result["Series"].astype("string").str.strip().str.upper()
    )

    eligible_mask = (
        result["Series"].eq("EQ")
        & result["ISIN"].notna()
        & result["Symbol"].notna()
    )

    eligible = result.loc[eligible_mask].copy()

    if eligible["ISIN"].duplicated().any():
        raise ValueError(
            "Duplicate ISIN found in verified NSE EQ universe."
        )

    amfi = amfi_data.copy()
    amfi["ISIN"] = (
        amfi["ISIN"].astype("string").str.strip().str.upper()
    )
    amfi["AMFI NSE Symbol"] = (
        amfi["AMFI NSE Symbol"]
        .astype("string")
        .str.strip()
        .str.upper()
    )

    merged = eligible.merge(
        amfi,
        on="ISIN",
        how="left",
        validate="one_to_one",
    )

    matched = (
        merged["AMFI NSE Symbol"].notna()
        & merged["Symbol"].eq(merged["AMFI NSE Symbol"])
    )

    isin_found = merged["AMFI NSE Symbol"].notna()

    merged["Market Cap Match Status"] = "NO_AMFI_MATCH"
    merged.loc[isin_found & ~matched, "Market Cap Match Status"] = (
        "ISIN_SYMBOL_MISMATCH"
    )
    merged.loc[matched, "Market Cap Match Status"] = "MATCHED"

    # Never expose a category for an ISIN-only or symbol-only match.
    merged.loc[~matched, "Market Cap Category"] = pd.NA

    merged["AMFI Period"] = AMFI_PERIOD
    merged["Market Cap Source"] = AMFI_SOURCE_NAME

    output = result.copy()

    extra_columns = [
        "AMFI NSE Symbol",
        "Market Cap Category",
        "Market Cap Match Status",
        "AMFI Period",
        "Market Cap Source",
    ]

    if "AMFI Average Market Cap (₹ Cr)" in merged.columns:
        extra_columns.append("AMFI Average Market Cap (₹ Cr)")

    for column in extra_columns:
        output[column] = pd.NA

    output.loc[eligible_mask, extra_columns] = (
        merged[extra_columns].to_numpy()
    )

    return output


def filter_by_market_cap(universe, selected_category):
    """
    Filter verified NSE EQ securities by AMFI category.

    'All Market Caps' returns the input unchanged.
    Unknown or unavailable categories fail closed.
    """
    if selected_category == "All Market Caps":
        return universe.copy()

    if selected_category not in {
        "Large Cap",
        "Mid Cap",
        "Small Cap",
    }:
        raise ValueError("Invalid market-cap selection.")

    required = {
        "Series",
        "Market Cap Category",
        "Market Cap Match Status",
    }
    missing = required.difference(universe.columns)

    if missing:
        raise ValueError(
            "AMFI classification has not been integrated. "
            "Missing columns: "
            + ", ".join(sorted(missing))
        )

    mask = (
        universe["Series"].astype("string").str.upper().eq("EQ")
        & universe["Market Cap Match Status"].eq("MATCHED")
        & universe["Market Cap Category"].eq(
            selected_category.upper()
        )
    )

    return universe.loc[mask].copy()
      
