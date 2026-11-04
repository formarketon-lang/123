"""Search helpers for official exchange security universes."""

from __future__ import annotations

import pandas as pd


def search_stock_universe(
    universe: pd.DataFrame,
    query: str = "",
    limit: int = 100,
) -> pd.DataFrame:
    """Search an exchange universe by trading symbol or company name."""

    if not isinstance(universe, pd.DataFrame):
        raise TypeError("universe must be a pandas DataFrame.")

    if limit < 1:
        raise ValueError("limit must be at least 1.")

    required = {"Symbol", "Company"}
    missing = required.difference(universe.columns)

    if missing:
        raise ValueError(
            "Stock universe is missing required columns: "
            + ", ".join(sorted(missing))
        )

    if universe.empty:
        return universe.copy()

    result = universe.copy()
    search_text = str(query or "").strip().casefold()

    if search_text:
        symbol_match = (
            result["Symbol"].astype("string").str.casefold()
            .str.contains(search_text, na=False, regex=False)
        )

        company_match = (
            result["Company"].astype("string").str.casefold()
            .str.contains(search_text, na=False, regex=False)
        )

        result = result[symbol_match | company_match]

    return (
        result.sort_values("Symbol")
        .head(limit)
        .reset_index(drop=True)
    )
