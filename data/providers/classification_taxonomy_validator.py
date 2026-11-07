"""Validate company classifications against an official four-level taxonomy.

This module never infers or assigns a classification.
A company hierarchy passes only when its exact code/name path exists
in the supplied official taxonomy reference.
"""

from __future__ import annotations

import pandas as pd


HIERARCHY_COLUMNS = [
    "Macro Economic Sector Code",
    "Macro Economic Sector",
    "Sector Code",
    "Sector",
    "Industry Code",
    "Industry",
    "Basic Industry Code",
    "Basic Industry",
]


def _normalise(series: pd.Series) -> pd.Series:
    """Normalize comparison values without changing source records."""
    return (
        series.astype("string")
        .str.strip()
        .str.casefold()
    )


def _validate_columns(
    frame: pd.DataFrame,
    required: list[str],
    label: str,
) -> None:
    """Reject missing required columns."""
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        raise ValueError(f"{label} data is empty or invalid.")

    missing = sorted(set(required).difference(frame.columns))

    if missing:
        raise ValueError(
            f"{label} is missing required columns: "
            + ", ".join(missing)
        )


def validate_classification_taxonomy(
    classification: pd.DataFrame,
    official_taxonomy: pd.DataFrame,
) -> tuple[pd.DataFrame, dict]:
    """Compare each company hierarchy with an official taxonomy.

    Both inputs must contain all eight HIERARCHY_COLUMNS.
    No fuzzy matching, label inference, or automatic correction occurs.
    """

    _validate_columns(
        classification,
        HIERARCHY_COLUMNS,
        "Company classification",
    )
    _validate_columns(
        official_taxonomy,
        HIERARCHY_COLUMNS,
        "Official taxonomy",
    )

    company_data = classification.copy().reset_index(drop=True)
    taxonomy_data = official_taxonomy.copy()

    taxonomy_data = taxonomy_data[HIERARCHY_COLUMNS].copy()

    taxonomy_missing = taxonomy_data[HIERARCHY_COLUMNS].isna().any(
        axis=1
    )

    for column in HIERARCHY_COLUMNS:
        taxonomy_data[column] = _normalise(
            taxonomy_data[column]
        )

    taxonomy_missing |= taxonomy_data[HIERARCHY_COLUMNS].eq("").any(
        axis=1
    )

    if taxonomy_missing.any():
        raise ValueError(
            "Official taxonomy contains missing hierarchy values."
        )

    duplicate_paths = taxonomy_data.duplicated(
        subset=HIERARCHY_COLUMNS,
        keep=False,
    )

    if duplicate_paths.any():
        raise ValueError(
            "Official taxonomy contains duplicate hierarchy paths."
        )

    comparison = company_data[HIERARCHY_COLUMNS].copy()

    missing_company_values = comparison.isna()

    for column in HIERARCHY_COLUMNS:
        comparison[column] = _normalise(comparison[column])

    missing_company_values |= comparison.eq("")

    taxonomy_paths = set(
        map(
            tuple,
            taxonomy_data[HIERARCHY_COLUMNS].itertuples(
                index=False,
                name=None,
            ),
        )
    )

    statuses = []

    for position, row in enumerate(
        comparison.itertuples(index=False, name=None)
    ):
        if bool(missing_company_values.iloc[position].any()):
            statuses.append("MISSING_HIERARCHY_FIELD")
        elif tuple(row) in taxonomy_paths:
            statuses.append("MATCH")
        else:
            statuses.append("NOT_IN_OFFICIAL_TAXONOMY")

    result = company_data.copy()
    result["Taxonomy_Status"] = statuses
    result["Taxonomy_Validated"] = result[
        "Taxonomy_Status"
    ].eq("MATCH")

    total = len(result)
    matched = int(result["Taxonomy_Validated"].sum())
    missing = int(
        result["Taxonomy_Status"]
        .eq("MISSING_HIERARCHY_FIELD")
        .sum()
    )
    unknown = int(
        result["Taxonomy_Status"]
        .eq("NOT_IN_OFFICIAL_TAXONOMY")
        .sum()
    )

    summary = {
        "status": (
            "PASS"
            if total > 0 and matched == total
            else "REVIEW"
        ),
        "classification_rows": total,
        "taxonomy_matched_rows": matched,
        "missing_hierarchy_rows": missing,
        "unknown_hierarchy_rows": unknown,
        "official_taxonomy_paths": len(taxonomy_paths),
        "matching_method": "EXACT_EIGHT_FIELD_HIERARCHY",
        "fuzzy_matching_used": False,
        "classification_inferred": False,
        "sector_mapping_activated": False,
    }

    return result, summary
