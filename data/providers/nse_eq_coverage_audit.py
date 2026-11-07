"""Full NSE EQ universe versus company classification coverage audit.

This module performs identity reconciliation only.
It never infers or assigns sector classifications.
It does not authorize or activate production sector mapping.
"""

from __future__ import annotations

import pandas as pd


REQUIRED_CLASSIFICATION_COLUMNS = {"Symbol", "ISIN"}
REQUIRED_NSE_COLUMNS = {"Symbol", "ISIN", "Series"}


def _normalise(series: pd.Series) -> pd.Series:
    return series.astype("string").str.strip().str.upper()


def _source_is_primary_mii(data: pd.DataFrame) -> bool:
    if "Source" not in data.columns:
        return False

    sources = (
        data["Source"]
        .dropna()
        .astype("string")
        .str.strip()
        .str.upper()
        .unique()
        .tolist()
    )

    return bool(sources) and all("MII" in item for item in sources)


def build_nse_eq_coverage_audit(
    classification: pd.DataFrame,
    nse_universe: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Return NSE EQ detail, classification-only rows and summary."""

    if not isinstance(classification, pd.DataFrame) or classification.empty:
        raise ValueError("Classification input is empty or invalid.")

    if not isinstance(nse_universe, pd.DataFrame) or nse_universe.empty:
        raise ValueError("NSE universe input is empty or invalid.")

    missing_classification = (
        REQUIRED_CLASSIFICATION_COLUMNS.difference(
            classification.columns
        )
    )
    if missing_classification:
        raise ValueError(
            "Classification requires Symbol and ISIN."
        )

    missing_nse = REQUIRED_NSE_COLUMNS.difference(
        nse_universe.columns
    )
    if missing_nse:
        raise ValueError(
            "NSE universe requires Symbol, ISIN and Series."
        )

    classification_data = classification.copy().reset_index(drop=True)
    nse_data = nse_universe.copy().reset_index(drop=True)

    classification_data["Symbol"] = _normalise(
        classification_data["Symbol"]
    )
    classification_data["ISIN"] = _normalise(
        classification_data["ISIN"]
    )

    nse_data["Symbol"] = _normalise(nse_data["Symbol"])
    nse_data["ISIN"] = _normalise(nse_data["ISIN"])
    nse_data["Series"] = _normalise(nse_data["Series"])

    if classification_data[["Symbol", "ISIN"]].isna().any().any():
        raise ValueError(
            "Classification contains missing Symbol or ISIN."
        )

    if classification_data[["Symbol", "ISIN"]].eq("").any().any():
        raise ValueError(
            "Classification contains blank Symbol or ISIN."
        )

    if nse_data[["Symbol", "ISIN", "Series"]].isna().any().any():
        raise ValueError(
            "NSE input contains missing Symbol, ISIN or Series."
        )

    if nse_data[["Symbol", "ISIN", "Series"]].eq("").any().any():
        raise ValueError(
            "NSE input contains blank Symbol, ISIN or Series."
        )

    nse_eq = nse_data.loc[
        nse_data["Series"].eq("EQ")
    ].copy().reset_index(drop=True)

    if nse_eq.empty:
        raise ValueError("NSE input contains no EQ rows.")

    classification_symbol_counts = (
        classification_data["Symbol"].value_counts(dropna=False)
    )
    classification_isin_counts = (
        classification_data["ISIN"].value_counts(dropna=False)
    )
    nse_symbol_counts = nse_eq["Symbol"].value_counts(dropna=False)
    nse_isin_counts = nse_eq["ISIN"].value_counts(dropna=False)

    classification_symbols = set(classification_data["Symbol"])
    nse_symbols = set(nse_eq["Symbol"])

    detail = nse_eq.copy()

    detail["NSE_Symbol_Count"] = (
        detail["Symbol"].map(nse_symbol_counts).astype(int)
    )
    detail["NSE_ISIN_Count"] = (
        detail["ISIN"].map(nse_isin_counts).astype(int)
    )

    detail["Classification_Symbol_Count"] = (
        detail["Symbol"]
        .map(classification_symbol_counts)
        .fillna(0)
        .astype(int)
    )

    detail["Classification_ISIN_Count"] = (
        detail["Symbol"]
        .map(
            classification_data
            .drop_duplicates(subset=["Symbol"], keep=False)
            .set_index("Symbol")["ISIN"]
            .map(classification_isin_counts)
        )
        .fillna(0)
        .astype(int)
    )

    classification_by_symbol = (
        classification_data
        .drop_duplicates(subset=["Symbol"], keep=False)
        .set_index("Symbol")["ISIN"]
    )

    detail["Classification_ISIN"] = detail["Symbol"].map(
        classification_by_symbol
    )

    statuses = []

    for row in detail.itertuples(index=False):
        symbol = row.Symbol
        isin = row.ISIN

        if (
            row.NSE_Symbol_Count > 1
            or row.NSE_ISIN_Count > 1
        ):
            status = "NSE_IDENTITY_AMBIGUOUS"

        elif row.Classification_Symbol_Count == 0:
            status = "CLASSIFICATION_MISSING"

        elif (
            row.Classification_Symbol_Count > 1
            or row.Classification_ISIN_Count > 1
        ):
            status = "CLASSIFICATION_AMBIGUOUS"

        elif pd.isna(row.Classification_ISIN):
            status = "CLASSIFICATION_MISSING"

        elif isin == row.Classification_ISIN:
            status = "MATCH"

        else:
            status = "ISIN_MISMATCH"

        statuses.append(status)

    detail["Coverage_Status"] = statuses

    classification_only = classification_data.loc[
        ~classification_data["Symbol"].isin(nse_symbols)
    ].copy()

    classification_only["Coverage_Status"] = (
        "CLASSIFICATION_SYMBOL_NOT_IN_NSE_EQ"
    )

    primary_mii = _source_is_primary_mii(nse_universe)

    total_nse_eq = len(detail)
    matched = int(detail["Coverage_Status"].eq("MATCH").sum())
    missing = int(
        detail["Coverage_Status"].eq("CLASSIFICATION_MISSING").sum()
    )
    mismatches = int(
        detail["Coverage_Status"].eq("ISIN_MISMATCH").sum()
    )
    nse_ambiguous = int(
        detail["Coverage_Status"]
        .eq("NSE_IDENTITY_AMBIGUOUS")
        .sum()
    )
    classification_ambiguous = int(
        detail["Coverage_Status"]
        .eq("CLASSIFICATION_AMBIGUOUS")
        .sum()
    )

    coverage_pct = (
        round((matched / total_nse_eq) * 100, 4)
        if total_nse_eq
        else 0.0
    )

    classification_only_rows = len(classification_only)

    full_coverage_passed = bool(
        primary_mii
        and total_nse_eq > 0
        and matched == total_nse_eq
        and missing == 0
        and mismatches == 0
        and nse_ambiguous == 0
        and classification_ambiguous == 0
        and classification_only_rows == 0
    )

    summary = {
        "status": "PASS" if full_coverage_passed else "REVIEW",
        "nse_source_status": (
            "PRIMARY_MII" if primary_mii else "NOT_PRIMARY_MII"
        ),
        "nse_eq_input_rows": total_nse_eq,
        "classification_input_rows": len(classification_data),
        "exact_symbol_isin_matches": matched,
        "classification_missing_rows": missing,
        "isin_mismatch_rows": mismatches,
        "nse_identity_ambiguous_rows": nse_ambiguous,
        "classification_ambiguous_rows": classification_ambiguous,
        "classification_symbols_not_in_nse_eq": (
            classification_only_rows
        ),
        "nse_eq_coverage_pct": coverage_pct,
        "full_universe_coverage_passed": full_coverage_passed,
        "matching_rule": "EXACT_NORMALISED_SYMBOL_AND_ISIN",
        "fuzzy_matching_used": False,
        "classification_inferred": False,
        "source_authenticity_verified": False,
        "mapping_eligible": False,
        "sector_mapping_activated": False,
        "note": (
            "Coverage is an identity audit only. A PASS does not "
            "prove classification source authenticity or licensing "
            "and does not authorize production sector mapping."
        ),
    }

    detail = detail.sort_values("Symbol").reset_index(drop=True)
    classification_only = (
        classification_only.sort_values("Symbol").reset_index(drop=True)
    )

    return detail, classification_only, summary
  
