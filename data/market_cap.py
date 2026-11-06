"""TradeLab Pro - AMFI Market Capitalization Classification.

Official AMFI half-yearly classification.
This is not live daily market capitalization.

AMFI ISIN is the unique matching key. Duplicate NSE symbols
are permitted when they belong to different ISIN records.
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
    """Normalize source column names."""
    return "".join(
        character
        for character in str(value).strip().lower()
        if character.isalnum()
    )


def _find_column(columns, required_token):
    for column in columns:
        if _token(column) == required_token:
            return column

    raise ValueError(
        f"AMFI source is missing column: {required_token}"
    )


def _find_header_row(raw):
    """Find AMFI table header despite title rows."""
    for index in range(len(raw)):
        values = {
            _token(value)
            for value in raw.iloc[index].dropna().tolist()
        }

        if (
            "isin" in values
            and "nsesymbol" in values
            and any(
                value.startswith("categorization")
                for value in values
            )
        ):
            return index

    raise ValueError("AMFI Excel header row could not be identified.")


def fetch_amfi_market_cap():
    """Download and normalize official AMFI Excel data."""
    response = requests.get(
        AMFI_SOURCE_URL,
        timeout=30,
        headers={"User-Agent": "TradeLab-Pro/1.0"},
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
    """Normalize AMFI ISIN, NSE symbol and SEBI category."""
    if not isinstance(data, pd.DataFrame):
        raise TypeError("AMFI data must be a pandas DataFrame.")

    if data.empty:
        raise ValueError("AMFI market-cap data is empty.")

    isin_col = _find_column(data.columns, "isin")
    symbol_col = _find_column(data.columns, "nsesymbol")

    category_col = next(
        (
            column for column in data.columns
            if _token(column).startswith("categorization")
        ),
        None,
    )

    if category_col is None:
        raise ValueError("AMFI SEBI categorization column is missing.")

    average_col = next(
        (
            column for column in data.columns
            if _token(column).startswith("averageofallexchanges")
        ),
        None,
    )

    result = pd.DataFrame({
        "ISIN": (
            data[isin_col]
            .astype("string")
            .str.strip()
            .str.upper()
        ),
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

    result = result[
        result["ISIN"].notna()
        & result["ISIN"].ne("")
        & result["AMFI NSE Symbol"].notna()
        & result["AMFI NSE Symbol"].ne("")
    ].copy()

    invalid = (
        set(result["Market Cap Category"].dropna())
        - VALID_CATEGORIES
    )

    if invalid:
        raise ValueError(
            "Unknown AMFI categories: " + ", ".join(sorted(invalid))
        )

    if result["Market Cap Category"].isna().any():
        raise ValueError("AMFI category is missing.")

    # ISIN must be unique because it is the authoritative join key.
    if result["ISIN"].duplicated().any():
        duplicates = (
            result.loc[
                result["ISIN"].duplicated(keep=False),
                "ISIN",
            ]
            .dropna()
            .unique()
            .tolist()
        )
        raise ValueError(
            "Duplicate ISIN values in AMFI data: "
            + ", ".join(duplicates[:10])
        )

    # IMPORTANT:
    # Duplicate NSE symbols are allowed when ISIN values differ.
    # Enrichment validates both ISIN and NSE Symbol before approval.

    return result.reset_index(drop=True)


def enrich_nse_universe_with_amfi(universe, amfi_data):
    """Enrich verified NSE EQ securities using ISIN + symbol."""
    if not isinstance(universe, pd.DataFrame) or universe.empty:
        raise ValueError("Verified NSE universe is empty.")

    required = {"Symbol", "ISIN", "Series"}
    missing = required - set(universe.columns)

    if missing:
        raise ValueError(
            f"NSE universe missing columns: {sorted(missing)}"
        )

    if not isinstance(amfi_data, pd.DataFrame) or amfi_data.empty:
        raise ValueError("AMFI data is empty.")

    required_amfi = {
        "ISIN",
        "AMFI NSE Symbol",
        "Market Cap Category",
    }

    if required_amfi - set(amfi_data.columns):
        amfi_data = normalize_amfi_market_cap(amfi_data)

    output = universe.copy()

    output["Symbol"] = (
        output["Symbol"].astype("string").str.strip().str.upper()
    )
    output["ISIN"] = (
        output["ISIN"].astype("string").str.strip().str.upper()
    )
    output["Series"] = (
        output["Series"].astype("string").str.strip().str.upper()
    )

    eligible_mask = (
        output["Series"].eq("EQ")
        & output["ISIN"].notna()
        & output["Symbol"].notna()
    )

    eligible = output.loc[eligible_mask].copy()

    if eligible["ISIN"].duplicated().any():
        raise ValueError("Duplicate ISIN in NSE EQ universe.")

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

    if amfi["ISIN"].duplicated().any():
        raise ValueError("Duplicate ISIN in AMFI data.")

    enrichment_columns = [
        "AMFI NSE Symbol",
        "Market Cap Category",
        "Market Cap Match Status",
        "AMFI Period",
        "AMFI Source",
        "Market Cap Source",
        "AMFI Average Market Cap (₹ Cr)",
    ]

    eligible = eligible.drop(
        columns=[
            column for column in enrichment_columns
            if column in eligible.columns
        ],
        errors="ignore",
    )

    merged = eligible.merge(
        amfi,
        on="ISIN",
        how="left",
        validate="one_to_one",
    )

    isin_found = merged["AMFI NSE Symbol"].notna()

    exact_match = (
        isin_found
        & merged["Symbol"].eq(merged["AMFI NSE Symbol"])
    )

    merged["Market Cap Match Status"] = "NO_AMFI_MATCH"

    merged.loc[
        isin_found & ~exact_match,
        "Market Cap Match Status",
    ] = "ISIN_SYMBOL_MISMATCH"

    merged.loc[
        exact_match,
        "Market Cap Match Status",
    ] = "MATCHED"

    # Approve category only when BOTH identifiers match.
    merged["Market Cap Category"] = (
        merged["Market Cap Category"].where(exact_match)
    )

    merged["AMFI Period"] = AMFI_PERIOD
    merged["AMFI Source"] = AMFI_SOURCE_NAME

    output = output.drop(
        columns=[
            column for column in enrichment_columns
            if column in output.columns
        ],
        errors="ignore",
    )

    output["AMFI NSE Symbol"] = pd.NA
    output["Market Cap Category"] = pd.NA
    output["Market Cap Match Status"] = "NO_AMFI_MATCH"
    output["AMFI Period"] = AMFI_PERIOD
    output["AMFI Source"] = AMFI_SOURCE_NAME

    if "AMFI Average Market Cap (₹ Cr)" in merged.columns:
        output["AMFI Average Market Cap (₹ Cr)"] = pd.NA

    output.loc[
        eligible_mask,
        "AMFI NSE Symbol",
    ] = merged["AMFI NSE Symbol"].to_numpy()

    output.loc[
        eligible_mask,
        "Market Cap Category",
    ] = merged["Market Cap Category"].to_numpy()

    output.loc[
        eligible_mask,
        "Market Cap Match Status",
    ] = merged["Market Cap Match Status"].to_numpy()

    if "AMFI Average Market Cap (₹ Cr)" in merged.columns:
        output.loc[
            eligible_mask,
            "AMFI Average Market Cap (₹ Cr)",
        ] = merged["AMFI Average Market Cap (₹ Cr)"].to_numpy()

    return output


def filter_by_market_cap(universe, selected_category):
    """Filter only verified NSE EQ rows with approved AMFI categories."""
    if selected_category == "All Market Caps":
        return universe.copy()

    category_map = {
        "Large Cap": "LARGE CAP",
        "Mid Cap": "MID CAP",
        "Small Cap": "SMALL CAP",
    }

    if selected_category not in category_map:
        raise ValueError("Invalid market-cap selection.")

    required = {
        "Series",
        "Market Cap Category",
        "Market Cap Match Status",
    }

    missing = required - set(universe.columns)

    if missing:
        raise ValueError(
            "AMFI classification has not been integrated. "
            f"Missing columns: {sorted(missing)}"
        )

    mask = (
        universe["Series"].astype("string").str.upper().eq("EQ")
        & universe["Market Cap Match Status"].eq("MATCHED")
        & universe["Market Cap Category"].eq(
            category_map[selected_category]
        )
    )

    return universe.loc[mask].copy()
            
