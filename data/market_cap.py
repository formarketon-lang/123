
"""AMFI half-yearly market-cap classification for NSE cash equities."""

from io import BytesIO

import pandas as pd
import requests


AMFI_SOURCE_URL = (
    "https://portal.amfiindia.com/spages/"
    "AverageMarketCapitalization30Jun2026.xlsx"
)
AMFI_PERIOD = "2026-01-01 to 2026-06-30"
AMFI_SOURCE_NAME = "AMFI Half-Yearly Classification"

VALID_CATEGORIES = {"LARGE CAP", "MID CAP", "SMALL CAP"}


def _token(value):
    """Normalize a column heading for reliable matching."""
    return "".join(
        character.lower()
        for character in str(value)
        if character.isalnum()
    )


def _find_column(columns, required_token):
    """Find a column by its normalized heading."""
    for column in columns:
        if _token(column) == required_token:
            return column
    raise ValueError(
        f"Required AMFI column not found: {required_token}"
    )


def _find_header_row(raw):
    """Locate the AMFI table header inside the Excel sheet."""
    for index, row in raw.iterrows():
        tokens = {_token(value) for value in row.tolist()}

        has_isin = "isin" in tokens
        has_symbol = "nsesymbol" in tokens
        has_category = any(
            token.startswith("categorization")
            for token in tokens
        )

        if has_isin and has_symbol and has_category:
            return index

    raise ValueError("AMFI table header row could not be located")


def normalize_amfi_market_cap(data):
    """Normalize AMFI data into verified NSE symbol/ISIN records."""
    if not isinstance(data, pd.DataFrame) or data.empty:
        raise ValueError("AMFI data is empty or invalid")

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
        raise ValueError("AMFI categorization column not found")

    average_col = next(
        (
            column for column in data.columns
            if _token(column).startswith("averageofallexchanges")
        ),
        None,
    )

    result = pd.DataFrame()
    result["ISIN"] = (
        data[isin_col].fillna("").astype(str).str.strip().str.upper()
    )
    result["AMFI NSE Symbol"] = (
        data[symbol_col].fillna("").astype(str).str.strip().str.upper()
    )
    result["Market Cap Category"] = (
        data[category_col].fillna("").astype(str)
        .str.strip().str.upper()
    )

    if average_col is not None:
        result["Average Market Cap (Rs. Cr.)"] = pd.to_numeric(
            data[average_col].astype(str).str.replace(",", "", regex=False),
            errors="coerce",
        )

    result = result[
        result["ISIN"].ne("")
        & result["AMFI NSE Symbol"].ne("")
    ].copy()

    invalid = set(result["Market Cap Category"]) - VALID_CATEGORIES
    if invalid:
        raise ValueError(
            f"Unknown or missing AMFI categories: {sorted(invalid)}"
        )

    if result["ISIN"].duplicated().any():
        raise ValueError("Duplicate ISIN found in AMFI data")

    if result["AMFI NSE Symbol"].duplicated().any():
        raise ValueError("Duplicate NSE Symbol found in AMFI data")

    return result.reset_index(drop=True)


def fetch_amfi_market_cap():
    """Download and normalize the official AMFI Excel classification."""
    response = requests.get(
        AMFI_SOURCE_URL,
        timeout=30,
        headers={"User-Agent": "Mozilla/5.0 TradeLabPro/1.0"},
    )
    response.raise_for_status()

    raw = pd.read_excel(
        BytesIO(response.content),
        header=None,
        dtype=object,
        engine="openpyxl",
    )

    header_index = _find_header_row(raw)
    headers = raw.iloc[header_index].tolist()

    data = raw.iloc[header_index + 1:].copy()
    data.columns = headers
    data = data.dropna(how="all")

    return normalize_amfi_market_cap(data)


def enrich_nse_universe_with_amfi(universe, amfi_data):
    """Match AMFI categories to NSE EQ securities using ISIN and symbol."""
    required = {"Symbol", "ISIN", "Series"}
    missing = required - set(universe.columns)

    if missing:
        raise ValueError(
            f"NSE universe missing columns: {sorted(missing)}"
        )

    if not isinstance(amfi_data, pd.DataFrame):
        raise ValueError("AMFI data must be a DataFrame")

    required_amfi = {
        "ISIN", "AMFI NSE Symbol", "Market Cap Category"
    }
    if required_amfi - set(amfi_data.columns):
        amfi_data = normalize_amfi_market_cap(amfi_data)

    output = universe.copy()

    output["Market Cap Category"] = pd.NA
    output["Market Cap Match Status"] = "NO_AMFI_MATCH"
    output["AMFI Period"] = AMFI_PERIOD
    output["AMFI Source"] = AMFI_SOURCE_NAME

    if "Average Market Cap (Rs. Cr.)" in amfi_data.columns:
        output["Average Market Cap (Rs. Cr.)"] = pd.NA

    eligible_mask = (
        output["Series"].astype(str).str.strip().str.upper().eq("EQ")
        & output["ISIN"].notna()
    )

    eligible = output.loc[eligible_mask].copy()
    eligible["ISIN"] = (
        eligible["ISIN"].astype(str).str.strip().str.upper()
    )
    eligible["Symbol"] = (
        eligible["Symbol"].astype(str).str.strip().str.upper()
    )

    if eligible["ISIN"].duplicated().any():
        raise ValueError("Duplicate ISIN found in NSE EQ universe")

    amfi = amfi_data.copy()
    amfi["ISIN"] = amfi["ISIN"].astype(str).str.strip().str.upper()
    amfi["AMFI NSE Symbol"] = (
        amfi["AMFI NSE Symbol"].astype(str).str.strip().str.upper()
    )

    if amfi["ISIN"].duplicated().any():
        raise ValueError("Duplicate ISIN found in AMFI data")

    merged = eligible.merge(
        amfi,
        on="ISIN",
        how="left",
        validate="one_to_one",
    )

    has_match = merged["AMFI NSE Symbol"].notna()
    exact_match = (
        has_match
        & merged["Symbol"].eq(merged["AMFI NSE Symbol"])
    )

    merged["Market Cap Match Status"] = "NO_AMFI_MATCH"
    merged.loc[has_match & ~exact_match, "Market Cap Match Status"] = (
        "ISIN_SYMBOL_MISMATCH"
    )
    merged.loc[exact_match, "Market Cap Match Status"] = "MATCHED"

    merged["Market Cap Category"] = merged[
        "Market Cap Category"
    ].where(exact_match)

    output.loc[
        eligible_mask, "Market Cap Match Status"
    ] = merged["Market Cap Match Status"].to_numpy()

    output.loc[
        eligible_mask, "Market Cap Category"
    ] = merged["Market Cap Category"].to_numpy()

    if "Average Market Cap (Rs. Cr.)" in merged.columns:
        output.loc[
            eligible_mask, "Average Market Cap (Rs. Cr.)"
        ] = merged["Average Market Cap (Rs. Cr.)"].to_numpy()

    return output


def filter_by_market_cap(universe, selected_category):
    """Return only NSE EQ rows with an exact verified AMFI category."""
    if selected_category == "All Market Caps":
        return universe.copy()

    category = str(selected_category).strip().upper()
    if category not in VALID_CATEGORIES:
        raise ValueError(
            f"Unsupported market-cap category: {selected_category}"
        )

    required = {
        "Series",
        "Market Cap Category",
        "Market Cap Match Status",
    }
    if required - set(universe.columns):
        raise ValueError(
            "Market-cap classification has not been integrated "
            "with the NSE universe"
        )

    mask = (
        universe["Series"].astype(str).str.strip().str.upper().eq("EQ")
        & universe["Market Cap Match Status"].eq("MATCHED")
        & universe["Market Cap Category"].eq(category)
    )

    return universe.loc[mask].copy()
  
